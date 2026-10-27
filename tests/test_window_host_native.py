"""Real HWND regression: Qt flag changes must preserve edge resizing.
Run separately with QT_QPA_PLATFORM=windows; never touches a library.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import win32con
import win32gui
from fluent_ui.window_shell import NekoriWindow, NekoriTitleBar

@pytest.fixture
def host():
    app = QApplication.instance() or QApplication([])
    if app.platformName() != 'windows':
        pytest.skip('requires the native Windows platform')
    window = NekoriWindow()
    window.setTitleBar(NekoriTitleBar(window))
    window.resize(640, 360)
    window.setAttribute(Qt.WA_ShowWithoutActivating)
    window.show()
    app.processEvents()
    yield window
    window.close()
    window.deleteLater()
    app.processEvents()

@pytest.mark.parametrize('transition', ['flags', 'close'])
def test_native_frame_survives_flag_rewrite_or_close_reopen(host, transition):
    hwnd = int(host.winId())
    if transition == 'flags':
        host.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    else:
        host.close()
    host.show()
    QApplication.processEvents()
    assert win32gui.GetWindowLong(int(host.winId()), win32con.GWL_STYLE) & win32con.WS_THICKFRAME

def test_edge_hit_uses_message_coordinates_after_flag_rewrite(host):
    host.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    host.show()
    QApplication.processEvents()
    hwnd = int(host.winId())
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    cx, cy = (left+right)//2, (top+bottom)//2
    inset = round(6*host.devicePixelRatioF())
    points = [(left+2,cy,10), (right-3,cy,11), (cx,top+2,12), (cx,bottom-3,15),
              (left+inset,top+inset,13), (right-inset-1,top+inset,14),
              (left+inset,bottom-inset-1,16), (right-inset-1,bottom-inset-1,17)]
    # No physical cursor movement: queued native coordinates must be authoritative.
    for x,y,expected in points:
        actual = win32gui.SendMessage(hwnd,win32con.WM_NCHITTEST,0,((y&0xffff)<<16)|(x&0xffff))
        assert actual == expected
