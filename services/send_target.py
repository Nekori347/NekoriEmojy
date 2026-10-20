"""Shared Windows target tracking and bounded, validated clipboard sending."""
import ctypes
import os
from ctypes import wintypes
from enum import Enum
from PySide6.QtCore import QObject, QTimer


class SendResult(str, Enum):
    SENT = 'SENT'
    COPIED_ONLY = 'COPIED_ONLY'
    COPY_FAILED = 'COPY_FAILED'


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.c_void_p)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_void_p)]


class INPUTUNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('data', INPUTUNION)]


class WindowsTargetAPI:
    def __init__(self):
        self.native = ctypes.WinDLL('user32', use_last_error=True)
        self.native.GetForegroundWindow.restype = wintypes.HWND
        self.native.IsWindow.argtypes = [wintypes.HWND]
        self.native.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.native.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.native.IsIconic.argtypes = [wintypes.HWND]
        self.native.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.native.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.native.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self.native.SendInput.restype = wintypes.UINT

    def foreground(self):
        return int(self.native.GetForegroundWindow() or 0)

    def is_window(self, hwnd):
        return bool(self.native.IsWindow(hwnd))

    def process_id(self, hwnd):
        pid = wintypes.DWORD()
        self.native.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)

    def class_name(self, hwnd):
        name = ctypes.create_unicode_buffer(256)
        self.native.GetClassNameW(hwnd, name, len(name))
        return name.value

    def acquire_foreground(self, hwnd):
        if self.native.IsIconic(hwnd):
            self.native.ShowWindow(hwnd, 9)  # SW_RESTORE
        self.native.SetForegroundWindow(hwnd)


class PasteInjector:
    def __init__(self, api):
        self.api = api

    def paste(self):
        sequence = ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2))
        inputs = (INPUT * len(sequence))()
        for index, (key, flags) in enumerate(sequence):
            inputs[index].type = 1  # INPUT_KEYBOARD
            inputs[index].data.ki = KEYBDINPUT(key, 0, flags, 0, None)
        sent = self.api.native.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))
        if 0 < sent < len(inputs):
            # Release modifiers if Windows accepted only part of the sequence.
            releases = (INPUT * 2)()
            for index, key in enumerate((0x56, 0x11)):
                releases[index].type = 1
                releases[index].data.ki = KEYBDINPUT(key, 0, 2, 0, None)
            self.api.native.SendInput(2, releases, ctypes.sizeof(INPUT))
        return sent == len(inputs)


class SendTargetService(QObject):
    SHELL_CLASSES = frozenset(('Progman', 'WorkerW', 'Shell_TrayWnd',
        'Shell_SecondaryTrayWnd', 'CabinetWClass', 'ExploreWClass', 'Windows.UI.Core.CoreWindow'))

    def __init__(self, parent=None, *, api=None, injector=None, schedule=None):
        super().__init__(parent)
        self.api = api or WindowsTargetAPI()
        self.injector = injector or PasteInjector(self.api)
        self.schedule = schedule or (lambda callback: QTimer.singleShot(10, self, callback))
        self.last_external_hwnd = None
        self._target_pid = None
        self._generation = 0

    def valid(self, hwnd, expected_pid=None):
        if not hwnd or not self.api.is_window(hwnd):
            return False
        pid = self.api.process_id(hwnd)
        class_name = self.api.class_name(hwnd)
        return bool(pid and pid != os.getpid() and (expected_pid is None or pid == expected_pid)
                    and class_name and class_name not in self.SHELL_CLASSES)

    def remember(self, hwnd):
        if self.valid(hwnd):
            self.last_external_hwnd = int(hwnd)
            self._target_pid = self.api.process_id(hwnd)
            return True
        return False

    def capture_foreground(self):
        return self.remember(self.api.foreground())

    def send(self, path, clipboard, storage, completed, recent_limit=30):
        """Deliver exactly one final SendResult through completed, possibly later."""
        self._generation += 1
        generation = self._generation
        if not storage.availability.exists(path, revalidate=True) or not clipboard.copy_image_to_clipboard(path):
            completed(SendResult.COPY_FAILED)
            return
        storage.add_recent_image(path, recent_limit)
        self.capture_foreground()
        hwnd, pid = self.last_external_hwnd, self._target_pid
        if not self.valid(hwnd, pid):
            self.last_external_hwnd = self._target_pid = None
            completed(SendResult.COPIED_ONLY)
            return
        self.api.acquire_foreground(hwnd)

        def attempt(remaining=10):
            if generation != self._generation or not self.valid(hwnd, pid):
                completed(SendResult.COPIED_ONLY)
                return
            if self.api.foreground() == hwnd:
                # Check identity and foreground again immediately before input.
                if self.valid(hwnd, pid) and self.api.foreground() == hwnd and self.injector.paste():
                    completed(SendResult.SENT)
                else:
                    completed(SendResult.COPIED_ONLY)
            elif remaining:
                self.schedule(lambda: attempt(remaining - 1))
            else:
                completed(SendResult.COPIED_ONLY)

        attempt()
