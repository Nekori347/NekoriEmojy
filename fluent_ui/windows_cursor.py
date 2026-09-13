"""Windows client cursor repair, adapted after reviewing upstream efc0103.

WM_SETCURSOR's hit test is LOWORD(lParam), not wParam (which is HWND).
Only this window's client area is handled. Qt widget/override cursor semantics
are preserved; native resize borders and mouse capture stay with Qt/Windows.
"""
import ctypes
from ctypes import wintypes
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from services.diagnostics import event

user32 = ctypes.windll.user32
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = ctypes.c_void_p
user32.SetCursor.argtypes = [ctypes.c_void_p]
user32.SetCursor.restype = ctypes.c_void_p
user32.GetCapture.restype = wintypes.HWND

_SYSTEM_CURSORS = {
    Qt.ArrowCursor: 32512, Qt.IBeamCursor: 32513, Qt.WaitCursor: 32514,
    Qt.CrossCursor: 32515, Qt.SizeFDiagCursor: 32642, Qt.SizeBDiagCursor: 32643,
    Qt.SizeHorCursor: 32644, Qt.SizeVerCursor: 32645, Qt.SizeAllCursor: 32646,
    Qt.ForbiddenCursor: 32648, Qt.PointingHandCursor: 32649,
    Qt.BusyCursor: 32650, Qt.WhatsThisCursor: 32651,
}
_HANDLES = {}


def native_message(message):
    return wintypes.MSG.from_address(int(message))


def restore_client_cursor(window, msg):
    if msg.message != 0x20 or (msg.lParam & 0xffff) != 1 or user32.GetCapture():
        return False
    position = QCursor.pos()
    widget = QApplication.widgetAt(position)
    if widget is None or widget.window() is not window:
        return False
    cursor = QApplication.overrideCursor() or widget.cursor()
    shape = cursor.shape()
    if shape == Qt.BlankCursor:
        handle = None
    elif shape in _SYSTEM_CURSORS:
        if shape not in _HANDLES:
            _HANDLES[shape] = user32.LoadCursorW(None, _SYSTEM_CURSORS[shape])
        handle = _HANDLES[shape]
        if not handle:
            return False
    else:
        # Custom pixmaps/open-hand/drag cursors remain managed by Qt.
        return False
    user32.SetCursor(handle)
    event('window.client_cursor', detailed=True, throttle=0.1,
          count={'hit': 1, 'qt_shape': shape.value, 'dpi_percent': round(window.devicePixelRatioF()*100)})
    return True
