"""Cooperative export cancellation and final-file publication for ZIP exporters."""
from contextlib import contextmanager
from pathlib import Path
import os
import tempfile


class ExportCancelled(Exception):
    """Cancellation confirmed at an export boundary, distinct from failure."""


def check_export_cancelled(cancel_check):
    if cancel_check is not None and cancel_check():
        raise ExportCancelled('Export cancelled')


@contextmanager
def staged_export_path(target, cancel_check=None):
    """Publish only a closed, complete archive; preserve an existing destination."""
    check_export_cancelled(cancel_check)
    target = Path(target).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix='.' + target.name + '.', suffix='.part', dir=target.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        yield temporary
        check_export_cancelled(cancel_check)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
