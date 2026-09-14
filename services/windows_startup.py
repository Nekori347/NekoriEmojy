"""Per-user Windows startup entry, changed only by an explicit settings save."""
from pathlib import Path
import subprocess
import winreg
from services.library import LibraryError, program_root

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'NekoriEmojy'


def startup_command(library, executable=None):
    program = Path(executable) if executable else program_root() / 'NekoriEmojy.exe'
    if not program.is_file():
        raise LibraryError('尚未找到 NekoriEmojy 启动程序，无法设置开机自启。')
    command = subprocess.list2cmdline([str(program.resolve()), '--library', str(library.root)])
    if len(command) > 260:
        raise LibraryError('程序与资源库路径过长，Windows 启动项最多支持 260 个字符。')
    return command


def read_startup():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as key:
            return winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return None


def restore_startup(value):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if value is None:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
        else:
            data, kind = value
            winreg.SetValueEx(key, VALUE_NAME, 0, kind, data)


def apply_startup(enabled, library, executable=None):
    command = startup_command(library, executable) if enabled else None
    restore_startup((command, winreg.REG_SZ) if command else None)
