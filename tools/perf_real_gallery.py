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
parser.add_argument('--mode',choices=['measure','native','native-long','native-final','native-regression','import','import-nosort','visual','windows','frame-cache'],default='measure')
parser.add_argument('--label',help='Private output prefix; preserves previous comparison evidence')
parser.add_argument('--no-motion',action='store_true',help='Isolated A/B only, skip UI animations')
parser.add_argument('--opaque',action='store_true')
parser.add_argument('--cache-kb',type=int,default=131072)
parser.add_argument('--native-window-input',action='store_true',help='Requires an agreed exclusive mouse window')
args=parser.parse_args()
ROOT=Path(args.root).resolve();LIB=ROOT/'library';SOURCE=Path(__file__).resolve().parents[1]
if not (ROOT/'snapshot-summary.json').exists() or not LIB.is_dir():
    raise RuntimeError('A verified isolated snapshot is required')
os.environ['NEKORI_APP_DATA']=str(ROOT/'app')
os.environ['NEKORI_LIBRARY']=str(LIB)
if args.opaque:os.environ['NEKORI_OPAQUE_MATERIAL']='1'
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

events=collections.deque(maxlen=180000);phase='startup';began=time.perf_counter();paint_counts=collections.Counter()
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
        if kind==QEvent.Paint:paint_counts[phase]+=1
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
 (GalleryInterface,('set_node','refresh_content','refresh_content_incremental','_queued_files_finished','_queued_resources_committed','get_preview_metadata','get_preview_info','_on_card_clicked','_on_scroll','_sync_background_tasks','sync_content_after_reorder')),
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
config.config.update(ui_animations_enabled=not args.no_motion,window_acrylic_enabled=not args.opaque)
i18n_engine.init(config);visual.theme.configure(config)
storage=StorageService(library_path=LIB,config=config)
assert Path(storage.library_root).resolve()==LIB
MainWindow._init_global_hotkey=lambda self:setattr(self,'hotkey_listener',None)
if args.mode=='windows':
    setter=ctypes.windll.user32.SetWindowCompositionAttribute
    setter.argtypes=[wintypes.HWND,ctypes.c_void_p];setter.restype=wintypes.BOOL
    class AttributeData(ctypes.Structure):
        _fields_=[('attribute',ctypes.c_int),('data',ctypes.c_void_p),('size',ctypes.c_size_t)]
    def composition(hwnd,data):
        value=ctypes.cast(data,ctypes.POINTER(AttributeData)).contents
        if value.attribute==19:emit('native_accent',hwnd=int(hwnd.value),state=ctypes.cast(value.data,ctypes.POINTER(ctypes.c_int)).contents.value)
        return setter(hwnd,ctypes.cast(data,ctypes.c_void_p))
    ctypes.windll.user32.SetWindowCompositionAttribute=composition
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

