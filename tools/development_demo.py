"""One persistent development Demo. Specialized probes live outside this directory."""
import ast,importlib,json,os,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'Source';HERE=ROOT/'DevData/Demo'
LAB_MODE='--lab-root' in sys.argv
if LAB_MODE:
    HERE=Path(sys.argv[sys.argv.index('--lab-root')+1]).resolve()
    if not HERE.is_relative_to(ROOT/'DevData/DragSendLab') or not (HERE/'library/index.sqlite3').is_file():
        raise RuntimeError('Lab Demo requires an existing isolated DragSendLab Library')
HERE.mkdir(parents=True,exist_ok=True)
if LAB_MODE:
    import tempfile
    temporary=HERE/'tmp';temporary.mkdir(exist_ok=True)
    os.environ['TEMP']=os.environ['TMP']=str(temporary)
    tempfile.tempdir=str(temporary)
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalServer,QLocalSocket
SERVER='NekoriEmojy_Development_Demo'
if LAB_MODE:SERVER+='_'+hashlib.sha256(str(HERE).casefold().encode()).hexdigest()[:16]
if '--stop' in sys.argv:
    app=QCoreApplication([]);client=QLocalSocket();client.connectToServer(SERVER)
    if client.waitForConnected(500):
        client.write(b'stop');client.waitForBytesWritten(500)
        if client.state()==QLocalSocket.UnconnectedState or client.waitForDisconnected(15000):
            print('旧开发 Demo 已正常退出。')
        else:
            print('旧开发 Demo 未在15秒内退出；保留进程，不启动第二个实例。');sys.exit(1)
    else:print('没有运行中的项目级开发 Demo。')
    sys.exit(0)
branch=subprocess.check_output(['git','branch','--show-current'],cwd=SOURCE).decode().strip()
if branch!='dev/post-0.2.1':raise RuntimeError('Development Demo requires dev/post-0.2.1')
DATA=HERE if LAB_MODE else HERE/'data'
os.environ['NEKORI_APP_DATA']=str(DATA/'app');os.environ['NEKORI_LIBRARY']=str(DATA/'library')
sys.path.insert(0,str(SOURCE))
sys.stdout=sys.stderr=(HERE/'demo.log').open('a',encoding='utf-8',buffering=1)
from PySide6.QtWidgets import QApplication,QSystemTrayIcon,QMenu
from fluent_ui.components.runtime_diagnostics import DiagnosticApplication as QApplication
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
from services.upgrade_shutdown import install_upgrade_shutdown
install_upgrade_shutdown(app)
from services.single_instance import SingleInstance
instance=SingleInstance(app)
if not instance.start():sys.exit(0)
from services.crash_evidence import install as install_crash_evidence
install_crash_evidence()
server=QLocalServer()
if not server.listen(SERVER):raise RuntimeError('A development Demo already exists; use Start-Demo.cmd to restart')
clients=[]
def connected():
    client=server.nextPendingConnection();clients.append(client)
    def command():
        raw=bytes(client.readAll())
        if raw==b'stop':app.quit()
    client.readyRead.connect(command)
    if client.bytesAvailable():command()
server.newConnection.connect(connected)
# Only these three protected W-01 files are read from current Git HEAD, never a
# frozen historical version. Other modules run directly from the current worktree.
def overlay_methods(base,current,class_name,names):
    old=next(n for n in ast.parse(base).body if isinstance(n,ast.ClassDef) and n.name==class_name)
    new=next(n for n in ast.parse(current).body if isinstance(n,ast.ClassDef) and n.name==class_name)
    lines=base.splitlines(keepends=True);source=current.splitlines(keepends=True)
    replacements=[];extra=[]
    for method in new.body:
        if not isinstance(method,ast.FunctionDef) or method.name not in names:continue
        previous=next((n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==method.name),None)
        body=source[method.lineno-1:method.end_lineno]
        if previous:replacements.append((previous.lineno-1,previous.end_lineno,body))
        else:extra+=['\n']+body
    replacements.append((old.end_lineno,old.end_lineno,extra))
    for start,end,body in sorted(replacements,reverse=True):lines[start:end]=body
    return ''.join(lines)

