"""Bounded local evidence for otherwise invisible desktop exceptions."""
import atexit
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import subprocess
from collections import deque
import re

from services.app_paths import app_data_dir


_installed = False
_fatal_file = None
_fatal_process = None
LOG_BYTES = 512 * 1024
RECORD_BYTES = 16 * 1024
RETENTION_SECONDS = 14 * 86400
_recent = deque(maxlen=64)
_context_lock = threading.RLock()
_environment = {}
_handler = None
_active_native = None


# One atomic document owns current state and bounded recovery candidates.
SESSION_FILE = 'sessions.json'
SESSION_BYTES = 4 * 1024 * 1024
PENDING_LIMIT = 3
EVIDENCE_BYTES = 768 * 1024  # per session, within the existing per-log cap
_session = None
_session_ready = True
_state_lock = threading.RLock()

# Import evidence shares the bounded exception log and session/export pipeline.
# Each task persists each entered stage and each error category only once, then
# one summary. No source objects, paths, messages or image references are held.
IMPORT_SOURCES=frozenset({'local_file','network_url','url_drop','clipboard_url','image_drop','clipboard_image','ole_image','mixed','operation','unknown'})
IMPORT_STAGES = frozenset({'queued','worker_create','worker_ready','thread_end','result_commit','receive','resolve','network','validate','decode','store','cleanup','finalize'})
IMPORT_ERRORS = frozenset({'unsupported_source','invalid_url','missing_source','http_status',
    'timeout','proxy_connection','connection','not_image','too_large','decode_failed',
    'permission','database','io','cancelled','unexpected','worker_ended','result_commit'})


def import_error(exc, stage):
    """Classify types and causes only; exception messages never enter evidence."""
    import socket, sqlite3
    from urllib.error import HTTPError, URLError
    from PIL import UnidentifiedImageError
    for _ in range(4):
        if exc.__cause__ is None:break
        exc=exc.__cause__
    if isinstance(exc,HTTPError):return ('proxy_connection' if exc.code==407 else 'http_status'),exc.code
    if isinstance(exc,URLError):
        reason=exc.reason
        if isinstance(reason,(TimeoutError,socket.timeout)):return 'timeout',None
        # A failed connection alone is not proof of a proxy fault.
        return 'connection',None
    if isinstance(exc,TimeoutError):return 'timeout',None
    if isinstance(exc,InterruptedError):return 'cancelled',None
    if isinstance(exc,FileNotFoundError):return 'missing_source',None
    if isinstance(exc,PermissionError):return 'permission',None
    if isinstance(exc,sqlite3.Error):return 'database',None
    if isinstance(exc,UnidentifiedImageError) or stage=='decode':return 'decode_failed',None
    if isinstance(exc,OSError):return 'io',None
    if isinstance(exc,ValueError) and stage in {'resolve','network'}:return 'invalid_url',None
    return 'unexpected',None


def record_import(task, stage, error=None, *, status=None, source=None, **counts):
    if stage not in IMPORT_STAGES or (error is not None and error not in IMPORT_ERRORS):return
    import hashlib
    value={'task':hashlib.sha256(str(task).encode()).hexdigest()[:16] if task else 'none',
           'stage':stage}
    if source in IMPORT_SOURCES:value['source']=source
    if error:value['error']=error
    if type(status) is int and 100<=status<=599:value['http_status']=status
    for key in ('saved','duplicates','failed','skipped','count','partial','cancelled','recovery'):
        number=counts.get(key)
        if type(number) in (bool,int):value[key]=max(0,min(int(number),2**31-1))
    with _context_lock:_recent.append(dict(event='import',**value))
    if _installed:
        try:
            logging.getLogger('nekori.crash_evidence').info('import=%s pid=%s session=%s',
                json.dumps(value,separators=(',',':')),os.getpid(),_session['id'] if _session else 'none')
            if stage in {'worker_create','worker_ready'} and _handler is not None:
                _handler.flush()
                if _handler.stream is not None:os.fsync(_handler.stream.fileno())
        except (OSError,ValueError):pass


