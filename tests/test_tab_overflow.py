"""Render the real QTabBar overflow path; no replacement scroll model."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QRegion, QCursor, QEnterEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QToolButton, QWidget
from PySide6.QtTest import QTest, QSignalSpy
from fluent_ui.components.navigation import TabStrip
from fluent_ui import visual


@pytest.fixture
def strip():
    app = QApplication.instance() or QApplication([])
    tabs = TabStrip(location_divider=True)
    tabs.resize(460, 43)
    tabs.set_tabs(['Location'] + ['Long category label ' + str(i) for i in range(18)])
    tabs.show()
    QTest.qWait(200)
    yield tabs
    tabs.close()
    tabs.deleteLater()
    app.processEvents()


def own_paint(tabs):
    image = QImage(tabs.size(), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    tabs.render(painter, QPoint(), QRegion(), QWidget.RenderFlag(0))
    painter.end()
    return image


def check_paint(tabs):
    image = own_paint(tabs)
    buttons = [b for b in tabs.findChildren(QToolButton) if b.isVisible()]
    for button in buttons:
        rect = button.geometry().intersected(image.rect())
        assert all(image.pixelColor(x,y).alpha() == 0
                   for x in range(rect.left(), rect.right()+1)
                   for y in range(rect.top(), rect.bottom()+1))
    accent = QColor(visual.colors()['accent'])
    points = [QPoint(x,y) for x in range(image.width()) for y in range(8,13)
              if image.pixelColor(x,y) == accent]
    selected = tabs.content_tab_rect(tabs.currentIndex())
    assert all(selected.contains(p) for p in points), 'indicator remains over an unrelated tab'
    if selected.right() < 0 or selected.left() >= tabs.width():
        assert not points
    return points


def test_overflow_paint_and_selection_survive_both_scroll_boundaries(strip):
    changes = QSignalSpy(strip.currentChanged)
    right = next(b for b in strip.findChildren(QToolButton) if b.arrowType() == Qt.RightArrow)
    left = next(b for b in strip.findChildren(QToolButton) if b.arrowType() == Qt.LeftArrow)
    assert check_paint(strip)
    for button in (right, left):
        for _ in range(strip.count()+2):
            if not button.isEnabled(): break
            QTest.mouseClick(button, Qt.LeftButton)
            QApplication.processEvents()
            check_paint(strip)
        assert not button.isEnabled()
    assert changes.count() == 0 and strip.currentIndex() == 0
    assert check_paint(strip)


def test_selection_animation_retargets_after_scroll_resize_and_tab_changes(strip):
    strip.setCurrentIndex(3)
    right = next(b for b in strip.findChildren(QToolButton) if b.arrowType() == Qt.RightArrow)
    QTest.mouseClick(right, Qt.LeftButton)
    QTest.qWait(200)
    check_paint(strip)
    strip.setFocus()
    QTest.keyClick(strip, Qt.Key_Right)
    assert strip.currentIndex() == 4
    QTest.qWait(200)
    check_paint(strip)
    for width in (300, 820, 460):
        strip.resize(width, 43)
        QApplication.processEvents()
        check_paint(strip)
    strip.set_tabs(['One', 'Two'], 1)
    QTest.qWait(200)
    assert check_paint(strip)
    assert not any(b.isVisible() for b in strip.findChildren(QToolButton))
    QTest.mouseClick(strip, Qt.LeftButton, pos=strip.tabRect(0).center())
    assert strip.currentIndex() == 0


def test_stationary_pointer_highlight_tracks_visible_tab_after_scroll(strip, monkeypatch):
    pointer = QPoint(215, 21)
    global_pointer = strip.mapToGlobal(pointer)
    monkeypatch.setattr(QCursor, 'pos', staticmethod(lambda: global_pointer))
    QApplication.sendEvent(strip, QEnterEvent(QPointF(pointer), QPointF(pointer), QPointF(global_pointer)))
    right = next(b for b in strip.findChildren(QToolButton) if b.arrowType() == Qt.RightArrow)
    hovered = []
    for _ in range(5):
        own_paint(strip)
        hovered.append(strip._hovered_tab)
        assert strip._hovered_tab == strip.tabAt(pointer)
        QTest.mouseClick(right, Qt.LeftButton)
        QApplication.processEvents()
    assert len(set(hovered)) > 1
    # The scroll button itself is outside the tab paint region.
    button_pointer = right.geometry().center()
    monkeypatch.setattr(QCursor, 'pos', staticmethod(lambda: strip.mapToGlobal(button_pointer)))
    own_paint(strip)
    assert strip._hovered_tab == -1


def test_wheel_scrolls_visible_tabs_without_selecting_or_reloading(strip):
    changes = QSignalSpy(strip.currentChanged)
    initial = strip.tabRect(0).x()
    point = QPointF(215, 20)

    def send(angle=QPoint(), pixels=QPoint()):
        wheel = QWheelEvent(point, QPointF(strip.mapToGlobal(point.toPoint())), pixels, angle,
                            Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
        QApplication.sendEvent(strip, wheel)
        QApplication.processEvents()
        assert wheel.isAccepted()

    send(angle=QPoint(0, -120))
    assert strip.tabRect(0).x() < initial
    after_notch = strip.tabRect(0).x()
    for _ in range(4):
        send(pixels=QPoint(0, -10))
    assert strip.tabRect(0).x() == after_notch
    send(pixels=QPoint(0, -10))
    assert strip.tabRect(0).x() < after_notch
    assert strip.currentIndex() == 0 and changes.count() == 0
    check_paint(strip)

    for _ in range(strip.count()+2):
        send(angle=QPoint(0, 120))
    assert strip.tabRect(0).x() == initial
    assert strip.currentIndex() == 0 and changes.count() == 0


def test_existing_scroll_buttons_show_hover_press_and_real_disabled_state(strip):
    right = next(b for b in strip.findChildren(QToolButton) if b.arrowType() == Qt.RightArrow)
    left = next(b for b in strip.findChildren(QToolButton) if b.arrowType() == Qt.LeftArrow)
    assert not left.isEnabled() and left.cursor().shape() == Qt.ArrowCursor
    assert right.isEnabled() and right.cursor().shape() == Qt.PointingHandCursor
    QTest.mouseMove(strip, QPoint(220, 20))
    QApplication.processEvents()
    normal = right.grab().toImage().pixelColor(10, 21)
    QTest.mouseMove(right, right.rect().center())
    QApplication.processEvents()
    hover = right.grab().toImage().pixelColor(10, 21)
    QTest.mousePress(right, Qt.LeftButton, pos=right.rect().center())
    QApplication.processEvents()
    pressed = right.grab().toImage().pixelColor(10, 21)
    QTest.mouseRelease(right, Qt.LeftButton, pos=right.rect().center())
    assert normal != hover != pressed
    assert left.isEnabled() and left.cursor().shape() == Qt.PointingHandCursor
    check_paint(strip)


def test_scroll_hover_is_inset_but_full_button_remains_clickable(strip):
    right = next(b for b in strip.findChildren(QToolButton) if b.arrowType() == Qt.RightArrow)
    size = right.size()
    QTest.mouseMove(right, right.rect().center())
    QApplication.processEvents()
    hover = right.grab().toImage()
    assert hover.pixelColor(2, 21).alpha() > 0
    assert hover.pixelColor(2, 2).alpha() == 0
    assert hover.pixelColor(2, size.height() - 3).alpha() == 0
    for y in (2, size.height() - 3):
        before = strip.tabRect(0).x()
        QTest.mouseClick(right, Qt.LeftButton, pos=QPoint(size.width() // 2, y))
        QApplication.processEvents()
        assert strip.tabRect(0).x() < before
    assert right.size() == size


def test_selected_rule_tracks_full_body_through_switch_scroll_resize(strip,monkeypatch):
    def matches():
        strip.grab()  # drive the existing geometry synchronization path
        body=strip.content_tab_rect(strip.currentIndex())
        target=strip._target_line()
        if strip._tab_viewport().intersects(body):
            assert target.left()==body.left()+8 and target.width()==max(0,body.width()-16)
            assert target.top()==9
        else:assert target.isEmpty()
    matches()
    for index in (1,3,0):
        strip.setCurrentIndex(index);QTest.qWait(210);matches()
        assert strip._line_rect==strip._target_line()
    right=next(b for b in strip._scroll_buttons if b.arrowType()==Qt.RightArrow)
    for _ in range(4):
        right.click();QApplication.processEvents();matches()
    strip.resize(680,43);QApplication.processEvents();matches()
    strip.set_tabs(['Short','Much longer category title'],1);QTest.qWait(210);matches()
    assert strip._target_line().width()>38
    from PySide6.QtCore import QRect
    monkeypatch.setattr(strip,'content_tab_rect',lambda index:QRect(0,0,12,43))
    assert strip._target_line().width()==0  # no negative line on an exceptionally narrow body
