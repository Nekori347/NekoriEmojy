"""Tag foreground chrome: real geometry, transparent input states and motion."""
import pytest
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest
from test_tag_panel_collapse import scene,settle
from test_tab_overflow import own_paint


def test_new_tag_lives_in_header_and_horizontal_control_stays_centered(scene):
    app,window,host,panel,content,config,model=scene
    host.set_placement('top');settle(app)
    assert panel.header.isAncestorOf(panel.btn_new)
    control=panel.btn_collapse
    assert control.width()>control.height()*2
    for text in ('6','999999'):
        panel.count_label.setText(text);panel._fit_collapsed_identity();settle(app)
        assert abs(control.mapTo(panel.header,control.rect().center()).x()-panel.header.rect().center().x())<=2
        assert panel.btn_new.mapTo(panel.header,QPoint()).x()<panel.btn_sort.mapTo(panel.header,QPoint()).x()


def test_linear_control_press_never_fills_its_hit_rectangle(scene):
    app,window,host,panel,*_=scene
    control=panel.btn_collapse
    control.setDown(True)
    image=own_paint(control)
    assert image.pixelColor(2,2).alpha()==0,'pressed chrome must not create an opaque box'
    control.setDown(False)


def test_top_header_identity_does_not_drift_during_collapse(scene,monkeypatch):
    from PySide6.QtWidgets import QApplication
    app,window,host,panel,*_=scene
    host.set_placement('top');settle(app)
    monkeypatch.setattr(QApplication,'platformName',staticmethod(lambda:'windows'))
    host.set_expanded(False);host._motion.pause()
    positions=[]
    for time in (0,55,110,165):
        host._motion.setCurrentTime(time);settle(app)
        assert panel.header.isVisible()
        assert panel.header.height()==30
        positions.append(panel.chrome.mapTo(host,QPoint(5,15)))
    assert len({(p.x(),p.y()) for p in positions})==1
    host._motion.resume();QTest.qWait(260)


@pytest.mark.parametrize('placement',['top','bottom','left','right'])
def test_drawer_motion_keeps_chrome_in_its_dock_coordinate_system(scene,monkeypatch,placement):
    from PySide6.QtWidgets import QApplication
    app,window,host,panel,content,*_=scene
    host.set_placement(placement);settle(app)
    original=content.geometry()
    monkeypatch.setattr(QApplication,'platformName',staticmethod(lambda:'windows'))
    host.set_expanded(False);host._motion.pause()
    positions=[];extents=[]
    for time in (0,55,110,165):
        host._motion.setCurrentTime(time);settle(app)
        assert content.geometry()==original
        assert panel.header.isVisible() and panel.flow_area.isVisible()
        assert panel.chrome.isVisible() and not panel.btn_sort.isVisible() and not panel.btn_new.isVisible()
        assert panel.chrome.height()==30 if host.horizontal else panel.chrome.width()==panel.collapsed_extent()
        positions.append(panel.chrome.mapTo(host,QPoint(5,15)))
        extents.append(panel.height() if host.horizontal else panel.width())
        image=own_paint(panel)
        assert image.pixelColor(panel.width()//2,15).alpha()==210
        if panel.height()>35:assert image.pixelColor(panel.width()//2,34).alpha()==175
    assert extents==sorted(extents,reverse=True) and extents[0]>extents[-1]
    if placement=='bottom':
        assert [p.y() for p in positions]==sorted(p.y() for p in positions)
        assert positions[0].y()<positions[-1].y()
    else:assert len({(p.x(),p.y()) for p in positions})==1
    host._motion.resume();QTest.qWait(260)
    assert not panel.flow_area.isVisible()


def test_linear_chrome_input_lifecycle_keeps_no_box_or_mouse_focus_highlight(scene,monkeypatch):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QCursor
    from PySide6.QtWidgets import QApplication
    app,window,host,panel,*_=scene
    button=panel.btn_collapse
    outside=window.mapToGlobal(QPoint(-20,-20))
    monkeypatch.setattr(QCursor,'pos',lambda:outside)
    button.clearFocus();baseline=own_paint(button)
    button.setFocus(Qt.MouseFocusReason);settle(app)
    assert own_paint(button)==baseline
    monkeypatch.setattr(QCursor,'pos',lambda:button.mapToGlobal(button.rect().center()))
    assert own_paint(button)!=baseline
    assert own_paint(button).pixelColor(2,2).alpha()==0
    button.setDown(True)
    app.sendEvent(button,QEvent(QEvent.UngrabMouse));settle(app)
    assert not button.isDown()
    monkeypatch.setattr(QCursor,'pos',lambda:outside)
    assert own_paint(button)==baseline
    QTest.keyClick(button,Qt.Key_Tab);button.setFocus(Qt.TabFocusReason);settle(app)
    assert own_paint(button)!=baseline and own_paint(button).pixelColor(2,2).alpha()==0
    button.hide();button.show();settle(app)
    assert not button.isDown()


def test_reused_motion_does_not_apply_previous_progress_while_configuring(scene,monkeypatch):
    from PySide6.QtWidgets import QApplication
    app,window,host,panel,*_=scene
    monkeypatch.setattr(QApplication,'platformName',staticmethod(lambda:'windows'))
    host.set_expanded(False);QTest.qWait(280)
    host.set_expanded(True);QTest.qWait(280)
    observed=[];set_sizes=host.splitter.setSizes
    def trace(sizes):
        set_sizes(sizes);observed.append(panel.height())
    monkeypatch.setattr(host.splitter,'setSizes',trace)
    host.set_expanded(False);QTest.qWait(280)
    assert observed==sorted(observed,reverse=True),observed


def test_header_new_tag_and_keyboard_toggle_use_existing_commands(scene,monkeypatch):
    from fluent_ui.components import dialogs
    app,window,host,panel,content,config,model=scene
    host.set_placement('top');settle(app)
    monkeypatch.setattr(dialogs,'prompt_text',lambda *a,**kw:('HeaderTag',True))
    messages=[];panel.message_requested.connect(lambda *args:messages.append(args))
    panel.btn_new.click()
    assert 'HeaderTag' in model.names() and messages and not messages[-1][2]
    panel.btn_collapse.setFocus(Qt.TabFocusReason);QTest.keyClick(panel.btn_collapse,Qt.Key_Space);settle(app)
    assert not host.expanded and panel.chrome.isVisible()
    panel.chrome.setFocus(Qt.TabFocusReason);QTest.keyClick(panel.chrome,Qt.Key_Space);settle(app)
    assert host.expanded and not panel.axis_strip.isVisible(),'manual order has no empty index toolbar'
