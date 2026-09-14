"""Behavioral UI probe. Synthetic assets and settings only; no desktop hooks or registry writes."""
import itertools,json,os,sys,traceback,time
from pathlib import Path
from unittest.mock import patch
work=Path(os.environ['P3_WORK_DIR']).resolve()
work.mkdir(parents=True,exist_ok=True)
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo));os.chdir(repo)
root=work/'ui';root.mkdir(exist_ok=False)
os.environ['QT_QPA_PLATFORM']=os.environ.get('P3_QPA','offscreen')
os.environ['NEKORI_BOOTSTRAP_DIR']=str(root/'bootstrap')
from PIL import Image,ImageDraw
from PySide6.QtCore import Qt,QPoint,QPointF,QTimer
from PySide6.QtGui import QDropEvent,QDragMoveEvent,QDragLeaveEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from services.library import create_library,LibrarySession,digest
from services.storage import StorageService
from services.config import ConfigService
from services.clipboard import ClipboardService
from services.category_groups import CategoryGroups
from fluent_ui.drag_payload import make_payload,paths_from_mime
from services.i18n import i18n_engine
from qfluentwidgets import qconfig
import requests
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
from PySide6.QtGui import QFontDatabase,QFont
fontfile=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'msyh.ttc'
if fontfile.is_file():
    QFontDatabase.addApplicationFont(str(fontfile))
    app.setFont(QFont('Microsoft YaHei',9))
context=create_library(root/'library');session=LibrarySession(context)
config=ConfigService(session);config.set('always_on_top',False)
store=StorageService(session)
paths=[]
for i in range(64):
    source=root/f'input-{i}.png'
    pic=Image.new('RGB',(160,160),((i*43)%256,(i*23+64)%256,(i*13+128)%256))
    draw=ImageDraw.Draw(pic);draw.rounded_rectangle((15,18,145,142),radius=25,fill='white')
    draw.text((44,69),f'ITEM {i+1:02d}',fill='black')
    pic.save(source)
    path=store.save_file(source,target_category='日常')[0];paths.append(path)
store.add_category('收藏');store.set_image_keywords(paths[0],'测试猫猫')
groups=CategoryGroups(session)
one=groups.create('日常','猫猫');two=groups.create('日常','常用');empty=groups.create('日常','待整理')
groups.add(one,paths[:12]);groups.add(two,paths[8:20]);groups.set_collapsed(two,True)
before={str(p):digest(p) for p in context.images_dir.iterdir()}
qconfig.file=context.data_dir/'cache'/'qt-state.json';i18n_engine.init(config)
report={'platform':os.environ['QT_QPA_PLATFORM'],'synthetic_images':len(paths),'checks':[],'layout_combinations':[]}
errors=[]
def record_exception(*args):
    errors.append(''.join(traceback.format_exception(*args)))
    if len(errors) <= 3: traceback.print_exception(*args)
sys.excepthook=record_exception
def check(name,condition):
    assert condition,name
    report['checks'].append(name)
