"""Native cursor probe on a synthetic library and a task-owned MainWindow only."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch
work=Path(os.environ['P2_WORK_DIR']).resolve();work.mkdir(parents=True,exist_ok=True)
repo=Path(__file__).resolve().parents[2]
os.chdir(repo);sys.path.insert(0,str(repo))
os.environ.pop('QT_QPA_PLATFORM',None)
os.environ['NEKORI_BOOTSTRAP_DIR']=str(work/'p2-native-bootstrap-2')
from PySide6.QtCore import QPoint,Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication,QLineEdit,QLabel
from PySide6.QtTest import QTest
from services.library import create_library,open_library
from services.storage import StorageService
from services.config import ConfigService
from services.clipboard import ClipboardService
from fluent_ui.main_window import MainWindow
import fluent_ui.windows_cursor as cursor_module
import requests
user32=ctypes.windll.user32
user32.GetForegroundWindow.restype=wintypes.HWND
user32.SetForegroundWindow.argtypes=[wintypes.HWND]
user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user32.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
user32.SendMessageW.restype=wintypes.LPARAM
class CURSORINFO(ctypes.Structure):
    _fields_=[('cbSize',wintypes.DWORD),('flags',wintypes.DWORD),('hCursor',wintypes.HANDLE),('ptScreenPos',wintypes.POINT)]
user32.GetCursorInfo.argtypes=[ctypes.POINTER(CURSORINFO)]
app=QApplication([])
original_position=QCursor.pos()
original_foreground=user32.GetForegroundWindow()
report={'platform':app.platformName(),'samples':[],'screens':[{'size':[s.geometry().width(),s.geometry().height()],'ratio':s.devicePixelRatio(),'dpi':s.logicalDotsPerInch()} for s in app.screens()], 'hotkeys':'disabled','source':'synthetic library only'}
context=create_library(work/'p2-native-library-2');session=open_library(context.root)
window=None
handles={name:user32.LoadCursorW(None,value) for name,value in {'arrow':32512,'ibeam':32513,'horizontal':32644,'vertical':32645,'hand':32649,'nwse':32642,'nesw':32643}.items()}
real_restore=cursor_module.restore_client_cursor
try:
    with patch('requests.sessions.Session.request',side_effect=requests.ConnectionError('isolated')),patch.object(MainWindow,'bind_global_hotkey'):
        config=ConfigService(session)
        window=MainWindow(StorageService(session),ClipboardService(config),config)
        window.resize(1080,760);window.move(140,120)
        window.show();window.raise_();window.activateWindow()
        text=QLineEdit('Native cursor verification',window);text.setGeometry(250,200,330,35);text.show();text.raise_()
        link=QLabel('Native link verification',window);link.setGeometry(250,250,330,35);link.setCursor(Qt.PointingHandCursor);link.show();link.raise_()
        QTest.qWait(1000)
        hwnd=int(window.winId())
        rect=wintypes.RECT();user32.GetWindowRect(hwnd,ctypes.byref(rect))
        report['native_rect']=[rect.left,rect.top,rect.right,rect.bottom]
        report['window_ratio']=window.devicePixelRatioF()
        center=((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
        def global_center(widget):
            point=widget.mapToGlobal(widget.rect().center())
            # QCursor operates in Qt logical coordinates; native positions are queried after movement.
            return point
        positions=[('left',QPoint(window.frameGeometry().left()+1,window.frameGeometry().center().y())),
                   ('content',window.mapToGlobal(QPoint(750,360))),
                   ('top',QPoint(window.frameGeometry().center().x(),window.frameGeometry().top()+1)),
                   ('title',window.mapToGlobal(QPoint(480,22))),
                   ('right',QPoint(window.frameGeometry().right()-1,window.frameGeometry().center().y())),
                   ('text',global_center(text)),
                   ('bottom',QPoint(window.frameGeometry().center().x(),window.frameGeometry().bottom()-1)),
                   ('link',global_center(link)),
                   ('top_left',window.frameGeometry().topLeft()+QPoint(1,1)),
                   ('content',window.mapToGlobal(QPoint(750,360)))]
        report['scenario']='explicit stale-resize-cursor injection; not natural reproduction'
        report['parsed_message_type']='ctypes.wintypes.MSG from native pointer'
        for label,widget,expected in [('text',text,'ibeam'),('link',link,'hand'),('title',window.titleBar,'arrow')]:
            point=widget.mapToGlobal(widget.rect().center())
            QCursor.setPos(point);QTest.qWait(150)
            if QCursor.pos()!=point or app.widgetAt(point).window() is not window:
                raise RuntimeError('probe interrupted by pointer/window change')
            msg=wintypes.MSG();msg.hwnd=hwnd;msg.message=0x20;msg.wParam=hwnd;msg.lParam=1|(0x200<<16)
            parsed=cursor_module.native_message(ctypes.addressof(msg))
            assert parsed.wParam==hwnd and parsed.lParam & 0xffff == 1
            user32.SetCursor(handles['horizontal'])
            before=CURSORINFO();before.cbSize=ctypes.sizeof(before);user32.GetCursorInfo(ctypes.byref(before))
            handled=real_restore(window,parsed)
            after=CURSORINFO();after.cbSize=ctypes.sizeof(after);user32.GetCursorInfo(ctypes.byref(after))
            actual=next((n for n,h in handles.items() if h==after.hCursor),'other')
            report['samples'].append({'target':label,'before':'horizontal' if before.hCursor==handles['horizontal'] else 'other','handled':handled,'expected':expected,'actual':actual,'passed':handled and actual==expected})
        # An edge message must remain delegated to Windows/Qt.
        msg.lParam=10|(0x200<<16)
        report['edge_delegated']=real_restore(window,msg) is False
        cursor_module.restore_client_cursor=real_restore
        window.showMaximized();QTest.qWait(150)
        QCursor.setPos(global_center(text));QTest.qWait(100)
        info=CURSORINFO();info.cbSize=ctypes.sizeof(info);user32.GetCursorInfo(ctypes.byref(info))
        report['maximized_text_cursor']=next((n for n,h in handles.items() if h==info.hCursor),'other')
        window.showNormal();QTest.qWait(150)
        report['normal_restored']=not window.isMaximized()
except Exception:
    report['error']=traceback.format_exc()
finally:
    cursor_module.restore_client_cursor=real_restore
    if window is not None:
        window.hide()
        window.quick_panel.hide()
        window.deleteLater()
        app.processEvents()
    QCursor.setPos(original_position)
    if original_foreground:
        user32.SetForegroundWindow(original_foreground)
    session.close()
report['limitations']=['first monitor at 96 DPI only; two screens detected','no physical drag-resize or suspend/resume','source run, not packaged EXE']
(work/'p2-native-cursor-2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

sys.exit(0 if "error" not in report and all(item["passed"] for item in report["samples"]) and len(report["samples"]) == 3 and report.get("edge_delegated") else 1)
