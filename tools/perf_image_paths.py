"""Bounded real GIF decode/playback evidence; private snapshot only, no hooks.

Samples are selected from private-plan.json created during this investigation;
no resource filenames/content enter the output. No CacheAll or business changes.
"""
import argparse,ctypes,json,os,sys,time
from ctypes import wintypes as W
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args()
root=Path(a.root).resolve();assert (root/'snapshot-summary.json').exists()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['NEKORI_APP_DATA']=str(root/'app-image');os.environ['NEKORI_LIBRARY']=str(root/'library')
from PySide6.QtCore import QSize,Qt,QEvent,QTimer
from PySide6.QtGui import QImageReader,QImageIOHandler,QMovie,QPixmap
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtTest import QTest
from services.image_frames import frame_at
rows=[];phase='read';clock=time.perf_counter();last=[clock];current=[None]
def record(event,**kw):rows.append(dict(t=round((time.perf_counter()-clock)*1000,3),phase=phase,event=event,**kw))
class App(QApplication):
    def notify(self,obj,event):
        t=time.perf_counter()
        try:return super().notify(obj,event)
        finally:
            ms=(time.perf_counter()-t)*1000
            if ms>=4:record('qt_event',receiver=type(obj).__name__,kind=int(event.type()),ms=round(ms,3))
app=App([])
class M(ctypes.Structure):
    _fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','rss','qpp','qp','qnp','qn','private','peak_private')]
kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=W.HANDLE;handle=kernel.GetCurrentProcess()
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[W.HANDLE,ctypes.c_void_p,W.DWORD]
def memory():
    m=M();m.cb=ctypes.sizeof(m)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(handle,ctypes.byref(m),m.cb):raise ctypes.WinError()
    return dict(rss=m.rss,private=m.private,peak_rss=m.peak,faults=m.faults,cpu=time.process_time())
def tick():
    t=time.perf_counter();record('heartbeat',ms=round((t-last[0])*1000,3));last[0]=t
timer=QTimer();timer.setInterval(10);timer.timeout.connect(tick);timer.start()
metrics=QTimer();metrics.setInterval(100);metrics.timeout.connect(lambda:record('memory',**memory()));metrics.start()
samples=json.loads((root/'private-plan.json').read_text())['largest'][:6]
label=QLabel();label.resize(320,320);label.show()
for n,sample in enumerate(samples):
    path=str(root/'library'/sample['relative'])
    record('sample',index=n,bytes=sample['bytes'],width=sample['w'],height=sample['h'],frames=sample['frames'])
    for size in (128,320,0):
        reader=QImageReader(path);native=reader.supportsOption(QImageIOHandler.ScaledSize)
        if size:
            target=reader.size();target.scale(size,size,Qt.KeepAspectRatio);reader.setScaledSize(target)
        t=time.perf_counter();image=reader.read();ms=(time.perf_counter()-t)*1000
        t=time.perf_counter();pix=QPixmap.fromImage(image);convert=(time.perf_counter()-t)*1000
        record('first_frame',index=n,size=size,native_scaled=native,ms=round(ms,3),pixmap_ms=round(convert,3),**memory())
    phase='pillow'
    for frame in (0,sample['frames']//2):
        t=time.perf_counter();image=frame_at(path,frame)
        record('pillow_frame',index=n,frame=frame,ms=round((time.perf_counter()-t)*1000,3),**memory())
    # Main-thread frame extraction here is an isolated decoder benchmark,
    # NOT a claim that GalleryThumbnails calls Pillow on the GUI thread.
    phase='movie';movie=QMovie(path);movie.setCacheMode(QMovie.CacheNone);movie.setScaledSize(QSize(304,304))
    frames=[0];frame_last=[None]
    def changed(index):
        t=time.perf_counter();frames[0]+=1
        if frame_last[0] is not None:record('frame',gap_ms=round((t-frame_last[0])*1000,3),index=index)
        frame_last[0]=t
    movie.frameChanged.connect(changed);label.setMovie(movie)
    t=time.perf_counter();movie.start();record('movie_start',index=n,ms=round((time.perf_counter()-t)*1000,3))
    last[0]=time.perf_counter();QTest.qWait(2500)
    t=time.perf_counter();movie.stop();label.clear();movie.setDevice(None);movie.deleteLater()
    record('movie_stop',index=n,frames_displayed=frames[0],ms=round((time.perf_counter()-t)*1000,3),**memory())
    phase='read';QTest.qWait(50)
timer.stop();metrics.stop();label.hide()
(root/'image-paths.json').write_text(json.dumps(rows),encoding='utf-8')
print(json.dumps(dict(samples=len(samples),events=len(rows),peak_rss=max(x.get('peak_rss',0) for x in rows))))
