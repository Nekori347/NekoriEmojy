import sys
import os
import glob
import warnings


def _lock_ffmpeg_path_for_frozen_app():
    """在 Nuitka/PyInstaller 冻结环境中锁定随程序发布的 FFmpeg。"""
    is_frozen = bool(getattr(sys, "frozen", False) or globals().get("__compiled__"))
    if not is_frozen:
        return

    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    pattern = os.path.join(
        executable_dir,
        "imageio_ffmpeg",
        "binaries",
        "ffmpeg*.exe",
    )
    ffmpeg_candidates = sorted(glob.glob(pattern))
    if ffmpeg_candidates:
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_candidates[0]
        print(f"[INFO] Locked FFmpeg executable: {ffmpeg_candidates[0]}")
    else:
        print(f"[WARNING] Bundled FFmpeg executable not found under: {os.path.dirname(pattern)}")


_lock_ffmpeg_path_for_frozen_app()

# 忽略 requests 与 urllib3 版本轻微不兼容产生的非致命警告
try:
    from requests.exceptions import RequestsDependencyWarning
    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    if sys.platform == 'win32':
        import ctypes
        identify = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        identify.argtypes = [ctypes.c_wchar_p]
        identify.restype = ctypes.c_long
        identify('Nekori347.NekoriEmojy')
    app = QApplication(sys.argv)
    
    from PySide6.QtCore import QSharedMemory
    shared_memory = QSharedMemory("NekoriEmojy_App_Instance")
    if not shared_memory.create(1):
        sys.exit(0)
    
    next_path = None
    while True:
        next_path = _run_library_session(app, next_path)
        if next_path is None:
            break
    shared_memory.detach()


def _run_library_session(app, requested=None):
    from services.config import ConfigService
    from services.library import BootstrapStore
    from services.diagnostics import configure, install_exception_hooks, event
    from fluent_ui.library_dialog import choose_session
    bootstrap = BootstrapStore()
    diagnostics = configure(bootstrap.directory / "logs")
    install_exception_hooks()
    app.next_library = None
    if requested is None and "--library" in sys.argv:
        index = sys.argv.index("--library")
        if index + 1 < len(sys.argv):
            requested = sys.argv[index + 1]
    session = choose_session(bootstrap, requested)
    if session is None:
        diagnostics.close()
        return None
    try:
        bootstrap.remember(session.context)
    except OSError as exc:
        event("bootstrap.save_failed", level="warning", error=exc)
    diagnostics = configure(session.context.data_dir / "logs", session.context)
    event("application.startup", status="connected")
    config_service = ConfigService(session)
    from qfluentwidgets import qconfig
    # Fluent's derived theme state is expendable; user preferences remain in DB.
    qconfig.file = session.context.data_dir / "cache" / "qt-state.json"
    
    app_font = app.font()
    if app_font.pointSize() <= 0:
        app_font.setPointSize(9)
        app.setFont(app_font)

    if config_service.get("use_system_font", False):
        try:
            system_font = app.font().family()
            if system_font:
                from qfluentwidgets import setFontFamilies
                setFontFamilies([system_font])
        except Exception as e:
            print(f"Failed to set system font: {e}")
            
    from PySide6.QtWidgets import QSystemTrayIcon
    from PySide6.QtGui import QIcon
    from qfluentwidgets import setTheme, Theme, RoundMenu, Action
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine, t
    
    app.setQuitOnLastWindowClosed(False)
    
    from fluent_ui.main_window import MainWindow

    # Old formats are read only by the explicit isolated migration workflow.
    # Startup never scans/hash-deduplicates or cleans the selected library.
    storage_service = StorageService(session)
    clipboard_service = ClipboardService(config_service)
    
    # 初始化多语言引擎
    i18n_engine.init(config_service)
    
    # 外观模式使用 appearance_mode；兼容旧版本保存的 theme_mode
    theme_mode = config_service.get(
        "appearance_mode",
        config_service.get("theme_mode", "system"),
    )
    if theme_mode == "dark":
        setTheme(Theme.DARK)
    elif theme_mode == "light":
        setTheme(Theme.LIGHT)
    else:
        setTheme(Theme.AUTO)

    app.library_session = session
    app.bootstrap_store = bootstrap
    app.diagnostics = diagnostics
    window = MainWindow(storage_service, clipboard_service, config_service)
    
    tray_icon = QSystemTrayIcon()
    if getattr(sys, 'frozen', False):
        icon_dir = sys._MEIPASS
    else:
        icon_dir = os.path.dirname(__file__)
    icon_path = os.path.join(icon_dir, "ico.ico")
    if os.path.exists(icon_path):
        tray_icon.setIcon(QIcon(icon_path))
        window.setWindowIcon(QIcon(icon_path))
    else:
        pass
    
    window.apply_runtime_icon()
    window.title_settings.setVisible(config_service.get("show_setting_button", True))
    tray_icon.setToolTip("NekoriEmojy")
    
    tray_menu = RoundMenu()
    
    show_action = Action(t("显示主面板"), triggered=window.show_gallery)
    tray_menu.addAction(show_action)
    
    def open_settings():
        window.show_settings()
        
    settings_action = Action(t("设置"), triggered=open_settings)
    tray_menu.addAction(settings_action)
    
    tray_menu.addSeparator()
    
    def quit_when_idle():
        from fluent_ui.library_panel import running_window_jobs
        from PySide6.QtWidgets import QMessageBox
        if running_window_jobs(window):
            QMessageBox.information(window, "正在处理任务", "请等待后台任务结束后退出。")
            return
        try:
            with session.maintenance():
                pass
        except Exception:
            return
        app.quit()
    quit_action = Action(t("退出"), triggered=quit_when_idle)
    tray_menu.addAction(quit_action)
    
    # 动态刷新托盘菜单文案
    def update_tray_texts(lang):
        show_action.setText(t("显示主面板"))
        settings_action.setText(t("设置"))
        quit_action.setText(t("退出"))
    i18n_engine.language_changed.connect(update_tray_texts)
    
    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.Trigger or reason == QSystemTrayIcon.DoubleClick:
            window.show_gallery()
        elif reason == QSystemTrayIcon.Context:
            from PySide6.QtGui import QCursor
            tray_menu.exec(QCursor.pos())
            
    tray_icon.activated.connect(on_tray_activated)
    tray_icon.show()
    
    window.show()
    
    
    app.library_session = session
    app.bootstrap_store = bootstrap
    app.diagnostics = diagnostics
    exit_code = app.exec()
    if getattr(window, "hotkey_listener", None):
        window.hotkey_listener.stop()
    window.close()
    tray_icon.hide()
    event("application.shutdown", status="clean")
    session.close()
    diagnostics.close()
    next_path = app.next_library
    i18n_engine.language_changed.disconnect(update_tray_texts)
    from PySide6.QtCore import QCoreApplication, QEvent
    window.quick_panel.close()
    window.quick_panel.deleteLater()
    window.deleteLater()
    tray_icon.deleteLater()
    tray_menu.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    return next_path

if __name__ == "__main__":
    main()