def wait(ms):
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
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
        if args.mode=='visual':visual_probe();return
        if args.mode=='windows':window_probe();return
        if args.mode=='frame-cache':frame_cache_probe();return
        if args.mode in ('native','native-long','native-final','native-regression'):native()
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
        output=ROOT/((args.label or args.mode)+'-events.json')
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
    if args.mode in ('native-final','native-regression'):
        tests=[('real_scroll_card_100','card',100,350),('real_scroll_blank_100','blank',100,350),('real_scroll_card_1000','card',1000,350)]
        if args.mode=='native-regression':
            g.config.config['thumbnail_size']=160;g._apply_thumbnail_size(160)
        navigate(plan['animated'] if args.mode=='native-regression' else plan['static'])
        assert g.scroll_area.verticalScrollBar().maximum()>500
    for label,location,delay,interval in tests:
        scenario(label);g.config.config['preview_delay']=delay;g.preview_controller.set_delay(delay)
        if args.mode in ('native-final','native-regression'):g.scroll_area.verticalScrollBar().setValue(0);wait(200)
        else:navigate(plan['animated'])
        g.preview_controller.cancel();g.preview_controller._warm_until=0
        cs=cards();card=cs[min(3,len(cs)-1)]
        point=card.mapToGlobal(card.rect().center()) if location=='card' else g.scroll_area.verticalScrollBar().mapToGlobal(g.scroll_area.verticalScrollBar().rect().center())
        QCursor.setPos(point);wait(450)
        hit=QApplication.widgetAt(QCursor.pos())
        emit('native_target',foreground=int(u.GetForegroundWindow())==hwnd,card_hit=isinstance(hit,EmojiCard),expected=location,configured_delay=g.config.get('preview_delay'),effective_delay=g.preview_controller.delay)
        count=6 if args.mode in ('native-final','native-regression') else 16
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
                moved=entries[-1]['id'];before=entries[0]['id']
                g._reorder_by_drop([entries[-1]['path']],DropTarget(INSERT_BEFORE,MOVE,before,target,0))
                order=[e['id'] for e in storage.index.content(target)]
                assert order.index(moved)+1==order.index(before)
            emit('reorder',ms=round(now()-t,3),order_valid=True)
        wait(220);iteration+=1
    emit('import_end',state=request.state,saved=request.saved,kept=request.kept,failed=request.failed,elapsed=now()-start)
    order=[e['id'] for e in storage.index.content(target)]
    assert len(order)==len(set(order))==40
    assert [e['id'] for e in g._entries]==order
    assert all(Path(path).is_file() for path in request.paths)
    with storage.index.connect() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('SELECT 1 FROM task_checkpoints WHERE task_id=?',(rid,)).fetchone()
    emit('import_consistency',unique_members=len(order),projection_matches=True,checkpoints_finished=True)
    scenario('import_after');wait(1800)

def visual_probe():
    from fluent_ui.components.emoji_card import ThumbnailCache
    cache=ThumbnailCache();cache._normal_limit_kb=args.cache_kb
    QPixmapCache.setCacheLimit(args.cache_kb)
    process=ProcessMetrics();previous=process.read()
    def state(label):
        nonlocal previous
        value=process.read();loader=g.renderer.loader
        emit('cache_state',label=label,limit=QPixmapCache.cacheLimit(),rss=value['rss'],
             cpu_delta=value['cpu']-previous['cpu'],decodes=loader.decodes,disk_hits=loader.disk_hits,
             memory_hits=loader.memory_hits,active=len(loader.running),queued=len(loader.wanted),paints=paint_counts[phase])
        previous=value
    emit('visual_config',no_motion=args.no_motion,opaque=args.opaque,cache_kb=args.cache_kb,
         material=window.property('nativeMaterial'),hwnd=int(window.winId()),utc=time.time())
    for repeat in range(2):
        scenario('navigation_'+str(repeat));start=now()
        g.set_node(plan['static'])
        top=g.scroll_area.verticalScrollBar().value()
        indices=list(g.renderer.index.between(top,top+g.scroll_area.viewport().height()))
        from fluent_ui.components.gallery_model import occurrence_id
        def bound():
            return all((c:=g.renderer.active.get(occurrence_id(g._entries[i]))) is not None
                       and c.isVisible() and c.content_entry is g._entries[i] for i in indices)
        while not bound() and now()-start<2500:wait(10)
        emit('visible_ready',ms=now()-start,cards=len(cards()),repeat=repeat,complete=bound())
        wait(350);state('static_'+str(repeat))
        g.set_node(plan['animated']);wait(500);state('animated_'+str(repeat))
    scenario('incremental_profile')
    profile=cProfile.Profile()
    try:
        for _ in range(3):
            profile.enable()
            g.refresh_content_incremental(paths=[str(LIB/m['relative']) for m in plan['largest'][:8]],parents={LIBROOT,plan['animated']})
            profile.disable();wait(70)
    finally:
        profile.disable();out=io.StringIO();pstats.Stats(profile,stream=out).sort_stats('cumtime').print_stats(45)
        (ROOT/((args.label or args.mode)+'-profile.txt')).write_text(out.getvalue(),encoding='utf-8')
    wait(400);state('incremental')
    scenario('flips');flips();state('flips')
    scenario('window_lifecycle')
    start_hwnd=int(window.winId());normal=window.geometry()
    window.showMaximized();wait(150);window.showNormal();wait(150)
    window.setGeometry(normal);window.resize(1120,780);wait(150)
    window.move(window.x()+20,window.y()+10);wait(150)
    window.move(normal.topLeft());window.resize(normal.size());wait(150)
    emit('window_check',same_hwnd=int(window.winId())==start_hwnd,material=window.property('nativeMaterial'),maximized=window.isMaximized())
    scenario('movie_content')
    item=plan['largest'][0];popup=g.preview_controller.popup
    popup.show_preview(str(LIB/item['relative']),QPoint(50,50),320,info={})
    frames=[]
    if popup.current_movie:popup.current_movie.frameChanged.connect(frames.append)
    wait(650);emit('movie_frames',changes=len(frames));popup.hide_preview();state('movie')
