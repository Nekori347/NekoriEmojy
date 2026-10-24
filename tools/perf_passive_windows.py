"""Read-only process/GUI-thread counters and WM_NULL; never activates windows.

Example: python tools/perf_passive_windows.py --pid 123 --pid 456 --output X.json
WM_NULL is message-loop response, not scroll/paint/DWM latency. Fault counts
include soft faults. No remote code, user input, memory reads or stack injection.
"""
import argparse,ctypes,json,time
from ctypes import wintypes as W
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--pid',type=int,action='append',required=True);p.add_argument('--output',required=True);a=p.parse_args()
k=ctypes.WinDLL('kernel32',use_last_error=True);u=ctypes.WinDLL('user32',use_last_error=True);ps=ctypes.WinDLL('psapi',use_last_error=True)
k.OpenProcess.restype=W.HANDLE;k.OpenThread.restype=W.HANDLE
k.GetProcessTimes.argtypes=[W.HANDLE]+[ctypes.c_void_p]*4
k.GetThreadTimes.argtypes=[W.HANDLE]+[ctypes.c_void_p]*4
k.CloseHandle.argtypes=[W.HANDLE]
ps.GetProcessMemoryInfo.argtypes=[W.HANDLE,ctypes.c_void_p,W.DWORD]
u.SendMessageTimeoutW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,ctypes.c_void_p]
class Memory(ctypes.Structure):
    _fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak_rss','rss','qpp','qp','qnp','qn','commit','peak_commit','private')]
def cpu(handle,thread=False):
    values=[ctypes.c_ulonglong() for _ in range(4)]
    fn=k.GetThreadTimes if thread else k.GetProcessTimes
    if not fn(handle,*map(ctypes.byref,values)):return None
    return (values[2].value+values[3].value)/1e7
windows={}
@ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
def visit(hwnd,_):
    pid=W.DWORD();tid=u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    if pid.value in a.pid:
        rect=W.RECT();u.GetWindowRect(hwnd,ctypes.byref(rect))
        area=(rect.right-rect.left)*(rect.bottom-rect.top)
        if area>40000 and (pid.value not in windows or area>windows[pid.value][2]):windows[pid.value]=(int(hwnd),tid,area)
    return True
u.EnumWindows(visit,0)
handles={pid:k.OpenProcess(0x410,False,pid) for pid in a.pid}
threads={pid:k.OpenThread(0x800,False,entry[1]) for pid,entry in windows.items()}
rows=[]
for _ in range(40):
    for pid,handle in handles.items():
        if not handle:continue
        m=Memory();m.cb=ctypes.sizeof(m)
        if not ps.GetProcessMemoryInfo(handle,ctypes.byref(m),m.cb):continue
        record=dict(utc=time.time(),pid=pid,rss=m.rss,private=m.private,faults=m.faults,cpu=cpu(handle))
        if pid in windows:
            hwnd,tid,area=windows[pid];out=ctypes.c_size_t();start=time.perf_counter()
            ok=u.SendMessageTimeoutW(hwnd,0,0,0,2,50,ctypes.byref(out))
            record.update(gui_cpu=cpu(threads[pid],True),wm_null_ms=round((time.perf_counter()-start)*1000,3),ok=bool(ok),visible=bool(u.IsWindowVisible(hwnd)),minimized=bool(u.IsIconic(hwnd)))
        rows.append(record)
    time.sleep(.25)
for handle in list(handles.values())+list(threads.values()):
    if handle:k.CloseHandle(handle)
Path(a.output).write_text(json.dumps(rows),encoding='utf-8');print(json.dumps(dict(records=len(rows),processes=len(handles),gui_threads=len(threads))))