for name in ('materials','window_shell','main_window'):
    module=importlib.import_module('fluent_ui.'+name)
    code=subprocess.check_output(['git','show',f'HEAD:fluent_ui/{name}.py'],cwd=SOURCE).decode('utf-8')
    if name == 'materials':
        current=(SOURCE/'fluent_ui/materials.py').read_text('utf-8')
        old=next(n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef) and n.name=='_transparency_allowed')
        new=next(n for n in ast.parse(current).body if isinstance(n,ast.FunctionDef) and n.name=='_transparency_allowed')
        lines=code.splitlines(keepends=True);lines[old.lineno-1:old.end_lineno]=current.splitlines(keepends=True)[new.lineno-1:new.end_lineno]
        code=''.join(lines)
    if name == 'window_shell':
        # Keep W01 excluded while loading the current, verified host fixes.
        current=(SOURCE/'fluent_ui/window_shell.py').read_text('utf-8')
        def native_method(text):
            host=next(node for node in ast.parse(text).body if isinstance(node,ast.ClassDef) and node.name=='NekoriWindow')
            return next(node for node in host.body if isinstance(node,ast.FunctionDef) and node.name=='nativeEvent')
        old,new=native_method(code),native_method(current)
        lines=code.splitlines(keepends=True)
        lines[old.lineno-1:old.end_lineno]=current.splitlines(keepends=True)[new.lineno-1:new.end_lineno]
        code=''.join(lines)
        code=overlay_methods(code,current,'NekoriTitleBar',{'canDrag'})
    elif name=='main_window':
        current=(SOURCE/'fluent_ui/main_window.py').read_text('utf-8')
        code=overlay_methods(code,current,'MainWindow',{'search_clipboard_text'})
    exec(compile(code,str(SOURCE/'fluent_ui'/f'{name}.py'),'exec'),module.__dict__)
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from services.qq_extractor import QQExtractor
from services.resource_import import ImportTarget
from fluent_ui import visual
from fluent_ui.main_window import MainWindow
from PIL import Image,ImageDraw
config=ConfigService()
config.config.update(clipboard_import_enabled=False,auto_check_updates=False)
if LAB_MODE:config.config.update(clipboard_search_hotkey='',ocr_auto=False)
if not config.config_existed:
    config.config.update(language='zh',ocr_auto=False,always_on_top=True,thumbnail_size=80,gallery_click_action='select')
i18n_engine.init(config);visual.theme.configure(config)
from fluent_ui.components.tooltip import install_global_tooltips
install_global_tooltips(app,int(config.get('tooltip_delay',120)))
storage=StorageService(config=config)
seeded=DATA/'seeded.json'
def find(name):return next((n['id'] for n in storage.index.nodes() if n['name']==name),None)
samples=DATA/'samples';samples.mkdir(parents=True,exist_ok=True)
def picture(i,folder):
    path=samples/folder/f'{i:03d}.png';path.parent.mkdir(exist_ok=True)
    if not path.exists():
        im=Image.new('RGB',(500,350),(90+i%100,110+(i*3)%100,150+(i*5)%100))
        draw=ImageDraw.Draw(im);draw.text((30,30),f'NEKORI SAMPLE {i}',fill='white',font_size=35)
        draw.ellipse((150,100,320,280),outline='white',width=5);im.save(path)
    return str(path)
parent=find('WP-B · 混排与移动源')
if not LAB_MODE and not seeded.exists():
    parent=parent or storage.create_node('WP-B · 混排与移动源')
    for i in range(3):
        name=f'WP-B 子分类 {i+1}'
        if not find(name):storage.create_node(name,parent)
    for i in range(45):
        name=f'侧栏观察位置 {i+1:02d}'
        if not find(name):storage.create_node(name)
    if not any(e['kind']=='resource' for e in storage.entries_of(parent)):
        for i in range(120):storage.save_file(picture(i,'existing'),target=ImportTarget(parent))
    seeded.write_text(json.dumps(dict(initialized=True)),encoding='utf-8')
