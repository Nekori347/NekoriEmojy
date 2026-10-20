"""Current-user Windows login startup; importing never changes the OS.

Process-image lookup and StartupApproved handling adapted from SuzuEmojy
dc14f4a1f5149d964480528dd5a50b41df803752 (IxinorTyan), under GPL-3.0.
Nekori resolves its public entry through its own release manifest.
"""
import os
import subprocess
import sys
from pathlib import Path
import json


def _process_executable():
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    read = kernel.GetModuleFileNameW
    read.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    read.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = read(None, buffer, len(buffer))
    if not length:
        raise ctypes.WinError(ctypes.get_last_error())
    if length >= len(buffer):
        raise OSError('The executable path is too long')
    return Path(buffer.value).resolve()


def _package_launcher(executable=None):
    """Only a Nekori manifest identifies the public entry; no bin-name guess."""
    from services.update_protocol import read_manifest
    base = executable.parent if executable else Path(__file__).resolve().parent.parent
    for root in (base, base.parent):
        try:
            metadata = json.loads((root / 'version.json').read_text('utf-8'))
            if metadata.get('update_repository') != 'Nekori347/NekoriEmojy':
                continue
            manifest = read_manifest(root)
            # Public entry and manifest use the same current Nekori identity.
            entry = root / 'NekoriEmojy.exe'
            if 'NekoriEmojy.exe' in manifest['files'] and entry.is_file():
                return entry
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


class AutostartService:
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    VALUE_NAME = "NekoriEmojy"
    APPROVAL_KEYS = (
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32",
    )

    def __init__(self):
        self.supported = sys.platform == "win32"

    def command(self):
        compiled = bool(getattr(sys, "frozen", False) or globals().get("__compiled__"))
        executable = _process_executable() if compiled else Path(sys.executable).resolve()
        launcher = _package_launcher(executable if compiled else None)
        if launcher:
            args = [str(launcher)]
        elif compiled:
            args = [str(executable)]
        else:
            # Reuse the working runtime, including the lightweight launcher's runtime.
            pythonw = executable.with_name("pythonw.exe")
            if pythonw.is_file():
                executable = pythonw
            script = Path(__file__).resolve().parent.parent / "main.py"
            if not script.is_file():
                raise FileNotFoundError(str(script))
            args = [str(executable), str(script)]
        return subprocess.list2cmdline(args + ["--autostart"])

    def is_enabled(self):
        if not self.supported:
            return False
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
                value, kind = winreg.QueryValueEx(key, self.VALUE_NAME)
            return (kind == winreg.REG_SZ and os.path.normcase(value) == os.path.normcase(self.command())
                    and not self._disabled_approval_keys())
        except FileNotFoundError:
            return False

    def _disabled_approval_keys(self):
        import winreg
        disabled = []
        for path in self.APPROVAL_KEYS:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                    value, kind = winreg.QueryValueEx(key, self.VALUE_NAME)
            except FileNotFoundError:
                continue
            if kind == winreg.REG_BINARY and isinstance(value, bytes) and value and value[0] in (3, 7):
                disabled.append(path)
        return disabled

    def _write_command(self, command):
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, self.VALUE_NAME, 0, winreg.REG_SZ, command)

    def repair_registration(self):
        """Repair only exact obsolete commands of this installation, without enabling."""
        compiled = bool(getattr(sys, 'frozen', False) or globals().get('__compiled__'))
        image = _process_executable() if compiled else None
        if not self.supported or (not compiled and not _package_launcher()):
            return False
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
                value, kind = winreg.QueryValueEx(key, self.VALUE_NAME)
        except FileNotFoundError:
            return False
        if kind != winreg.REG_SZ:
            return False
        if compiled:
            candidates = [[str(image), '--autostart'], [str(image.with_name('python.exe')), '--autostart']]
        else:
            python = Path(sys.executable).resolve()
            script = str(Path(__file__).resolve().parent.parent / 'main.py')
            candidates = [[str(p), script, '--autostart'] for p in (python, python.with_name('pythonw.exe'))]
        current = self.command()
        previous = os.path.normcase(value)
        if previous == os.path.normcase(current) or previous not in {os.path.normcase(subprocess.list2cmdline(args)) for args in candidates}:
            return False
        self._write_command(current)
        return True

    def set_enabled(self, enabled):
        if not self.supported:
            raise OSError("Windows login startup is unavailable on this platform")
        import winreg
        if enabled:
            command = self.command()
            self._write_command(command)
            # Only explicit enable may remove this app's system-disabled entry.
            for path in self._disabled_approval_keys():
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, self.VALUE_NAME)
                except FileNotFoundError:
                    pass
            if not self.is_enabled():
                raise OSError('Windows 未能启用开机启动，请检查系统的启动应用设置')
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY,
                                    0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, self.VALUE_NAME)
            except FileNotFoundError:
                pass


def should_start_hidden(argv, tray_available):
    """Never leave the app inaccessible when no system tray is available."""
    return "--autostart" in argv and tray_available
