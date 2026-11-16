"""Task-owned temp failures and missing business signals in real Qt queues."""
import time
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from PySide6.QtTest import QTest
from services.resource_import import ImportTarget
from test_wpa_import_diagnostics import rig,web,execute,events
from test_phase2_interaction import surface


def settle(s,ids):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        QTest.qWait(10)
        if s.g.imports.worker is None and all(s.g.imports.requests[i].state not in {'running','waiting','finalizing'} for i in ids):break
    assert s.g.imports.worker is None
    return [s.g.imports.requests[i] for i in ids]


def test_cleanup_permission_partial_then_next_exact_once(rig,web):
    s=rig;q=s.g.imports;results=[];q.files_finished.connect(lambda r:results.append(r.id))
    before=len(s.storage.index.resources());unlink=Path.unlink;owned=[]
    def denied(path,*args,**kwargs):
        if path.suffix=='.tmp':owned.append(str(path));raise PermissionError('private locked path')
        return unlink(path,*args,**kwargs)
    source=s.tmp/'untouched-original.png';Image.new('RGB',(47,37),(71,11,91)).save(source)
    original=source.read_bytes()
    with patch.object(Path,'unlink',denied):
        a=q.submit([web+'/ok.png',web+'/denied'],ImportTarget(s.parent),s.g)
        b=q.submit([str(source)],ImportTarget(s.child),s.g)
        first,second=settle(s,[a,b])
    assert (first.saved,first.failed,first.state)==(1,1,'completed')
    assert (second.saved,second.failed,second.state)==(1,0,'completed')
    assert results.count(a)==results.count(b)==1
    assert source.read_bytes()==original and len(s.storage.index.resources())==before+2
    assert any(e.get('stage')=='cleanup' and e.get('error')=='permission' for e in events(s))
    assert owned
    # Only clean synthetic mkstemp remnants after releasing this test's lock.
    for name in set(owned):Path(name).unlink(missing_ok=True)
    with s.storage.index.connect() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_native_finish_without_business_result_releases_queue(rig,monkeypatch):
    from fluent_ui.views.gallery_view import ImportThread
    s=rig;q=s.g.imports;run=ImportThread.run;results=[];q.files_finished.connect(lambda r:results.append(r.id))
    calls=[]
    def silent(worker):
        calls.append(worker)
        if len(calls)==1:return  # actual QThread ends, no business result
        run(worker)
    monkeypatch.setattr(ImportThread,'run',silent)
    path=s.tmp/'native-next.png';Image.new('RGB',(45,35),'orange').save(path)
    a=q.submit([str(path)],ImportTarget(s.parent),s.g)
    b=q.submit([str(path)],ImportTarget(s.parent),s.g)
    first,second=settle(s,[a,b])
    assert first.state=='failed' and first.failed==1
    assert second.saved==1 and second.state=='completed'
    assert results.count(a)==results.count(b)==1
    assert any(e.get('error')=='worker_ended' for e in events(s))
    # Late callbacks cannot consume a new task or emit a second completion.
    q._business_finished(calls[0],99,99,99);q._thread_finished(calls[0])
    assert results.count(a)==1 and q.worker is None


def test_unexpected_after_partial_keeps_counts_context_and_next(rig,monkeypatch):
    from fluent_ui.views.gallery_view import ImportThread
    s=rig;q=s.g.imports;original=ImportThread._run_import;calls=[];cleared=[]
    def broken(worker):
        calls.append(worker)
        if len(calls)>1:return original(worker)
        # Exercise the real importer and wrapper, then fail after one accepted item.
        from services.crash_evidence import ImportTrace
        c=s.storage.import_context;c.job_id=worker.job_id
        worker.trace=ImportTrace(worker.job_id);c.import_trace=worker.trace
        result=s.storage.import_paths(worker.sources,ImportTarget(s.parent))
        worker.result_paths=result.paths;worker.new_resource_count=result.imported
        worker.outcome=(result.imported,result.duplicates,len(result.errors))
        raise RuntimeError('synthetic unexpected end')
    monkeypatch.setattr(ImportThread,'_run_import',broken)
    # Check the worker-local context after outer cleanup, before QThread returns.
    emit=ImportThread._emit_result
    def observed(worker,*counts):
        if len(calls)==1:
            c=s.storage.import_context
            cleared.append(c.job_id=='' and c.import_trace is None and c.committed is None)
        return emit(worker,*counts)
    monkeypatch.setattr(ImportThread,'_emit_result',observed)
    path=s.tmp/'partial.png';Image.new('RGB',(41,43),'pink').save(path)
    result=execute(s,[str(path)])
    assert (result.saved,result.failed,result.state)==(1,1,'completed') and cleared==[True]
    assert execute(s,[str(path)]).duplicates==1


def test_duplicate_cancel_and_business_native_exact_once(rig):
    s=rig;counts=[];s.g.imports.files_finished.connect(lambda r:counts.append(r.id))
    path=s.tmp/'duplicate.png';Image.new('RGB',(51,43),'navy').save(path)
    first=execute(s,[str(path)])
    second=execute(s,[str(path)])
    assert first.saved==1 and second.duplicates==1 and second.saved==0
    q=s.g.imports
    cancelled=q.submit([str(path)],ImportTarget(s.parent),s.g);q.cancel(cancelled)
    QTest.qWait(50)
    assert q.requests[cancelled].state=='cancelled'
    assert counts.count(first.id)==counts.count(second.id)==1 and counts.count(cancelled)==0


def test_result_commit_failure_releases_queue_without_replay(rig,monkeypatch):
    s=rig;q=s.g.imports;original=q._finished;calls=[]
    def failure(*args):
        calls.append(True)
        if len(calls)==1:raise OSError('synthetic result commit failure')
        return original(*args)
    monkeypatch.setattr(q,'_finished',failure)
    path=s.tmp/'commit.png';Image.new('RGB',(49,47),'teal').save(path)
    result=execute(s,[str(path)])
    assert result.state=='interrupted'
    assert execute(s,[str(path)]).duplicates==1
    assert any(e.get('error')=='result_commit' for e in events(s))
