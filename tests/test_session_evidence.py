"""Primary session boundaries and bounded recovery, using only disposable child processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parents[1]


def child(tmp_path, code, *args):
    env=os.environ.copy()
    env.update(NEKORI_APP_DATA=str(tmp_path/'app'),NEKORI_LIBRARY=str(tmp_path/'library'),
               QT_QPA_PLATFORM='offscreen',PYTHONDONTWRITEBYTECODE='1',TEMP=str(tmp_path),TMP=str(tmp_path))
    result=subprocess.run([sys.executable,'-B','-c',code,*args],cwd=SOURCE,env=env,
                          capture_output=True,text=True,timeout=20)
    assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
    return result


def state(tmp_path):
    return json.loads((tmp_path/'app/diagnostics/sessions.json').read_text(encoding='utf-8'))


BEGIN="from services import crash_evidence as c; c.begin_session(); c.install(); "


def test_normal_restart_and_nonfatal_exception(tmp_path):
    child(tmp_path,BEGIN+r"""
import sys
try:raise ValueError('PRIVATE_IMAGE.png')
except ValueError:sys.excepthook(*sys.exc_info())
assert c.session_snapshot()['current']['state']=='running'
assert c.complete_session()
""")
    first=state(tmp_path);assert first['current']['state']=='completed'
    assert first['pending']==[]
    child(tmp_path,BEGIN+"assert c.complete_session()")
    second=state(tmp_path);assert second['current']['id']!=first['current']['id']
    assert second['pending']==[]


def test_abrupt_exit_without_native_trace(tmp_path):
    r=subprocess.run([sys.executable,'-B','-c',
        "import os;from services import crash_evidence as c;c.begin_session();os._exit(23)"],
        cwd=SOURCE,env=dict(os.environ,NEKORI_APP_DATA=str(tmp_path/'app')),capture_output=True,timeout=10)
    assert r.returncode==23
    old=state(tmp_path)['current'];assert old['state']=='running'
    child(tmp_path,BEGIN+"assert c.complete_session()")
    candidate=state(tmp_path)['pending'][0]
    assert candidate['session']['id']==old['id']
    assert candidate['assessment']=='possible_abnormal_exit'
    assert candidate['evidence_kind']=='none'


def test_native_trace_survives_restart_before_retention(tmp_path):
    # A real independent native writer, synthetic traceback (not an actual crash).
    code=BEGIN+"import faulthandler,os;faulthandler.dump_traceback(file=c._fatal_file);os._exit(23)"
    env=dict(os.environ,NEKORI_APP_DATA=str(tmp_path/'app'),PYTHONDONTWRITEBYTECODE='1')
    r=subprocess.run([sys.executable,'-B','-c',code],cwd=SOURCE,env=env,capture_output=True,timeout=10)
    assert r.returncode==23
    previous=state(tmp_path)['current'];native=tmp_path/'app/diagnostics'/previous['native_log']
    for _ in range(50):
        if native.exists() and native.stat().st_size:break
        time.sleep(.02)
    assert native.read_bytes()
    child(tmp_path,BEGIN+"assert c.complete_session()")
    candidate=state(tmp_path)['pending'][0]
    assert candidate['evidence_kind']=='native_trace'
    assert candidate['assessment']=='possible_abnormal_exit'
    assert any('File ' in e['text'] for e in candidate['evidence'])


def test_fatal_signature_and_redaction_and_rotation_order(tmp_path):
    child(tmp_path,r"""
from services import crash_evidence as c
from pathlib import Path
import os,time
s=c.begin_session();d=c.app_data_dir()/'diagnostics'
p=d/s['native_log']
p.write_text('Windows fatal exception: access violation\n'+r'C:\private\PRIVATE_IMAGE.png'+'\nhttps://private.test/a?token=SECRET\nAuthorization: Bearer SECRET\n',encoding='utf-8')
# Populate extra native files that install's quota would remove.
for i in range(3):
 p=d/f'fatal-20261115-01000{i}-{i+100}.log';p.write_text('unrelated');os.utime(p,(time.time()+i,time.time()+i))
""")
    old=state(tmp_path)['current']
    child(tmp_path,BEGIN+"assert c.complete_session()")
    v=state(tmp_path);candidate=v['pending'][0]
    assert candidate['assessment']=='fatal_error_recorded'
    assert candidate['evidence_kind']=='fatal_signature'
    text=json.dumps(candidate)
    for secret in ['PRIVATE_IMAGE','private.test','SECRET','C:\\private']:
        assert secret not in text
    # Task02 pins this source until native completion or bounded capture finishes.
    assert (tmp_path/'app/diagnostics'/old['native_log']).exists()
    child(tmp_path,r"""
