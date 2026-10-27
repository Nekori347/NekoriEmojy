import json
import os
from pathlib import Path
import time
import zipfile
from unittest.mock import Mock

from services import crash_evidence as c
from test_crash_evidence import child


def test_closed_segment_age_capacity_and_unknown_files(tmp_path):
    now=time.time()
    def log(name,age=0,size=4):
        path=tmp_path/name;path.write_bytes(b'x'*size)
        os.utime(path,(now-age,now-age));return path
    active=log('exceptions.log',15*86400)
    old=log('exceptions.log.1',15*86400)
    oversized=log('exceptions.log.2',1,c.LOG_BYTES+500)
    unknown=log('fatal-private.log',20*86400)
    exported=log('diagnostic.zip',30*86400)
    for i in range(4):log(f'fatal-20261024-120000-{i}.log',100-i)
    active_native=tmp_path/'fatal-20261024-120000-0.log'
    c.maintain(tmp_path,active=(active,active_native),now=now)
    assert active.exists() and not old.exists()
    assert oversized.stat().st_size==c.LOG_BYTES
    assert unknown.exists() and exported.exists()
    assert len(list(tmp_path.glob('fatal-20261024-*.log')))==2
    assert active_native.exists()


def test_cleanup_failure_and_context_exception_export(tmp_path,monkeypatch):
    old=tmp_path/'exceptions.log.1';old.write_text('old')
    os.utime(old,(1,1))
    with monkeypatch.context() as m:
        m.setattr(Path,'unlink',Mock(side_effect=PermissionError('in use')))
        c.maintain(tmp_path)  # no exception or startup dependency
    result=child(tmp_path,'''from services import crash_evidence as c
c.install()
for i in range(100):c.breadcrumb('task_state',kind='import',count=i)
c.breadcrumb('task_state',path='PRIVATE_RESOURCE',state='running')
assert len(c.context_snapshot()['recent'])==64
raise RuntimeError('PRIVATE_RESOURCE')
''')
    text=(tmp_path/'app/diagnostics/exceptions.log').read_text(encoding='utf-8')
    assert result.returncode and 'task_state' in text and 'exception' in text
    assert 'PRIVATE_RESOURCE' not in text
    # Export includes the live bounded context without saving a new log file.
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    from services.diagnostic_export import export_diagnostics
    before=set((tmp_path/'app/diagnostics').iterdir())
    c.breadcrumb('window_show',role='main')
    target=tmp_path/'report.zip';export_diagnostics(target)
    with zipfile.ZipFile(target) as archive:
        context=json.loads(archive.read('environment.json'))['runtime_context']
        assert context['recent'][-1]['event']=='window_show'
    assert set((tmp_path/'app/diagnostics').iterdir())==before
    c.maintain(tmp_path/'app/diagnostics',now=time.time()+30*86400)
    assert target.exists()


def test_active_python_segment_rotates_before_age_reclamation(tmp_path):
    result=child(tmp_path,'''import os,time
from services import crash_evidence as c
c.install();c.breadcrumb('startup');c.persist_context('startup')
p=c.app_data_dir()/'diagnostics/exceptions.log'
os.utime(p,(time.time()-15*86400,)*2)
c.maintenance()
c.breadcrumb('shutdown');c.persist_context('shutdown')
assert 'shutdown' in p.read_text()
assert not (p.parent/'exceptions.log.1').exists()
''')
    assert result.returncode==0,result.stderr


def test_window_observer_bounded_sessions_and_qt_dispatch(tmp_path):
    result=child(tmp_path,'''import json
from PySide6.QtCore import QEvent,QCoreApplication,QTimer
from PySide6.QtWidgets import QWidget
from PySide6.QtTest import QTest
from fluent_ui.components.runtime_diagnostics import DiagnosticApplication,install_runtime_diagnostics
from services import crash_evidence as c
c.install();app=DiagnosticApplication([]);w=QWidget();o=install_runtime_diagnostics(app,w)
w.setProperty('nativeMaterial','opaque');w.show();QTest.qWait(40)
for i in range(8):
 o.native_message(w,0x231);o.native_message(w,0x216)
 QCoreApplication.sendEvent(w,QEvent(QEvent.Move))
 o.native_message(w,0x232);app.processEvents()
assert o.normal_saved==3 and o.drag_totals['sessions']==8
assert o.drag_totals['max_dispatch_ms']>=0
assert o.maintenance_timer.interval()==86400000
w.hide();app.processEvents()
context=c.context_snapshot();assert len(context['recent'])<=64
assert context['environment']['windows']['main']['material']=='opaque'
assert context['environment']['pyside6']!='unknown'
o.shutdown()
log=(c.app_data_dir()/'diagnostics/exceptions.log').read_text()
assert log.count('window_move context=')==3
assert 'window_hide' in log and 'shutdown' in log
''')
    assert result.returncode==0,result.stderr
