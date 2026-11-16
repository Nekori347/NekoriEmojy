import sys
import os
import glob
import warnings

if __name__ == '__main__' and len(sys.argv)==3 and sys.argv[1]=='--backup-worker':
    from services.backup_worker import main as backup_worker_main
    raise SystemExit(backup_worker_main(sys.argv[2]))

if __name__ == '__main__' and len(sys.argv)==4 and sys.argv[1]=='--diagnostic-writer':
    from services.crash_evidence import collect_native
    collect_native(sys.argv[2],sys.argv[3])
    raise SystemExit(0)


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
    standalone_ffmpeg = os.path.join(executable_dir, "ffmpeg", "ffmpeg.exe")
    if os.path.isfile(standalone_ffmpeg):
        ffmpeg_candidates.insert(0, standalone_ffmpeg)
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

from fluent_ui.components.runtime_diagnostics import DiagnosticApplication as QApplication
from PySide6.QtCore import Qt, QTimer

def main():
    # Windows login startup does not inherit the application's working directory.
    from services.autostart import _process_executable, AutostartService
    base_dir = (str(_process_executable().parent)
                if getattr(sys, "frozen", False) or globals().get("__compiled__")
                else os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base_dir)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("NekoriEmojy")
    app.setOrganizationName("Nekori")
    
    from services.single_instance import SingleInstance
    instance = SingleInstance(app)
    if not instance.start():
        return

    from services.crash_evidence import begin_session, complete_session, install as install_crash_evidence
    begin_session()
    install_crash_evidence()
    result = _run_primary(app, instance)
    # aboutToQuit can precede unfinished teardown; only normal return commits.
    if result is None:
        complete_session('startup_cancelled')
    elif result == 0:
        complete_session('event_loop_returned')
    return result


def _run_primary(app, instance):
    from services.autostart import AutostartService

    try:
        AutostartService().repair_registration()
    except OSError as error:
        print(f'[WARNING] Login startup repair failed: {error}')
    
    from services.config import ConfigService
    config_service = ConfigService(defer_create=True)
    from fluent_ui.visual import load_fonts
    load_fonts()
    
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
    from qfluentwidgets import setTheme, Theme, Action
    from fluent_ui.components.safe_round_menu import SafeRoundMenu as RoundMenu
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine, t
    
    app.setQuitOnLastWindowClosed(False)
    from services.upgrade_shutdown import install_upgrade_shutdown
    install_upgrade_shutdown(app)
    
    from PySide6.QtWidgets import QProgressDialog
    from services.migration_manager import MigrationManager
    from fluent_ui.main_window import MainWindow

    # Nekori owns one selected external library. Adoption is limited to data
    # already inside that library; startup never mutates an old installation.
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

    from fluent_ui.components.library_setup import open_startup_library
    storage_service = open_startup_library(config_service)
    if storage_service is None:return
    clipboard_service = ClipboardService(config_service)
    storage_service.cleanup_dead_links()

    # 初始化多语言引擎
    i18n_engine.init(config_service)

    # One short tooltip delay for the whole application; widgets only declare text.
    from fluent_ui.components.tooltip import install_global_tooltips
    install_global_tooltips(app, int(config_service.get('tooltip_delay', 120)))

    window = MainWindow(storage_service, clipboard_service, config_service)
    from fluent_ui.components.runtime_diagnostics import install_runtime_diagnostics
    install_runtime_diagnostics(app, window)
    
    from services.app_icon import ApplicationIconService, set_app_user_model_id
    set_app_user_model_id()

    tray_icon = QSystemTrayIcon()
    window.tray_icon = tray_icon
    icon_path = ApplicationIconService(config_service).current_path()
    if os.path.exists(icon_path):
        tray_icon.setIcon(QIcon(icon_path))
        window.setWindowIcon(QIcon(icon_path))

    tray_icon.setToolTip("NekoriEmojy")
    
    tray_menu = RoundMenu()
    
    show_action = Action(t("显示主面板"), triggered=window.show_gallery)
    tray_menu.addAction(show_action)
    
    def open_settings():
        window.show_settings()
        
    settings_action = Action(t("设置"), triggered=open_settings)
    tray_menu.addAction(settings_action)
    
    tray_menu.addSeparator()
    
    quit_action = Action(t("退出"), triggered=app.quit)
    tray_menu.addAction(quit_action)
    
    # 动态刷新托盘菜单文案
    def update_tray_texts(lang):
        show_action.setText(t("显示主面板"))
        settings_action.setText(t("设置"))
        quit_action.setText(t("退出"))
    i18n_engine.language_changed.connect(update_tray_texts)
    
    # Three rebindable gestures over one action set and one dispatcher; no
    # gesture has its own implementation, and the right button is fixed.
    from fluent_ui.components.tray_activation import TrayAction, TrayActivation, execute_tray_action

    def gesture_action(key, *legacy):
        """Read a gesture binding, still honouring keys from the older model."""
        for name in (key,) + legacy:
            value = config_service.get(name, None)
            if value:
                return value
        return TrayAction.NONE.value

    def run_left_click():
        execute_tray_action(window, gesture_action('tray_left_click', 'tray_single_click'))

    def run_left_double_click():
        execute_tray_action(window, gesture_action('tray_left_double_click', 'tray_double_click'))

    def run_middle_click():
        execute_tray_action(window, gesture_action('tray_middle_click'))

    def open_tray_menu():
        from PySide6.QtGui import QCursor
        tray_menu.exec(QCursor.pos())

    window.tray_activation = TrayActivation({
        QSystemTrayIcon.Trigger: run_left_click,
        QSystemTrayIcon.DoubleClick: run_left_double_click,
        QSystemTrayIcon.MiddleClick: run_middle_click,
    }, open_tray_menu, window)
    tray_icon.activated.connect(window.tray_activation.activate)
    tray_icon.show()
    from fluent_ui.components.clipboard_import_command import install_clipboard_import
    install_clipboard_import(window, config_service, tray_icon)
    
    from services.autostart import should_start_hidden
    if not should_start_hidden(sys.argv, QSystemTrayIcon.isSystemTrayAvailable()):
        window.show()
    instance.set_window(window)
    from fluent_ui.components.auto_crash_reports import install_auto_crash_reports
    install_auto_crash_reports(app, window)
    from fluent_ui.components.update_center import update_center
    QTimer.singleShot(0, lambda: update_center().check_on_startup(config_service))
    
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