from services import crash_evidence as c
candidate=c.session_snapshot()['pending'][0]
c.update_candidate(candidate['session']['id'],capture_state='ready',native_complete=True)
c.maintain(c.app_data_dir()/'diagnostics',native_slots=0)
""")
    assert not (tmp_path/'app/diagnostics'/old['native_log']).exists()
    assert candidate['evidence']


def test_failed_protection_is_retryable_and_disables_maintenance(tmp_path):
    child(tmp_path,"from services import crash_evidence as c;c.begin_session()")
    original=(tmp_path/'app/diagnostics/sessions.json').read_bytes()
    child(tmp_path,r"""
from services import crash_evidence as c
from unittest.mock import patch
with patch.object(c.os,'replace',side_effect=PermissionError('denied')):
 assert c.begin_session() is None
 assert c.install() is None
assert c._handler is None
""")
    assert (tmp_path/'app/diagnostics/sessions.json').read_bytes()==original
    assert not (tmp_path/'app/diagnostics/sessions.tmp').exists()
    child(tmp_path,BEGIN+"assert c.complete_session()")
    assert len(state(tmp_path)['pending'])==1


def test_evidence_read_failure_does_not_claim_saved(tmp_path):
    child(tmp_path,r"""
from services import crash_evidence as c
s=c.begin_session();(c.app_data_dir()/'diagnostics'/s['native_log']).write_text('synthetic native')
""")
    old=(tmp_path/'app/diagnostics/sessions.json').read_bytes()
    child(tmp_path,r"""
from services import crash_evidence as c
from pathlib import Path
from unittest.mock import patch
original=Path.open
def blocked(p,*a,**kw):
 if p.name.startswith('fatal-'):raise PermissionError('denied')
 return original(p,*a,**kw)
with patch.object(Path,'open',blocked):
 assert c.begin_session() is None
 assert c.install() is None
""")
    assert (tmp_path/'app/diagnostics/sessions.json').read_bytes()==old


def test_corrupt_state_and_unwritable_directory_do_not_block(tmp_path):
    d=tmp_path/'app/diagnostics';d.mkdir(parents=True);(d/'sessions.json').write_text('{bad')
    child(tmp_path,BEGIN+"assert c.session_snapshot()['current']['state']=='running';assert c.complete_session()")
    assert state(tmp_path)['pending']==[]
    child(tmp_path,r"""
from services import crash_evidence as c
from unittest.mock import patch
with patch.object(c,'_atomic_sessions',side_effect=PermissionError()):
 assert c.begin_session() is None
 assert c.install() is None
""")


def test_limits_and_pid_correlation(tmp_path):
    for _ in range(5):
        child(tmp_path,r"""
from services import crash_evidence as c
import time,os
s=c.begin_session();d=c.app_data_dir()/'diagnostics'
# Selected and unselected PID records; preserve only the matching session.
stamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
(d/'exceptions.log').write_text(f'{stamp} pid={os.getpid()+1} unrelated_secret\n'+f'2020-01-01T01:00:00Z pid={os.getpid()} old_pid_secret\n'+f'{stamp} pid={os.getpid()} source=python exception=builtins.ValueError\n')
(d/s['native_log']).write_text('x'* (c.LOG_BYTES+100))
""")
    child(tmp_path,BEGIN+"assert c.complete_session()")
    v=state(tmp_path);assert len(v['pending'])==3
    assert 'unrelated_secret' not in json.dumps(v)
    assert 'old_pid_secret' not in json.dumps(v)
    assert any(e['kind']=='python' and 'ValueError' in e['text'] for e in v['pending'][-1]['evidence'])
    assert (tmp_path/'app/diagnostics/sessions.json').stat().st_size<=4*1024*1024
    for candidate in v['pending']:
        assert sum(len(e['text'].encode('utf-8')) for e in candidate['evidence'])<=768*1024


def test_completion_write_failure_keeps_running(tmp_path):
    child(tmp_path,r"""
from services import crash_evidence as c
from unittest.mock import patch
c.begin_session()
with patch.object(c.os,'replace',side_effect=PermissionError()):assert not c.complete_session()
assert c.session_snapshot()['current']['state']=='running'
""")


def test_auxiliary_flags_never_begin_sessions(tmp_path):
    for flag in ['--diagnostic-writer','--backup-worker']:
        child(tmp_path,"from services import crash_evidence as c;assert c.begin_session() is None",flag)
    assert not (tmp_path/'app/diagnostics/sessions.json').exists()


def test_main_marks_only_after_exec_return_and_hide_is_running(tmp_path):
    child(tmp_path,r"""
