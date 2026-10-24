"""Temporary isolated real-library investigation, no production instrumentation.

Run with the project's Python and --root pointing at a snapshot directory made
by perf_library_snapshot.py. Never uses the active user's config or single-instance
endpoint. Input/send and QDrag.exec are intercepted; no external delivery occurs.
Private result files contain resource aliases, not resource names or contents.
"""
import argparse, collections, functools, importlib, json, os, subprocess, sys
import threading, time
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--root',required=True)
parser.add_argument('--mode',choices=['measure','native','native-long','native-final','import','import-nosort'],default='measure')
args=parser.parse_args()
ROOT=Path(args.root).resolve();LIB=ROOT/'library';SOURCE=Path(__file__).resolve().parents[1]
if not (ROOT/'snapshot-summary.json').exists() or not LIB.is_dir():
    raise RuntimeError('A verified isolated snapshot is required')
os.environ['NEKORI_APP_DATA']=str(ROOT/'app')
os.environ['NEKORI_LIBRARY']=str(LIB)
sys.path.insert(0,str(SOURCE))
from PySide6.QtCore import Qt,QEvent,QTimer,QEventLoop,QPoint,QPointF,QSize,QAbstractAnimation
from PySide6.QtGui import QMovie,QImageReader,QPixmapCache,QMouseEvent,QWheelEvent,QDrag,QCursor
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest
import ctypes
from ctypes import wintypes