class ImportTrace:
    def __init__(self, task):
        self.task=task;self.stage='receive';self.entered=set();self.failures=set();self.reported=False

    def enter(self, stage):
        if stage not in IMPORT_STAGES:return
        self.stage=stage
        if stage not in self.entered:
            self.entered.add(stage);record_import(self.task,stage)

    def begin_item(self):self.reported=False;self.enter('resolve')

    def failure(self, exc=None, *, error=None, stage=None):
        stage=stage or self.stage
        if self.reported and stage!='cleanup':return
        error,status=(error,None) if error else import_error(exc,stage)
        key=(stage,error,status)
        if key not in self.failures and len(self.failures)<64:
            self.failures.add(key);record_import(self.task,stage,error,status=status)
        if stage!='cleanup':self.reported=True

    def finish(self, saved, duplicates, failed, skipped, cancelled=False, recovery=False):
        record_import(self.task,'finalize',saved=saved,duplicates=duplicates,failed=failed,
                      skipped=skipped,partial=bool(failed and (saved or duplicates)),
                      cancelled=cancelled,recovery=recovery)


def import_stage(context, stage):
    trace=getattr(context,'import_trace',None)
    if trace:trace.enter(stage)


def _atomic_sessions(directory, value):
    data = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(data) > SESSION_BYTES:
        raise ValueError('Session evidence budget exceeded')
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / 'sessions.tmp'
    if directory.is_symlink() or temporary.is_symlink():raise OSError('Invalid diagnostics destination')
    try:
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / SESSION_FILE)
    finally:
        try:temporary.unlink(missing_ok=True)
        except OSError:pass


def _valid_session(value):
    if not isinstance(value, dict):return False
    environment=value.get('environment',{})
    if (not isinstance(environment,dict) or set(environment)-{'python','system','system_release','system_version','machine','qt'}
        or any(not isinstance(v,str) or len(v)>128 for v in environment.values())):return False
    if value.get('native_protocol',0) not in (0,1):return False
    if ('process_created' in value and (type(value['process_created']) is not int or not 0<value['process_created']<2**64)):return False
    if 'executable_hash' in value and (not isinstance(value['executable_hash'],str) or not re.fullmatch(r'[a-f0-9]{64}',value['executable_hash'])):return False
    return (set(value) <= {'id','version','pid','started_at','state','completed_at','completion','native_log','environment','native_protocol','process_created','executable_hash'}
            and isinstance(value.get('id'),str) and re.fullmatch(r'[a-f0-9]{32}',value['id'])
            and isinstance(value.get('version'),str) and re.fullmatch(r'[A-Za-z0-9_.+-]{1,32}',value['version'])
            and type(value.get('pid')) is int and 0 < value['pid'] < 2**32
            and type(value.get('started_at')) in (int,float) and 0 < value['started_at'] < 10**11
            and value.get('state') in {'running','completed'}
            and isinstance(value.get('native_log'),str)
            and re.fullmatch(r'fatal-\d{8}-\d{6}-\d+\.log',value['native_log'])
            and (value['state']=='running' or
                 (type(value.get('completed_at')) in (int,float)
                  and value['started_at'] <= value['completed_at'] < 10**11
                  and value.get('completion') in {'event_loop_returned','startup_cancelled','system_session_ended'})))


