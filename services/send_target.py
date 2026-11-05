"""Shared Windows target tracking and bounded, validated clipboard sending."""
import ctypes
import os
from ctypes import wintypes
from enum import Enum
from dataclasses import dataclass
from collections import deque
import uuid, time, logging
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
        self.last_error=0

    def paste(self):
        sequence = ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2))
        inputs = (INPUT * len(sequence))()
        for index, (key, flags) in enumerate(sequence):
            inputs[index].type = 1  # INPUT_KEYBOARD
            inputs[index].data.ki = KEYBDINPUT(key, 0, flags, 0, None)
        ctypes.set_last_error(0)
        sent = self.api.native.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))
        self.last_error=ctypes.get_last_error() if sent!=len(inputs) else 0
        if 0 < sent < len(inputs):
            # Release modifiers if Windows accepted only part of the sequence.
            releases = (INPUT * 2)()
            for index, key in enumerate((0x56, 0x11)):
                releases[index].type = 1
                releases[index].data.ki = KEYBDINPUT(key, 0, 2, 0, None)
            self.api.native.SendInput(2, releases, ctypes.sizeof(INPUT))
        return sent == len(inputs)


@dataclass(frozen=True)
class SendOutcome:
    request_id: str
    result: SendResult
    reason: str
    hwnd: int | None
    pid: int | None
    elapsed_ms: float
    details: str = ''


