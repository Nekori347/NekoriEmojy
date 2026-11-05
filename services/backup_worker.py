"""Single low-priority, rate-limited backup/restore subprocess protocol."""
import json
import os
import sys
import threading
import time
from pathlib import Path
from services.library_backup import (create_backup,restore_backup,BackupError,BackupCancelled,LibraryChanged,
                                     atomic_json,utc_now)


class WorkerControl:
    def __init__(self,emit,rate=16*1024*1024):
        self.emit=emit;self.rate=max(64*1024,int(rate));self.condition=threading.Condition()
        self.cancelled=False;self.pause_reason=''
        self.capacity=max(256*1024,min(self.rate,self.rate//10));self.tokens=float(self.capacity);self.updated=time.monotonic()
        self._paused=False;self._last_progress=0;self.phase='inventory';self.done=0;self.total=0

    def command(self,value):
        with self.condition:
            if value.get('cancel'):self.cancelled=True
            if 'pause' in value:self.pause_reason=str(value['pause'] or '')
            self.condition.notify_all()

    def checkpoint(self,cost=0):
        with self.condition:
            while True:
                if self.cancelled:raise BackupCancelled('备份已取消')
                if self.pause_reason:
                    if not self._paused:self.emit(dict(type='paused',reason=self.pause_reason));self._paused=True
                    self.condition.wait();continue
                if self._paused:
                    self._paused=False;self.updated=time.monotonic();self.tokens=0;self.emit(dict(type='resumed',phase=self.phase))
                now=time.monotonic();self.tokens=min(self.capacity,self.tokens+(now-self.updated)*self.rate);self.updated=now
                if cost>self.tokens:self.condition.wait((cost-self.tokens)/self.rate);continue
                self.tokens-=cost
                return

    def sql_progress(self):
        self.checkpoint()
        return 0

    def progress(self,phase,done,total):
        changed=phase!=self.phase;self.phase,self.done,self.total=phase,done,total
        now=time.monotonic()
        if changed or now-self._last_progress>=.3 or (total and done==total):
            self._last_progress=now;self.emit(dict(type='progress',phase=phase,done=done,total=total))


def background_priority():
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes as W
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=W.HANDLE
        kernel.SetPriorityClass.argtypes=[W.HANDLE,W.DWORD]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(),0x00100000):
            raise ctypes.WinError(ctypes.get_last_error())
        return 'PROCESS_MODE_BACKGROUND_BEGIN'
    os.nice(10)
    return 'nice+10; I/O scheduling depends on platform'


class ExclusiveWorker:
    def __init__(self,control):self.control=control;self.handle=None
    def __enter__(self):
        if os.name!='nt':return self
        import ctypes
        from ctypes import wintypes as W
        self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        self.api.CreateMutexW.argtypes=[W.LPVOID,W.BOOL,W.LPCWSTR];self.api.CreateMutexW.restype=W.HANDLE
        self.api.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
        self.api.ReleaseMutex.argtypes=[W.HANDLE];self.api.CloseHandle.argtypes=[W.HANDLE]
        self.handle=self.api.CreateMutexW(None,False,'Local\\NekoriEmojy.LibraryBackup.v1')
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        announced=False
        while True:
            self.control.checkpoint()
            result=self.api.WaitForSingleObject(self.handle,100)
            if result in (0,0x80):return self
            if result!=0x102:raise ctypes.WinError(ctypes.get_last_error())
            if not announced:
                self.control.emit(dict(type='waiting',reason='正在等待其他备份任务结束'));announced=True
    def __exit__(self,*_):
        if self.handle:self.api.ReleaseMutex(self.handle);self.api.CloseHandle(self.handle)


def main(job_path=None):
    if job_path is None:job_path=sys.argv[sys.argv.index('--job')+1]
    job=json.loads(Path(job_path).read_text('utf-8'))
    def emit(value):
        print(json.dumps(value,ensure_ascii=False,separators=(',',':')),flush=True)
    control=WorkerControl(emit,job.get('read_limit',16*1024*1024))
    def commands():
        for line in sys.stdin:
            try:control.command(json.loads(line))
            except (ValueError,TypeError):continue
        control.command(dict(cancel=True))  # Parent exit never leaves an autonomous backup.
    threading.Thread(target=commands,daemon=True,name='BackupCommands').start()
    try:
        priority=background_priority();emit(dict(type='started',pid=os.getpid(),priority=priority))
        with ExclusiveWorker(control):
            control.checkpoint()
            emit(dict(type='resumed',phase='inventory'))
            result=(restore_backup if job.get('mode')=='restore' else create_backup)(job,control)
        emit(dict(type='done',result=result));return 0
    except BackupCancelled as exc:
        emit(dict(type='cancelled',reason=str(exc)));return 2
    except LibraryChanged as exc:
        emit(dict(type='changed',reason=str(exc)));return 3
    except Exception as exc:
        import traceback
        detail=traceback.format_exc()
        try:atomic_json(Path(job['work'])/'failure.json',dict(at=utc_now(),error=str(exc),details=detail))
        except OSError:pass  # A full/unavailable disk must not suppress the result on stdout.
        if isinstance(exc,BackupError):reason=str(exc)
        elif isinstance(exc,OSError) and (exc.errno==28 or getattr(exc,'winerror',None)==112):reason='磁盘剩余空间不足，请选择其他备份位置或释放空间'
        else:reason='操作未完成，请查看详情后重试。'
        emit(dict(type='failed',reason=reason,details=detail));return 1


if __name__=='__main__':raise SystemExit(main())
