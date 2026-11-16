"""Synthetic HTTP, isolated Library, real Qt worker/queue and existing feedback."""
import io, json, logging, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from services import crash_evidence as ce
from services.resource_import import ImportTarget


@pytest.fixture
def rig(surface, monkeypatch):
    s=surface
    log=s.tmp/'import-evidence.log'
    handler=logging.FileHandler(log,encoding='utf-8')
    logger=logging.getLogger('nekori.crash_evidence');logger.addHandler(handler);logger.setLevel(logging.INFO)
    monkeypatch.setattr(ce,'_installed',True)
    s.log=log
    s.g.imports._ask_batch=lambda request,candidates:['reuse']*len(candidates)
    s.g.imports._ask_duplicate=lambda *args:'reuse'
    yield s
    logger.removeHandler(handler);handler.close()


@pytest.fixture
def web():
    data=io.BytesIO();Image.new('RGB',(33,29),(37,61,93)).save(data,format='PNG')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path.startswith('/denied'):
                self.send_response(403);self.end_headers();return
            self.send_response(200)
            self.send_header('Content-Type','text/plain' if self.path.startswith('/text') else 'image/png')
            self.end_headers()
            self.wfile.write(b'private URL token cookie not image' if self.path.startswith(('/text','/corrupt')) else data.getvalue())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown();server.server_close();thread.join(2)


def execute(s,sources):
    rid=s.g.imports.submit(sources,ImportTarget(s.parent),s.g)
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        QTest.qWait(10)
        if s.g.imports.worker is None and s.g.imports.requests[rid].state not in {'waiting','running','finalizing'}:break
    request=s.g.imports.requests[rid]
    assert s.g.imports.worker is None,request.state
    s.g._sync_background_tasks()
    return request


def events(s):
    return [json.loads(line.split('import=',1)[1].split(' pid=',1)[0])
            for line in s.log.read_text('utf-8').splitlines() if 'import=' in line]


@pytest.mark.parametrize('route,error,stage',[
    ('/ok.png',None,None),('/denied?Token=secret','http_status','network'),
    ('/text','not_image','validate'),('/corrupt.png','decode_failed','decode')])
def test_network_stage_state_feedback_and_private_evidence(rig,web,route,error,stage):
    s=rig;request=execute(s,[web+route]);records=events(s)
    assert request.saved==int(error is None) and request.failed==int(error is not None)
    assert request.state==('completed' if error is None else 'failed')
    feedback=s.g.feedback_host.named_tasks[request.id]
    assert feedback['state']==('success' if error is None else 'error')
    if error:
        entry=next(r for r in records if r.get('error')==error)
        assert entry['stage']==stage
        if error=='http_status':assert entry['http_status']==403
    assert records[-1]['stage']=='finalize' and records[-1]['failed']==request.failed
    text=s.log.read_text('utf-8')
    assert all(secret not in text for secret in (web,'Token','secret','private URL',str(s.tmp),'corrupt.png'))


def test_timeout_then_following_success(rig,web,monkeypatch):
    import urllib.request
    with patch.object(urllib.request,'urlopen',side_effect=TimeoutError('private-path token=secret')):
        result=execute(rig,[web+'/timeout.png'])
    assert result.failed==1
    assert any(r.get('error')=='timeout' for r in events(rig))
    assert execute(rig,[web+'/ok.png']).saved==1


def test_write_failure_mixed_and_following_success(rig,web):
    import builtins
    original=builtins.open
    def failing(file,mode='r',*args,**kwargs):
        if 'w' in mode and str(file).startswith(rig.storage.images_dir):raise PermissionError('private write path')
        return original(file,mode,*args,**kwargs)
    with patch('builtins.open',failing):result=execute(rig,[web+'/ok.png'])
    assert result.failed==1 and any(r.get('stage')=='store' and r.get('error')=='permission' for r in events(rig))
    result=execute(rig,[web+'/ok.png',web+'/denied'])
    assert (result.saved,result.failed,result.state)==(1,1,'completed')
    assert rig.g.feedback_host.named_tasks[result.id]['state']=='partial'
    assert events(rig)[-1]['partial']==1
    assert execute(rig,[web+'/ok.png']).duplicates==1


def test_cancel_while_worker_and_next_task(rig,web,monkeypatch):
    from fluent_ui.views.gallery_view import DownloadThread
    original=DownloadThread.run;entered=threading.Event();release=threading.Event()
    def slow(worker):entered.set();release.wait(3);original(worker)
    monkeypatch.setattr(DownloadThread,'run',slow)
    rid=rig.g.imports.submit([web+'/ok.png'],ImportTarget(rig.parent),rig.g)
    while not entered.is_set():QTest.qWait(10)
    rig.g.imports.cancel(rid);release.set()
    deadline=time.monotonic()+12
    while rig.g.imports.worker and time.monotonic()<deadline:QTest.qWait(10)
    assert rig.g.imports.requests[rid].state=='cancelled'
    assert events(rig)[-1]['cancelled']==1
    monkeypatch.setattr(DownloadThread,'run',original)
    path=rig.tmp/'follow.png';Image.new('RGB',(39,31),'purple').save(path)
    assert execute(rig,[str(path)]).saved==1


def test_trace_budget_and_nonfatal_diagnostic_failure(monkeypatch):
    trace=ce.ImportTrace('controlled-id')
    with patch.object(ce,'record_import') as record:
        for _ in range(1000):
            trace.begin_item();trace.enter('network');trace.enter('decode');trace.enter('store')
        assert record.call_count==4
    assert len(trace.entered)==4 and len(trace.failures)==0
    assert not any(hasattr(v,'bits') for v in vars(trace).values())
    monkeypatch.setattr(ce,'_installed',True)
    with patch.object(logging.getLogger('nekori.crash_evidence'),'info',side_effect=OSError('disk unavailable')):
        ce.record_import('id','network','timeout')  # diagnostics cannot stop imports


def test_invalid_url_and_size_limit(rig,web,monkeypatch):
    assert execute(rig,['http:///invalid.png']).failed==1
    assert any(e.get('stage')=='resolve' and e.get('error')=='invalid_url' for e in events(rig))
    from fluent_ui.views import gallery_view
    monkeypatch.setattr(gallery_view,'MAX_IMAGE_DOWNLOAD_BYTES',8)
    assert execute(rig,[web+'/ok.png']).failed==1
    assert any(e.get('stage')=='validate' and e.get('error')=='too_large' for e in events(rig))