@dataclass
class _SendRequest:
    identity: str
    path: str
    clipboard: object
    storage: object
    completed: object
    recent_limit: int
    hwnd: int | None
    pid: int | None
    started: float
    done: bool = False
    clipboard_ticket: object = None
    preparation_ticket: object = None
    observed_hwnd: int | None = None
    prepared_async: bool = False


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
        self.last_outcome = None
        self._queue=deque();self._active=None;self._closed=False
        from services.drag_activity import drag_activity
        self._drag_activity=drag_activity()
        self._drag_activity.idle.connect(self._start_next)
        self.destroyed.connect(self.cancel_requests)
        from PySide6.QtCore import QCoreApplication
        application=QCoreApplication.instance()
        if application is not None:application.aboutToQuit.connect(self.cancel_requests)

    def valid(self, hwnd, expected_pid=None):
        if not hwnd or not self.api.is_window(hwnd):return False
        pid=self.api.process_id(hwnd);name=self.api.class_name(hwnd)
        return bool(pid and pid!=os.getpid() and (expected_pid is None or pid==expected_pid)
                    and name and name not in self.SHELL_CLASSES)

    def remember(self, hwnd):
        if self.valid(hwnd):
            self.last_external_hwnd=int(hwnd);self._target_pid=self.api.process_id(hwnd)
            return True
        return False

    def capture_foreground(self):return self.remember(self.api.foreground())

    def send(self,path,clipboard,storage,completed,recent_limit=30):
        # Freeze the intended external window before file conversion can yield.
        observed=None
        try:observed=self.api.foreground();self.remember(observed)
        except (OSError,RuntimeError):pass
        request=_SendRequest(uuid.uuid4().hex,path,clipboard,storage,completed,recent_limit,
            self.last_external_hwnd,self._target_pid,time.perf_counter())
        request.observed_hwnd=observed
        from services.backup_activity import activity_for
        library_root=getattr(storage,'library_root',None)
        if isinstance(library_root,(str,os.PathLike)) and library_root:
            request.backup_pressure=activity_for(library_root)
            request.backup_pressure.operation(request.identity,'正在发送表情',True)
        self._queue.append(request)
        if self._active is None:self._start_next()
        return request.identity

    def _start_next(self):
        if self._closed or self._active is not None or not self._queue:return
        if self._drag_activity.operation is not None:return
        request=self._active=self._queue.popleft()
        try:
            if not request.storage.availability.exists(request.path,revalidate=True):
                self._finish(request,SendResult.COPY_FAILED,'resource_missing');return
            prepare=getattr(type(request.clipboard),'prepare_image_async',None)
            if callable(prepare):
                request.prepared_async=True
                getter=getattr(type(request.clipboard),'delivery_revision',None)
                if callable(getter):request.preparation_ticket=request.clipboard.delivery_revision()
                request.clipboard.prepare_image_async(request.path,
                    lambda data,error:self._prepared(request,data,error))
            else:
                if not request.clipboard.copy_image_to_clipboard(request.path):
                    self._finish(request,SendResult.COPY_FAILED,'clipboard_failed');return
                self._copied(request)
        except (OSError,RuntimeError,ValueError,TypeError) as error:
            self._finish(request,SendResult.COPY_FAILED,'clipboard_failed',str(error))

    def _prepared(self,request,data,error):
        from shiboken6 import isValid
        if not isValid(self) or self._closed or request.done:return
        try:
            if request.preparation_ticket is not None:
                matches=getattr(type(request.clipboard),'delivery_matches',None)
                same=request.clipboard.delivery_matches(request.preparation_ticket) if callable(matches) else request.clipboard.delivery_revision()==request.preparation_ticket
                if not same:
                    self._finish(request,SendResult.COPIED_ONLY,'clipboard_changed');return
            if error or not request.clipboard.publish_prepared(data):
                self._finish(request,SendResult.COPY_FAILED,'clipboard_failed',error);return
            self._copied(request)
        except (OSError,RuntimeError,ValueError,TypeError) as exception:
            self._finish(request,SendResult.COPY_FAILED,'clipboard_failed',str(exception))

    def _copied(self,request):
        getter=getattr(type(request.clipboard),'delivery_revision',None)
        if callable(getter):request.clipboard_ticket=request.clipboard.delivery_revision()
        try:request.storage.add_recent_image(request.path,request.recent_limit)
        except (OSError,RuntimeError):
            logging.getLogger('nekori.send').exception('request=%s recent update failed',request.identity)
        try:
            if not self.valid(request.hwnd,request.pid):
                if self.last_external_hwnd==request.hwnd:self.last_external_hwnd=self._target_pid=None
                self._finish(request,SendResult.COPIED_ONLY,'no_target');return
            if request.prepared_async and self.api.foreground() not in (request.observed_hwnd,request.hwnd):
                self._finish(request,SendResult.COPIED_ONLY,'foreground_changed');return
            self.api.acquire_foreground(request.hwnd)
        except (OSError,RuntimeError) as error:
            self._finish(request,SendResult.COPIED_ONLY,'activation_failed',str(error));return
        self._attempt(request)

    def _attempt(self,request,remaining=10):
        if request.done or self._closed:return
        try:
            if not self.valid(request.hwnd,request.pid):
                self._finish(request,SendResult.COPIED_ONLY,'target_changed');return
            if self.api.foreground()==request.hwnd:
                if not self.valid(request.hwnd,request.pid) or self.api.foreground()!=request.hwnd:
                    self._finish(request,SendResult.COPIED_ONLY,'foreground_changed');return
                ticket=request.clipboard_ticket
                if ticket is not None:
                    matches=getattr(type(request.clipboard),'delivery_matches',None)
                    same=request.clipboard.delivery_matches(ticket) if callable(matches) else request.clipboard.delivery_revision()==ticket
                    if not same:
                        self._finish(request,SendResult.COPIED_ONLY,'clipboard_changed');return
                if self.injector.paste():
                    from services.send_sound import completed_sound
                    config=getattr(request.storage,'config',None)
                    if config is not None:completed_sound(config,'send')
                    self._finish(request,SendResult.SENT,'input_submitted')
                else:
                    self._finish(request,SendResult.COPIED_ONLY,'input_failed',str(getattr(self.injector,'last_error','')))
            elif remaining:
                self.schedule(lambda:self._attempt(request,remaining-1))
            else:self._finish(request,SendResult.COPIED_ONLY,'activation_timeout')
        except (OSError,RuntimeError,ValueError) as error:
            self._finish(request,SendResult.COPIED_ONLY,'input_failed',str(error))

    def _finish(self,request,result,reason,details=''):
        if request.done:return
        request.done=True
        pressure=getattr(request,'backup_pressure',None)
        if pressure is not None:pressure.operation(request.identity,'正在发送表情',False)
        outcome=SendOutcome(request.identity,result,reason,request.hwnd,request.pid,
            (time.perf_counter()-request.started)*1000,details)
        self.last_outcome=outcome
        from services import crash_evidence as evidence
        evidence.breadcrumb('send_result',request=outcome.request_id,result=result.value,reason=reason,hwnd=outcome.hwnd,pid=outcome.pid,elapsed_ms=round(outcome.elapsed_ms,2))
        logging.getLogger('nekori.crash_evidence').info('send_result %s',outcome)
        log=logging.getLogger('nekori.send')
        log.log(logging.INFO if result==SendResult.SENT else logging.WARNING,
            'request=%s result=%s reason=%s hwnd=%s pid=%s elapsed_ms=%.2f details=%s',
            outcome.request_id,result.value,reason,outcome.hwnd,outcome.pid,outcome.elapsed_ms,details)
        try:request.completed(result)
        except Exception:log.exception('request=%s completion receiver failed',request.identity)
        finally:
            if self._active is request:self._active=None
            if self._queue and not self._closed:QTimer.singleShot(0,self,self._start_next)

    def cancel_requests(self,*_):
        self._closed=True
        for request in ([self._active] if self._active else [])+list(self._queue):
            request.done=True
            pressure=getattr(request,'backup_pressure',None)
            if pressure is not None:pressure.operation(request.identity,'正在发送表情',False)
        self._queue.clear();self._active=None
