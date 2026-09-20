"""Bounded Windows candidate probe helper. Uses only the supplied test EXE / PID.

launch EXE LIBRARY WORK starts with an isolated bootstrap and disabled network.
dump PID WORK records that process' UI Automation tree and its main window image.
action PID HELPER (invoke|value|select|focus) INDEX [VALUE] calls Windows UIA.
"""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

def processes_at(path):
    import win32process
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    found = []
    for pid in win32process.EnumProcesses():
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            continue
        try:
            name = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(name))
            if kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
                if os.path.normcase(name.value) == os.path.normcase(str(path)):
                    found.append(pid)
        finally:
            kernel.CloseHandle(handle)
    return found

if sys.argv[1] == 'launch':
    executable, library, work = [Path(p).resolve() for p in sys.argv[2:5]]
    assert (library / 'nekori-library.json').is_file()
    core = executable.parent / 'bin/NekoriEmojy.exe'
    assert core.is_file() and not processes_at(core)
    env = os.environ.copy()
    env.pop('QT_QPA_PLATFORM', None)
    env['NEKORI_BOOTSTRAP_DIR'] = str(work / 'bootstrap')
    env['HTTPS_PROXY'] = env['HTTP_PROXY'] = 'http://127.0.0.1:9'
    env['NO_PROXY'] = ''
    subprocess.run([str(executable), '--library', str(library)], env=env,
                   cwd=work, check=True, timeout=15)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        pids = processes_at(core)
        if pids:
            (work / 'pid.txt').write_text(str(pids[0]), encoding='ascii')
            print(json.dumps({'pid': pids[0], 'core': str(core)}))
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Core process did not start')
elif sys.argv[1] == 'action':
    pid, helper, action, index, *values = sys.argv[2:]
    subprocess.run([helper, pid, action, index, *values], check=True, timeout=15)
elif sys.argv[1] == 'click':
    import win32gui, win32process, win32con
    pid, x, y = map(int, sys.argv[2:5])
    windows = []
    def target_window(hwnd, _):
        if win32process.GetWindowThreadProcessId(hwnd)[1] != pid or not win32gui.IsWindowVisible(hwnd):
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if left <= x < right and top <= y < bottom:
            windows.append(hwnd)
    win32gui.EnumWindows(target_window, None)
    if not windows:
        raise RuntimeError('No owned test window at supplied position')
    hwnd = windows[0]
    cx, cy = win32gui.ScreenToClient(hwnd, (x, y))
    point = (cy << 16) | (cx & 0xffff)
    button = len(sys.argv) > 5 and sys.argv[5] == 'right'
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, point)
    win32gui.PostMessage(hwnd, win32con.WM_RBUTTONDOWN if button else win32con.WM_LBUTTONDOWN,
                         win32con.MK_RBUTTON if button else win32con.MK_LBUTTON, point)
    win32gui.PostMessage(hwnd, win32con.WM_RBUTTONUP if button else win32con.WM_LBUTTONUP, 0, point)
elif sys.argv[1] == 'dump':
    pid, work_arg = sys.argv[2:4]
    work = Path(work_arg).resolve()
    raw = subprocess.check_output([str(work / 'uia.exe'), pid, 'dump'], timeout=20, text=True, encoding='utf-8')
    rows = []
    for line in raw.splitlines():
        index, kind, name, identity, rect, offscreen, patterns = line.split('\t')
        rows.append({'index': int(index), 'type': kind, 'name': base64.b64decode(name).decode('utf-8'),
                     'id': identity, 'rect': rect, 'offscreen': offscreen == 'True', 'patterns': patterns})
    (work / 'ui.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    visible = [r for r in rows if not r['offscreen']]
    print(json.dumps(visible, ensure_ascii=False, indent=2))
    import win32gui, win32process
    import win32ui
    from PIL import Image
    handles = []
    def collect(hwnd, _):
        if win32process.GetWindowThreadProcessId(hwnd)[1] == int(pid) and win32gui.IsWindowVisible(hwnd):
            if win32gui.GetWindowText(hwnd) == 'NekoriEmojy':
                handles.append(hwnd)
    win32gui.EnumWindows(collect, None)
    if handles:
        hwnd = handles[0]
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right-left, bottom-top
        dc = win32gui.GetWindowDC(hwnd)
        source = win32ui.CreateDCFromHandle(dc)
        memory = source.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source, width, height)
        memory.SelectObject(bitmap)
        try:
            # Capture only this window, excluding unrelated overlapping apps.
            ctypes.windll.user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
            ctypes.windll.user32.PrintWindow.restype = wintypes.BOOL
            if not ctypes.windll.user32.PrintWindow(hwnd, memory.GetSafeHdc(), 2):
                raise RuntimeError('Test window capture failed')
            Image.frombuffer('RGB', (width,height), bitmap.GetBitmapBits(True),
                             'raw', 'BGRX', 0, 1).save(work / 'window.png')
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            memory.DeleteDC(); source.DeleteDC(); win32gui.ReleaseDC(hwnd, dc)
else:
    raise ValueError('Unknown action')
