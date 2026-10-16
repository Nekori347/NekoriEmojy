"""Six local acceptance corrections: actual Qt events, isolated library/config."""
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtTest import QTest
from test_phase2_interaction import surface, settle, card
from test_softframe_acceptance import mime, drop
from fluent_ui import visual
from fluent_ui.components.drop_contract import TAG_MIME
from fluent_ui.components.navigation import HierarchyLocationHeader
from services.config import ConfigService


OUT = Path('../DevData/demo-local-fixes-1015')


@pytest.fixture(autouse=True)
def readable_font(surface):
    from PySide6.QtGui import QFont, QFontDatabase
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    surface.app.setFont(QFont('Microsoft YaHei',9))


def test_tree_leaf_space_body_chevron_and_single_stripe(surface):
    s,g=surface,surface.g
    tree=g.sidebar.tree
    parent=tree._find_item(s.parent);leaf=tree._find_item(s.other)
    assert parent.isFirstColumnSpanned() and leaf.isFirstColumnSpanned()
    assert tree.chevron_rect(leaf).isEmpty()
    before=g.current_node;expanded=parent.isExpanded()
    QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.chevron_rect(parent).center())
    assert parent.isExpanded()!=expanded and g.current_node==before
    QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.visualItemRect(leaf).center())
    assert g.current_node==s.other
    QTest.qWait(visual.MOTION.select+20)
    settle(s.app)
    image=tree.viewport().grab().toImage()
    row=tree.visualItemRect(leaf)
    accent=visual.colors()['accent']
    runs=[];start=None
    for x in range(0,30):
        hit=image.pixelColor(x,row.center().y()).name()==accent
        if hit and start is None:start=x
        if not hit and start is not None:runs.append((start,x-1));start=None
    assert len(runs)==1, runs
    OUT.mkdir(exist_ok=True);image.save(str(OUT/'sidebar.png'))