def frame_cache_probe():
    from fluent_ui.components.gallery_thumbnails import GalleryThumbnails
    item=plan['largest'][0];path=str(LIB/item['relative']);record=storage.index.resource(path)
    metadata=json.loads(record['metadata_json']);metadata['thumb_frame']=item['frames']//2
    entry=dict(kind='resource',id=record['id'],path=path,resource=dict(record,metadata_json=json.dumps(metadata)))
    card=EmojiCard(path,size=120,load_image=False,parent=g);card.content_entry=entry
    loader=GalleryThumbnails(config,g);loader.cache_dir=ROOT/'frame-cache';loader.cache_dir.mkdir(exist_ok=True)
    key,*_,disk=loader.key(entry,120);cold=not disk.exists();pixels=None
    if disk.exists():
        disk.rename(ROOT/('frame-cache-prior-'+str(time.time_ns())+'.png'));cold=True
    for label in ('source','disk','memory'):
        scenario('frame_cache_'+label)
        if label!='memory':QPixmapCache.remove(key)
        card._is_loaded=False;card._gallery_thumbnail_key=None
        start=now();loader.request([card])
        if not card._is_loaded:
            loop=QEventLoop();timeout=QTimer();timeout.setSingleShot(True);timeout.timeout.connect(loop.quit)
            tasks=[task for _,task in loader.running.values()]
            for task in tasks:task.signals.finished.connect(loop.quit)
            timeout.start(5000);loop.exec();timeout.stop()
        assert card._is_loaded
        image=card.pixmap().toImage()
        if pixels is not None:assert image==pixels
        pixels=image
        emit('frame_cache_result',label=label,ms=now()-start,cold_source=cold,
             frame=metadata['thumb_frame'],decodes=loader.decodes,disk_hits=loader.disk_hits,memory_hits=loader.memory_hits)
    card.deleteLater();loader.deleteLater()