def session_snapshot():
    """Next-stage read API; only controlled metadata and redacted bounded evidence."""
    path = app_data_dir() / 'diagnostics' / SESSION_FILE
    try:
        if path.is_symlink() or path.stat().st_size > SESSION_BYTES:raise ValueError('Invalid state file')
        value = json.loads(path.read_text(encoding='utf-8'))
        if set(value) != {'schema','current','pending'} or value['schema'] != 1:raise ValueError('Invalid schema')
        if not _valid_session(value['current']):raise ValueError('Invalid session')
        pending = value['pending']
        if not isinstance(pending,list) or len(pending)>PENDING_LIMIT:raise ValueError('Invalid candidates')
        for item in pending:
            if (not isinstance(item,dict) or not {'session','assessment','evidence_kind','evidence'} <= set(item)
                or set(item)-{'session','assessment','evidence_kind','evidence','capture_state','capture_started','capture_checks','native_complete','report_state','notification_state'}
                or not _valid_session(item['session'])
                or item['assessment'] not in {'possible_abnormal_exit','fatal_error_recorded'}
                or item['evidence_kind'] not in {'none','python_log','native_trace','fatal_signature'}
                or not isinstance(item['evidence'],list) or len(item['evidence'])>4):raise ValueError('Invalid candidate')
            if item.get('capture_state','ready') not in {'collecting','ready'}:raise ValueError('Invalid capture state')
            if item.get('report_state','new') not in {'new','failed','ready'}:raise ValueError('Invalid report state')
            if item.get('notification_state','pending') not in {'pending','shown','dismissed'}:raise ValueError('Invalid reminder state')
            if type(item.get('capture_checks',0)) is not int or not 0<=item.get('capture_checks',0)<=8:raise ValueError('Invalid capture checks')
            if type(item.get('capture_started',0)) not in (int,float):raise ValueError('Invalid capture time')
            if type(item.get('native_complete',False)) is not bool:raise ValueError('Invalid completion')
            size=0
            for entry in item['evidence']:
                if (not isinstance(entry,dict) or set(entry)!={'kind','text'}
                    or entry['kind'] not in {'python','native'} or not isinstance(entry['text'],str)):
                    raise ValueError('Invalid evidence')
                size+=len(entry['text'].encode('utf-8'))
            if size>EVIDENCE_BYTES:raise ValueError('Invalid evidence size')
        return value
    except FileNotFoundError:return None
    except OSError:return {'unavailable':True,'reason':'io_error'}
    except (ValueError,TypeError,KeyError,RecursionError):return {'unavailable':True,'reason':'invalid_state'}


def _previous_evidence(directory, previous):
    from services.diagnostic_export import redact
    evidence=[];remaining=EVIDENCE_BYTES;native=False;fatal=False
    # Exact native name is reserved before writer startup; PID reuse alone is insufficient.
    paths=[('native',directory/previous['native_log'])]
    paths += [('python',directory/name) for name in ('exceptions.log.2','exceptions.log.1','exceptions.log')]
    for kind,path in paths:
        try:
            if path.is_symlink():continue
            stamp=path.stat().st_mtime
            if not previous['started_at']-2 <= stamp <= time.time()+2:continue
            with path.open('rb') as stream:raw=stream.read(LOG_BYTES).decode('utf-8',errors='replace')
        except FileNotFoundError:continue
        # Other I/O failures must abort protection, preserving old state/logs for retry.
        if kind=='python':
            selected=[];include=False
            for line in raw.splitlines():
                if re.match(r'^\d{4}-\d\d-\d\dT',line):
                    import calendar
                    try:recorded=calendar.timegm(time.strptime(line[:19],'%Y-%m-%dT%H:%M:%S'))
                    except ValueError:recorded=0
                    include=(previous['started_at']-2 <= recorded <= time.time()+2
                             and bool(re.search(r'\bpid='+str(previous['pid'])+r'\b',line)))
                if include:selected.append(line)
            raw='\n'.join(selected)
        if not raw.strip():continue
        text=redact(raw).encode('utf-8')[:min(LOG_BYTES,remaining)].decode('utf-8',errors='ignore')
        if not text:continue
        evidence.append({'kind':kind,'text':text});remaining-=len(text.encode('utf-8'))
        if kind=='native':
            native=True
            fatal=bool(re.search(r'Windows fatal exception:|Fatal Python error:',raw))
        if not remaining:break
    return dict(session=previous,assessment='fatal_error_recorded' if fatal else 'possible_abnormal_exit',
                evidence_kind='fatal_signature' if fatal else 'native_trace' if native else 'python_log' if evidence else 'none',
                evidence=evidence)


def _serialized(function):
    from functools import wraps
    @wraps(function)
    def call(*args,**kwargs):
        with _state_lock:return function(*args,**kwargs)
    return call