def test_rail_visible_rows_continuous_animation_scrub_and_fixed_layout(surface,monkeypatch):
    s,g=surface,surface.g
    h=g.hierarchy_header if hasattr(g,'hierarchy_header') else g.findChild(HierarchyLocationHeader)
    path=[{'id':str(i),'name':f'Level {i}'} for i in range(5)]
    h.set_path(path,{'id':'child','name':'Return child'})
    assert set(h._rows(h.path,h.return_item))=={'3','4','child'}
    anchor=h.current_rect();height=h.height();search=g.search_box.mapTo(g,QPoint())
    monkeypatch.setattr(QApplication,'platformName',lambda:'animation-test')
    h.set_path(path[:-1],path[-1])
    h.animation.pause();h.animation.setCurrentTime(0)
    first=h.grab().toImage()
    h.animation.setCurrentTime(80);middle=h.grab().toImage()
    h.animation.setCurrentTime(180);last=h.grab().toImage()
    assert first!=middle and middle!=last
    assert h.current_rect()==anchor and h.height()==height and g.search_box.mapTo(g,QPoint())==search
    nav=[];h.navigate_requested.disconnect();h.navigate_requested.connect(nav.append)
    start=QPoint(2,6)
    QTest.mousePress(h,Qt.LeftButton,pos=start)
    def move(dy):
        point=start+QPoint(0,dy)
        event=QMouseEvent(QMouseEvent.MouseMove,QPointF(point),QPointF(h.mapToGlobal(point)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
        QApplication.sendEvent(h,event)
    move(13);a=h.grab().toImage();position=h._scrub_position
    move(14);b=h.grab().toImage()
    assert h._scrub_position<position and a!=b and not nav
    expected=h.path[h._preview][0]
    QTest.mouseRelease(h,Qt.LeftButton,pos=start+QPoint(0,14))
    assert nav==[expected] and h.current_rect()==anchor
    OUT.mkdir(exist_ok=True);last.save(str(OUT/'hierarchy.png'))


@pytest.fixture
def main(surface,monkeypatch):
    from fluent_ui.main_window import MainWindow
    monkeypatch.setattr(MainWindow,'_init_global_hotkey',lambda _:None)
    monkeypatch.setattr(MainWindow,'apply_window_flags',lambda _:None)
    window=MainWindow(surface.storage,surface.clipboard,surface.config)
    window.gallery_interface.focus_timer.stop()
    window.resize(1080,790);window.show();settle(surface.app)
    yield window
    window.setting_interface.discard()
    window.quick_panel.shutdown();window.quick_panel.hide();window.settings_window.hide()
    window.close();window.deleteLater();settle(surface.app)
    QApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_esc_independent_immediate_persist_and_internal_priority(surface,main):
    s,w=surface,main;g=w.gallery_interface;q=w.quick_panel;c=w.setting_interface
    c._select_page(2)
    assert not s.config.get('esc_hide_main') and not s.config.get('esc_hide_quick')
    c._rows['esc_hide_main'][0].switch.setChecked(True)
    assert s.config.get('esc_hide_main') and not s.config.get('esc_hide_quick')
    assert ConfigService(s.tmp/'app').get('esc_hide_main')
    assert 'esc_hide_main' not in c.pending
    c.discard();assert s.config.get('esc_hide_main')
    g.set_mode('manage')
    g.filter_flyout.toggle(g.filter_state);settle(s.app)
    QTest.keyClick(g.filter_flyout.checkboxes['no_tag'],Qt.Key_Escape)
    assert not g.filter_flyout.isVisible() and g.mode=='manage' and w.isVisible()
    QTest.keyClick(g.search_box,Qt.Key_Escape)
    assert g.mode=='normal' and w.isVisible()
    menu=QMenu(w);menu.addAction('Entry');menu.popup(w.mapToGlobal(QPoint(40,70)));settle(s.app)
    QTest.keyClick(menu,Qt.Key_Escape)
    assert not menu.isVisible() and w.isVisible()
    QTest.keyClick(g.search_box,Qt.Key_Escape)
    assert not w.isVisible()
    w.show();q._activation_guard=True;q.show();settle(s.app)
    QTest.keyClick(q.search_box,Qt.Key_Escape)
    assert q.isVisible() and w.isVisible()
    c._rows['esc_hide_quick'][0].switch.setChecked(True)
    QTest.keyClick(q.search_box,Qt.Key_Escape)
    assert not q.isVisible() and w.isVisible()
    c._rows['esc_hide_main'][0].switch.setChecked(False)
    QTest.keyClick(g.search_box,Qt.Key_Escape)
    assert w.isVisible() and ConfigService(s.tmp/'app').get('esc_hide_quick')
    OUT.mkdir(exist_ok=True);w.settings_window.show();settle(s.app)
    w.settings_window.grab().save(str(OUT/'esc-settings.png'))


def test_theme_cycle_settings_preview_pending_save_discard_and_geometry(surface,main):
    s,w=surface,main;c=w.setting_interface;b=w.titleBar.themeButton
    s.config.set('appearance_mode','system');w.on_settings_changed('appearance_mode')
    for expected in ('light','dark','system'):
        QTest.mouseClick(b,Qt.LeftButton)
        assert b.property('themeMode')==expected
        assert ConfigService(s.tmp/'app').get('appearance_mode')==expected
    c._select_page(1);row=c._rows['appearance_mode'][0]
    row.set_value('dark');row.changed.emit()
    assert c.pending['appearance_mode']=='dark' and b.property('themeMode')=='dark'
    QTest.mouseClick(b,Qt.LeftButton)
    assert b.property('themeMode')=='system' and row.value()=='system'
    assert 'appearance_mode' not in c.pending and 'appearance_mode' not in s.config.preview_values
    c._stage('thumbnail_size',140);assert c.save()
    assert s.config.get('appearance_mode')=='system'
    row.set_value('light');row.changed.emit();c.discard()
    assert b.property('themeMode')=='system' and row.value()=='system'
    row.set_value('dark');row.changed.emit();assert c.save()
    assert ConfigService(s.tmp/'app').get('appearance_mode')=='dark'
    settle(s.app)
    assert b.geometry().right()<w.titleBar.settingsButton.geometry().left()
    assert b.geometry().right()<w.titleBar.minBtn.geometry().left()
    assert not w.titleBar.canDrag(b.geometry().center())
    assert w.accent_line.geometry().bottom()<b.geometry().top()
    OUT.mkdir(exist_ok=True);w.grab().save(str(OUT/'main-dark.png'))
    QTest.mouseClick(b,Qt.LeftButton);QTest.mouseClick(b,Qt.LeftButton)
    settle(s.app);w.grab().save(str(OUT/'main-light.png'))


@pytest.mark.parametrize('ending',['leave','drop','end','return'])
def test_tag_reorder_hint_only_attempt_and_session_cleanup(surface,ending):
    s,g=surface,surface.g
    s.storage.apply_tags([s.paths[1]],['Dog'],'add');g.refresh_content_incremental(reason='test')
    g.tag_panel.set_sort('a_z');flow=g.tag_panel.flow
    def point(name):return flow._rects[next(i for i,x in enumerate(flow._items) if x.name==name)].center()
    data=mime(TAG_MIME,['Cat'])
    enter=QDragEnterEvent(point('Cat'),Qt.MoveAction,data,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(flow,enter)
    def move(name):
        event=QDragMoveEvent(point(name),Qt.MoveAction,data,Qt.LeftButton,Qt.NoModifier)
        QApplication.sendEvent(flow,event)
    move('Cat');assert not g.feedback_host.hint_label.isVisible()
    move('Dog');assert g.feedback_host.hint_label.isVisible()
    assert not g.feedback_host.toasts
    owner=g.feedback_host._hint_owner
    move('Dog');assert g.feedback_host._hint_owner is owner
    if ending=='leave':QApplication.sendEvent(flow,QDragLeaveEvent())
    elif ending=='drop':QApplication.sendEvent(flow,QDropEvent(QPointF(point('Cat')),Qt.MoveAction,data,Qt.LeftButton,Qt.NoModifier))
    elif ending=='return':move('Cat')
    else:flow.end_drag_session()
    assert not g.feedback_host.hint_label.isVisible() and not g.feedback_host.hint_timer.isActive()
    drop(card(s,s.paths[1]),card(s,s.paths[1]).rect().center(),data)
    assert 'Cat' in s.storage.resource_of(s.paths[1])['tags'].split()
    assert not g.feedback_host.hint_label.isVisible()


@pytest.mark.parametrize('dimensions',[(400,200),(200,400),(300,300)])
def test_thumbnail_four_dip_full_aspect_and_stable_states(surface,dimensions):
    s=surface;c=card(s,s.paths[0]);c.update_size(120,load_image=False)
    source=QPixmap(*dimensions);source.fill(Qt.red)
    s.g.renderer.loader.attach(c,'test-image',source)
    result=c.pixmap()
    assert max(result.width(),result.height())==112
    assert abs(result.width()/result.height()-dimensions[0]/dimensions[1])<.02
    size=c.size()
    for selected in (True,False):
        c.set_selected(selected);assert c.size()==size and c.pixmap().size()==result.size()
    c.setProperty('state','missing');c.update_style();assert c.size()==size


def test_gif_cover_is_contained_with_four_dip_inset(surface):
    from PIL import Image
    from fluent_ui.components.emoji_card import EmojiCard, _thumbnail_pool
    path=surface.tmp/'wide.gif'
    Image.new('RGB',(400,200),'cyan').save(path,save_all=True,
        append_images=[Image.new('RGB',(400,200),'magenta')],duration=100,loop=0)
    c=EmojiCard(str(path),120)
    _thumbnail_pool.waitForDone();settle(surface.app)
    assert c.pixmap().size().width()==112 and c.pixmap().size().height()==56
    c.close();c.deleteLater()