class ProcessMetrics:
    class Memory(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    class Io(ctypes.Structure):
        _fields_=[(n,ctypes.c_ulonglong) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
    def __init__(self):
        ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
        self.handle=ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        ctypes.windll.kernel32.GetProcessIoCounters.argtypes=[wintypes.HANDLE,ctypes.c_void_p]
    def read(self):
        mem=self.Memory();mem.cb=ctypes.sizeof(mem);io=self.Io()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(self.handle,ctypes.byref(mem),mem.cb):
            raise ctypes.WinError()
        if not ctypes.windll.kernel32.GetProcessIoCounters(self.handle,ctypes.byref(io)):
            raise ctypes.WinError()
        return dict(rss=mem.WorkingSetSize,read=io.ReadTransferCount,write=io.WriteTransferCount,cpu=time.process_time())

events=collections.deque(maxlen=180000);phase='startup';began=time.perf_counter()
lock=threading.Lock();main_id=threading.get_ident();last_tick=[began];finished=threading.Event()
def now():return (time.perf_counter()-began)*1000
def emit(event_name,**values):
    with lock:events.append(dict(t=round(now(),3),phase=phase,event=event_name,**values))
def alias(value):
    if not value:return None
    return identities.get(os.path.normcase(str(value)))
identities={};seq=[0]
def resource_alias(value):
    key=os.path.normcase(str(value))
    if key not in identities:seq[0]+=1;identities[key]=seq[0]
    return identities[key]

class App(QApplication):
    def notify(self,obj,event):
        kind=event.type();start=time.perf_counter()
        inp=kind in (QEvent.MouseButtonPress,QEvent.MouseButtonRelease,QEvent.Wheel,QEvent.ContextMenu)
        if inp:emit('qt_input',kind=int(kind),receiver=type(obj).__name__)
        try:return super().notify(obj,event)
        finally:
            ms=(time.perf_counter()-start)*1000
            if ms>=20 or isinstance(obj,QMovie):
                emit('qt_event',kind=int(kind),receiver=type(obj).__name__,ms=round(ms,3))
app=App([]);app.setQuitOnLastWindowClosed(False)

def sample():
    process=ProcessMetrics();last_resource=0
    while not finished.wait(.025):
        if time.perf_counter()-last_tick[0]>.08:
            frame=sys._current_frames().get(main_id);stack=[]
            while frame and len(stack)<12:
                stack.append(f'{Path(frame.f_code.co_filename).name}:{frame.f_lineno}:{frame.f_code.co_name}')
                frame=frame.f_back
            emit('blocked_stack',stack=stack)
        if time.perf_counter()-last_resource>.25:
            last_resource=time.perf_counter();emit('process',**process.read())
threading.Thread(target=sample,daemon=True).start()
def heartbeat():
    t=time.perf_counter();emit('heartbeat',ms=round((t-last_tick[0])*1000,3));last_tick[0]=t
timer=QTimer();timer.setInterval(10);timer.timeout.connect(heartbeat);timer.start()

def wrap(cls,name):
    if not hasattr(cls,name):return
    original=getattr(cls,name)
    @functools.wraps(original)
    def measured(obj,*a,**kw):
        start=now();label=cls.__name__+'.'+name;extra={}
        if name in ('bind','attach'):
            card=a[0];extra['resource']=resource_alias(a[1].get('path','') if name=='bind' else getattr(card,'image_path',''))
        if name in ('file','show_preview') and a:extra['resource']=resource_alias(a[0])
        if name=='_drain':extra.update(pending=len(obj._pending),busy=bool(obj.gallery.sidebar.tree.itemDelegate()._selection_timer.isActive() or obj.gallery.sidebar.tree.itemDelegate()._selection_motion.state()==QAbstractAnimation.Running))
        if name in ('file','show_preview','_queued_files_finished','set_node'):emit('begin',name=label,**extra)
        try:return original(obj,*a,**kw)
        finally:emit('call',name=label,start=round(start,3),ms=round(now()-start,3),thread='gui' if threading.get_ident()==main_id else 'worker',**extra)
    setattr(cls,name,measured)

# Same protected-host policy as the fixed Demo: use committed host files only.
for name in ('materials','window_shell','main_window'):
    module=importlib.import_module('fluent_ui.'+name)
    code=subprocess.check_output(['git','show',f'HEAD:fluent_ui/{name}.py'],cwd=SOURCE).decode('utf-8')
    exec(compile(code,str(SOURCE/'fluent_ui'/f'{name}.py'),'exec'),module.__dict__)
from services.config import ConfigService
from services.storage import StorageService
from services.library_index import LibraryIndex,ROOT as LIBROOT
from services.resource_import import ResourceImporter,ImportTarget
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from fluent_ui import visual
from fluent_ui.views.gallery_view import GalleryInterface,ImportThread
from fluent_ui.components.virtual_gallery import VirtualGallery
from fluent_ui.components.gallery_model import GalleryEntryModel
from fluent_ui.components.gallery_thumbnails import GalleryThumbnails
from fluent_ui.components.emoji_card import EmojiCard,_ThumbnailLoadTask,_thumbnail_pool
from fluent_ui.components.hover_preview import HoverPreviewPopup
from fluent_ui.components.hover_preview_controller import HoverPreviewController
from fluent_ui.components.import_queue import ImportQueue
from fluent_ui.main_window import MainWindow

for cls,names in [
 (GalleryInterface,('set_node','refresh_content','refresh_content_incremental','_queued_files_finished','get_preview_metadata','get_preview_info','_on_card_clicked','_on_scroll','_sync_background_tasks','sync_content_after_reorder')),
 (VirtualGallery,('acquire','bind','sync','_drain')),
 (GalleryThumbnails,('request','attach','completed','dispatch')),
 (GalleryEntryModel,('sync','patch')),
 (HoverPreviewPopup,('show_preview','hide_preview')),
 (HoverPreviewController,('_on_delay_timeout','_resume_under_cursor','cancel')),
 (EmojiCard,('mousePressEvent','mouseReleaseEvent','mouseMoveEvent')),
 (ResourceImporter,('file',)),(StorageService,('_save_file_source','_standardize_and_save','_get_sync_key_index','get_categories_by_image','reorder_resources','entries_of')),
 (LibraryIndex,('register','resource_records','assign_memberships','reorder_resources')),
 (ImportQueue,('_progress','_finished'))]:
    for method in names:wrap(cls,method)
# patch is a staticmethod, preserve descriptor (otherwise wrapper's self is wrong).
GalleryEntryModel.patch=staticmethod(GalleryEntryModel.patch)

original_init=_ThumbnailLoadTask.__init__;original_run=_ThumbnailLoadTask.run
def init_decode(self,*a,**k):
    original_init(self,*a,**k);self._probe_created=now();self._probe_disk_hit=bool(self.cache_file and Path(self.cache_file).exists())
def run_decode(self):
    start=now()
    try:return original_run(self)
    finally:emit('decode',resource=resource_alias(self.image_path),wait_ms=round(start-self._probe_created,3),ms=round(now()-start,3),cached=self._probe_disk_hit)
_ThumbnailLoadTask.__init__=init_decode;_ThumbnailLoadTask.run=run_decode
class Movie(QMovie):
    def start(self):
        start=now();self.frameChanged.connect(lambda f:emit('movie_frame',frame=f))
        try:return super().start()
        finally:emit('movie_start',ms=round(now()-start,3))
import fluent_ui.components.hover_preview as preview_module
preview_module.QMovie=Movie
# Reader wrapper records GUI vs worker decode separately; real Qt decoder retained.
class Reader:
    def __init__(self,*a,**k):self.reader=QImageReader(*a,**k)
    def __getattr__(self,k):return getattr(self.reader,k)
    def read(self,*a):
        start=now()
        try:return self.reader.read(*a)
        finally:emit('image_read',ms=round(now()-start,3),thread='gui' if threading.get_ident()==main_id else 'worker')
preview_module.QImageReader=Reader
import fluent_ui.components.emoji_card as card_module
card_module.QImageReader=Reader

config=ConfigService();config.config.update(library_path=str(LIB),ocr_auto=False,always_on_top=False,
    auto_check_updates=False,clipboard_import_enabled=False,preview_delay=100,thumbnail_size=60,gallery_click_action='send',hide_main_after_paste=False)
i18n_engine.init(config);visual.theme.configure(config)
storage=StorageService(library_path=LIB,config=config)
assert Path(storage.library_root).resolve()==LIB
MainWindow._init_global_hotkey=lambda self:setattr(self,'hotkey_listener',None)
window=MainWindow(storage,ClipboardService(config),config);g=window.gallery_interface
window.setWindowTitle('Nekori isolated performance investigation');window.resize(1150,800)
sent=[]
def intercepted(path):sent.append(resource_alias(path));emit('send_intercept',resource=resource_alias(path))
g._send_to_clipboard=intercepted
original_drag=QDrag.exec
def intercepted_drag(self,*a,**kw):emit('drag_intercept');return Qt.IgnoreAction
QDrag.exec=intercepted_drag
window.show_gallery(refresh=False);window.showNormal()

plan=json.loads((ROOT/'private-plan.json').read_text(encoding='utf-8'))
stats={};commit_times={};before_register=LibraryIndex.register
def registered(obj,*a,**kw):
    result=before_register(obj,*a,**kw);commit_times[result]=now();emit('commit',resource=resource_alias(a[0]),identity=result);return result
LibraryIndex.register=registered
g.imports.changed.connect(lambda rid:emit('queue_changed',state=g.imports.requests[rid].state,done=g.imports.requests[rid].done) if rid in g.imports.requests else None)
g.scroll_area.verticalScrollBar().valueChanged.connect(lambda value:emit('view_scroll',value=value))

# One bounded GUI callback profile; no production source edit or global profiler.
import cProfile,io,pstats
old_finish=GalleryInterface._queued_files_finished
def finish_profile(self,request):
    if args.mode=='import-nosort':return old_finish(self,request)
    profile=cProfile.Profile();profile.enable()
    try:return old_finish(self,request)
    finally:
        profile.disable();out=io.StringIO();pstats.Stats(profile,stream=out).sort_stats('cumtime').print_stats(40)
        (ROOT/'import-finish-profile.txt').write_text(out.getvalue(),encoding='utf-8')
# Existing bound signal must be reconnected for the private profiling wrapper.
g.imports.files_finished.disconnect(g._queued_files_finished)
GalleryInterface._queued_files_finished=finish_profile
g.imports.files_finished.connect(g._queued_files_finished)
old_paint=EmojiCard.paintEvent
painted=set()
def paint(self,event):
    result=old_paint(self,event)
    key=(self.image_path,self._is_loaded)
    if key not in painted and phase.startswith('import'):
        painted.add(key);emit('card_paint',resource=resource_alias(self.image_path),loaded=self._is_loaded)
    return result
EmojiCard.paintEvent=paint

# A background sender measures event-loop admission independent of the GUI's
# own timers. These are synthetic probe events, not OS input-to-photon timings.
from PySide6.QtCore import QObject,QCoreApplication
PROBE=QEvent.Type(QEvent.registerEventType())
class Admission(QObject):
    def event(self,event):
        if event.type()==PROBE:emit('admission',ms=round(now()-event.sent,3));return True
        return super().event(event)
admission=Admission()
def send_probes():
    while not finished.wait(.1):
        event=QEvent(PROBE);event.sent=now();QCoreApplication.postEvent(admission,event)
threading.Thread(target=send_probes,daemon=True).start()

def wait(ms):QTest.qWait(ms)
def scenario(name):
    global phase
    phase=name;emit('phase');last_tick[0]=time.perf_counter()
def navigate(node):g.set_node(node);wait(1600)
def cards():return [c for c in g.renderer.active.values() if isinstance(c,EmojiCard) and c.isVisible() and c.visibleRegion().boundingRect().height()>15]
def input_test():
    cs=cards()
    if not cs:emit('no_card');return
    card=cs[0];emit('input_send',loaded=card._is_loaded,resource=resource_alias(card.image_path));QTest.mouseClick(card,Qt.LeftButton)
    QTest.mousePress(card,Qt.LeftButton,pos=QPoint(8,8))
    point=QPoint(40,40);event=QMouseEvent(QEvent.MouseMove,QPointF(point),QPointF(card.mapToGlobal(point)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(card,event);card._drag_start_pos=None;card._is_dragging=True
    QTest.mouseRelease(card,Qt.LeftButton);card._is_dragging=False
def wheels(count=12,interval=130):
    viewport=g.scroll_area.viewport();point=QPoint(80,100)
    for i in range(count):
        dy=-120 if i<count//2 else 120
        event=QWheelEvent(QPointF(point),QPointF(viewport.mapToGlobal(point)),QPoint(),QPoint(0,dy),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        emit('wheel_post');QApplication.postEvent(viewport,event);wait(interval)
def flips():
    for _ in range(3):
        window.hide();wait(200);window.show_gallery(refresh=False);window.showNormal();wait(300)
        window.showMinimized();wait(200);window.showNormal();wait(300)

def execute():
    try:
        scenario('settle');wait(1300)
        if args.mode in ('native','native-long','native-final'):native()
        else:
            if args.mode in ('import','import-nosort'):
                focused_import();return
            for label in ('static','animated'):
                scenario(label+'_cold');g.set_node(plan[label]);input_test();wait(1400);input_test();wheels()
                scenario(label+'_warm');navigate(LIBROOT);navigate(plan[label]);input_test();wheels()
            scenario('preview_large')
            for sample in plan['largest'][:6]:
                p=str(LIB/sample['relative']);g.preview_controller.cancel()
                g.preview_controller.popup.show_preview(p,QPoint(50,50),320,info={})
                wait(1800);g.preview_controller.popup.hide_preview();wait(150)
            scenario('foreground');navigate(plan['animated']);flips()
            focused_import()
    except Exception as exc:
        emit('harness_error',type=type(exc).__name__)
        import traceback;traceback.print_exc()
    finally:
        g.preview_controller.cancel();g.imports.shutdown();g.ocr.close();window.hide()
        finished.set();timer.stop()
        output=ROOT/(args.mode+'-events.json')
        output.write_text(json.dumps(list(events)),encoding='utf-8')
        print(json.dumps(dict(events=len(events),output=output.name)),flush=True)
        app.quit()

def native():
    # No native input unless explicitly selected by developer during an agreed window.
    import ctypes
    from ctypes import wintypes
    u=ctypes.windll.user32;hwnd=int(window.winId());u.SetForegroundWindow(hwnd)
    window.raise_();window.activateWindow();wait(400)
    tests=[('animated_card_long_corrected','card',1000,350)] if args.mode=='native-long' else [('animated_card_slow','card',100,350),('animated_blank_slow','blank',100,350),('animated_card_long','card',1000,350),('animated_card_normal','card',100,130)]
    if args.mode=='native-final':
        tests=[('real_scroll_card_100','card',100,350),('real_scroll_blank_100','blank',100,350),('real_scroll_card_1000','card',1000,350)]
        navigate(plan['static'])
        assert g.scroll_area.verticalScrollBar().maximum()>500
    for label,location,delay,interval in tests:
        scenario(label);g.config.config['preview_delay']=delay;g.preview_controller.set_delay(delay)
        if args.mode=='native-final':g.scroll_area.verticalScrollBar().setValue(0);wait(200)
        else:navigate(plan['animated'])
        g.preview_controller.cancel();g.preview_controller._warm_until=0
        cs=cards();card=cs[min(3,len(cs)-1)]
        point=card.mapToGlobal(card.rect().center()) if location=='card' else g.scroll_area.verticalScrollBar().mapToGlobal(g.scroll_area.verticalScrollBar().rect().center())
        QCursor.setPos(point);wait(450)
        hit=QApplication.widgetAt(QCursor.pos())
        emit('native_target',foreground=int(u.GetForegroundWindow())==hwnd,card_hit=isinstance(hit,EmojiCard),expected=location,configured_delay=g.config.get('preview_delay'),effective_delay=g.preview_controller.delay)
        count=6 if args.mode=='native-final' else 16
        def drive():
            for i in range(count):
                emit('native_wheel_sent',delta=-120 if i<count//2 else 120)
                u.mouse_event(0x0800,0,0,ctypes.c_ulong(-120 if i<count//2 else 120),0);time.sleep(interval/1000)
        driver=threading.Thread(target=drive);driver.start()
        while driver.is_alive():
            wait(30)
            hit=QApplication.widgetAt(QCursor.pos())
            while hit is not None and not isinstance(hit,EmojiCard):hit=hit.parentWidget()
            emit('native_state',scroll=g.scroll_area.verticalScrollBar().value(),resource=resource_alias(hit.image_path) if hit else None,position=[QCursor.pos().x(),QCursor.pos().y()])
        wait(100)
        g.preview_controller.cancel()

def focused_import():
    scenario('import_setup')
    target=storage.create_node('PERF disposable import')
    storage.index.assign_memberships([m['id'] for m in list(plan['resources'].values())[:32]],target)
    navigate(target)
    g.preview_controller.cancel()
    g.imports._ask_batch=lambda request,candidates:['keep']*len(candidates)
    scenario('import_running')
    rid=g.imports.submit([str(LIB/m['relative']) for m in plan['largest'][:8]],ImportTarget(target,0),g)
    start=now();deadline=time.perf_counter()+120;iteration=0
    while time.perf_counter()<deadline:
        request=g.imports.requests[rid]
        if request.state in ('completed','failed','cancelled'):break
        input_test()
        if args.mode!='import-nosort' and iteration%4==0:
            from fluent_ui.components.drop_contract import DropTarget,INSERT_BEFORE,MOVE
            entries=[e for e in g._entries if e['kind']=='resource']
            t=now()
            if len(entries)>1:
                g._reorder_by_drop([entries[-1]['path']],DropTarget(INSERT_BEFORE,MOVE,entries[0]['id'],target,0))
            emit('reorder',ms=round(now()-t,3))
        wait(220);iteration+=1
    emit('import_end',state=request.state,saved=request.saved,kept=request.kept,failed=request.failed,elapsed=now()-start)
    scenario('import_after');wait(1800)
QTimer.singleShot(0,execute)
app.exec()
