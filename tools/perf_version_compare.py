"""Same real catalog, two source revisions, same Qt/runtime and private settings.

--ref v0.2.1 exports a disposable read-only source specimen (not a worktree).
This is a SOURCE comparison, not an assertion about the compiled installation.
No global hotkeys/single-instance IPC; send and drag are intercepted before use.
"""
import argparse,collections,cProfile,functools,io,json,os,pstats,sqlite3,subprocess,sys,tarfile,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--ref',default='HEAD');p.add_argument('--label',required=True);p.add_argument('--focus',choices=['all','menu','input','small'],default='all')
a=p.parse_args();root=Path(a.root).resolve();repo=Path(__file__).resolve().parents[1]
assert (root/'snapshot-summary.json').exists()
if a.ref!='HEAD':
    source=root/'release-source'
    if not source.exists():
        data=subprocess.check_output(['git','archive',a.ref,'fluent_ui','services','translations','config','assets','version.json','ico.ico'],cwd=repo)
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(source,filter='data')
else:source=repo
# Previous isolated process must have exited; reset only this private DB.
with sqlite3.connect(root/'catalog-comparison.sqlite3') as clean,sqlite3.connect(root/'library/index.sqlite3') as db:clean.backup(db)
os.environ['NEKORI_APP_DATA']=str(root/('app-compare-'+a.label));os.environ['NEKORI_LIBRARY']=str(root/'library')
sys.path.insert(0,str(source))
from PySide6.QtCore import Qt,QEvent,QTimer,QPoint,QPointF,QSize
from PySide6.QtGui import QDrag,QMovie,QWheelEvent,QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
phase='startup';events=[];start=time.perf_counter();last=[start]
def now():return round((time.perf_counter()-start)*1000,3)
def record(event_name,**kw):events.append(dict(t=now(),phase=phase,event=event_name,**kw))
record('clock',utc=time.time(),ref=a.ref)
class App(QApplication):
    def notify(self,obj,event):
        t=time.perf_counter()
        try:return super().notify(obj,event)
        finally:
            ms=(time.perf_counter()-t)*1000
            if ms>20:record('qt_event',receiver=type(obj).__name__,ms=round(ms,3))
app=App([]);app.setQuitOnLastWindowClosed(False)
def tick():
    t=time.perf_counter();record('heartbeat',ms=round((t-last[0])*1000,3));last[0]=t
timer=QTimer();timer.setInterval(10);timer.timeout.connect(tick);timer.start()
if a.ref=='HEAD':
    import importlib
    for name in ('materials','window_shell','main_window'):
        module=importlib.import_module('fluent_ui.'+name)
        exec(compile(subprocess.check_output(['git','show',f'HEAD:fluent_ui/{name}.py'],cwd=repo).decode('utf-8'),str(repo/'fluent_ui'/f'{name}.py'),'exec'),module.__dict__)
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from services.library_index import ROOT
from fluent_ui import visual
from fluent_ui.main_window import MainWindow
from fluent_ui.views.gallery_view import GalleryInterface
from fluent_ui.components.virtual_gallery import VirtualGallery
from fluent_ui.components.gallery_thumbnails import GalleryThumbnails
from fluent_ui.components.emoji_card import EmojiCard,_thumbnail_pool
from fluent_ui.components.hover_preview import HoverPreviewPopup
def wrap(cls,name):
    if not hasattr(cls,name):return
    old=getattr(cls,name)
    @functools.wraps(old)
    def measured(self,*args,**kw):
        t=now()
        try:return old(self,*args,**kw)
        finally:record('call',name=cls.__name__+'.'+name,ms=round(now()-t,3))
    setattr(cls,name,measured)
for cls,names in [(GalleryInterface,('set_node','refresh_content','get_preview_metadata','get_preview_info','_build_resource_menu','use_resource','_entry_clicked')),(StorageService,('get_categories_by_image','get_image_to_categories_map','get_all_categories')),(VirtualGallery,('bind','_drain','sync')),(GalleryThumbnails,('attach','completed')),(HoverPreviewPopup,('show_preview','hide_preview'))]:
    for name in names:wrap(cls,name)
config=ConfigService();config.config.update(ocr_auto=False,always_on_top=False,auto_check_updates=False,clipboard_import_enabled=False,preview_delay=100,thumbnail_size=60,gallery_click_action='send',hide_main_after_paste=False)
i18n_engine.init(config);visual.theme.configure(config)
storage=StorageService(library_path=root/'library',config=config)
MainWindow._init_global_hotkey=lambda self:setattr(self,'hotkey_listener',None)
window=MainWindow(storage,ClipboardService(config),config);window.resize(1150,800)
g=window.gallery_interface;sent=[]
g._send_to_clipboard=lambda path:sent.append(path)
QDrag.exec=lambda *args:Qt.IgnoreAction
window.setWindowTitle('Isolated source comparison '+a.label);window.show_gallery(refresh=False);window.showNormal()
plan=json.loads((root/'private-plan.json').read_text());metadata_profile=cProfile.Profile()
def wait(ms):QTest.qWait(ms)
def setphase(s):
    global phase
    phase=s;record('phase');last[0]=time.perf_counter()
def visible():return [c for c in g.renderer.active.values() if isinstance(c,EmojiCard) and c.visibleRegion().boundingRect().height()>15]
def click():
    cs=visible()
    if cs:
        card=cs[0];before=len(sent);t=now();loaded=card._is_loaded;QTest.mouseClick(card,Qt.LeftButton)
        record('click',loaded=loaded,ms=round(now()-t,3),sent=len(sent)==before+1,correct=sent[-1:]==[card.image_path])
