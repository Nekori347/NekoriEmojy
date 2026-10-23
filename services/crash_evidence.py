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

from services.app_paths import app_data_dir


_installed = False
_fatal_file = None
_fatal_process = None
LOG_BYTES = 512 * 1024
RECORD_BYTES = 16 * 1024


class BoundedRotatingHandler(RotatingFileHandler):
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
    finally:
        if not written:
            try:Path(path).unlink()
            except OSError:pass


def _native_sink(path):
    read_fd, write_fd = os.pipe()
    options = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    frozen = getattr(sys,'frozen',False) or globals().get('__compiled__')
    prefix = [sys.executable,'--diagnostic-writer'] if frozen else [sys.executable,'-m','services.crash_evidence','--diagnostic-writer']
    try:
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
    global _installed, _fatal_file, _fatal_process
    if _installed:
        return app_data_dir() / 'diagnostics'
    directory = app_data_dir() / 'diagnostics'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.glob('exceptions.log*'):
            if path.name in {'exceptions.log','exceptions.log.1','exceptions.log.2'}:_trim(path)
        handler = BoundedRotatingHandler(directory / 'exceptions.log', maxBytes=LOG_BYTES,
                                      backupCount=2, encoding='utf-8', delay=True)
    except OSError:
        return None

    logger = logging.getLogger('nekori.crash_evidence')
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    formatter = logging.Formatter('%(asctime)sZ %(message)s', '%Y-%m-%dT%H:%M:%S')
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    version = _version()

    def record(kind, exc_type, tb):
        try:
            name = f'{exc_type.__module__}.{exc_type.__qualname__}'
            logger.error('version=%s pid=%s thread=%s source=%s exception=%s\n%s',
                         version, os.getpid(), threading.get_ident(),
                         kind, name, _frames(tb))
        except Exception:
            pass  # Evidence collection must never replace the original exception.

    previous_sys_hook = sys.excepthook
    previous_thread_hook = threading.excepthook

    def python_exception(exc_type, exc, tb):
        record('python', exc_type, tb)
        previous_sys_hook(exc_type, exc, tb)

    def thread_exception(args):
        record('thread', args.exc_type, args.exc_traceback)
        previous_thread_hook(args)

    sys.excepthook = python_exception
    threading.excepthook = thread_exception

    # CPython's Windows fault handler can retain a fatal traceback when the
    # console-less executable cannot show stderr. Keep at most two such files.
    try:
        fatal_path = directory / f'fatal-{time.strftime("%Y%m%d-%H%M%S")}-{os.getpid()}.log'
        old = sorted(directory.glob('fatal-*.log'), key=lambda path: path.stat().st_mtime)
        for path in old[:-1]:
            path.unlink()
        for path in old[-1:]:_trim(path)
        _fatal_file, _fatal_process = _native_sink(fatal_path)
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
