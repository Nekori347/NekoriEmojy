"""Exercise real dialog input and affected interaction paths on isolated data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from unittest.mock import Mock
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent,QTimer,QObject,QRect
from PySide6.QtGui import QEnterEvent,QMouseEvent,QHelpEvent,QColor
from PySide6.QtWidgets import QApplication,QLabel,QDialog
from PySide6.QtTest import QTest
from qfluentwidgets import Theme,setTheme,Action
from test_phase2_interaction import surface,settle,card
from test_l1_l3_interaction import settings
from test_softframe_compact import painted
from fluent_ui import visual
from fluent_ui.components import dialogs


def schedule_text(app,text):
    observed=[]
    def complete():
        dialog=app.activeModalWidget()
        if not isinstance(dialog,dialogs.NekoriDialog):return
        from fluent_ui.components.controls import LineEdit,PushButton
        editor=dialog.findChild(LineEdit)
        observed.append((editor.text(),hasattr(dialog,'code_label')))
        editor.setText(text)
        next(b for b in dialog.findChildren(PushButton) if b.text()=='确定').click()
    QTimer.singleShot(0,complete)
    def release_stalled_dialog():
        if observed:return
        for widget in app.topLevelWidgets():
            if isinstance(widget,dialogs.NekoriDialog) and widget.isVisible():widget.reject()
    QTimer.singleShot(1500,release_stalled_dialog)
    return observed


@pytest.mark.parametrize('entry',['sidebar','resource','sidebar-menu','resource-menu'])
def test_all_creation_entries_open_real_input_and_create(surface,monkeypatch,entry):
    s=surface;g=s.g;before={n['id'] for n in s.storage.index.nodes()}
    seen=schedule_text(s.app,'Created '+entry)
    if entry=='sidebar':g.sidebar.btn_new.click()
    elif entry=='resource':g.create_node_here()
    else:
        from fluent_ui.components.safe_round_menu import SafeRoundMenu
        shown=[]
        original=SafeRoundMenu._show_menu
        def collect(menu,*_args,**_kwargs):shown.extend(menu.actions())
        monkeypatch.setattr(SafeRoundMenu,'_show_menu',collect)
        if entry=='sidebar-menu':g.sidebar._show_root_menu(QPoint())
        else:g.show_content_menu(QPoint(50,50))
        action=next(a for a in shown if '新建' in a.text())
        action.trigger()
    assert seen and not seen[0][1]
    created=[n for n in s.storage.index.nodes() if n['id'] not in before]
    assert len(created)==1 and created[0]['name']=='Created '+entry


def test_rename_prefills_and_commits_real_text(surface):
    seen=schedule_text(surface.app,'Renamed')
    surface.g.sidebar.rename_node(surface.parent)
    assert seen[0][0]=='Parent'
    assert surface.storage.node(surface.parent)['name']=='Renamed'


def test_hover_repaints_card_and_tree_without_a_click(surface):
    g=surface.g;c=card(surface,surface.paths[0]);before=painted(c)
    QApplication.sendEvent(c,QEnterEvent(QPointF(20,20),QPointF(20,20),QPointF(c.mapToGlobal(QPoint(20,20)))))
    assert c._hovered and not c.is_selected and painted(c)!=before
    QApplication.sendEvent(c,QEvent(QEvent.Leave));assert not c._hovered and painted(c)==before
    tree=g.sidebar.tree;item=tree._find_item(surface.other);pos=tree.visualItemRect(item).center()
    event=QMouseEvent(QEvent.MouseMove,QPointF(pos),QPointF(tree.viewport().mapToGlobal(pos)),Qt.NoButton,Qt.NoButton,Qt.NoModifier)
    QApplication.sendEvent(tree.viewport(),event)
    assert tree._hovered_index==tree.indexFromItem(item)
    QApplication.sendEvent(tree.viewport(),QEvent(QEvent.Leave));assert tree._hovered_index is None
    from fluent_ui.components.node_card import NodeCard
    node=next(w for w in g.findChildren(NodeCard) if w.isVisible())
    QApplication.sendEvent(node,QEnterEvent(QPointF(8,8),QPointF(8,8),QPointF(node.mapToGlobal(QPoint(8,8)))))
    assert node._hovered
    QApplication.sendEvent(node,QEvent(QEvent.Leave));assert not node._hovered


def test_tooltip_consumes_native_events_and_reuses_one_popup(surface):
    from fluent_ui.components.tooltip import install_global_tooltips,TooltipSurface
    from PySide6.QtWidgets import QToolTip
    tip=install_global_tooltips(surface.app,0)
    buttons=[surface.g.btn_content_sort,surface.g.tag_panel_host.splitter.handle(1)]
    buttons[1].setToolTip('收起标签')
    for b in buttons:
        event=QHelpEvent(QEvent.ToolTip,QPoint(2,2),b.mapToGlobal(QPoint(2,2)))
        assert tip.eventFilter(b,event)
        settle(surface.app)
        assert tip._tooltip.text()==b.toolTip() and not QToolTip.isVisible()
        assert sum(w.isVisible() for w in surface.app.topLevelWidgets() if isinstance(w,TooltipSurface))==1
        assert not tip._timer.isActive()
    tip._hide()


def test_preview_uses_tags_and_separate_saved_image_text(surface):
    s=surface;p=s.paths[0]
    s.storage.apply_tags([p],['KnownTag'],'add')
    s.storage.index.set_search_fields(s.storage.index.resource(p)['id'],ocr_text='Saved words')
    cat,tags=s.g.get_preview_metadata(p)
    popup=s.g.preview_popup
    popup.show_preview(p,s.g.mapToGlobal(QPoint(200,100)),220,cat,tags,info=s.g.get_preview_info(p))
    assert 'KnownTag' in [item.name for item in popup.tags._items]
    assert popup.ocr_label.isVisible() and 'Saved words' in popup.ocr_label.text()
    popup.hide_preview()


def test_switching_preview_has_short_delay_and_cancel_resets_it(surface,monkeypatch):
    c=surface.g.preview_controller;c.settle_timer.stop()
    monkeypatch.setattr(c,'_owner_is_visible',lambda:True)
    a=card(surface,surface.paths[0]);b=card(surface,surface.paths[1])
    c.enter(a,a.image_path);assert c.hover_timer.interval()==c.delay
    c.popup.show();c.leave(a);c.enter(b,b.image_path)
    assert c.hover_timer.interval()<=70 and c.current_hover_card is b
    c.cancel();c.enter(a,a.image_path);assert c.hover_timer.interval()==c.delay
    c.cancel()


def test_animated_preview_invalidates_the_entire_scaled_surface(surface):
    from PIL import Image,ImageDraw
    from fluent_ui.components.hover_preview import HoverPreviewPopup
    path=surface.tmp/'partial.gif';frames=[]
    for x in (0,20,40,60):
        frame=Image.new('RGBA',(90,60),(0,0,0,0));ImageDraw.Draw(frame).rectangle((x,10,x+15,45),fill='red');frames.append(frame)
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=70,loop=0,optimize=True,disposal=2)
    popup=HoverPreviewPopup();popup.show_preview(str(path),QPoint(200,200),300)
    label=popup.image_label
    class PaintRegions(QObject):
        def __init__(self):super().__init__();self.regions=[]
        def eventFilter(self,obj,event):
            if event.type()==QEvent.Paint:self.regions.append(event.region().boundingRect())
            return False
    spy=PaintRegions();label.installEventFilter(spy);QTest.qWait(360)
    assert len(spy.regions)>=3 and all(r==label.rect() for r in spy.regions)
    pix=popup.current_movie.currentPixmap()
    assert not pix.isNull() and abs(pix.width()/pix.height()-1.5)<.03
    popup.hide_preview();popup.deleteLater();settle(surface.app)


def test_tag_editor_preserves_untouched_mixed_tags_and_applies_explicit_changes(surface):
    s=surface;a,b=s.paths[:2]
    s.storage.apply_tags([a],['OnlyA'],'add');s.storage.apply_tags([a,b],['Shared'],'add')
    d=dialogs.TagEditorDialog(s.g,s.storage,[a,b]);d.show();settle(s.app)
    assert not hasattr(d,'mode_box') and not hasattr(d,'code_label')
    assert d.chips['OnlyA'].state==Qt.PartiallyChecked and d.chips['Shared'].state==Qt.Checked
    d.chips['Shared'].click();d.editor.setText('NewTag');d._add_entered();d.apply_button.click()
    assert 'OnlyA' in s.storage.parse_tags(s.storage.get_image_keywords(a))
    assert 'OnlyA' not in s.storage.parse_tags(s.storage.get_image_keywords(b))
    for path in (a,b):
        tags=s.storage.parse_tags(s.storage.get_image_keywords(path));assert 'NewTag' in tags and 'Shared' not in tags
    d.deleteLater();settle(s.app)


def test_tag_editor_cancel_changes_nothing(surface):
    p=surface.paths[0];old=surface.storage.get_image_keywords(p)
    d=dialogs.TagEditorDialog(surface.g,surface.storage,[p]);d.editor.setText('WillNotSave');d._add_entered();d.reject()
    assert surface.storage.get_image_keywords(p)==old
    d.deleteLater();settle(surface.app)


def test_target_tree_search_retains_ancestors_and_has_compact_depth(surface):
    d=dialogs.CategoryPickerDialog(surface.g,'移动到分类','选择目标分类',[(surface.parent,'Parent'),(surface.child,'    Child'),(surface.other,'Other')],{surface.child:'Parent / Child'})
    d.show();settle(surface.app)
    assert d.tree.height()>=300 and d.tree.indentation()==12
    child=d.items[1];assert child.parent() is d.items[0] and child.text(0)=='Child'
    d.search.setText('Child');settle(surface.app)
    assert not child.isHidden() and not child.parent().isHidden() and d.items[2].isHidden()
    d.tree.setCurrentItem(child);d.confirm_button.click();assert d.selected_value==surface.child
    d.deleteLater();settle(surface.app)


def test_settings_pending_marks_and_full_width_library_path(surface,settings):
    c=settings;c._select_page(1);c._show_tab(1);settle(surface.app)
    row=c._rows['thumbnail_size'][0];old=row.value()
    c._stage('thumbnail_size',old+10);assert row.property('pending')
    assert not c._rows['sidebar_icon_size'][0].property('pending')
    c._stage('thumbnail_size',old);assert not row.property('pending')
    c._stage('thumbnail_size',old+10);c.discard();assert not row.property('pending')
    c._select_page(3);c._show_tab(0);settle(surface.app)
    path='F:/Library/'+('directory/'*15)+'Pictures';c.library_info.set_value(path);settle(surface.app)
    label=c.library_info.value_label
    assert label.text()==path and label.width()>c.library_info.width()*.8
    assert label.y()>c.library_info.hint_label.y()


@pytest.mark.parametrize('dark',[False,True])
def test_about_text_tracks_theme(surface,dark):
    from fluent_ui.views.about_view import AboutInterface
    setTheme(Theme.DARK if dark else Theme.LIGHT);visual.theme.refresh()
    a=AboutInterface();a.resize(850,700);a.show();settle(surface.app)
    expected=QColor(visual.colors()['text'])
    assert expected.name() in a.styleSheet()
    labels=[l for l in a.findChildren(QLabel) if l.text()=='Nekori347']
    assert labels and labels[0].isVisible()
    image=painted(labels[0])
    assert any((c:=image.pixelColor(x,y)).alpha()>180 and abs(c.lightness()-expected.lightness())<12 for y in range(image.height()) for x in range(image.width()))
    a.close();a.deleteLater();setTheme(Theme.LIGHT);visual.theme.refresh();settle(surface.app)


def test_update_badges_share_state_and_never_query_suzu(surface,settings,monkeypatch):
    from fluent_ui.components.update_center import update_center
    from services.update_service import UpdateService
    center=update_center();settings._select_page(4);settle(surface.app)
    center.set_release(dict(version='9.0.0',date='',notes='',size=0));settle(surface.app)
    assert surface.g.btn_update.isVisible() and settings.update_badge.isVisible()
    assert surface.g.btn_update.height()<=surface.g.brand_lockup.height()
    open_dialog=Mock();monkeypatch.setattr(center,'open',open_dialog)
    surface.g.btn_update.click();settings.update_badge.click();settings.btn_update.click()
    assert open_dialog.call_count==3
    center.set_release(None)
    service=UpdateService(repository='Nekori347/NekoriEmojy',asset_name='NekoriEmojy_Release.zip')
    assert 'Nekori347/NekoriEmojy' in service.api_url and 'Suzu' not in service.releases_url


def test_feedback_does_not_move_gallery_or_tag_panel(surface):
    g=surface.g
    before=[w.geometry() for w in (g.location_rail,g.scroll_area,g.tag_panel_host)]
    host=g.feedback_host
    host.task('正在导入','3 / 7',total=7);settle(surface.app)
    host.update_task(3,7,'3 / 7');settle(surface.app)
    assert before==[w.geometry() for w in (g.location_rail,g.scroll_area,g.tag_panel_host)]
    assert g.workspace_layout.indexOf(host.strip)==-1
    host.finish('导入完成','7 项');host.notice('完成','可以继续操作');settle(surface.app)
    assert before==[w.geometry() for w in (g.location_rail,g.scroll_area,g.tag_panel_host)]
    host.dismiss()


@pytest.mark.parametrize('dark',[False,True])
def test_caption_task_is_transparent_and_single_line(surface,dark):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.feedback import FeedbackHost
    setTheme(Theme.DARK if dark else Theme.LIGHT);visual.theme.refresh()
    caption=QWidget();caption.resize(720,80)
    host=FeedbackHost(caption);host.dock_to_caption(caption);caption.show()
    host.task('正在导入',total=100,cancel=lambda:None);host.update_task(31,100)
    settle(surface.app)
    assert host.strip.height()==24
    assert host.title_label.width()>=host.title_label.fontMetrics().horizontalAdvance('正在导入')
    widgets=[host.title_label,host.progress,host.count_label,host.action_button]
    assert all(host.strip.rect().contains(w.geometry()) for w in widgets)
    assert max(w.geometry().center().y() for w in widgets)-min(w.geometry().center().y() for w in widgets)<=1
    assert all(not a.geometry().intersects(b.geometry()) for i,a in enumerate(widgets) for b in widgets[i+1:])
    image=painted(host.strip)
    assert image.pixelColor(0,0).alpha()==0 and image.pixelColor(2,23).alpha()==0
    host.finish('导入完成','100 项');settle(surface.app)
    assert host.progress.isHidden() and host.count_label.text()=='100 项' and host.strip.height()==24
    caption.close();caption.deleteLater();setTheme(Theme.LIGHT);visual.theme.refresh();settle(surface.app)


def test_qq_result_actions_follow_available_selection(surface):
    from fluent_ui.views.qq_scan_view import QQScanInterface
    v=QQScanInterface(config_service=surface.config);v.show();settle(surface.app)
    assert not v.importSelectedButton.isEnabled() and not v.importAllButton.isEnabled()
    v._on_scan_finished(surface.paths[:2]);settle(surface.app)
    assert v.importAllButton.isEnabled() and not v.importSelectedButton.isEnabled()
    v.previewListWidget.setCurrentRow(0);settle(surface.app)
    assert v.importSelectedButton.isEnabled()
    v.previewListWidget.clearSelection();settle(surface.app)
    assert not v.importSelectedButton.isEnabled() and v.importAllButton.isEnabled()
    v.shutdown();v.close();v.deleteLater();settle(surface.app)


def test_menu_actions_keep_unpadded_text_and_full_width(surface):
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    menu=SafeRoundMenu(parent=surface.g)
    action=Action('移动到「这是一个完整分类名称」',menu);menu.addAction(action)
    item=menu.view.item(0)
    assert item.text()==action.text()
    assert item.sizeHint().width()>=menu.view.fontMetrics().horizontalAdvance(action.text())+64
    submenu=SafeRoundMenu('顺序',menu);submenu.addAction(Action('移到最后',submenu));menu.addMenu(submenu)
    menu.deleteLater();settle(surface.app)


@pytest.mark.parametrize('language',['zh','en','zh_TW','ja'])
def test_tool_workbenches_keep_source_results_and_actions_visible(surface,language):
    from services.i18n import i18n_engine
    from fluent_ui.views.qq_scan_view import QQScanInterface
    from fluent_ui.views.tg_sticker_view import TGStickerInterface
    from fluent_ui.components.controls import PushButton
    i18n_engine.set_language(language)
    for view in (QQScanInterface(config_service=surface.config),TGStickerInterface()):
        view.show()
        for width in (720,980):
            view.resize(width,650);settle(surface.app);QTest.qWait(50)
            bench=view.presentation;grid=view.previewListWidget
            assert grid.viewport().height()>=250,(language,width,grid.size())
            assert bench.inputs.geometry().right()<bench.results.geometry().left()
            assert view.configScrollArea.verticalScrollBar().maximum()==0,(language,width)
            assert bench.actions.height()>=view.importSelectedButton.height()
            for button in (view.importSelectedButton,view.importAllButton,bench.more):
                assert bench.actions.rect().contains(button.geometry())
                assert button.width()>=button.sizeHint().width(),(language,width,button.text(),button.size(),button.sizeHint())
        view.collapse_config(animated=False);assert bench.inputs.isVisible()
        if hasattr(view,'urlInputEdit'):
            # No networking: the options surface keeps the original controls.
            bench.build_network();bench.network.show();settle(surface.app)
            assert bench.network.findChild(type(view.tokenEdit)) is not None
            bench.network.close()
        view.shutdown();view.close();view.deleteLater();settle(surface.app)
    i18n_engine.set_language('zh')
