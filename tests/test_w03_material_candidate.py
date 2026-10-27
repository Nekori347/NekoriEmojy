"""Exercise the unapplied candidate, never load protected worktree experiments."""
import ctypes
from pathlib import Path
import subprocess
import types
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication

SOURCE=Path(__file__).resolve().parents[1]


@pytest.fixture
def candidate(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    for name in ('materials','window_shell'):
        target=tmp_path/'fluent_ui'/f'{name}.py';target.parent.mkdir(exist_ok=True)
        target.write_bytes(subprocess.check_output(['git','show',f'ae74066:fluent_ui/{name}.py'],cwd=SOURCE))
    subprocess.run(['git','apply','--ignore-space-change',str(SOURCE/'docs/W03_WIN10_MOVE_CANDIDATE.patch')],
                   cwd=tmp_path,check=True,capture_output=True)
    module=types.ModuleType('candidate_materials')
    exec(compile((tmp_path/'fluent_ui/materials.py').read_text(encoding='utf-8'),
                 'candidate_materials.py','exec'),module.__dict__)
    module.sys=types.SimpleNamespace(platform='win32',getwindowsversion=lambda:types.SimpleNamespace(build=19044))
    monkeypatch.setattr(QApplication,'platformName',lambda:'windows')
    module._transparency_allowed=lambda:True
    effects=[];accepted=[True]
    def apply(hwnd,pointer):
        data=pointer._obj
        values=ctypes.cast(data.data,ctypes.POINTER(ctypes.c_int*4)).contents
        effects.append((values[0],values[2]));return accepted[0]
    setter=Mock(side_effect=apply)
    api=types.SimpleNamespace(dwmapi=types.SimpleNamespace(DwmSetWindowAttribute=Mock(return_value=0),
                                DwmExtendFrameIntoClientArea=Mock(return_value=0)),
                             user32=types.SimpleNamespace(SetWindowCompositionAttribute=setter))
    module.ctypes=types.SimpleNamespace(**{name:getattr(ctypes,name) for name in
        ('Structure','c_int','c_void_p','c_size_t','sizeof','byref','addressof','POINTER')},windll=api)
    class Window:
        def __init__(self):self.props={};self.hwnd=123;self.updates=0
        def winId(self):assert self.hwnd;return self.hwnd
        def internalWinId(self):return self.hwnd
        def property(self,key):return self.props.get(key)
        def setProperty(self,key,value):self.props[key]=value
        def update(self):self.updates+=1
        def mask(self):return types.SimpleNamespace(isEmpty=lambda:True)
        def clearMask(self):pytest.fail('candidate changed the window mask')
    return module,Window(),effects,accepted,tmp_path


def test_move_material_transaction_and_ordinary_resize(candidate):
    m,w,effects,_,_=candidate
    m.native_material(w,overlay=True);original=effects[-1]
    m.material_move_message(w,0x112,0xf000|4);m.material_move_message(w,0x231)
    assert effects==[original]  # SC_SIZE is not a title-bar move.
    m.material_move_message(w,0x232)
    m.material_move_message(w,0x112,0xf010|2)
    assert effects==[original]  # Arming does not yet change the material.
    m.material_move_message(w,0x231);m.material_move_message(w,0x231)
    assert [effect[0] for effect in effects]==[4,0]
    assert m.shell_color(w).alpha()==255 and w.hwnd==123
    m.native_material(w,overlay=True)
    assert len(effects)==2  # Existing cache/reapplication cannot re-enable it mid-move.
    m.material_move_message(w,0x232);m.material_move_message(w,0x232)
    assert [effect[0] for effect in effects]==[4,0,4] and effects[-1]==original
    assert m.shell_color(w).alpha()==12


def test_cancel_lifecycle_and_rebuilt_handle(candidate):
    m,w,effects,_,_=candidate;m.native_material(w)
    for end in ('cancel','hide_or_state','hwnd_lost'):
        m.material_move_message(w,0x112,0xf012);m.material_move_message(w,0x231)
        if end=='cancel':m.material_move_message(w,0x1f)
        elif end=='hide_or_state':m.finish_material_move(w)
        else:
            before=len(effects);w.hwnd=0;m.finish_material_move(w)
            assert len(effects)==before  # No winId() call or recreation.
            w.hwnd=456;m.native_material(w)
        assert w.property('nativeMaterial')=='acrylic' and w._material_move is None


def test_api_rejection_and_current_policy_restore(candidate):
    m,w,effects,accepted,_=candidate;m.native_material(w)
    accepted[0]=False
    m.material_move_message(w,0x112,0xf012);m.material_move_message(w,0x231)
    assert w.property('nativeMaterial')=='acrylic' and w._material_move is None
    assert not w.property('nativeMaterialAccepted')
    accepted[0]=True
    m.material_move_message(w,0x112,0xf012);m.material_move_message(w,0x231)
    m._transparency_allowed=lambda:False
    m.material_move_message(w,0x232)
    assert w.property('nativeMaterial')=='opaque'  # Respect changed system policy.
    m._transparency_allowed=lambda:True;m.native_material(w)
    m.material_move_message(w,0x112,0xf012);m.material_move_message(w,0x231)
    accepted[0]=False;m.material_move_message(w,0x232)
    assert w.property('nativeMaterial')=='opaque' and not w.property('nativeMaterialAccepted')
    accepted[0]=True;m.native_material(w)
    assert w.property('nativeMaterial')=='acrylic'


def test_win11_and_static_opaque_have_no_candidate_effect(candidate):
    m,w,effects,_,_=candidate
    m.sys.getwindowsversion=lambda:types.SimpleNamespace(build=26340)
    m.native_material(w);baseline=list(effects)
    for code,param in ((0x112,0xf012),(0x231,0),(0x232,0)):
        m.material_move_message(w,code,param)
    assert effects==baseline and not hasattr(w,'_material_move')
    m.sys.getwindowsversion=lambda:types.SimpleNamespace(build=19044)
    m._transparency_allowed=lambda:False;m.native_material(w);baseline=list(effects)
    m.material_move_message(w,0x112,0xf012);m.material_move_message(w,0x231)
    assert effects==baseline


def test_candidate_host_events_keep_hwnd_mask_and_eight_resize_hits(candidate,monkeypatch):
    import sys
    from ctypes import wintypes
    import win32con,win32gui
    from PySide6.QtCore import QEvent
    from PySide6.QtTest import QTest
    m,_,effects,_,directory=candidate
    monkeypatch.setitem(sys.modules,'fluent_ui.materials',m)
    host=types.ModuleType('candidate_window_shell')
    monkeypatch.setitem(sys.modules,host.__name__,host)
    exec(compile((directory/'fluent_ui/window_shell.py').read_text(encoding='utf-8'),
                 'candidate_window_shell.py','exec'),host.__dict__)
    window=host.NekoriWindow();window.resize(600,420);window.show();QTest.qWait(30)
    try:
        hwnd=int(window.winId());mask=window.mask()
        def message(code,wparam=0,lparam=0):
            msg=wintypes.MSG();msg.hWnd=hwnd;msg.message=code;msg.wParam=wparam;msg.lParam=lparam
            return window.nativeEvent(b'windows_generic_MSG',ctypes.addressof(msg))
        def hits():
            left,top,right,bottom=win32gui.GetWindowRect(hwnd)
            points=((left+1,top+1,win32con.HTTOPLEFT),(right-2,top+1,win32con.HTTOPRIGHT),
                (left+1,bottom-2,win32con.HTBOTTOMLEFT),(right-2,bottom-2,win32con.HTBOTTOMRIGHT),
                (left+1,(top+bottom)//2,win32con.HTLEFT),(right-2,(top+bottom)//2,win32con.HTRIGHT),
                ((left+right)//2,top+1,win32con.HTTOP),((left+right)//2,bottom-2,win32con.HTBOTTOM))
            for x,y,expected in points:
                assert message(win32con.WM_NCHITTEST,0,(x&0xffff)|((y&0xffff)<<16))==(True,expected)
        hits();message(win32con.WM_SYSCOMMAND,win32con.SC_MOVE|win32con.HTCAPTION)
        message(0x231)
        assert window.property('nativeMaterial')=='opaque' and int(window.winId())==hwnd
        hits();assert window.mask()==mask
        message(0x232)
        assert window.property('nativeMaterial')=='acrylic' and int(window.winId())==hwnd
        message(win32con.WM_SYSCOMMAND,win32con.SC_SIZE);before=len(effects)
        message(0x231);message(0x232);assert len(effects)==before
        message(win32con.WM_SYSCOMMAND,win32con.SC_MOVE|win32con.HTCAPTION);message(0x231)
        window.hide();assert window.property('nativeMaterial')=='acrylic'
        window.show();QTest.qWait(20);assert window.property('nativeMaterial')=='acrylic'
    finally:window.close();window.deleteLater();QApplication.instance().processEvents()