@_serialized
def begin_session():
    """Call only after acquiring the primary-instance lock, before install/maintenance.

    Protection and new identity commit in one replacement. On failure, old state
    and logs stay retryable; diagnostics disable destructive maintenance this run.
    """
    global _session, _session_ready
    if _session is not None:return dict(_session)
    if any(flag in sys.argv for flag in ('--diagnostic-writer','--backup-worker')):return None
    import uuid
    directory=app_data_dir()/'diagnostics'
    try:
        old=session_snapshot()
        if old and old.get('reason')=='io_error':raise OSError('Cannot read previous state')
        pending=[] if not old or old.get('unavailable') else old['pending']
        if old and not old.get('unavailable') and old['current']['state']=='running':
            candidate=_previous_evidence(directory,old['current'])
            candidate.update(capture_state='collecting',capture_started=time.time(),capture_checks=0,
                             native_complete=False,report_state='new',notification_state='pending')
            pending=(pending+[candidate])[-PENDING_LIMIT:]
        started=time.time()
        current=dict(id=uuid.uuid4().hex,version=_version(),pid=os.getpid(),started_at=started,state='running',
                     native_log=f'fatal-{time.strftime("%Y%m%d-%H%M%S",time.localtime(started))}-{os.getpid()}.log')
        import platform
        current['environment']=dict(python=platform.python_version(),system=platform.system(),
            system_release=platform.release(),system_version=platform.version(),machine=platform.machine())
        try:
            from PySide6.QtCore import qVersion
            current['environment']['qt']=qVersion()
        except ImportError:pass
        current['native_protocol']=1
        from services.windows_fault_event import process_identity
        current.update(process_identity())
        _exception_counts.clear()
        _atomic_sessions(directory,dict(schema=1,current=current,pending=pending))
        _session=current;_session_ready=True
        return dict(current)
    except (OSError,ValueError,TypeError):
        _session_ready=False
        return None


GUI_STALL_SECONDS = 20
_gui_watch = None


class GuiHeartbeat:
    """One sleeping observer. The Qt thread only updates the heartbeat in memory."""
    def __init__(self, session_id):
        self.session_id = session_id
        self.gui_ident = threading.get_ident()
        self.last = time.monotonic()
        self.stopped = threading.Event()

    def observe(self):
        try:
            while not self.stopped.is_set():
                last = self.last
                remaining = GUI_STALL_SECONDS - (time.monotonic() - last)
                if remaining > 0:
                    self.stopped.wait(remaining)
                    continue
                frame = sys._current_frames().get(self.gui_ident)
                stack = []
                while frame is not None and len(stack) < 32:
                    code = frame.f_code
                    module = frame.f_globals.get('__name__', '')
                    name = code.co_name
                    stack.append([module if isinstance(module,str) and re.fullmatch(r'[A-Za-z0-9_.]{1,96}',module) else '<module>',
                                  frame.f_lineno, name if re.fullmatch(r'[A-Za-z0-9_<>]{1,80}',name) else '<function>'])
                    frame = frame.f_back
                if self.last != last:
                    continue
                if stack and not self.stopped.is_set():
                    logging.getLogger('nekori.crash_evidence').warning(
                        'gui_unresponsive_sample pid=%d session=%s missed_ms=%d frames=%s',
                        os.getpid(), self.session_id, int((time.monotonic()-last)*1000),
                        json.dumps(stack,separators=(',',':')))
                return
        except Exception:
            # The optional observer must not invoke the application's exception hook.
            return
        finally:
            self.stopped.set()


def start_gui_watch():
    global _gui_watch
    if (not _installed or not _session or _session['state'] != 'running'
            or _gui_watch is not None or threading.current_thread() is not threading.main_thread()):
        return None
    watch = GuiHeartbeat(_session['id'])
    try:
        threading.Thread(target=watch.observe, name='GUI heartbeat', daemon=True).start()
    except RuntimeError:
        return None
    _gui_watch = watch
    return watch


def stop_gui_watch():
    if _gui_watch is not None:
        _gui_watch.stopped.set()