window=None
try:
    with patch('requests.sessions.Session.request',side_effect=requests.ConnectionError('isolated')),patch('fluent_ui.main_window.MainWindow.bind_global_hotkey'):
        from fluent_ui.main_window import MainWindow
        window=MainWindow(store,ClipboardService(config),config);window.show();QTest.qWait(1000)
        g=window.gallery_interface;g.sidebar.set_active_category('日常');QTest.qWait(500)
        check('flat section headers incl empty and ungrouped',len(g._group_sections)==4)
        check('collapsed membership hidden',next(s for s in g._group_sections if s['id']==two)['paths']==[])
        g.set_selection_mode(True);g.on_selection_changed(paths[0],True);g.on_selection_changed(paths[1],True)
        cat=g.current_category;selected=set(g.selected_paths)
        window.show_settings();QTest.qWait(100)
        check('settings is independent and modeless',window.settings_window.isWindow() and not window.settings_window.isModal() and window.stacked_widget.currentWidget() is g)
        check('settings open preserves category and selection',g.current_category==cat and g.selected_paths==selected)
        for bits in itertools.product((False,True),repeat=3):
            for key,value in zip(('left_multiselect','left_filter','left_search'),bits):config.set(key,value)
            window.apply_preferences();QTest.qWait(90)
            for widget,left in zip((g.btn_multi_select,g.btn_filter,g.search_box),bits):
                expected=g.sidebar.tools if left else g.top_bar
                assert widget.parentWidget() is expected,(bits,widget.objectName(),widget.parentWidget())
            assert g.current_category==cat and g.selected_paths==selected
            report['layout_combinations'].append(list(bits))
        check('preview does not persist',not ConfigService(session).get('left_search'))
        window.settings_window.close();QTest.qWait(150)
        check('close reverts preview',not config.get('left_search') and g.search_box.parentWidget() is g.top_bar)
        window.show_settings();config.set('left_search',True);window.apply_preferences();window.settings_window.save()
        check('save commits current preview',ConfigService(session).get('left_search'))
        config.set('left_search',False);window.apply_preferences();window.settings_window.close();QTest.qWait(100)
        check('close after save restores saved baseline',config.get('left_search') and g.search_box.parentWidget() is g.sidebar.tools)
        window.show_settings();config.set('sidebar_is_grid_mode',True);config.set('category_grid_icon_size',80);window.apply_preferences();g.set_selection_mode(False);QTest.qWait(300)
        check('existing category list supports grid',g.sidebar.is_grid_mode and g.sidebar.list_widget.iconSize().width()<=80)
        window.settings_window.grab().save(str(root/'settings.png'))
        window.settings_window.hide();window.resize(1000,730);QTest.qWait(250)
        window.grab().save(str(root/'groups.png'))
        window.resize(520,430);QTest.qWait(250)
        check('narrow search remains within window',window.rect().contains(g.search_box.mapTo(window,QPoint(g.search_box.width()-1,g.search_box.height()-1))))
        window.grab().save(str(root/'narrow.png'))
        window.resize(1000,730);QTest.qWait(250)
        groups.set_collapsed(two,False);g.on_images_changed();QTest.qWait(300)
        repeats=[w for w in g._all_card_widgets if w.image_path==paths[8]]
        check('shared asset appears in both groups',len(repeats)==2)
        g.set_selection_mode(True);g.on_selection_changed(paths[8],True)
        check('selection synced across occurrences',all(w.is_selected for w in repeats))
        g.select_all_cards();check('select all counts unique assets',len(g.selected_paths)==len(paths))
        g.select_all_cards();check('select all toggles off with shared assets',not g.selected_paths)
        g.on_selection_changed(paths[0],True);g.on_selection_changed(paths[1],True);g.on_selection_changed(paths[13],True)
        groups.set_collapsed(two,True);g.on_images_changed();QTest.qWait(200)
        payload=make_payload(context,g.drag_paths(paths[1]),paths[1])
        check('drag any selection includes hidden selected members',len(paths_from_mime(payload,context))==3)
        target=next(g.sidebar.list_widget.item(i) for i in range(g.sidebar.list_widget.count()) if g.sidebar.list_widget.item(i).data(Qt.UserRole)=='收藏')
        pos=g.sidebar.list_widget.visualItemRect(target).center()
        hover=QDragMoveEvent(pos,Qt.CopyAction,payload,Qt.LeftButton,Qt.NoModifier);g.sidebar.list_widget.dragMoveEvent(hover)
        check('category drag target highlighted',g.sidebar.list_widget._drop_target==g.sidebar.list_widget.row(target))
        drop=QDropEvent(QPointF(pos),Qt.CopyAction,payload,Qt.LeftButton,Qt.NoModifier);g.sidebar.list_widget.dropEvent(drop);QTest.qWait(200)
        check('drop adds all and clears highlight',drop.isAccepted() and len(store.get_images_by_category('收藏'))==3 and g.sidebar.list_widget._drop_target==-1)
        check('drop preserves original memberships',len(store.get_images_by_category('日常'))==64)
        header=next(s['header'] for s in g._group_sections if s['id']==empty)
        drop=QDropEvent(QPointF(20,20),Qt.CopyAction,payload,Qt.LeftButton,Qt.NoModifier);header.dropEvent(drop);QTest.qWait(200)
        check('drop into small group adds all',len(next(s for s in groups.list('日常') if s['id']==empty)['paths'])==3)
        g.change_group_members(empty,[paths[0]],False);QTest.qWait(150)
        check('small group removal preserves parent and file',len(next(s for s in groups.list('日常') if s['id']==empty)['paths'])==2 and paths[0] in store.get_images_by_category('日常') and Path(paths[0]).exists())
        order=store.get_all_images();moving=[order[3],order[5]];target=order[12]
        g.reorder_resources(moving,target,False);QTest.qWait(150);order=store.get_all_images();index=order.index(target)
        check('multi-item reorder keeps whole selection',order[index-2:index]==moving)
        g.search_box.setText('测试猫猫');QTest.qWait(450)
        check('search temporarily expands groups',all(not s['collapsed'] for s in g._group_sections))
        g.search_box.clear();QTest.qWait(400)
        check('clearing search restores stored fold',next(s for s in g._group_sections if s['id']==two)['collapsed'])
        default=window.windowIcon().pixmap(64,64).toImage()
        config.set('runtime_icon',Path(paths[0]).name);window.apply_runtime_icon()
        check('runtime icon changes window',window.windowIcon().pixmap(64,64).toImage()!=default)
        config.set('runtime_icon','missing.png');window.apply_runtime_icon()
        check('missing runtime icon falls back',window.windowIcon().pixmap(64,64).toImage()==default)
        check('source assets unchanged',all(digest(Path(p))==v for p,v in before.items()))
        from fluent_ui.library_image_picker import LibraryImagePicker
        picker=LibraryImagePicker(store,window);picker.show();QTest.qWait(180)
        picker.list.setCurrentRow(0);picker.choose();check('runtime picker selects library image',picker.selected_path in paths)
        picker.close()
        from fluent_ui.maintenance_dialog import MaintenanceDialog
        maintenance=MaintenanceDialog(window);maintenance.show();QTest.qWait(50)
        maintenance.start_repair();deadline=time.perf_counter()+5
        while maintenance.job.isRunning() and time.perf_counter()<deadline:QTest.qWait(10)
        QTest.qWait(50)
        check('maintenance completes without blocking library state',maintenance.repair.isEnabled() and len(store.get_all_images())==64)
        maintenance.close()
        check('no Qt slot exceptions',not errors)
except Exception:
    report['error']=traceback.format_exc()
finally:
    report['qt_errors']=errors
    (root/'report-before-close.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if window:
        for thread in window.findChildren(__import__('PySide6.QtCore',fromlist=['QThread']).QThread):thread.wait(5000)
        window.settings_window.close();window.close();window.quick_panel.close();QTest.qWait(60)
    session.close()
    report['passed']='error' not in report and not errors
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
sys.exit(0 if report['passed'] else 1)
