"""Actual receiving HWND matters: a native child must not swallow host edges."""
import pytest
import win32con
import win32gui
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_window_maximize_lifecycle import host as committed_host


@pytest.fixture
def native_children(committed_host):
    # Match the fixed Demo: reuse the #57 fixture's reviewed index modules,
    # rather than silently exercising the protected W-01 worktree experiments.
    host, body = committed_host
    app = QApplication.instance()
    host.setAttribute(Qt.WA_ShowWithoutActivating)
    host.setGeometry(80, 100, 680, 440)
    host.layout().setContentsMargins(0, 34, 0, 0)
    host.layout().activate()
    body.winId()
    host.titleBar.winId()
    host.show()
    app.processEvents()
    yield app, host, body


@pytest.mark.parametrize('fx,fy,expected', [
    (0,.5,10),(1,.5,11),(.5,0,12),(.5,1,15),
    (0,0,13),(1,0,14),(0,1,16),(1,1,17),
])
def test_native_child_edges_defer_to_resizable_host(native_children, fx, fy, expected):
    app, host, body = native_children
    hwnd = int(host.winId())
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    inset = 7 if fx in (0,1) and fy in (0,1) else 2
    x = left+inset if fx == 0 else right-inset-1 if fx == 1 else (left+right)//2
    y = top+inset if fy == 0 else bottom-inset-1 if fy == 1 else (top+bottom)//2
    receiver = win32gui.ChildWindowFromPoint(hwnd, win32gui.ScreenToClient(hwnd, (x,y)))
    assert receiver != hwnd
    position = ((y & 0xffff) << 16) | (x & 0xffff)
    assert win32gui.SendMessage(receiver, win32con.WM_NCHITTEST, 0, position) == win32con.HTTRANSPARENT
    assert win32gui.SendMessage(hwnd, win32con.WM_NCHITTEST, 0, position) == expected


def test_native_child_content_and_maximized_window_are_not_resize_edges(native_children):
    app, host, body = native_children
    child = int(body.winId())
    point = body.mapToGlobal(body.rect().center())
    position = ((point.y() & 0xffff) << 16) | (point.x() & 0xffff)
    assert win32gui.SendMessage(child, win32con.WM_NCHITTEST, 0, position) == win32con.HTCLIENT
    host.showMaximized()
    app.processEvents()
    left, top, right, bottom = win32gui.GetWindowRect(int(host.winId()))
    position = ((((top+bottom)//2) & 0xffff) << 16) | ((left+2) & 0xffff)
    assert win32gui.SendMessage(child, win32con.WM_NCHITTEST, 0, position) != win32con.HTTRANSPARENT


def test_native_caption_double_click_releases_its_child_capture(native_children):
    app, host, body = native_children
    bar = host.titleBar
    win32gui.SetCapture(int(bar.winId()))
    position = QPointF(180, 18)
    event = QMouseEvent(QEvent.MouseButtonDblClick, position,
                        QPointF(bar.mapToGlobal(position.toPoint())),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    app.sendEvent(bar, event)
    QTest.qWait(80)
    assert host.isMaximized()
    assert not win32gui.GetCapture()
