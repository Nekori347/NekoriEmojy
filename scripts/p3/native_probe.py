import ctypes,json,os,sys,traceback
from pathlib import Path
from unittest.mock import patch
work=Path(os.environ['P3_WORK_DIR']).resolve();repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo));os.chdir(repo);os.environ.pop('QT_QPA_PLATFORM',None)
from ctypes import wintypes
shell=ctypes.windll.shell32;shell.SetCurrentProcessExplicitAppUserModelID.argtypes=[ctypes.c_wchar_p];shell.SetCurrentProcessExplicitAppUserModelID('Nekori347.NekoriEmojy.P3Test')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QThread
from PySide6.QtTest import QTest
from services.library import open_library
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from qfluentwidgets import qconfig
import requests
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
session=open_library(work/'ui/library');config=ConfigService(session);store=StorageService(session)
qconfig.file=session.context.data_dir/'cache'/'qt-state.json';i18n_engine.init(config)
config.begin_preview();config.set('always_on_top',False);config.set('appearance_mode','light')
report={'platform':app.platformName(),'scope':'native Qt window and WM_GETICON; final EXE and actual login startup not tested','checks':[]}
errors=[];sys.excepthook=lambda *exc:errors.append(str(exc[1]))
user=ctypes.windll.user32
user.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM];user.SendMessageW.restype=ctypes.c_ssize_t
window=None
with patch('requests.sessions.Session.request',side_effect=requests.ConnectionError('isolated')),patch('fluent_ui.main_window.MainWindow.bind_global_hotkey'):
    try:
        from fluent_ui.main_window import MainWindow
        window=MainWindow(store,ClipboardService(config),config)
        window.setAttribute(Qt.WA_ShowWithoutActivating);window.setGeometry(40,60,860,640);window.show();window.apply_preferences();QTest.qWait(500)
        def icons():return [int(user.SendMessageW(int(window.winId()),0x007F,kind,0)) for kind in (0,1)]
        before=icons();config.set('runtime_icon',Path(store.get_all_images()[0]).name);window.apply_runtime_icon();QTest.qWait(150);after=icons()
        assert all(after) and after!=before;report['checks'].append('native small/big window icons updated')
        window.settings_window.show();QTest.qWait(250)
        assert window.settings_window.isWindow() and not window.settings_window.isModal()
        window.settings_window.grab().save(str(work/'p3-native-settings-light.png'))
        config.set('appearance_mode','dark');window.apply_preferences();QTest.qWait(180)
        window.settings_window.grab().save(str(work/'p3-native-settings-dark.png'))
        report['checks'].append('independent settings rendered in light and dark themes')
        window.settings_window.hide();window.gallery_interface.sidebar.set_active_category('日常');QTest.qWait(200)
        window.grab().save(str(work/'p3-native-groups.png'))
        config.set('runtime_icon','missing.png');window.apply_runtime_icon();QTest.qWait(100)
        assert all(icons());report['checks'].append('missing library image falls back to native default icon')
    except Exception:report['error']=traceback.format_exc()
    finally:
        if window:
            for thread in window.findChildren(QThread):thread.wait(5000)
            window.settings_window.close();window.close();window.quick_panel.close();QTest.qWait(50)
        session.close()
report['qt_errors']=errors;report['passed']='error' not in report and not errors
(work/'p3-native.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