import main
from services import crash_evidence as c
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer
observed=[]
def run(app,instance):
 w=QWidget();w.show();w.hide()
 assert c.session_snapshot()['current']['state']=='running'
 app.aboutToQuit.connect(lambda:observed.append(c.session_snapshot()['current']['state']))
 QTimer.singleShot(0,app.quit)
 code=app.exec()
 assert c.session_snapshot()['current']['state']=='running'
 return code
main._run_primary=run
assert main.main()==0
assert observed==['running']
assert c.session_snapshot()['current']['state']=='completed'
""")


def test_real_early_library_cancel_completes(tmp_path):
    child(tmp_path,r"""
import main
from services import crash_evidence as c
from services.autostart import AutostartService
from fluent_ui.components import library_setup
AutostartService.repair_registration=lambda self:None
library_setup.open_startup_library=lambda config:None
assert main.main() is None
s=c.session_snapshot()['current']
assert s['state']=='completed' and s['completion']=='startup_cancelled'
""")


def test_main_startup_exception_not_completed(tmp_path):
    child(tmp_path,r"""
import main
from services import crash_evidence as c
def failed(*a):raise RuntimeError('synthetic startup error')
main._run_primary=failed
try:main.main()
except RuntimeError:pass
else:assert False
assert c.session_snapshot()['current']['state']=='running'
""")


def test_second_instance_does_not_replace_live_state(tmp_path):
    env=dict(os.environ,NEKORI_APP_DATA=str(tmp_path/'app'),QT_QPA_PLATFORM='offscreen',PYTHONDONTWRITEBYTECODE='1')
    code="""
from PySide6.QtCore import QCoreApplication
from services.single_instance import SingleInstance
from services import crash_evidence as c
import sys
app=QCoreApplication([]);instance=SingleInstance(app);assert instance.start()
c.begin_session();print('READY',flush=True)
sys.stdin.readline();assert c.complete_session()
"""
    first=subprocess.Popen([sys.executable,'-B','-c',code],cwd=SOURCE,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert first.stdout.readline().strip()=='READY'
        identity=state(tmp_path)['current']['id']
        child(tmp_path,"import main;main._run_primary=lambda *a:(_ for _ in ()).throw(AssertionError('must not run'));assert main.main() is None")
        assert state(tmp_path)['current']['id']==identity
        assert state(tmp_path)['current']['state']=='running'
    finally:
        first.communicate('exit\n',timeout=10)
    assert first.returncode==0


def test_main_diagnostics_failure_still_runs_primary(tmp_path):
    child(tmp_path,r"""
import main
from services import crash_evidence as c
from unittest.mock import patch
called=[]
main._run_primary=lambda *a:called.append(True) or 0
with patch.object(c,'_atomic_sessions',side_effect=PermissionError()):
 assert main.main()==0
assert called==[True]
assert not (c.app_data_dir()/'diagnostics/sessions.json').exists()
""")


def test_abrupt_about_to_quit_is_not_completed(tmp_path):
    env=dict(os.environ,NEKORI_APP_DATA=str(tmp_path/'app'),QT_QPA_PLATFORM='offscreen',PYTHONDONTWRITEBYTECODE='1')
    code=r"""
import main,os
from PySide6.QtCore import QTimer
def run(app,instance):
 app.aboutToQuit.connect(lambda:os._exit(23))
 QTimer.singleShot(0,app.quit)
 return app.exec()
main._run_primary=run
main.main()
"""
    r=subprocess.run([sys.executable,'-B','-c',code],cwd=SOURCE,env=env,capture_output=True,timeout=20)
    assert r.returncode==23
    assert state(tmp_path)['current']['state']=='running'


def test_sessions_never_open_library_or_configuration(tmp_path):
    library=tmp_path/'library';library.mkdir();sentinel=library/'PRIVATE_IMAGE.png';sentinel.write_bytes(b'not an image, private sentinel')
    child(tmp_path,r"""
from services import crash_evidence as c
import builtins,os
from pathlib import Path
from unittest.mock import patch
original=builtins.open
io_open=__import__('io').open
def guard(original):
 def opened(path,*a,**kw):
  if isinstance(path,(str,Path)):
   p=Path(path).resolve()
   assert not p.is_relative_to(Path(os.environ['NEKORI_LIBRARY']).resolve())
   assert p.name!='config.json'
  return original(path,*a,**kw)
 return opened
with patch('builtins.open',guard(original)),patch('io.open',guard(io_open)):
 c.begin_session();c.install();assert c.complete_session()
""")
    assert sentinel.read_bytes()==b'not an image, private sentinel'
    assert list(library.iterdir())==[sentinel]