def window_probe():
    from fluent_ui.window_shell import ToolWindow
    from fluent_ui.materials import shell_color
    from PySide6.QtWidgets import QLabel
    u=ctypes.windll.user32
    u.GetForegroundWindow.restype=wintypes.HWND
    u.WindowFromPoint.argtypes=[wintypes.POINT];u.WindowFromPoint.restype=wintypes.HWND
    u.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];u.GetAncestor.restype=wintypes.HWND
    tool=ToolWindow(window,QLabel('Isolated visual preference test'),'Visual preference test')
    settings=window.settings_window
    def input_action(action):
        driver=threading.Thread(target=action);driver.start()
        while driver.is_alive():wait(15)
    def click(point):
        assert int(u.GetAncestor(u.WindowFromPoint(wintypes.POINT(point.x(),point.y())),2))==hwnd==int(u.GetForegroundWindow())
        def perform():
            u.SetCursorPos(point.x(),point.y());u.mouse_event(2,0,0,0,0);time.sleep(.06)
            u.mouse_event(4,0,0,0,0);time.sleep(.18)
        input_action(perform)
    def drag(point,dx,dy):
        assert int(u.GetAncestor(u.WindowFromPoint(wintypes.POINT(point.x(),point.y())),2))==hwnd==int(u.GetForegroundWindow())
        def perform():
            u.SetCursorPos(point.x(),point.y());u.mouse_event(2,0,0,0,0);time.sleep(.07)
            u.SetCursorPos(point.x()+dx,point.y()+dy);time.sleep(.13)
            u.mouse_event(4,0,0,0,0);time.sleep(.18)
        input_action(perform)
    for title,w in [('main',window),('settings',settings),('tool',tool)]:
        scenario('window_'+title)
        if title=='main':w.showNormal()
        else:w.present()
        w.setGeometry(60,60,1100,740);w.raise_();w.activateWindow();wait(220)
        hwnd=int(w.winId());normal=w.geometry();h=wintypes.HWND(hwnd)
        u.SetForegroundWindow(h)
        if u.GetForegroundWindow()!=hwnd:
            foreground=u.GetWindowThreadProcessId(u.GetForegroundWindow(),None)
            current=ctypes.windll.kernel32.GetCurrentThreadId()
            attached=bool(u.AttachThreadInput(current,foreground,True))
            try:u.BringWindowToTop(h);u.SetForegroundWindow(h)
            finally:
                if attached:u.AttachThreadInput(current,foreground,False)
        emit('foreground_check',window=title,active=u.GetForegroundWindow()==hwnd)
        if args.native_window_input:
            u.SetForegroundWindow(h);wait(150)
            assert int(u.GetForegroundWindow())==hwnd
            point=w.mapToGlobal(QPoint(210,14));drag(point,70,35)
            moved=w.geometry();emit('native_drag_check',window=title,dx=moved.x()-normal.x(),dy=moved.y()-normal.y())
            corner=w.mapToGlobal(QPoint(w.width()-2,w.height()-2));before=w.size()
            drag(corner,30,20)
            emit('native_resize_check',window=title,dw=w.width()-before.width(),dh=w.height()-before.height())
            click(w.titleBar.maxBtn.mapToGlobal(w.titleBar.maxBtn.rect().center()))
        else:w.showMaximized();wait(180)
        maximum=w.geometry();native_max=bool(u.IsZoomed(h));qt_max=w.isMaximized()
        if args.native_window_input:click(w.titleBar.maxBtn.mapToGlobal(w.titleBar.maxBtn.rect().center()))
        else:w.showNormal();wait(180)
        restored=w.geometry()
        w.showMinimized();wait(100);w.showNormal();wait(140)
        w.hide();wait(80)
        if title=='main':w.show_gallery(refresh=False)
        else:w.present()
        wait(180)
        emit('host_check',window=title,material=w.property('nativeMaterial'),alpha=shell_color(w).alpha(),
             same_hwnd=int(w.winId())==hwnd,native_max=native_max,qt_max=qt_max,
             larger=maximum.width()>restored.width() and maximum.height()>restored.height(),
             restored=not w.isMaximized(),native_contour=w.property('nativeContour'),
             size=[w.width(),w.height()],layout=[w.body_layout.geometry().width(),w.body_layout.geometry().height()] if hasattr(w,'body_layout') else [])
        assert int(w.winId())==hwnd and native_max and qt_max and not w.isMaximized()
        if title!='main':w.hide()
    waits=[]
    for _ in range(6):
        t=now();ctypes.windll.dwmapi.DwmFlush();waits.append(round(now()-t,3))
    emit('dwm_flush_roundtrip',ms=waits)
    tool.hide();tool.deleteLater()

QTimer.singleShot(0,execute)
app.exec()
