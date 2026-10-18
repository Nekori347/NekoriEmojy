"""The final explicitly requested UI corrections, with disposable data."""
import time
from unittest.mock import Mock
from PySide6.QtCore import Qt,QPoint,QEvent
from PySide6.QtWidgets import QApplication,QDialog,QWidget
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings


def test_filter_keeps_full_row_hit_and_square_marker(surface):
    g=surface.g;g.filter_flyout.toggle(g.filter_state);row=g.filter_flyout.checkboxes['no_tag'];settle(surface.app)
    QTest.mouseClick(row,Qt.LeftButton,pos=QPoint(row.width()-3,row.height()//2));assert g.filter_state.no_tag
    image=row.grab().toImage()
    from fluent_ui import visual
    from PySide6.QtGui import QColor
    color=QColor(visual.accent());points=[]
    for y in range(row.height()):
        for x in range(3,18):
            if image.pixelColor(x,y)==color:points.append((x,y))
    assert points
    width=max(x for x,y in points)-min(x for x,y in points)+1;height=max(y for x,y in points)-min(y for x,y in points)+1
    assert 8<=width<=11 and 8<=height<=11


def test_shell_mask_agrees_with_painter_and_legacy_main_path(surface,monkeypatch):
    from fluent_ui.main_window import MainWindow
    from fluent_ui.materials import sync_native_clip
    monkeypatch.setattr(MainWindow,'_init_global_hotkey',lambda self:setattr(self,'hotkey_listener',None))
    window=MainWindow(surface.storage,surface.clipboard,surface.config);window.show();settle(surface.app)
    try:
        for win in (window,window.settings_window):
            win.show();sync_native_clip(win)
            assert not win.mask().isEmpty() and not win.mask().contains(QPoint(0,0))
            assert win.mask().contains(QPoint(14,1))
            win.resize(win.width()-11,win.height()-9);settle(surface.app)
            assert win.mask().boundingRect()==win.rect()
        before=window.mask();window.apply_rounded_corners();assert window.mask()==before
    finally:
        window.gallery_interface.imports.shutdown();window.gallery_interface.ocr.close();window.close();window.settings_window.close()


def test_language_entry_is_bilingual_only_where_needed_and_staged(settings):
    from services.i18n import i18n_engine
    from fluent_ui.icons import Icon
    c=settings;c._select_page(0);c._show_tab(2)
    for language,label in (('zh','语言 / Language'),('zh_TW','語言 / Language'),('en','Language'),('ja','言語 / Language')):
        i18n_engine.load_language(language);settle(QApplication.instance())
        assert c.tab_bar.tabText(2)==label and not c.tab_bar.tabIcon(2).isNull()
        combo=c._rows['language'][0].combo
        assert [combo.itemText(i) for i in range(combo.count())]==['简体中文','繁體中文','English','日本語']
    i18n_engine.load_language('zh');row=c._rows['language'][0]
    original=c.config.get('language','zh');row.set_value('en');row.changed.emit()
    assert c.pending['language']=='en' and c.config.get('language','zh')==original
    c.discard()


def test_about_is_inline_and_social_links_use_exact_targets(settings,monkeypatch):
    from fluent_ui.views.about_view import AUTHOR_LINKS
    c=settings;c._select_page(4);c._show_tab(0);settle(QApplication.instance())
    info=c.about_information;opened=[]
    monkeypatch.setattr(QDesktopServices,'openUrl',lambda url:opened.append(url.toString()) or True)
    for label,_,url in AUTHOR_LINKS:info.external_buttons[label].click()
    assert opened==[url for _,_,url in AUTHOR_LINKS]
    assert c.version_row.isVisible() and info.isVisible()
    assert all('查看详情'!=b.text() for b in c.body_widget.findChildren(__import__('PySide6.QtWidgets',fromlist=['QAbstractButton']).QAbstractButton))
    names=[name for _,name,_ in info.links]
    assert any('SuzuEmojy' in name for name in names) and any('VanillaNahida' in name for name in names)
    assert all(not button.text() and button.accessibleName() for button in info.external_buttons.values())


def test_qq_discovery_does_not_block_or_request_nicknames(surface,monkeypatch):
    from fluent_ui.views.qq_scan_view import QQScanInterface
    from services.qq_extractor import QQExtractor
    nickname=Mock(side_effect=AssertionError('opening QQ must not request remote nicknames'))
    monkeypatch.setattr(QQExtractor,'get_userdata_save_path',lambda *args:str(surface.tmp))
    def users(*args):time.sleep(.25);return ['123456']
    monkeypatch.setattr(QQExtractor,'get_numeric_subdirectories',users)
    monkeypatch.setattr(QQExtractor,'load_nickname_cache',lambda:{'123456':{'name':'本地昵称'}})
    monkeypatch.setattr(QQExtractor,'get_user_nickname',nickname)
    start=time.perf_counter();view=QQScanInterface(config_service=surface.config);elapsed=time.perf_counter()-start
    ticks=[];from PySide6.QtCore import QTimer
    timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:ticks.append(time.perf_counter()));timer.start()
    view.show();QTest.qWait(400);timer.stop();settle(surface.app)
    try:
        assert elapsed<.6 and len(ticks)>=8
        assert view.userComboBox.currentData()=='123456' and '本地昵称' in view.userComboBox.currentText()
        nickname.assert_not_called()
    finally:view.shutdown();view.close()


def test_qq_shutdown_discards_queued_results_before_widgets_are_deleted(surface,monkeypatch):
    from fluent_ui.views.qq_scan_view import QQScanInterface
    from services.qq_extractor import QQExtractor
    from PySide6.QtCore import QCoreApplication
    monkeypatch.setattr(QQExtractor,'get_userdata_save_path',lambda *args:str(surface.tmp))
    monkeypatch.setattr(QQExtractor,'get_numeric_subdirectories',lambda *args:['123456'])
    monkeypatch.setattr(QQExtractor,'load_nickname_cache',lambda:{})
    for _ in range(4):
        view=QQScanInterface(config_service=surface.config);view.populateUserComboBox()
        worker=view._discovery_workers[-1]
        worker.result.emit(worker.generation,'users',{'root':str(surface.tmp),'items':[('123456','')]})
        view.shutdown();view.close();view.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);QTest.qWait(20)


