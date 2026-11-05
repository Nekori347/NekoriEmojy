"""Windows read/handle-cache leases that yield to replacement and deletion.

FILE_SHARE_DELETE alone does not make legacy MoveFileEx replacement of an
open target succeed. A RH oplock lets Windows request closure *before* the
conflicting operation proceeds. Its waiter cancels/closes our handle even
while the archive thread is cooperatively paused; the snapshot is invalidated.
"""
import ctypes
import os
import threading
from ctypes import wintypes as W


class LeaseBroken(OSError):pass


class Overlapped(ctypes.Structure):
    _fields_=[('internal',ctypes.c_size_t),('high',ctypes.c_size_t),('offset',W.DWORD),
              ('offset_high',W.DWORD),('event',W.HANDLE)]


class Request(ctypes.Structure):
    _fields_=[('version',W.WORD),('length',W.WORD),('level',W.DWORD),('flags',W.DWORD)]


class Response(ctypes.Structure):
    _fields_=[('version',W.WORD),('length',W.WORD),('original',W.DWORD),('new',W.DWORD),
              ('flags',W.DWORD),('access',W.DWORD),('share',W.WORD)]


WaitCallback=ctypes.WINFUNCTYPE(None,W.LPVOID,ctypes.c_ubyte)


class LeasedReader:
    def __init__(self,path):
        import msvcrt
        self.name=str(path);self.offset=0;self.broken=False;self.closing=False;self.closed=False
        self.lock=threading.Lock();self.fd=None;self.wait_handle=None;self.op_event=None;self.read_event=None
        self.api=k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
        k.CreateEventW.argtypes=[W.LPVOID,W.BOOL,W.BOOL,W.LPCWSTR];k.CreateEventW.restype=W.HANDLE
        k.CloseHandle.argtypes=[W.HANDLE];k.ResetEvent.argtypes=[W.HANDLE]
        k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
        k.CancelIoEx.argtypes=[W.HANDLE,W.LPVOID]
        k.ReadFile.argtypes=[W.HANDLE,W.LPVOID,W.DWORD,W.LPVOID,W.LPVOID]
        k.GetOverlappedResult.argtypes=[W.HANDLE,W.LPVOID,ctypes.POINTER(W.DWORD),W.BOOL]
        k.DeviceIoControl.argtypes=[W.HANDLE,W.DWORD,W.LPVOID,W.DWORD,W.LPVOID,W.DWORD,W.LPVOID,W.LPVOID]
        k.RegisterWaitForSingleObject.argtypes=[ctypes.POINTER(W.HANDLE),W.HANDLE,WaitCallback,W.LPVOID,W.DWORD,W.DWORD]
        k.UnregisterWaitEx.argtypes=[W.HANDLE,W.HANDLE]
        self.handle=k.CreateFileW(self.name,0x80000000,7,None,3,0x48000000,None)
        if self.handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        self.fd=msvcrt.open_osfhandle(self.handle,os.O_RDONLY|os.O_BINARY)
        try:
            self.op_event=k.CreateEventW(None,True,False,None);self.read_event=k.CreateEventW(None,True,False,None)
            if not self.op_event or not self.read_event:raise ctypes.WinError(ctypes.get_last_error())
            self.op=Overlapped(event=self.op_event);self.request=Request(1,ctypes.sizeof(Request),3,1);self.response=Response()
            ok=k.DeviceIoControl(self.handle,0x00090240,ctypes.byref(self.request),ctypes.sizeof(self.request),
                                 ctypes.byref(self.response),ctypes.sizeof(self.response),None,ctypes.byref(self.op))
            error=ctypes.get_last_error()
            if ok or error!=997:raise LeaseBroken('文件无法获得可撤销读取租约（Windows %s）'%error)
            self.callback=WaitCallback(self._watch);self.wait_handle=W.HANDLE()
            if not k.RegisterWaitForSingleObject(ctypes.byref(self.wait_handle),self.op_event,self.callback,None,0xffffffff,8):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:self.close();raise

    def _watch(self,*_):
        with self.lock:
            if self.closing:return
            self.broken=True
            self._close_fd()

    def _close_fd(self):
        if self.fd is not None:
            self.api.CancelIoEx(self.handle,None)
            os.close(self.fd);self.fd=None

    def fileno(self):
        if self.broken or self.fd is None:raise LeaseBroken('文件已发生变化，读取租约已释放')
        return self.fd

    def read(self,size=-1):
        self.fileno()
        if size<0:size=max(0,os.fstat(self.fd).st_size-self.offset)
        if not size:return b''
        data=ctypes.create_string_buffer(size);over=Overlapped(offset=self.offset&0xffffffff,offset_high=self.offset>>32,event=self.read_event)
        self.api.ResetEvent(self.read_event);got=W.DWORD()
        ok=self.api.ReadFile(self.handle,data,size,ctypes.byref(got),ctypes.byref(over))
        if not ok:
            error=ctypes.get_last_error()
            if error==38:return b''
            if error!=997:
                if self.broken:raise LeaseBroken('文件已发生变化')
                raise ctypes.WinError(error)
            # The lease callback may close the HANDLE to unblock a writer.
            # Keep the OVERLAPPED and its Python buffer alive until completion,
            # even when cancellation made the original HANDLE invalid.
            self.api.WaitForSingleObject(self.read_event,0xffffffff)
            if self.broken:raise LeaseBroken('文件已发生变化')
            if not self.api.GetOverlappedResult(self.handle,ctypes.byref(over),ctypes.byref(got),True):
                error=ctypes.get_last_error()
                if error==38:return b''
                if self.broken:raise LeaseBroken('文件已发生变化')
                raise ctypes.WinError(error)
        if self.broken:raise LeaseBroken('文件已发生变化')
        self.offset+=got.value
        return data.raw[:got.value]

    def seek(self,offset,whence=0):
        self.fileno()
        self.offset=(0 if whence==0 else self.offset if whence==1 else os.fstat(self.fd).st_size)+offset
        if self.offset<0:raise ValueError('Negative seek')
        return self.offset

    def tell(self):return self.offset
    def seekable(self):return True
    def readable(self):return True
    def writable(self):return False

    def close(self):
        if self.closed:return
        with self.lock:
            self.closing=True
        # Unregister before cancelling an ordinary close, avoiding a context
        # switch/thread per file. Wait for any already-running break callback.
        if self.wait_handle:self.api.UnregisterWaitEx(self.wait_handle,ctypes.c_void_p(-1))
        with self.lock:self._close_fd()
        if self.op_event:self.api.CloseHandle(self.op_event)
        if self.read_event:self.api.CloseHandle(self.read_event)
        self.closed=True

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
