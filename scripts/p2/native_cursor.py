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
os.environ['NEKORI_BOOTSTRAP_DIR']=str(work/'p2-native-bootstrap-1')
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
context=create_library(work/'p2-native-library-1');session=open_library(context.root)
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
        for mode in ['without_client_repair','with_client_repair']:
            cursor_module.restore_client_cursor=(lambda *args:False) if mode=='without_client_repair' else real_restore
            for name,point in positions:
                QCursor.setPos(point);QTest.qWait(85)
                info=CURSORINFO();info.cbSize=ctypes.sizeof(info);user32.GetCursorInfo(ctypes.byref(info))
                native_point=info.ptScreenPos
                packed=(native_point.x&0xffff)|((native_point.y&0xffff)<<16)
                hit=user32.SendMessageW(hwnd,0x84,0,packed)
                report['samples'].append({'mode':mode,'target':name,'hit':hit,'cursor':next((n for n,h in handles.items() if h==info.hCursor),'other'),'qt_widget':type(app.widgetAt(QCursor.pos())).__name__})
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
report['limitations']=['single current monitor layout only','no physical drag-resize or suspend/resume','source run, not packaged EXE']
(work/'p2-native-cursor-1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