def test_ocr_split_body_and_arrow_have_separate_actions(settings,monkeypatch):
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    c=settings;c._select_page(3);c._show_tab(1);ocr=c.ocr_controls;s=ocr.service
    available={'value':True};monkeypatch.setattr(type(s),'available',property(lambda self:available['value']))
    monkeypatch.setattr(type(s),'library_busy',property(lambda self:False))
    running={'value':False};monkeypatch.setattr(type(s),'busy',property(lambda self:running['value']))
    calls=[];monkeypatch.setattr(s,'supplement',lambda **kw:calls.append(kw))
    ocr._has_failures=True;ocr._failure_revision=s.storage.index.search_revision;ocr.refresh();settle(QApplication.instance())
    ocr.retry.click();assert calls==[{'failed_only':True}]
    assert ocr.more is ocr.retry_group.dropButton and ocr.supplement_group.dropButton.isHidden()
    ocr.more.click();settle(QApplication.instance())
    menu=next(m for m in c.findChildren(SafeRoundMenu) if any(a.text()=='重新识别全部表情…' for a in m.actions()))
    assert menu.isVisible() and calls==[{'failed_only':True}]
    from fluent_ui.components import dialogs
    confirmation=Mock(return_value=False);monkeypatch.setattr(dialogs,'confirm',confirmation)
    next(a for a in menu.actions() if a.text()=='重新识别全部表情…').trigger()
    confirmation.assert_called_once();assert calls==[{'failed_only':True}]
    menu.hide();ocr._has_failures=False;ocr.refresh()
    assert ocr.retry_group.isHidden() and ocr.more is ocr.supplement_group.dropButton
    running['value']=True;cancel=Mock();monkeypatch.setattr(s,'cancel',cancel);ocr.refresh()
    assert not ocr.stop_group.isHidden() and ocr.supplement_group.isHidden() and ocr.retry_group.isHidden()
    ocr.cancel_button.click();cancel.assert_called_once()
    running['value']=False;available['value']=False;ocr.refresh()
    assert not ocr.supplement.isEnabled() and ocr.more.isEnabled()


