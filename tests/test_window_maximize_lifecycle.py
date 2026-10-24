"""Windows regression: close/reopen must not switch the native surface type."""
import ctypes
import subprocess
import sys
import types
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Win32 lifecycle')


@pytest.fixture
def host(monkeypatch):
    app = QApplication.instance() or QApplication([])
    if app.platformName() != 'windows':
        pytest.skip('Requires the real Windows Qt platform')
    # Match the fixed Demo: do not load the protected W-01 worktree experiments.
    repo = Path(__file__).resolve().parents[1]
    for short in ('materials', 'window_shell'):
        name = 'fluent_ui.' + short
        module = types.ModuleType(name)
        source = subprocess.check_output(['git', 'show', ':' + name.replace('.', '/') + '.py'], cwd=repo)
        monkeypatch.setitem(sys.modules, name, module)
        exec(compile(source, name + '.py', 'exec'), module.__dict__)
    shell = sys.modules['fluent_ui.window_shell']
    window = shell.NekoriWindow()
    window.setTitleBar(shell.NekoriTitleBar(window))
    layout = QVBoxLayout(window)
    content = QWidget(window)
    layout.addWidget(content)
    window.resize(850, 610)
    window.show()
    QTest.qWait(100)
    yield window, content
    window.close()
    window.deleteLater()
    app.processEvents()


def test_reopened_maximize_has_matching_native_and_content_geometry(host):
    import win32con
    import win32gui
    window, content = host
    for reopened in (False, True):
        if reopened:
            window.close()
            QTest.qWait(30)
            window.show()
            QTest.qWait(80)
        normal = window.geometry()
        assert window.windowHandle().format().alphaBufferSize() < 0
        QTest.mouseClick(window.titleBar.maxBtn, Qt.LeftButton)
        QTest.qWait(150)
        hwnd = int(window.winId())
        assert window.isMaximized() and ctypes.windll.user32.IsZoomed(hwnd)
        client = win32gui.GetClientRect(hwnd)
        scale = window.devicePixelRatioF()
        assert (round(window.width()*scale), round(window.height()*scale)) == client[2:]
        margins = window.layout().contentsMargins()
        assert content.width() == window.width() - margins.left() - margins.right()
        assert content.height() == window.height() - margins.top() - margins.bottom()
        QTest.mouseClick(window.titleBar.maxBtn, Qt.LeftButton)
        QTest.qWait(150)
        assert not window.isMaximized() and window.geometry() == normal


def test_reopened_double_click_hide_restore_and_eight_resize_hits(host):
    import win32con
    import win32gui
    window, _ = host
    window.close()
    window.show()
    QTest.qWait(80)
    hwnd = int(window.winId())
    x, y, r, b = win32gui.GetWindowRect(hwnd)
    points = [(x+1,y+1,13),(r-2,y+1,14),(x+1,b-2,16),(r-2,b-2,17),
              (x+1,(y+b)//2,10),(r-2,(y+b)//2,11),((x+r)//2,y+1,12),((x+r)//2,b-2,15)]
    for px, py, hit in points:
        assert win32gui.SendMessage(hwnd, win32con.WM_NCHITTEST, 0,
                                   ((py & 65535) << 16) | (px & 65535)) == hit
    window.hide()
    window.show()
    QTest.mouseDClick(window.titleBar, Qt.LeftButton, pos=QPoint(120, 18))
    QTest.qWait(150)
    assert window.isMaximized()
    QTest.mouseDClick(window.titleBar, Qt.LeftButton, pos=QPoint(120, 18))
    QTest.qWait(150)
    assert not window.isMaximized()