def complete_session(reason='event_loop_returned'):
    if _session is None or reason not in {'event_loop_returned','startup_cancelled','system_session_ended'}:return False
    stop_gui_watch()
    # Logging/rotation may read session state; never hold its write lock here.
    try:flush_exception_counts()
    except Exception:pass
    return _complete_session(reason)


@_serialized
def _complete_session(reason):
    """Normal return or committed OS session end; never aboutToQuit/hide/query."""
    global _session
    if _session is None or reason not in {'event_loop_returned','startup_cancelled','system_session_ended'}:return False
    try:
        value=session_snapshot()
        if not value or value.get('unavailable') or value['current']['id']!=_session['id']:return False
        completed=dict(_session,state='completed',completed_at=time.time(),completion=reason)
        value['current']=completed
        _atomic_sessions(app_data_dir()/'diagnostics',value)
        _session=completed
        return True
    except (OSError,ValueError):return False


@_serialized
def update_candidate(identity, **changes):
    allowed={'assessment','evidence_kind','evidence','capture_state','capture_started','capture_checks',
             'native_complete','report_state','notification_state'}
    if set(changes)-allowed:return False
    try:
        value=session_snapshot()
        if not value or value.get('unavailable'):return False
        item=next((c for c in value['pending'] if c['session']['id']==identity),None)
        if item is None:return False
        item.update(changes)
        _atomic_sessions(app_data_dir()/'diagnostics',value)
        return True
    except (OSError,ValueError):return False


def refresh_candidate(candidate):
    """Bounded nonblocking recheck; never wait for a native writer on the UI thread."""
    directory=app_data_dir()/'diagnostics'
    session=candidate['session'];marker=directory/(session['native_log']+'.done')
    try:done=not marker.is_symlink() and marker.read_bytes()==b'done'
    except FileNotFoundError:done=False
    checks=candidate.get('capture_checks',0)
    if not done and checks<6:
        update_candidate(session['id'],capture_state='collecting',capture_checks=checks+1)
        return False
    refreshed=_previous_evidence(directory,session)
    # Never replace already saved evidence with an empty/shorter partial snapshot.
    if sum(len(x['text']) for x in refreshed['evidence']) < sum(len(x['text']) for x in candidate['evidence']):
        refreshed={key:candidate[key] for key in ('assessment','evidence_kind','evidence')}
    else:refreshed.pop('session',None)
    return update_candidate(session['id'],**refreshed,capture_state='ready',native_complete=done)


def breadcrumb(event, **fields):
    """Internal event codes and scalar counts only; never accept user text."""
    if event not in {'startup','shutdown','window_show','window_hide','window_state',
                     'window_environment','task_state','exception','drag_summary'}:return
    safe = {key:value for key,value in fields.items()
            if key in {'count','duration_ms','max_dispatch_ms','events','kind','state','phase','role',
                       'qt_dispatches','native_events','hit_tests','nc_calculations','position_changes'}
            and (isinstance(value,(int,float,bool)) or
                 (isinstance(value,str) and re.fullmatch(r'[A-Za-z_]{1,32}',value)))}
    with _context_lock:
        _recent.append(dict(time=round(time.monotonic(),3),event=event,**safe))


def context_snapshot():
    with _context_lock:return dict(environment=dict(_environment),recent=list(_recent))


def set_environment(values):
    with _context_lock:_environment.update(values)


def persist_context(label):
    if _installed:
        logging.getLogger('nekori.crash_evidence').info('%s context=%s pid=%s session=%s',label,
            json.dumps(context_snapshot(),ensure_ascii=True,separators=(',',':')),
            os.getpid(),_session['id'] if _session else 'none')


