"""Bounded, anonymous diagnosis with synthetic records and isolated app data."""
import json,logging,time
from datetime import datetime,timezone
from unittest.mock import Mock
from test_phase2_interaction import surface
from services import crash_evidence as c
from services import windows_fault_event as native
from test_auto_crash_reports import isolated,seed


def test_native_match_requires_process_creation_image_pid_and_unique_event(monkeypatch):
    now=2000000000
    session=dict(pid=123,started_at=now-100,process_created=123456,
                 executable_hash=native._image_hash(r'C:\private\NekoriEmojy.exe'))
    stamp=datetime.fromtimestamp(now-10,timezone.utc).isoformat()
    xml=f'''<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System><Provider Name="Application Error"/><EventID>1000</EventID><TimeCreated SystemTime="{stamp}"/></System>
    <EventData><Data Name="ProcessId">0x7b</Data><Data Name="ProcessCreationTime">0x1e240</Data>
    <Data Name="AppPath">C:\\private\\NekoriEmojy.exe</Data><Data Name="ModuleName">Qt6Core.dll</Data>
    <Data Name="ExceptionCode">c0000005</Data><Data Name="FaultingOffset">00001234</Data></EventData></Event>'''
    matched=native.match_fault(session,[xml],now)
    assert matched['exception_code']=='0xc0000005' and matched['module']=='Qt6Core.dll'
    assert matched['module_offset']=='0x1234' and 'private' not in json.dumps(matched)
    assert native.match_fault(session,[xml,xml],now)['reason']=='ambiguous'
    for old,new in (('0x1e240','0x1e241'),('0x7b','0x7c'),('NekoriEmojy.exe','Other.exe')):
        assert native.match_fault(session,[xml.replace(old,new)],now)['status']=='unknown'
    assert native.match_fault(session,[xml],now-1000)['status']=='unknown'
    assert native.match_fault({'pid':123},[xml],now)['reason']=='identity_unavailable'
    monkeypatch.setattr(native,'_read_events',Mock(side_effect=PermissionError('private URL token')))
    assert native.query_fault(session)=={'status':'unknown','reason':'query_unavailable'}


def test_repeated_errors_aggregate_without_losing_distinct_reasons_or_error_codes(tmp_path,monkeypatch):
    log=tmp_path/'bounded.log';handler=c.BoundedRotatingHandler(log,maxBytes=c.LOG_BYTES,backupCount=2,encoding='utf-8')
    logger=logging.getLogger('nekori.crash_evidence')
    monkeypatch.setattr(logger,'handlers',[handler]);monkeypatch.setattr(logger,'propagate',False)
    monkeypatch.setattr(c,'_installed',True);monkeypatch.setattr(c,'_exception_counts',{})
    def trigger(message):
        try:raise RuntimeError(message)
        except RuntimeError as exc:c.record_exception('python',type(exc),exc,exc.__traceback__)
    for _ in range(1000):trigger('https://private.invalid/?Token=private-secret')
    trigger('a different private reason')
    try:raise OSError(13,'private permission path')
    except OSError as exc:c.record_exception('thread',type(exc),exc,exc.__traceback__)
    import sqlite3
    try:
        with sqlite3.connect(':memory:') as db:db.execute('SELECT * FROM missing_test_table')
    except sqlite3.Error as exc:c.record_exception('python',type(exc),exc,exc.__traceback__)
    c.flush_exception_counts();handler.close();text=log.read_text('utf-8')
    assert len(c._exception_counts)==4
    assert 'count=1' in text and '"count":1000' in text and 'errno=13' in text and 'sqlite_errorcode=1' in text
    assert all(secret not in text for secret in ('https://','Token','private-secret','private permission path','different private reason'))
    assert log.stat().st_size<16000


def test_import_boundaries_flush_only_worker_creation_and_keep_source_private(surface,monkeypatch):
    from PIL import Image
    from services.resource_import import ImportTarget,ImportBytes
    from PySide6.QtGui import QImage
    s=surface;log=s.tmp/'import.log';handler=logging.FileHandler(log,encoding='utf-8')
    from PySide6.QtCore import QThread
    queue=s.g.imports;ownership=[];finished=[]
    def observe(_):
        worker=queue.worker
        if worker is not None:
            ownership.append(worker.parent() is queue and worker.thread()==s.app.thread() and QThread.currentThread()==s.app.thread())
    queue.changed.connect(observe)
    original=queue._thread_finished
    def thread_finished(worker):
        finished.append(not worker.isRunning() and QThread.currentThread()==s.app.thread())
        original(worker)
    monkeypatch.setattr(queue,'_thread_finished',thread_finished)
    logger=logging.getLogger('nekori.crash_evidence');logger.setLevel(logging.INFO)
    monkeypatch.setattr(logger,'handlers',[handler]);monkeypatch.setattr(logger,'propagate',False)
    monkeypatch.setattr(c,'_installed',True);monkeypatch.setattr(c,'_handler',handler)
    synced=Mock();monkeypatch.setattr(c.os,'fsync',synced)
    source=s.tmp/'private-input-name.png';Image.new('RGB',(59,41),'coral').save(source)
    rid=s.g.imports.submit([str(source)],ImportTarget(s.parent),s.g)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        s.app.processEvents();time.sleep(.01)
        if s.g.imports.requests[rid].state not in {'waiting','running','finalizing'}:break
    assert s.g.imports.requests[rid].state=='completed'
    handler.flush();text=log.read_text('utf-8');events=[json.loads(line.split('import=',1)[1].split(' pid=',1)[0]) for line in text.splitlines() if 'import=' in line]
    stages=[v['stage'] for v in events]
    assert stages.index('queued')<stages.index('worker_create')<stages.index('worker_ready')<stages.index('thread_end')<stages.index('result_commit')
    assert len({v['task'] for v in events})==1 and events[0]['source']=='local_file'
    assert synced.call_count==2 and str(source) not in text and source.name not in text
    assert ownership and all(ownership) and finished==[True]
    q=s.g.imports
    assert q._source_kind([ImportBytes(b'fake')])=='ole_image'
    assert q._source_kind([QImage()])=='clipboard_image'
    assert q._source_kind(['https://private.invalid/Token'])=='network_url'
    handler.close()


