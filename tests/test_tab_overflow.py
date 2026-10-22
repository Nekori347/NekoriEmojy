"""Render the real QTabBar overflow path; no replacement scroll model."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QRegion, QCursor, QEnterEvent
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
