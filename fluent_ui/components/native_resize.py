"""Share host edge geometry with native children without intercepting content."""
import ctypes
from ctypes import wintypes

import win32con
import win32gui
from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication, QWidget

from fluent_ui import visual


def resize_hit(window, hwnd, position):
    """Existing host contract: message screen coordinates, eight DPI-aware edges."""
    frame = win32gui.GetWindowRect(hwnd)
    x = ctypes.c_short(position & 0xffff).value - frame[0]
    y = ctypes.c_short((position >> 16) & 0xffff).value - frame[1]
    corner = round(visual.WINDOW_RADIUS * window.devicePixelRatioF())
    width, height = frame[2]-frame[0], frame[3]-frame[1]
    left, right = 0 <= x < corner, width-corner <= x < width
    top, bottom = 0 <= y < corner, height-corner <= y < height
    hit = (win32con.HTTOPLEFT if left and top else
           win32con.HTTOPRIGHT if right and top else
           win32con.HTBOTTOMLEFT if left and bottom else
           win32con.HTBOTTOMRIGHT if right and bottom else None)
    edge = max(1, round(window.BORDER_WIDTH * window.devicePixelRatioF()))
    if hit is None:
        hit = (win32con.HTLEFT if 0 <= x < edge else
               win32con.HTRIGHT if width-edge <= x < width else
               win32con.HTTOP if 0 <= y < edge else
               win32con.HTBOTTOM if height-edge <= y < height else
               win32con.HTCLIENT)
    return hit


class _NativeChildEdges(QAbstractNativeEventFilter):
    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) not in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message != win32con.WM_NCHITTEST:
            return False, 0
        child = QWidget.find(int(msg.hWnd))
        if child is None or child.isWindow():
            return False, 0
        from fluent_ui.window_shell import NekoriWindow
        host = child.window()
        if (not isinstance(host, NekoriWindow) or not host._isResizeEnabled
                or host.isMaximized() or host.isFullScreen()):
            return False, 0
        if resize_hit(host, int(host.internalWinId()), msg.lParam) != win32con.HTCLIENT:
            # Windows continues hit testing beneath a transparent child in the
            # same UI thread. The real host then owns the system sizing loop.
            return True, win32con.HTTRANSPARENT
        return False, 0


def install_native_child_edges():
    app = QApplication.instance()
    if app.platformName() == 'windows' and not hasattr(app, '_nekori_child_edges'):
        app._nekori_child_edges = _NativeChildEdges()
        app.installNativeEventFilter(app._nekori_child_edges)