def test_tray_restores_only_previously_visible_owned_windows_and_unsaved_page(surface,monkeypatch):
    from fluent_ui.main_window import MainWindow
    from fluent_ui.window_shell import ToolWindow
    from fluent_ui.components.tray_activation import execute_tray_action,TrayAction
    import fluent_ui.main_window as module
    monkeypatch.setattr(MainWindow,'_init_global_hotkey',lambda self:setattr(self,'hotkey_listener',None))
    monkeypatch.setattr(module.user32,'SetForegroundWindow',lambda *args:True)
    main=MainWindow(surface.storage,surface.clipboard,surface.config);main.show()
    settings=main.settings_window;settings.show();c=settings.center;c._select_page(1);c._show_tab(1)
    row=c._rows['thumbnail_size'][0];row.set_value(surface.config.get('thumbnail_size',120)+10);row.changed.emit()
    pending=dict(c.pending);tool=ToolWindow(main,QWidget(),'隔离工具');tool.show()
    hidden=ToolWindow(main,QWidget(),'未打开工具');modal=QDialog(tool);modal.setWindowModality(Qt.WindowModal);modal.show()
    settle(surface.app);geometry={w:w.geometry() for w in (settings,tool,modal)};cancel=Mock();monkeypatch.setattr(main.gallery_interface.ocr,'cancel',cancel)
    try:
        execute_tray_action(main,TrayAction.TOGGLE_MAIN);settle(surface.app)
        assert all(not w.isVisible() for w in (main,settings,tool,modal)) and c.pending==pending
        execute_tray_action(main,TrayAction.TOGGLE_MAIN);settle(surface.app)
        assert all(w.isVisible() for w in (main,settings,tool,modal)) and not hidden.isVisible()
        assert all(w.geometry()==geometry[w] for w in geometry)
        assert c.pending==pending and (c._current_page,c._current_tab)==(1,1)
        assert modal.windowModality()==Qt.WindowModal and QApplication.activeModalWidget() is modal
        cancel.assert_not_called()
        modal.reject();main.show_about();settle(surface.app)
        assert c._current_page==4 and main.settings_window is settings
        assert settings.pages.count()==1 and settings.pages.currentWidget() is c
    finally:
        modal.reject();tool.close();hidden.close();c.discard();settings.close()
        main.gallery_interface.imports.shutdown();main.gallery_interface.ocr.close();main.close()


def test_import_icon_intersection_is_transparent_instead_of_background_paint(surface):
    from fluent_ui.icons import Icon
    from PySide6.QtGui import QImage,QPainter
    from PySide6.QtCore import QRectF
    image=QImage(96,96,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
    p=QPainter(image);Icon.IMPORT.render(p,QRectF(0,0,96,96),fill='#000000');p.end()
    assert image.pixelColor(60,36).alpha()==0
    assert image.pixelColor(76,76).alpha()>200
    assert image.pixelColor(84,64).alpha()==0


def test_toolbox_order_is_final_and_about_navigates_to_settings(surface,monkeypatch):
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    g=surface.g;g._show_tools_menu();settle(surface.app)
    menu=next(m for m in g.findChildren(SafeRoundMenu) if any(a.text()=='相似表情' for a in m.actions()))
    labels=[menu.view.item(i).text().lstrip() for i in range(menu.view.count())]
    assert labels==['文字识别','相似表情','QQ 导入','Telegram 导入','关于']
    menu.hide()


def test_content_mask_restores_bottom_curves_without_changing_open_top(surface):
    pane=surface.g.content_pane;settle(surface.app);mask=pane.mask()
    assert mask.contains(QPoint(0,0)) and mask.contains(QPoint(pane.width()-1,0))
    assert not mask.contains(QPoint(0,pane.height()-1))
    assert not mask.contains(QPoint(pane.width()-1,pane.height()-1))
    assert mask.contains(QPoint(pane.width()//2,pane.height()-1))


def test_windows_clipboard_advertisement_does_not_render_external_ole(surface,monkeypatch):
    import sys
    from types import SimpleNamespace
    from PySide6.QtGui import QGuiApplication
    class Mime:
        def hasImage(self):raise AssertionError('Must not ask OLE to synthesize an image')
        def text(self):return self.value
    mime=Mime();mime.value='ordinary text';state={'sequence':1,'image':True}
    native=SimpleNamespace(GetClipboardSequenceNumber=lambda:state['sequence'],RegisterClipboardFormat=lambda name:100,
        IsClipboardFormatAvailable=lambda fmt:(fmt==2 and state['image']) or fmt==13)
    monkeypatch.setitem(sys.modules,'win32clipboard',native)
    monkeypatch.setattr(QGuiApplication,'platformName',lambda:'windows')
    monkeypatch.setattr(surface.clipboard,'clipboard',SimpleNamespace(ownsClipboard=lambda:False,mimeData=lambda:mime))
    check=lambda:surface.clipboard.has_importable_data(surface.storage.SUPPORTED_FORMATS)
    assert check()
    state.update(sequence=2,image=False);assert not check()
    state['sequence']=3;mime.value='https://example.com/emote.png';assert check()