def test_local_report_survives_event_query_denial_and_carries_native_fields(isolated,monkeypatch):
    import zipfile
    from services import diagnostic_export as export
    candidate=seed(native=False)
    monkeypatch.setattr(native,'_read_events',Mock(side_effect=PermissionError('private path')))
    path=export.export_automatic_report(candidate)
    with zipfile.ZipFile(path) as archive:
        report=json.loads(archive.read('report.json'))
        assert report['native_fault']['status']=='unknown'
        assert b'private path' not in b''.join(archive.read(n) for n in archive.namelist())
    second=seed(native=False)
    monkeypatch.setattr(native,'query_fault',lambda session, *, event_id=1000:dict(status='unknown') if event_id==1002 else dict(status='matched',exception_code='0xc0000005',module='Qt6Core.dll',module_offset='0x1234',pid=session['pid'],occurred_at=session['started_at']+1,event_id=1000))
    with zipfile.ZipFile(export.export_automatic_report(second)) as archive:
        report=json.loads(archive.read('report.json'))
        assert report['native_fault']['module']=='Qt6Core.dll'
        assert report['native_stack_available'] is False


def test_exception_summary_failure_does_not_prevent_normal_completion(isolated,monkeypatch):
    monkeypatch.setattr(c,'flush_exception_counts',Mock(side_effect=OSError('synthetic log unavailable')))
    assert c.complete_session()
    assert c.session_snapshot()['current']['state']=='completed'

def test_hang_matches_its_own_identity_fields_without_fatal_signature(isolated,monkeypatch):
    import zipfile
    from services import diagnostic_export as export
    candidate=seed(native=False)
    session=candidate['session']
    if not session.get('process_created'):
        session['process_created']=0x123
    session['executable_hash']=native._image_hash(r'C:\private\App.exe')
    now=candidate['capture_started']
    stamp=datetime.fromtimestamp(now,timezone.utc).isoformat()
    xml=fr"""<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System><Provider Name="Application Hang"/><EventID>1002</EventID><TimeCreated SystemTime="{stamp}"/></System>
      <EventData><Data Name="ProcessId">{session['pid']:#x}</Data><Data Name="StartTime">{session['process_created']:#x}</Data>
      <Data Name="ExeFileName">C:\private\App.exe</Data></EventData></Event>"""
    match=lambda events:native.match_fault(session,events,now,event_id=1002)
    assert match([xml])['event_id']==1002
    assert match([xml,xml])['reason']=='ambiguous'
    assert match([xml.replace('StartTime','Other')])['reason']=='incomplete_identity'
    assert match([xml.replace('App.exe','Else.exe')])['status']=='unknown'
    assert native.match_fault(session,[xml],now)['status']=='unknown'
    monkeypatch.setattr(native,'_read_events',lambda *args:([xml],False))
    with zipfile.ZipFile(export.export_automatic_report(candidate)) as archive:
        report=json.loads(archive.read('report.json'))
        assert report['assessment']=='possible_abnormal_exit'
        assert report['windows_hang']['status']=='matched' and report['native_fault']['status']=='unknown'
        assert not report['gui_hang_python_sample'] and not report['symbolized_native_stack_available']
        assert 'private' not in json.dumps(report)

def test_gui_sample_is_bounded_survives_recovery_and_normal_exit(tmp_path):
    from test_crash_evidence import child
    result=child(tmp_path,"""
import time, zipfile, json
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QWidget
from fluent_ui.components.runtime_diagnostics import install_runtime_diagnostics
from services import crash_evidence as c, diagnostic_export as ex
app=QApplication([]);session=c.begin_session();c.install();window=QWidget()
observer=install_runtime_diagnostics(app,window)
c.GUI_STALL_SECONDS=.25;observer.heartbeat.setInterval(20)
def blocked_gui_callback():
    private='MY_PRIVATE_QUERY'
    time.sleep(.55)
QTimer.singleShot(150,blocked_gui_callback)
QTimer.singleShot(950,blocked_gui_callback)
QTimer.singleShot(1800,app.quit)
app.exec()
directory=c.app_data_dir()/'diagnostics'
candidate=c._previous_evidence(directory,session)
archive_path=ex.export_automatic_report(candidate)
with zipfile.ZipFile(archive_path) as archive:
    meta=json.loads(archive.read('report.json'))
    assert meta['gui_hang_python_sample'] and meta['assessment']=='possible_abnormal_exit'
    assert not meta['fatal_python_stack_available']
    text=archive.read('evidence/0.txt').decode()
    assert text.count('gui_unresponsive_sample')==1 and 'blocked_gui_callback' in text
    assert 'MY_PRIVATE_QUERY' not in text and str(directory) not in text
assert c.complete_session()
assert c.session_snapshot()['current']['state']=='completed' and not c.session_snapshot()['pending']
""")
    assert result.returncode==0,result.stderr
