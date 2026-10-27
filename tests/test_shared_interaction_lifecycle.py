"""Paint and input lifetime regressions; no Library, network or system mouse."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import Qt, QEvent, QPoint, Signal
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from fluent_ui import visual
from fluent_ui.components.controls import PushButton
from fluent_ui.components.panel_host import EdgeDockPanelChrome, TagPanelPlacement


class RailPanel(QWidget):
    toggle_collapse_requested = Signal()
    _placement = TagPanelPlacement.BOTTOM
    _collapsed_horizontal = True
    collapsed_metrics = visual.TAG_COLLAPSED_METRICS

    def header_action_hovered(self):
        return False

    def collapsed_extent(self):
        return visual.TAG_PANEL_COLLAPSED_EXTENT


@pytest.fixture
def scene(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(visual.theme, 'config', {'ui_animations_enabled': False})
    panel = RailPanel()
    panel.resize(420, 120)
    panel.show()
    app.setActiveWindow(panel)
    app.processEvents()
    yield app, panel
    panel.close()
    panel.deleteLater()
    app.processEvents()


def test_button_geometry_change_drops_unhit_hover_without_leave(scene, monkeypatch):
    app, panel = scene
    button = PushButton('Action', panel)
    button.setGeometry(10, 40, 120, 32)
    button.show()
    # Model a geometry change under a stationary pointer; Qt need not send Leave.
    monkeypatch.setattr(QCursor, 'pos', lambda: panel.mapToGlobal(QPoint(390, 100)))
    button._set_hover(0)
    baseline = button.grab().toImage()
    button._set_hover(1)
    assert button.grab().toImage() != baseline
    button.move(20, 40)
    QTest.qWait(5)
    assert button.grab().toImage() == baseline


def test_lost_mouse_capture_settles_pressed_and_hover(scene, monkeypatch):
    app, panel = scene
    button = PushButton('Action', panel)
    button.setGeometry(10, 40, 120, 32)
    button.show()
    monkeypatch.setattr(QCursor, 'pos', lambda: panel.mapToGlobal(QPoint(390, 100)))
    baseline = button.grab().toImage()
    button.setDown(True)
    button._set_hover(1)
    app.sendEvent(button, QEvent(QEvent.UngrabMouse))
    QTest.qWait(5)
    assert not button.isDown()
    assert button.grab().toImage() == baseline


def test_collapsed_rail_mouse_focus_is_not_persistent_hover(scene, monkeypatch):
    app, panel = scene
    rail = EdgeDockPanelChrome(panel)
    rail.setGeometry(0, 0, 420, 20)
    rail.show()
    monkeypatch.setattr(QCursor, 'pos', lambda: panel.mapToGlobal(QPoint(390, 100)))
    rail.clearFocus()
    baseline = rail.grab().toImage()
    rail.setFocus(Qt.MouseFocusReason)
    app.processEvents()
    assert rail.hasFocus()
    assert rail.grab().toImage() == baseline
    # A real keyboard action still exposes the independent accessibility cue.
    QTest.keyClick(rail, Qt.Key_Tab)
    rail.setFocus(Qt.TabFocusReason)
    app.processEvents()
    assert rail.grab().toImage() != baseline


def test_collapsed_rail_does_not_hover_through_cover(scene, monkeypatch):
    app, panel = scene
    rail = EdgeDockPanelChrome(panel)
    rail.setGeometry(0, 0, 420, 20)
    rail.show()
    rail.clearFocus()
    outside = panel.mapToGlobal(QPoint(390, 100))
    monkeypatch.setattr(QCursor, 'pos', lambda: outside)
    baseline = rail.grab().toImage()
    point = rail.mapToGlobal(QPoint(300, 10))
    monkeypatch.setattr(QCursor, 'pos', lambda: point)
    cover = QWidget(panel)
    cover.setGeometry(rail.geometry())
    cover.show()
    cover.raise_()
    app.processEvents()
    assert QApplication.widgetAt(point) is cover
    assert rail.grab().toImage() == baseline


def test_checked_state_and_click_survive_transient_reset(scene, monkeypatch):
    app, panel = scene
    button = PushButton('Toggle', panel)
    button.setCheckable(True)
    button.setGeometry(10, 40, 120, 32)
    button.show()
    monkeypatch.setattr(QCursor, 'pos', lambda: panel.mapToGlobal(QPoint(390, 100)))
    clicks = []
    button.clicked.connect(lambda: clicks.append(button.isChecked()))
    QTest.mouseClick(button, Qt.LeftButton)
    assert clicks == [True] and button.isChecked()
    baseline = button.grab().toImage()
    button.hide()
    button.show()
    QTest.qWait(5)
    assert button.isChecked() and button.grab().toImage() == baseline
    QTest.mouseClick(button, Qt.LeftButton)
    assert clicks == [True, False] and not button.isChecked()


def test_header_collapse_chevron_uses_shared_neutral_color(scene,monkeypatch):
    from fluent_ui.components import panel_host
    app,panel=scene
    button=panel_host.EdgeDockPanelChrome(panel,expanded=True);button.resize(24,24);button.show()
    monkeypatch.setattr(QCursor,'pos',lambda:panel.mapToGlobal(QPoint(500,500)))
    colors=[];original=panel_host.paint_dock_chevron
    def observe(painter,points,active=False):
        original(painter,points,active);colors.append((painter.pen().color().name(),active))
    monkeypatch.setattr(panel_host,'paint_dock_chevron',observe)
    button.grab();assert colors[-1]==(visual.colors()['text_secondary'],False)


def test_splitter_keyboard_cue_ends_when_pointer_input_keeps_qt_focus(scene, monkeypatch):
    from types import SimpleNamespace
    from fluent_ui.components.panel_host import PanelSplitter
    app, panel = scene
    split = PanelSplitter(Qt.Vertical, panel)
    split.dock_host = SimpleNamespace(expanded=True, placement=TagPanelPlacement.BOTTOM)
    split.addWidget(QWidget())
    split.addWidget(QWidget())
    split.setGeometry(0, 0, 300, 120)
    split.setHandleWidth(8)
    split.show()
    handle = split.handle(1)
    handle.setFocusPolicy(Qt.StrongFocus)
    other = PushButton('Pointer action', panel)
    other.setGeometry(305, 40, 110, 32)
    other.setFocusPolicy(Qt.NoFocus)
    other.show()
    app.processEvents()
    monkeypatch.setattr(QCursor, 'pos', lambda: panel.mapToGlobal(QPoint(500, 500)))
    handle.clearFocus()
    baseline = handle.grab().toImage()
    handle.setFocus(Qt.TabFocusReason)
    QTest.keyClick(handle, Qt.Key_Right)
    assert handle.hasFocus() and handle.grab().toImage() != baseline
    QTest.mouseClick(other, Qt.LeftButton)
    app.processEvents()
    assert handle.hasFocus()  # Qt focus intentionally remains; only input origin changes.
    assert handle.grab().toImage() == baseline


def test_resize_handle_lost_capture_clears_drag_feedback(scene,monkeypatch):
    from fluent_ui.components.panel_host import PanelSplitter
    app,panel=scene
    split=PanelSplitter(Qt.Vertical,panel)
    split.addWidget(QWidget());split.addWidget(QWidget())
    split.setGeometry(0,0,300,100);split.show();app.processEvents()
    handle=split.handle(1)
    monkeypatch.setattr(QCursor,'pos',lambda:panel.mapToGlobal(QPoint(500,500)))
    baseline=handle.grab().toImage()
    QTest.mousePress(handle,Qt.LeftButton,pos=handle.rect().center())
    assert handle.grab().toImage()!=baseline
    app.sendEvent(handle,QEvent(QEvent.UngrabMouse))
    assert handle.grab().toImage()==baseline
    QTest.mouseRelease(handle,Qt.LeftButton,pos=handle.rect().center())
