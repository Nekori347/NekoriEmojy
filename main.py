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

from PySide6.QtWidgets import QApplication
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
    
    from PySide6.QtCore import QSharedMemory
    instance_key = "NekoriEmojy_App_Instance" if "--smoke-test" not in sys.argv else f"NekoriEmojy_Smoke_{os.getpid()}"
    shared_memory = QSharedMemory(instance_key)
    if not shared_memory.create(1):
        sys.exit(0)

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
    if os.environ.get('NEKORI_VIEW_CHECK') == '1':
        # Temporary passive diagnostics: no injected desktop input or focus.
        from pathlib import Path
        from PySide6.QtGui import QShortcut, QKeySequence
        import time
        check_log = Path(config_service.base_dir)/'view-check.log'
        def note_view_check(text):
            with check_log.open('a', encoding='utf-8') as stream:
                stream.write(f'{time.time():.3f} {text}\n')
        note_view_check(f'START {__file__} library={storage_service.library_root}')
        def toggle_empty_content():
            window.stacked_widget.setVisible(not window.stacked_widget.isVisible())
            gallery = window.gallery_interface
            from PySide6.QtWidgets import QWidget
            children = gallery.findChildren(QWidget)
            note_view_check(f'CONTENT visible={window.stacked_widget.isVisible()} entries={len(gallery._entries)} '
                           f'cards={len(gallery._all_card_widgets)} children={len(children)} '
                           f'native_children={sum(w.testAttribute(Qt.WA_NativeWindow) for w in children)} '
                           f'translucent_main={window.testAttribute(Qt.WA_TranslucentBackground)}')
            if window._native_state_log:
                window._native_state_log.record(window, 'F9-content', int(window.windowHandle().winId()))
        window.view_check_shortcut = QShortcut(QKeySequence('F9'), window)
        window.view_check_shortcut.activated.connect(toggle_empty_content)
    tray_icon.show()
    
    from services.autostart import should_start_hidden
    if not should_start_hidden(sys.argv, QSystemTrayIcon.isSystemTrayAvailable()):
        window.show()
    
    
    if "--smoke-test" in sys.argv:
        def smoke_complete():
            assert window.gallery_interface.storage is storage_service
            assert window.quick_panel.storage is storage_service
            from fluent_ui.components import dialogs, setting_rows
            print("NEKORI_RUNTIME", sys.executable, os.path.abspath(__file__), os.getcwd(), flush=True)
            for module in (sys.modules[type(window.gallery_interface).__module__], dialogs, setting_rows):
                print("NEKORI_LOADED_MODULE", module.__name__, os.path.abspath(module.__file__), flush=True)
            print("NEKORI_DIALOG_BASE", dialogs.NekoriDialog.__bases__[0].__name__, flush=True)
            from services.dev_placement import dev_screen, selector
            monitor = dev_screen()
            print("NEKORI_DEV_PLACEMENT", selector() or 'unset',
                  monitor.name() if monitor else 'not-applied', window.geometry().getRect(), flush=True)
            print("NEKORI_STARTUP_OK", storage_service.library_root, flush=True)
            # Existing opt-in smoke mode also supports the console-less EXE.
            import json
            from pathlib import Path
            report = dict(argv=sys.argv, executable=sys.executable,
                          script=os.path.abspath(__file__), cwd=os.getcwd(),
                          visible=window.isVisible(), tray_available=QSystemTrayIcon.isSystemTrayAvailable(),
                          startup_command=AutostartService().command(),
                          library=str(storage_service.library_root))
            (Path(config_service.base_dir) / 'smoke-result.json').write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            app.quit()
        QTimer.singleShot(1200, smoke_complete)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