def maintain(directory, *, active=(), native_slots=2, now=None):
    """Only owned, closed segments. An exported ZIP and unknown files are untouched."""
    directory=Path(directory);now=time.time() if now is None else now
    active={Path(p) for p in active if p is not None}
    value=session_snapshot()
    if value and not value.get('unavailable'):
        active.update(directory/c['session']['native_log'] for c in value['pending']
                      if c.get('capture_state')=='collecting' or c.get('native_complete') is False)
    try:
        if directory.is_symlink():return
        native=[p for p in directory.glob('fatal-*.log')
                if re.fullmatch(r'fatal-\d{8}-\d{6}-\d+\.log',p.name) and not p.is_symlink()]
        python=[directory/name for name in ('exceptions.log','exceptions.log.1','exceptions.log.2')]
        for path in python+native:
            if path in active or path.is_symlink():continue
            try:
                if now-path.stat().st_mtime>RETENTION_SECONDS:path.unlink()
                else:_trim(path)
            except OSError:pass
        existing=[]
        for path in native:
            try:existing.append((path.stat().st_mtime,path))
            except OSError:pass
        # Active segments count against the same two-file budget.
        excess=max(0,len(existing)-native_slots)
        for _,path in sorted(existing):
            if not excess:break
            if path not in active:
                try:path.unlink();excess-=1
                except OSError:pass
        retained={p.name for p in directory.glob('fatal-*.log')}
        if value and not value.get('unavailable'):
            retained.update(c['session']['native_log'] for c in value['pending'])
        for marker in directory.glob('fatal-*.log.done'):
            if (re.fullmatch(r'fatal-\d{8}-\d{6}-\d+\.log\.done',marker.name)
                and not marker.is_symlink() and marker.name[:-5] not in retained):
                try:marker.unlink()
                except OSError:pass
    except OSError:pass


def maintenance():
    if _handler is not None:
        _handler.acquire()
        try:
            path=Path(_handler.baseFilename)
            # Close/rotate before removing an expired current Python segment.
            try:
                if path.exists() and time.time()-path.stat().st_mtime>RETENTION_SECONDS:
                    _handler.doRollover()
            except OSError:pass
            maintain(path.parent,active=(path,_active_native))
        finally:_handler.release()


class BoundedRotatingHandler(RotatingFileHandler):
    def doRollover(self):
        super().doRollover()
        maintain(Path(self.baseFilename).parent,active=(Path(self.baseFilename),_active_native))

    def format(self, record):
        text = super().format(record).encode('utf-8', errors='replace')
        return text[:RECORD_BYTES].decode('utf-8', errors='ignore')

    def shouldRollover(self, record):
        if self.stream is None:self.stream = self._open()
        self.stream.seek(0, 2)
        return self.stream.tell() + len(self.format(record).encode('utf-8')) + 2 > self.maxBytes


def _trim(path):
    if not path.is_symlink() and path.stat().st_size > LOG_BYTES:
        with path.open('r+b') as stream:stream.truncate(LOG_BYTES)


def collect_native(handle, path):
    """Drain independently of the crashing interpreter; never exceed LOG_BYTES.

    A Python thread cannot reliably drain while faulthandler holds the GIL.
    After the parent dies, EOF lets this small writer finish and exit itself.
    """
    fd = int(handle)
    if sys.platform == 'win32':
        import msvcrt
        fd = msvcrt.open_osfhandle(fd, os.O_RDONLY)
    written = 0
    completed = False
    try:
        with os.fdopen(fd, 'rb', buffering=0) as source, Path(path).open('wb') as target:
            while True:
                chunk = source.read(65536)
                if not chunk:break
                retained = chunk[:max(0, LOG_BYTES-written)]
                if retained:
                    target.write(retained);target.flush();written += len(retained)
                # Continue draining excess bytes; the faulting process must
                # not deadlock on a full pipe when the disk budget is reached.
            completed = True
    finally:
        if not written:
            try:Path(path).unlink()
            except OSError:pass
        # EOF reached: next launch can distinguish an empty result from an unfinished writer.
        if completed:
            try:Path(str(path)+'.done').write_bytes(b'done')
            except OSError:pass


