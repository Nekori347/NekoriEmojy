"""Delete owned files through the Windows shell; never fall back to unlink."""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path


def recycle_file(path, library_root):
    target = Path(path).resolve()
    target.relative_to(Path(library_root).resolve())
    if not target.is_file():
        raise FileNotFoundError(target)
    if os.name != "nt":
        raise OSError("Windows Recycle Bin is required")

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    operation = SHFILEOPSTRUCTW()
    operation.wFunc = 3  # FO_DELETE
    # FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
    operation.fFlags = 0x40 | 0x10 | 0x400 | 0x4
    paths = ctypes.create_unicode_buffer(str(target) + "\0\0")
    operation.pFrom = ctypes.cast(paths, wintypes.LPCWSTR)
    shell_delete = ctypes.windll.shell32.SHFileOperationW
    shell_delete.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell_delete.restype = ctypes.c_int
    code = shell_delete(ctypes.byref(operation))
    if code or operation.fAnyOperationsAborted:
        raise OSError(f"Recycle Bin operation failed or cancelled ({code})")