# QQ sample files remain reusable historical test assets, not another code tree.
qqroot=ROOT/'DevData/post-021-qq/qq-samples/Tencent Files'
QQExtractor.get_nickname_cache_path=staticmethod(lambda:str(DATA/'qq-nicknames.json'))
if not LAB_MODE and not config.get('qq_data_path') and qqroot.is_dir():config.set('qq_data_path',str(qqroot))
if not config.get('qq_save_path'):config.set('qq_save_path',str(DATA/'exports'))
(DATA/'exports').mkdir(exist_ok=True)
MainWindow._init_global_hotkey=lambda self:setattr(self,'hotkey_listener',None)
MainWindow.bind_global_hotkey=lambda self:None
window=MainWindow(storage,ClipboardService(config),config)
from fluent_ui.components.window_import import install_window_import
install_window_import(window,window.gallery_interface)
window.quick_panel.feedback_owner=window.gallery_interface.feedback_host
from fluent_ui.components.clipboard_search_command import ClipboardSearchCommand
window.clipboard_search_command=ClipboardSearchCommand(window,config)
from fluent_ui.components.runtime_diagnostics import install_runtime_diagnostics
install_runtime_diagnostics(app,window)
head=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=SOURCE).decode().strip()
window.setWindowTitle(f'NekoriEmojy · 开发 Demo · {head}'+(' · 完整隔离库' if LAB_MODE else ''))
gallery=window.gallery_interface
def show():window.show_gallery(refresh=False);window.showNormal();window.raise_()
def batch():
    show();gallery.imports.submit([picture(i,'incoming') for i in range(180,300)],ImportTarget(parent),gallery)
def duplicates():
    show();gallery.imports.submit([picture(i,'existing') for i in range(3)],ImportTarget(parent),gallery)
tray=QSystemTrayIcon(window.windowIcon(),app);tray.setToolTip('Nekori · 项目开发 Demo')
menu=QMenu();menu.addAction('显示开发 Demo',show)
menu.addAction('回到混排与移动源',lambda:(show(),gallery.set_node(parent))).setEnabled(bool(parent))
if (DATA/'sticky-sample.json').is_file():
    def sticky_sample():
        sample=json.loads((DATA/'sticky-sample.json').read_text(encoding='utf-8'))
        show();gallery.set_node(sample['scope'])
        gallery._expanded_nodes.update(sample['expanded']);gallery.refresh_content()
    menu.addAction('分类吸附样本',sticky_sample)
if not LAB_MODE:
    menu.addAction('导入120张样本',batch);menu.addAction('重复项集中决策',duplicates)
menu.addAction('打开QQ提取样本',window.show_qq_scan);menu.addAction('退出开发 Demo',app.quit)
tray.setContextMenu(menu);tray.activated.connect(lambda reason:show() if reason==QSystemTrayIcon.Trigger else None);tray.show()
from fluent_ui.components.clipboard_import_command import install_clipboard_import
install_clipboard_import(window,config,tray)
if LAB_MODE:
    # Lab settings may be saved, but may never claim the formal app's keys.
    def disable_shortcuts(*_):
        for command in (window.clipboard_search_command,window.clipboard_import_command):
            command.hotkey.close()
    disable_shortcuts()
    window.clipboard_search_command.configure=lambda *_:True
    window.clipboard_import_command.configure=lambda *_:True
def cleanup():
    gallery.imports.shutdown();gallery.ocr.close();window.settings_window.center.discard();tray.hide()
app.aboutToQuit.connect(cleanup)
window.resize(1150,800);show()
instance.set_window(window)
from PySide6.QtCore import QTimer
from services.send_sound import EVENT_SOUNDS
from fluent_ui.components.update_center import update_center
QTimer.singleShot(0,lambda:update_center().check_on_startup(config))
if parent:gallery.set_node(parent)
(HERE/'runtime.json').write_text(json.dumps(dict(pid=os.getpid(),hwnd=int(window.winId()),branch=branch,head=head,data=str(DATA),
    source=str(SOURCE),config=config.config_path,library=storage.library_root,index=str(storage.index.path),lab_mode=LAB_MODE,
    executable=sys.executable,entry=str(Path(__file__).resolve()),working_tree=True,
    clipboard_cache=gallery.clipboard.cache_dir,external_drag_cache=str(Path(config.base_dir)/'cache/external_drag'),
    temporary=__import__('tempfile').gettempdir(),global_hotkeys_disabled=LAB_MODE,ipc_server=SERVER,
    sound_service_file=__import__('services.send_sound',fromlist=['']).__file__,
    sound_events={event:dict(enabled=config.get(event+'_sound_enabled',False),path=config.get(event+'_sound_path',''),default=str(path)) for event,path in EVENT_SOUNDS.items()}),indent=2),encoding='utf-8')
exit_code=app.exec()
server.close()
for client in clients:client.abort()
(HERE/'last-exit.json').write_text(json.dumps(dict(pid=os.getpid(),exit_code=exit_code)),encoding='utf-8')