def _native_sink(path):
    read_fd, write_fd = os.pipe()
    options = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    frozen = getattr(sys,'frozen',False) or globals().get('__compiled__')
    try:
        if frozen:
            from services.autostart import _process_executable
            prefix=[str(_process_executable()),'--diagnostic-writer']
        else:prefix=[sys.executable,'-m','services.crash_evidence','--diagnostic-writer']
        handle = read_fd
        if sys.platform == 'win32':
            import msvcrt
            handle = msvcrt.get_osfhandle(read_fd)
            os.set_handle_inheritable(handle,True)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {'handle_list':[handle]}
            options.update(startupinfo=startup,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
        else:options['pass_fds']=(read_fd,)
        process = subprocess.Popen(prefix+[str(handle),str(path)],
                                   cwd=str(Path(__file__).resolve().parent.parent),**options)
        return os.fdopen(write_fd,'wb',buffering=0), process
    except Exception:
        os.close(write_fd)
        raise
    finally:os.close(read_fd)


def record_task_failure(key, kind, previous=None, *, exc_info=None):
    """Only an error transition, with identity/counts, never resource text."""
    if not _installed:return
    import hashlib
    task = hashlib.sha256(str(key).encode()).hexdigest()[:12]
    previous = previous or {}
    breadcrumb('exception',kind='task')
    persist_context('task_failure')
    logger = logging.getLogger('nekori.crash_evidence')
    safe_kind = kind if kind in {'import','ocr','export','migration','exchange'} else 'task'
    phase = previous.get('phase','')
    if phase not in {'waiting','decision','finalizing','running','recognizing',
                     '恢复分类关系','整理资源顺序','完成迁移收尾'}:
        phase = 'running' if previous.get('state')=='running' else 'result'
    logger.error('pid=%s task=%s kind=%s stage=%s current=%s total=%s%s',os.getpid(),task,safe_kind,
                 phase,
                 previous.get('current',0),previous.get('total',0),
                 '\nexception='+exc_info[0].__qualname__+'\n'+_frames(exc_info[2]) if exc_info else '')


# Bounded, session-local aggregation; messages only affect a keyed fingerprint.
_exception_counts={}
_exception_salt=os.urandom(16)


def record_exception(kind,exc_type,exc,tb):
    if not _installed:return
    kind=kind if kind in {'python','thread'} else 'python'
    try:
        import hashlib
        name=f'{exc_type.__module__}.{exc_type.__qualname__}'
        if not re.fullmatch(r'[A-Za-z0-9_.]{1,128}',name):name='Exception'
        frames=_frames(tb)
        codes={key:value for key in ('errno','winerror','sqlite_errorcode') if type(value:=getattr(exc,key,None)) is int and -2**31<=value<2**31}
        # Different messages/causes remain distinct without storing their contents.
        causes=[];cause=exc
        for _ in range(4):
            causes.append((type(cause).__module__,type(cause).__qualname__,str(cause)[:4096]))
            cause=cause.__cause__ or cause.__context__
            if cause is None:break
        reason=hashlib.blake2b(repr(causes).encode('utf-8',errors='replace'),key=_exception_salt,digest_size=16).hexdigest()
        signature=hashlib.sha256(repr((kind,name,frames,codes,reason)).encode()).hexdigest()[:16]
        with _context_lock:
            first=signature not in _exception_counts
            if first:
                if len(_exception_counts)>=128:_exception_counts.pop(next(iter(_exception_counts)))
                _exception_counts[signature]=dict(count=0,logged=0,last_at=0,type=name,**codes)
            item=_exception_counts[signature];item['count']+=1;item['last_at']=round(time.time(),3)
            count=item['count'];summary=dict(item)
        logger=logging.getLogger('nekori.crash_evidence')
        if first:
            breadcrumb('exception',kind=kind);persist_context('exception')
            logger.error('version=%s pid=%s session=%s thread=%s source=%s exception=%s signature=%s errno=%s winerror=%s sqlite_errorcode=%s count=1 last_at=%s\n%s',
                         _session['version'] if _session else _version(),os.getpid(),_session['id'] if _session else 'none',threading.get_ident(),kind,name,signature,codes.get('errno'),codes.get('winerror'),codes.get('sqlite_errorcode'),summary['last_at'],frames)
        elif count & (count-1)==0:
            logger.error('pid=%s session=%s exception_repeat signature=%s summary=%s',os.getpid(),_session['id'] if _session else 'none',signature,json.dumps({k:v for k,v in summary.items() if k!='logged'},separators=(',',':')))
        else:return
        with _context_lock:item['logged']=count
    except Exception:pass


def flush_exception_counts():
    if not _installed:return
    with _context_lock:
        pending=[(signature,dict(item)) for signature,item in _exception_counts.items() if item['count']!=item['logged']]
    for signature,item in pending:
        logging.getLogger('nekori.crash_evidence').error('pid=%s session=%s exception_repeat signature=%s summary=%s',os.getpid(),_session['id'] if _session else 'none',signature,
            json.dumps({k:v for k,v in item.items() if k!='logged'},separators=(',',':')))
        with _context_lock:
            current=_exception_counts.get(signature)
            if current and current['count']>=item['count']:current['logged']=max(current['logged'],item['count'])


def _version():
    root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) or globals().get('__compiled__') else Path(__file__).resolve().parent.parent
    if root.name.lower() == 'bin' and (root.parent / 'version.json').is_file():
        root = root.parent
    try:
        return str(json.loads((root / 'version.json').read_text(encoding='utf-8'))['version'])
    except (OSError, ValueError, KeyError):
        return 'unknown'