def wheel():
    vp=g.scroll_area.viewport();pt=QPoint(80,100)
    for i in range(12):
        t=now();QApplication.postEvent(vp,QWheelEvent(QPointF(pt),QPointF(vp.mapToGlobal(pt)),QPoint(),QPoint(0,-120 if i<6 else 120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False));wait(130)
        record('wheel_round',ms=round(now()-t,3))
def execute():
    try:
        setphase('settle');wait(1200)
        if a.focus=='input':
            g.set_node(plan['animated']);wait(1000);_thumbnail_pool.waitForDone(3000);wait(100)
            setphase('visible_unloaded')
            card=visible()[0];original_dispatch=g.renderer.loader.dispatch
            g.renderer.loader.dispatch=lambda:None
            # Controlled visual-only A/B: retain the real visible binding and
            # valid file while withholding just this renderer's thumbnail.
            card.clear_resources();assert not card._is_loaded and card.isVisible()
            before=len(sent);t=now();QTest.mouseClick(card,Qt.LeftButton)
            record('click',loaded=card._is_loaded,ms=round(now()-t,3),sent=len(sent)==before+1,correct=sent[-1:]==[card.image_path])
            from PySide6.QtGui import QMouseEvent
            dragged=[]
            def drag(self,*args):dragged.append(True);return Qt.IgnoreAction
            QDrag.exec=drag;t=now();QTest.mousePress(card,Qt.LeftButton,pos=QPoint(8,8))
            point=QPoint(40,40);QApplication.sendEvent(card,QMouseEvent(QEvent.MouseMove,QPointF(point),QPointF(card.mapToGlobal(point)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
            record('drag',loaded=card._is_loaded,started=bool(dragged),ms=round(now()-t,3))
            card._is_dragging=True;QTest.mouseRelease(card,Qt.LeftButton);card._is_dragging=False
            g.renderer.loader.dispatch=original_dispatch
            return
        if a.focus=='small':
            setphase('small_first');g.set_node(plan['static']);wait(1000);click();wheel()
            setphase('small_revisit');g.set_node(ROOT);wait(400);g.set_node(plan['static']);wait(800);click();wheel()
            return
        if a.focus=='menu':
            g.set_node(plan['animated']);wait(800)
            setphase('menu_profile')
            card=visible()[0]
            for n in range(2):
                profile=cProfile.Profile();t=now();profile.enable()
                try:menu=g._build_resource_menu(card)
                finally:profile.disable()
                stats=pstats.Stats(profile)
                counts={name:sum(row[1] for key,row in stats.stats.items()
                                 if key[2]==name and ('library_index' in key[0] or name=='node_choice_rows'))
                        for name in ('nodes','content','node_choice_rows')}
                counts['sqlite_connections']=sum(row[1] for key,row in stats.stats.items() if '_sqlite3.connect' in key[2])
                counts['sql_execute']=sum(row[1] for key,row in stats.stats.items() if 'execute' in key[2] and 'sqlite3.Connection' in key[2])
                record('menu_build',ms=round(now()-t,3),repeat=n,queries=counts)
                out=io.StringIO();pstats.Stats(profile,stream=out).sort_stats('cumtime').print_stats(32)
                (root/(a.label+f'-menu-{n}-profile.txt')).write_text(out.getvalue(),encoding='utf-8')
                menu.deleteLater();wait(200)
            return
        for label in ('static','animated'):
            setphase(label+'_cold');g.set_node(plan[label]);click();wait(1300);click();wheel()
            setphase(label+'_warm');g.set_node(ROOT);wait(600);g.set_node(plan[label]);wait(1300);click();wheel()
        setphase('metadata')
        resources=plan['largest'][:4]
        for item in resources:
            path=str(root/'library'/item['relative']);t=now();metadata_profile.enable()
            try:g.get_preview_metadata(path);g.get_preview_info(path)
            finally:metadata_profile.disable()
            record('metadata_total',ms=round(now()-t,3));wait(150)
        setphase('menu')
        cs=visible()
        if cs:
            t=now();menu=g._build_resource_menu(cs[0]);record('menu_build',ms=round(now()-t,3));menu.deleteLater()
        setphase('movie_large')
        for item in resources:
            t=now();g.preview_controller.popup.show_preview(str(root/'library'/item['relative']),QPoint(50,50),320,info={})
            record('preview_start',ms=round(now()-t,3));wait(1500);g.preview_controller.popup.hide_preview();wait(100)
        setphase('foreground')
        for _ in range(3):
            window.hide();wait(150);window.show_gallery(refresh=False);window.showNormal();wait(300)
            window.showMinimized();wait(150);window.showNormal();wait(300)
    except Exception as exc:
        record('error',type=type(exc).__name__)
        import traceback;traceback.print_exc()
    finally:
        g.preview_controller.cancel()
        if hasattr(g,'imports'):g.imports.shutdown()
        if hasattr(g,'ocr'):g.ocr.close()
        window.hide();timer.stop();_thumbnail_pool.waitForDone(5000)
        (root/(a.label+'-compare.json')).write_text(json.dumps(events),encoding='utf-8')
        output=io.StringIO()
        if metadata_profile.getstats():
            pstats.Stats(metadata_profile,stream=output).sort_stats('cumtime').print_stats(22)
        # Function locations are implementation paths, never private image paths.
        (root/(a.label+'-metadata-profile.txt')).write_text(output.getvalue(),encoding='utf-8')
        print(json.dumps(dict(label=a.label,events=len(events))),flush=True);app.quit()
QTimer.singleShot(0,execute);app.exec()
