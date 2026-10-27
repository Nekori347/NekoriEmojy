"""Client cursors belong to Qt, not the host edge-cursor reset."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import ctypes
from ctypes import wintypes
import pytest
import win32con
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QWidget
from qframelesswindow import FramelessWindow
from fluent_ui.window_shell import NekoriWindow

@pytest.mark.parametrize('shape,override',[(Qt.PointingHandCursor,False),(Qt.IBeamCursor,False),(Qt.ArrowCursor,True)])
def test_client_setcursor_does_not_replace_qt_cursor(monkeypatch,shape,override):
    app=QApplication.instance() or QApplication([])
    # The real host method with a minimal Qt instance isolates message dispatch
    # from DWM/regions, which are not part of the client-cursor responsibility.
    host=NekoriWindow.__new__(NekoriWindow);QWidget.__init__(host)
    host._native_message=wintypes.MSG();host._native_state_log=None
    host.setCursor(shape)
    if override:app.setOverrideCursor(Qt.WaitCursor)
    calls=[];backend=[]
    monkeypatch.setattr('fluent_ui.window_shell.win32gui.SetCursor',lambda cursor:calls.append(cursor))
    monkeypatch.setattr(FramelessWindow,'nativeEvent',lambda *args:(backend.append(args[1]) or (False,0)))
    msg=wintypes.MSG();msg.message=win32con.WM_SETCURSOR
    msg.lParam=(win32con.WM_MOUSEMOVE<<16)|win32con.HTCLIENT
    result=host.nativeEvent(b'windows_generic_MSG',ctypes.addressof(msg))
    assert calls==[],shape
    assert host.cursor().shape()==shape
    if override:
        assert app.overrideCursor().shape()==Qt.WaitCursor
        app.restoreOverrideCursor()
    assert result==(False,0) and backend==[b'windows_generic_MSG']
    host.deleteLater();app.processEvents()