def _frames(tb):
    root = Path(__file__).resolve().parent.parent
    lines = []
    for frame in traceback.extract_tb(tb, limit=64):
        path = Path(frame.filename)
        try:
            name = str(path.relative_to(root))
        except ValueError:
            name = path.name
        lines.append(f'  {name}:{frame.lineno} in {frame.name}')
    return '\n'.join(lines)


def install():
    """Install once; an unavailable diagnostics directory must not block startup."""
    global _installed, _fatal_file, _fatal_process, _handler, _active_native
    if not _session_ready:return None
    if _installed:
        return app_data_dir() / 'diagnostics'
    directory = app_data_dir() / 'diagnostics'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        maintain(directory)
        for path in directory.glob('exceptions.log*'):
            if path.name in {'exceptions.log','exceptions.log.1','exceptions.log.2'}:_trim(path)
        handler = BoundedRotatingHandler(directory / 'exceptions.log', maxBytes=LOG_BYTES,
                                      backupCount=2, encoding='utf-8', delay=True)
    except OSError:
        return None

    logger = logging.getLogger('nekori.crash_evidence')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter('%(asctime)sZ %(message)s', '%Y-%m-%dT%H:%M:%S')
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    _handler=handler
    previous_sys_hook = sys.excepthook
    previous_thread_hook = threading.excepthook

    def python_exception(exc_type, exc, tb):
        record_exception('python',exc_type,exc,tb)
        previous_sys_hook(exc_type, exc, tb)

    def thread_exception(args):
        record_exception('thread',args.exc_type,args.exc_value,args.exc_traceback)
        previous_thread_hook(args)

    sys.excepthook = python_exception
    threading.excepthook = thread_exception

    # CPython's Windows fault handler can retain a fatal traceback when the
    # console-less executable cannot show stderr. Keep at most two such files.
    try:
        fatal_path = directory / (_session['native_log'] if _session else
                                  f'fatal-{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}.log')
        maintain(directory,native_slots=1)
        _fatal_file, _fatal_process = _native_sink(fatal_path)
        _active_native=fatal_path
        faulthandler.enable(file=_fatal_file, all_threads=True)

        def close_fatal():
            faulthandler.disable()
            _fatal_file.close()
            try:_fatal_process.wait(timeout=2)
            except subprocess.TimeoutExpired:pass
            try:
                if fatal_path.stat().st_size == 0:
                    fatal_path.unlink()
            except OSError:
                pass

        atexit.register(close_fatal)
    except (OSError, RuntimeError):
        if _fatal_file is not None:
            _fatal_file.close()
            _fatal_file = None
    _installed = True
    return directory


if __name__ == '__main__' and len(sys.argv)==4 and sys.argv[1]=='--diagnostic-writer':
    collect_native(sys.argv[2],sys.argv[3])
