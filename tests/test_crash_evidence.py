"""Fault records must survive a console-less process without collecting user content."""
import os
from pathlib import Path
import subprocess
import sys


SOURCE = Path(__file__).resolve().parents[1]


def child(tmp_path, code):
    env = os.environ.copy()
    env['NEKORI_APP_DATA'] = str(tmp_path / 'app')
    return subprocess.run([sys.executable, '-c', code], cwd=SOURCE, env=env,
                          capture_output=True, text=True, timeout=20)


def test_uncaught_python_and_qt_thread_leave_bounded_private_free_evidence(tmp_path):
    code = '''
from services.crash_evidence import install
from PySide6.QtCore import QCoreApplication, QThread
install()
app=QCoreApplication([])
class Worker(QThread):
    def run(self):
        raise RuntimeError('PRIVATE_RESOURCE_NAME')
worker=Worker(); worker.start(); worker.wait(); app.processEvents()
raise ValueError('PRIVATE_RESOURCE_NAME')
'''
    result = child(tmp_path, code)
    assert result.returncode != 0
    directory = tmp_path / 'app' / 'diagnostics'
    log = (directory / 'exceptions.log').read_text(encoding='utf-8')
    assert 'source=python exception=builtins.RuntimeError' in log
    assert 'source=python exception=builtins.ValueError' in log
    assert 'version=' in log and ' in run' in log
    assert 'PRIVATE_RESOURCE_NAME' not in log
    assert not list(directory.glob('fatal-*.log'))


def test_normal_exit_and_unwritable_diagnostics_do_not_break_startup(tmp_path):
    result = child(tmp_path, 'from services.crash_evidence import install; assert install()')
    assert result.returncode == 0
    assert not list((tmp_path / 'app' / 'diagnostics').glob('*.log'))
    (tmp_path / 'blocked').write_text('file, not directory', encoding='utf-8')
    env = os.environ.copy()
    env['NEKORI_APP_DATA'] = str(tmp_path / 'blocked')
    blocked = subprocess.run([sys.executable, '-c',
                              'from services.crash_evidence import install; assert install() is None'],
                             cwd=SOURCE, env=env, capture_output=True, text=True, timeout=20)
    assert blocked.returncode == 0, blocked.stderr


def test_exception_log_rotates_with_a_fixed_file_count(tmp_path):
    code = '''
import logging
from services.crash_evidence import install
install()
logger=logging.getLogger('nekori.crash_evidence')
for _ in range(90):
    logger.error('diagnostic probe ' + 'x'*10000)
'''
    result = child(tmp_path, code)
    assert result.returncode == 0, result.stderr
    logs = list((tmp_path / 'app' / 'diagnostics').glob('exceptions.log*'))
    assert 1 < len(logs) <= 3
    assert all(path.stat().st_size <= 512 * 1024 + 11000 for path in logs)


def test_frozen_version_location_and_native_file_count(tmp_path, monkeypatch):
    from services import crash_evidence

    install = tmp_path / 'package'
    (install / 'bin').mkdir(parents=True)
    (install / 'version.json').write_text('{"version":"0.2.1"}', encoding='utf-8')
    with monkeypatch.context() as patch:
        patch.setattr(sys, 'frozen', True, raising=False)
        patch.setattr(sys, 'executable', str(install / 'bin' / 'NekoriEmojy.exe'))
        assert crash_evidence._version() == '0.2.1'

    directory = tmp_path / 'app' / 'diagnostics'
    directory.mkdir(parents=True)
    import time
    for index in range(4):
        path = directory / f'fatal-20261024-120000-{index}.log'
        path.write_text(f'old fault {index}', encoding='utf-8')
        stamp=time.time()-100+index
        os.utime(path, (stamp,stamp))
    result = child(tmp_path, 'from services.crash_evidence import install; assert install()')
    assert result.returncode == 0, result.stderr
    retained = list(directory.glob('fatal-*.log'))
    assert len(retained) == 1 and retained[0].read_text(encoding='utf-8') == 'old fault 3'


def test_large_records_and_native_pipe_obey_byte_limits(tmp_path):
    code='''
import faulthandler,logging
from services import crash_evidence as c
c.install()
logger=logging.getLogger('nekori.crash_evidence')
for i in range(110):logger.error('界'*700000)
faulthandler.dump_traceback(file=c._fatal_file,all_threads=False)
c._fatal_file.write(b'x'*(c.LOG_BYTES*4))
c.record_task_failure('private-task-path','import',dict(state='running',current=2,total=9))
'''
    result=child(tmp_path,code)
    assert result.returncode==0,result.stderr
    from services.crash_evidence import LOG_BYTES
    files=list((tmp_path/'app/diagnostics').glob('*.log*'))
    assert files and len(files)<=5
    assert all(p.stat().st_size<=LOG_BYTES for p in files)
    fatal=next(p for p in files if p.name.startswith('fatal-'))
    assert fatal.stat().st_size==LOG_BYTES
    assert b'File ' in fatal.read_bytes()
    assert sum(p.stat().st_size for p in files)<=5*LOG_BYTES
    text=(tmp_path/'app/diagnostics/exceptions.log').read_text(encoding='utf-8')
    assert 'kind=import stage=running current=2 total=9' in text
    assert 'private-task-path' not in text


def test_native_trace_survives_abrupt_parent_exit(tmp_path):
    result=child(tmp_path,'''import faulthandler,os
from services import crash_evidence as c
c.install()
faulthandler.dump_traceback(file=c._fatal_file,all_threads=True)
os._exit(23)
''')
    assert result.returncode==23
    import time
    directory=tmp_path/'app/diagnostics'
    for _ in range(100):
        logs=list(directory.glob('fatal-*.log'))
        if logs and b'File ' in logs[0].read_bytes():break
        time.sleep(.02)
    assert logs and b'File ' in logs[0].read_bytes()
