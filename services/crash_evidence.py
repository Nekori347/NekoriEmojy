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

from services.app_paths import app_data_dir


_installed = False
_fatal_file = None


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
    global _installed, _fatal_file
    if _installed:
        return app_data_dir() / 'diagnostics'
    directory = app_data_dir() / 'diagnostics'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / 'exceptions.log', maxBytes=512 * 1024,
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
                         version, os.getpid(), threading.current_thread().name,
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
        _fatal_file = fatal_path.open('w', encoding='utf-8')
        faulthandler.enable(file=_fatal_file, all_threads=True)

        def close_fatal():
            faulthandler.disable()
            _fatal_file.close()
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
