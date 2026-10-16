from services.i18n import t, bind_text
import os
import ctypes

from PySide6.QtCore import Qt, QObject, Signal, QEvent, QTimer
from PySide6.QtGui import QIcon, QShortcut, QKeySequence
from PySide6.QtWidgets import QApplication

from PySide6.QtWidgets import QVBoxLayout
from fluent_ui.window_shell import NekoriTitleBar
from fluent_ui.window_shell import NekoriWindow

from ctypes import wintypes

from fluent_ui.views.gallery_view import GalleryInterface
from fluent_ui.views.exchange_view import ExchangeInterface
from fluent_ui.views.qq_scan_view import QQScanInterface
from fluent_ui.views.tg_sticker_view import TGStickerInterface

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

# 显式声明 Win32 API 的参数类型，避免 64 位冻结程序中 HWND 被截断。
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL

# SetCursor / LoadCursorW：用于修复 resize 光标残留问题。
# 显式声明类型，避免 64 位冻结程序中 HCURSOR 句柄被截断为 32 位。
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = ctypes.c_void_p
user32.SetCursor.argtypes = [ctypes.c_void_p]
user32.SetCursor.restype = ctypes.c_void_p

dwmapi.DwmSetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    wintypes.LPCVOID,
    wintypes.DWORD,
]
dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2

class HotkeySignal(QObject):
    """跨线程桥接信号"""
    activated = Signal()
    quick_activated = Signal()

class MainWindow(NekoriWindow):
    """
    无侧边栏的极简主窗口架构。
    使用 qframelesswindow 提供云母特效和自定义标题栏。
    """
    def __init__(self, storage_service, clipboard_service, config_service):
        super().__init__()
        self.storage = storage_service
        self.clipboard = clipboard_service
        self.config = config_service
        from services.send_target import SendTargetService
        self.send_target_service = SendTargetService(self)
        from fluent_ui import visual
        visual.theme.configure(self.config)
        visual.theme.changed.connect(self._apply_theme)
        
        self.setTitleBar(NekoriTitleBar(self))
        self.titleBar.titleLabel.setProperty("role", "title")
        
        # 合并短时间内重复的全局快捷键事件，避免窗口动画和状态切换堆积
        self._toggle_window_requests = 0
        self._toggle_window_timer = QTimer(self)
        self._toggle_window_timer.setSingleShot(True)
        self._toggle_window_timer.timeout.connect(self._flush_toggle_window)
        self._toggle_quick_panel_requests = 0
        self._toggle_quick_panel_timer = QTimer(self)
        self._toggle_quick_panel_timer.setSingleShot(True)
        self._toggle_quick_panel_timer.timeout.connect(self._flush_toggle_quick_panel)

        self._init_window()
        self._init_ui()
        self._init_global_hotkey()
        self._init_paste_shortcut()
        self._update_background()
        self.apply_rounded_corners()
        self.apply_window_flags()
        QApplication.instance().aboutToQuit.connect(self._save_window_state)
        QApplication.instance().aboutToQuit.connect(self._save_session_state)

    def _init_window(self):
        self.setWindowTitle("NekoriEmojy")
        from services.app_icon import ApplicationIconService
        self.app_icon = ApplicationIconService(self.config)
        self.tray_icon = None
        self._dev_placement_done = False
        self.reload_application_icon()
        self._restore_geometry()

    def reload_application_icon(self):
        """Apply the user icon (or the shipped default) to every surface we own."""
        icon_path = self.app_icon.current_path()
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)
            self.titleBar.setIcon(icon)
            if hasattr(self, "settings_window"):
                self.settings_window.setWindowIcon(icon)
            if self.tray_icon is not None:
                self.tray_icon.setIcon(icon)

    @staticmethod
    def _usable_geometry(value, minimum):
        """Whether a saved geometry describes a real window.

        A degenerate rectangle (a zero or minimum-clamped size) is what a
        headless run leaves behind; restoring it puts the window in a corner
        instead of where the user left it, so it is treated as "nothing saved".
        """
        if not isinstance(value, list) or len(value) != 4:
            return False
        if not all(isinstance(number, int) for number in value):
            return False
        return value[2] >= minimum.width() and value[3] >= minimum.height()

    def _restore_geometry(self):
        self.setMinimumSize(780, 480)
        geometry = self.config.get("window_geometry", None)
        if self._usable_geometry(geometry, self.minimumSize()):
            self.setGeometry(*geometry)
        else:
            self.resize(1080, 740)

        font = self.font()
        if font.pointSize() <= 0:
            font.setPointSize(9)
            self.setFont(font)

        self.ensure_window_visible()
        # Development rule: an AI-launched instance opens on the development
        # monitor, resolved from the real QScreen list in dev_placement.
        # The user's saved geometry is never rewritten by this (see
        # _save_window_state).
        from services.dev_placement import move_to_dev_screen
        if move_to_dev_screen(self):
            self.setAttribute(Qt.WA_ShowWithoutActivating)

    def ensure_window_visible(self):
        """
        检查窗口是否完全位于所有屏幕的可用区域之外。
        如果是，则将其移动到主屏幕中央，防止高DPI或多显示器配置改变导致窗口丢失。
        """
        from PySide6.QtGui import QGuiApplication
        
        screens = QGuiApplication.screens()
        if not screens:
            return
        saved_name = self.config.get('window_screen', '')
        target = next((s for s in screens if s.name() == saved_name), None)
        geometry = self.normalGeometry() if self.isMaximized() else self.geometry()
        if target is None:
            target = max(screens, key=lambda s: s.availableGeometry().intersected(geometry).width()
                         * s.availableGeometry().intersected(geometry).height())
            if not target.availableGeometry().intersects(geometry):
                target = QGuiApplication.primaryScreen() or screens[0]
        area = target.availableGeometry()
        if not area.contains(geometry):
            self.resize(min(geometry.width(), area.width()), min(geometry.height(), area.height()))
            self.move(max(area.left(), min(geometry.x(), area.right()-self.width()+1)),
                      max(area.top(), min(geometry.y(), area.bottom()-self.height()+1)))

    def _save_window_state(self):
        from services.dev_placement import geometry_writable
        if not geometry_writable(self):
            # A development placement, a headless run and a smoke run all put
            # the window somewhere that is not the user's choice; none of them
            # may become the position the user gets back on a normal launch.
            return
        geometry = self.normalGeometry() if self.isMaximized() or self.isMinimized() else self.geometry()
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(geometry.center()) or self.screen()
        values = {'window_geometry': list(geometry.getRect())}
        if screen is not None and screen.name():
            # Never blank a real screen name with an unnamed one.
            values['window_screen'] = screen.name()
        # One fact, one place. Qt's opaque saveGeometry() blob used to be stored
        # next to this rect, and whenever the two disagreed the blob won: it
        # restored a size and position from whichever session wrote it last,
        # including a headless one, over the rect the user's own session saved.
        # The rect plus the screen name say everything this window restores.
        self.config.discard('window_geometry_qt')
        self.config.update(values)

    def _save_session_state(self):
        """Persist the working position.

        This is not geometry, so it is written even while a development
        placement is active -- otherwise a restart would lose the place the
        user was in. Only the position is stored; the transient session state
        (search, filter, mode, selection) is deliberately not.
        """
        if hasattr(self, 'gallery_interface'):
            self.gallery_interface.save_session_state()

    def hideEvent(self, event):
        self._save_session_state()
        self._save_window_state()
        super().hideEvent(event)

    def _update_background(self):
        from fluent_ui import visual
        visual.theme.refresh()

    def _apply_theme(self):
        from fluent_ui.window_shell import apply_shell_theme
        apply_shell_theme(self)

    def showEvent(self, event):
        super().showEvent(event)
        # The native window is created at show time, which can land after the
        # placement done in _restore_geometry, so the development placement is
        # re-asserted on the first show before the frame is painted.
        if not self._dev_placement_done:
            self._dev_placement_done = True
            from services.dev_placement import move_to_dev_screen
            move_to_dev_screen(self)
        # FramelessWindow 已在初始化时启用系统动画，显示/还原时不要重写窗口样式。
        self.apply_rounded_corners()
        # qframelesswindow/Windows 可能在显示阶段重新调整 Z 序，
        # 因此在窗口真正显示后再次应用置顶状态。
        self.apply_window_flags()

    def changeEvent(self, event):
        # Caption-button cleanup on losing activation lives in NekoriWindow.
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            # Regaining focus may need the topmost band reasserted.
            self.apply_window_flags()

    def closeEvent(self, event):
        """保存窗口状态和布局比例"""
        if hasattr(self, "settings_window") and self.settings_window.isVisible():
            if not self.settings_window.close():
                event.ignore()
                return
        self._save_session_state()
        self._save_window_state()
        if hasattr(self, 'about_interface'):
            self.about_interface.shutdown()
        if hasattr(self, 'qq_scan_interface') and hasattr(self.qq_scan_interface, 'shutdown'):
            self.qq_scan_interface.shutdown()
        if hasattr(self, 'tg_sticker_interface') and hasattr(self.tg_sticker_interface, 'shutdown'):
            self.tg_sticker_interface.shutdown()
        super().closeEvent(event)

    def _init_ui(self):
        from fluent_ui import visual
        self.main_layout = QVBoxLayout(self)
        
        self.main_layout.setContentsMargins(0, 46, 0, 0)
        self.main_layout.setSpacing(0)
        
        from fluent_ui.window_shell import add_shell_accent
        add_shell_accent(self)
        self.titleBar.titleLabel.setText('');self.titleBar.titleLabel.hide()
        self.titleBar.iconLabel.show()
        self.titleBar.setIcon(self.windowIcon())
        from fluent_ui.components.controls import TransparentToolButton
        from fluent_ui.icons import Icon as FIF
        self.titleBar.themeButton = TransparentToolButton(self.titleBar)
        self.titleBar.themeButton.setFixedSize(28, 28)
        self.titleBar.themeButton.clicked.connect(self._cycle_theme_mode)
        self.titleBar.hBoxLayout.insertSpacing(3,18)
        self.titleBar.hBoxLayout.insertWidget(4,self.titleBar.themeButton)
        visual.theme.changed.connect(self._sync_theme_button)
        from services.i18n import i18n_engine
        i18n_engine.language_changed.connect(self._sync_theme_button)
        self._sync_theme_button()
        self.accent_line.reposition()
        
        self.gallery_interface = GalleryInterface(self.storage, self.clipboard, self.config, self,
                                                  send_target_service=self.send_target_service)
        self.gallery_interface.hide_after_paste_requested.connect(self._hide_after_paste)
        
        from PySide6.QtWidgets import QStackedWidget
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.addWidget(self.gallery_interface)
        
        from fluent_ui.window_shell import SettingsWindow
        self.settings_window = SettingsWindow(self.config, self.storage, self)
        self.setting_interface = self.settings_window.center
        self.about_interface = self.settings_window.about
        self.setting_interface.settings_changed.connect(self.on_settings_changed)
        self.destroyed.connect(self.settings_window.deleteLater)

        # 导出导入页面
        self.exchange_interface = ExchangeInterface(self)
        self.exchange_interface.hide()
        self.exchange_interface.back_requested.connect(self.show_gallery)
        self.exchange_interface.import_requested.connect(self.gallery_interface._import_exchange_package)
        self.exchange_interface.export_all_requested.connect(self.gallery_interface._export_all_exchange_package)
        self.exchange_interface.export_selected_requested.connect(self.gallery_interface._export_selected_categories_exchange_package)
        self.exchange_interface.qq_scan_requested.connect(self.show_qq_scan)
        self.exchange_interface.tg_sticker_requested.connect(self.show_tg_sticker)
        self.exchange_interface.nekori_export_requested.connect(
            self.setting_interface.export_nekori_package)
        self.exchange_interface.nekori_import_requested.connect(
            self.setting_interface.import_nekori_package)
        self.exchange_interface.suzu_data_migration_requested.connect(
            self.setting_interface.migrate_from_suzu_data)
        self.exchange_interface.suzu_package_migration_requested.connect(
            self.setting_interface.migrate_from_suzu_package)


        # QQ / TG 是低频工具窗，按需创建：它们的界面构造在冷启动路径上要花
        # 数秒，而多数会话根本不会打开。相似图片窗口一直是这样做的。
        self.qq_scan_interface = None
        self.qq_window = None
        self.tg_sticker_interface = None
        self.tg_window = None
        
        self.gallery_interface.setting_requested.connect(self.show_settings)
        self.gallery_interface.exchange_requested.connect(self.show_exchange)
        self.gallery_interface.similarity_requested.connect(self.show_similarity)
        self.gallery_interface.qq_requested.connect(self.show_qq_scan)
        self.gallery_interface.tg_requested.connect(self.show_tg_sticker)
        self.gallery_interface.about_requested.connect(self.show_about)
        self._similarity_window = None
        
        self.main_layout.addWidget(self.stacked_widget)
        
        from fluent_ui.components.quick_panel import QuickPanel
        self.quick_panel = QuickPanel(self.storage, self.clipboard, self.config,
                                     send_target_service=self.send_target_service)
        self.quick_panel.resources_imported.connect(self.refresh_library)
        
    def refresh_library(self):
        """An owner-local import updates the shared library and existing views."""
        self.gallery_interface.sidebar.refresh_list(self.gallery_interface.current_node)
        self.gallery_interface.refresh_content_incremental(reason='external_import')
        self.quick_panel._cached_query = self.quick_panel._cached_results = None

    def show_settings(self):
        """Open Settings without replacing or rebuilding the gallery."""
        self.settings_window.present()

    def show_gallery(self, refresh=True):
        """切回主面板；快捷键唤醒时应使用 refresh=False 的轻量路径。"""
        self.send_target_service.capture_foreground()
        # 通过标题栏关闭后，按钮可能保留 pressed/hover 状态；
        # 每次重新唤醒主面板时统一恢复为正常状态。
        self.clear_transient_button_states()

        if hasattr(self, 'gallery_interface') and refresh:
            self.gallery_interface.sidebar.refresh_list(self.gallery_interface.current_category)
            self.gallery_interface.on_images_changed()
            
        self.stacked_widget.setCurrentWidget(self.gallery_interface)
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self._reapply_window_flags_after_show()

    def show_about(self):
        self.settings_window.show_page(self.about_interface)

    def show_exchange(self):
        self.setting_interface._select_page(3)
        self.settings_window.show_page(self.setting_interface)

    def show_similarity(self):
        from fluent_ui.views.similarity_view import SimilarityDialog
        from fluent_ui.window_shell import ToolWindow
        if self._similarity_window is None:
            dialog = SimilarityDialog(self.gallery_interface)
            dialog.setModal(False)
            dialog.setWindowModality(Qt.NonModal)
            self._similarity_window = ToolWindow(self, dialog, '相似图片')
            self.destroyed.connect(self._similarity_window.deleteLater)
        self._similarity_window.present()

    def show_qq_scan(self):
        if self.qq_window is None:
            from fluent_ui.window_shell import ToolWindow
            self.qq_scan_interface = QQScanInterface(self, self.config)
            self.qq_window = ToolWindow(self, self.qq_scan_interface, 'QQ 导入')
            self.qq_scan_interface.back_requested.connect(self.qq_window.close)
            self.destroyed.connect(self.qq_window.deleteLater)
        self.qq_window.present()

    def show_tg_sticker(self):
        if self.tg_window is None:
            from fluent_ui.window_shell import ToolWindow
            self.tg_sticker_interface = TGStickerInterface(self)
            self.tg_window = ToolWindow(self, self.tg_sticker_interface, 'Telegram 导入')
            self.tg_sticker_interface.back_requested.connect(self.tg_window.close)
            self.destroyed.connect(self.tg_window.deleteLater)
        self.tg_window.present()


    def _reapply_window_flags_after_show(self):
        """在窗口显示或被唤醒后重新应用 Windows 置顶状态及圆角。"""
        self.apply_rounded_corners()
        self.apply_window_flags()


    def _init_global_hotkey(self):
        self.hotkey_signal = HotkeySignal()
        self.hotkey_signal.activated.connect(self._request_toggle_window)
        self.hotkey_signal.quick_activated.connect(self._request_toggle_quick_panel)
        self.hotkey_listener = None
        self.bind_global_hotkey()

    def _parse_pynput_hotkey(self, hotkey_str):
        """将 'ctrl+shift+e' 转换为 pynput 格式 '<ctrl>+<shift>+e'"""
        parts = hotkey_str.lower().split('+')
        pynput_parts = []
        for part in parts:
            part = part.strip()
            if part in ('ctrl', 'shift', 'alt', 'win'):
                pynput_parts.append(f"<{part}>")
            else:
                pynput_parts.append(part)
        return "+".join(pynput_parts)

    def bind_global_hotkey(self):
        try:
            if self.hotkey_listener:
                self.hotkey_listener.stop()
                self.hotkey_listener = None
        except Exception:
            pass
            
        hotkey_str = self.config.get("global_hotkey", "ctrl+shift+e")
        quick_hotkey_str = self.config.get("quick_panel_hotkey", "alt+2")
        
        hotkeys_dict = {}
        
        try:
            from pynput import keyboard
            
            if hotkey_str:
                pynput_hotkey = self._parse_pynput_hotkey(hotkey_str)
                def on_activate():
                    self.hotkey_signal.activated.emit()
                hotkeys_dict[pynput_hotkey] = on_activate
                
            if quick_hotkey_str:
                pynput_quick_hotkey = self._parse_pynput_hotkey(quick_hotkey_str)
                def on_quick_activate():
                    self.hotkey_signal.quick_activated.emit()
                hotkeys_dict[pynput_quick_hotkey] = on_quick_activate
                
            if hotkeys_dict:
                self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys_dict)
                self.hotkey_listener.start()
        except Exception as e:
            print(f"Failed to bind pynput hotkey: {e}")

    def _request_toggle_window(self):
        self._toggle_window_requests += 1
        self._toggle_window_timer.start(40)

    def _flush_toggle_window(self):
        requests = self._toggle_window_requests
        self._toggle_window_requests = 0
        if requests % 2:
            self.toggle_window()

    def _request_toggle_quick_panel(self):
        self._toggle_quick_panel_requests += 1
        self._toggle_quick_panel_timer.start(40)

    def _flush_toggle_quick_panel(self):
        requests = self._toggle_quick_panel_requests
        self._toggle_quick_panel_requests = 0
        if requests % 2:
            self.toggle_quick_panel()

    def toggle_quick_panel(self, capture_target=True, from_tray=False):
        if self.quick_panel.isVisible():
            self.quick_panel.hide_panel()
        elif from_tray and self.quick_panel.hidden_by_focus_loss_within():
            # Clicking the tray icon takes focus away from the panel, so the
            # panel has just hidden itself: this click is the closing half of
            # the toggle and must not immediately reopen it.
            return
        else:
            # 在面板显示前，记录当前的前台窗口句柄。托盘点击时前台是任务栏 /
            # 外壳，不是用户想发往的目标，因此由调用方关闭捕获。
            if capture_target:
                self.send_target_service.capture_foreground()
            self.quick_panel.show_at_cursor()

    def show_quick_panel(self, from_tray=False):
        """Bring the quick panel up without toggling it away.

        The `SHOW_QUICK` action asks for the panel, so it is shown even when
        the panel just hid itself because the tray click took focus away.
        """
        if self.quick_panel.isVisible():
            return
        self.quick_panel.show_at_cursor()

    def show_main_panel(self):
        """Bring the main panel up without toggling it away."""
        if not self.isVisible():
            self.toggle_window()
            return
        self.show_gallery(refresh=False)

    def _hide_after_paste(self):
        self.clear_transient_button_states()
        self.gallery_interface.save_scroll_position()
        self.gallery_interface.preview_controller.cancel()
        self.hide()

    def toggle_window(self):
        """Show the main panel when hidden, hide it when it is up.

        Visibility alone decides: a visible but unfocused window is still "up",
        and requiring activation made a second tray click re-show it instead of
        hiding it.
        """
        if self.isVisible():
            # 隐藏前清除标题栏按钮的悬停绘制状态
            self.clear_transient_button_states()

            # 记录滚动位置
            if hasattr(self, 'gallery_interface'):
                self.gallery_interface.save_scroll_position()

            self.hide()
        else:
            self.show_gallery(refresh=False)
            
            self.showNormal()
            self.activateWindow()
            self.raise_()
            user32.SetForegroundWindow(ctypes.c_void_p(int(self.winId())))
            
            # 在下一帧恢复滚动位置
            if hasattr(self, 'gallery_interface'):
                # 卡片采用分帧懒加载，延迟恢复可避免布局尚未完成时被截断。
                QTimer.singleShot(0, self.gallery_interface, self.gallery_interface.restore_scroll_position)
                QTimer.singleShot(100, self.gallery_interface, self.gallery_interface.restore_scroll_position)
                QTimer.singleShot(300, self.gallery_interface, self.gallery_interface.restore_scroll_position)

    def apply_rounded_corners(self):
        """
        强制指定 Windows 11 DWM 窗口圆角。
        避免 qframelesswindow 动态添加 WS_THICKFRAME/WS_CAPTION 等原生样式时，
        Windows 11 将无边框窗口回退为直角矩形。
        """
        try:
            hwnd = int(self.winId())
            if not hwnd or not user32.IsWindow(hwnd):
                return False

            preference = wintypes.DWORD(DWMWCP_ROUND)
            hr = dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
            if hr != 0:
                return False

            # DWM 会直接应用圆角偏好；FRAMECHANGED 会额外触发非客户区重算和重绘。
            return True
        except (AttributeError, TypeError, ValueError, OSError):
            return False

    def apply_window_flags(self):
        """
        使用 user32.SetWindowPos 动态修改置顶状态，
        避免使用 self.setWindowFlag 导致重新创建窗口句柄而破坏无边框缩放特性。
        """
        try:
            hwnd = int(self.winId())
            if not hwnd or not user32.IsWindow(hwnd):
                return False

            always_on_top = bool(self.config.get("always_on_top", True))
            HWND_TOPMOST = ctypes.c_void_p(-1)
            HWND_NOTOPMOST = ctypes.c_void_p(-2)
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

            self.apply_taskbar_icon(hwnd)
            insert_after = HWND_TOPMOST if always_on_top else HWND_NOTOPMOST
            current_topmost = bool(user32.GetWindowLongW(hwnd, -20) & 0x8)
            result = True if current_topmost == always_on_top else user32.SetWindowPos(
                hwnd, insert_after, 0, 0, 0, 0, flags)
            # Independent non-modal windows must follow the owner's topmost
            # band, including delayed flag reapplication after Main.show().
            for name in ('settings_window', 'qq_window', 'tg_window', '_similarity_window'):
                auxiliary = getattr(self, name, None)
                if auxiliary is not None and auxiliary.isVisible():
                    auxiliary_hwnd = int(auxiliary.winId())
                    if bool(user32.GetWindowLongW(auxiliary_hwnd, -20) & 0x8) != always_on_top:
                        user32.SetWindowPos(auxiliary_hwnd, insert_after, 0, 0, 0, 0, flags)
            if not result:
                print(f"[WARNING] SetWindowPos failed, error={ctypes.get_last_error()}")
            return bool(result)
        except (AttributeError, TypeError, ValueError, OSError) as error:
            print(f"[WARNING] Failed to apply window topmost state: {error}")
            return False

    def apply_taskbar_icon(self, hwnd=None):
        """Show or hide the taskbar entry through the extended window style.

        WS_EX_TOOLWINDOW removes the taskbar button (and the Alt-Tab entry)
        while keeping the HWND, the frameless chrome, the owner relationships
        and the saved geometry untouched. Changing a Qt window flag instead
        would recreate the native window, which is exactly what this project
        avoids. Re-asserted on every show, so a change in Settings takes effect
        the next time the window is shown or the app restarts.
        """
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        try:
            hwnd = int(hwnd or self.winId())
            if not hwnd or not user32.IsWindow(hwnd):
                return False
            user32.GetWindowLongW.restype = ctypes.c_long
            original = style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if self.config.get('show_taskbar_icon', True):
                style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            else:
                style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            if style != original:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            return True
        except (AttributeError, TypeError, ValueError, OSError) as error:
            print(f"[WARNING] Failed to apply taskbar icon state: {error}")
            return False

    def _sync_theme_button(self, *_):
        from fluent_ui.components.interaction_controls import ThemeModeIcon
        modes = ('system', 'light', 'dark')
        mode = self.config.get('appearance_mode', 'system')
        mode = mode if mode in modes else 'system'
        next_mode = modes[(modes.index(mode)+1)%3]
        labels = {'system': t('跟随系统'), 'light': t('浅色'), 'dark': t('深色')}
        button = self.titleBar.themeButton
        button.setIcon(ThemeModeIcon(mode))
        button.setProperty('themeMode', mode)
        button.setToolTip(t('当前：{current}；点击切换到：{next}').format(current=labels[mode], next=labels[next_mode]))
        button.setAccessibleName(button.toolTip())

    def _cycle_theme_mode(self):
        modes = ('system', 'light', 'dark')
        current = self.config.get('appearance_mode', 'system')
        mode = modes[(modes.index(current)+1)%3] if current in modes else 'system'
        self.config.set('appearance_mode', mode)
        self.setting_interface.sync_external_preference('appearance_mode', mode)
        self.on_settings_changed('appearance_mode')

    def keyPressEvent(self, event):
        # Unconsumed Esc arrives only after the focused child/internal surface.
        if event.key() == Qt.Key_Escape:
            if self.gallery_interface.consume_escape():
                event.accept()
                return
            if not self.config.get('esc_hide_main', False):
                return super().keyPressEvent(event)
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def on_settings_changed(self, changed_key=""):
        """当设置界面修改了配置时被调用，按需局部刷新"""
        if changed_key == 'tag_panel_placement':
            self.gallery_interface.tag_panel_host.set_placement(self.config.get(changed_key, 'bottom'))
            return
        if changed_key in ('sidebar_mode', 'sidebar_icon_size', 'sidebar_show_labels'):
            self.gallery_interface.sidebar.apply_presentation()
            return
        if changed_key == "always_on_top":
            self.apply_window_flags()

        elif changed_key == "preview_position":
            self.gallery_interface.apply_preview_position()

        elif changed_key == 'quick_panel_thumbnail_size':
            self.quick_panel._apply_thumbnail_size(self.config.get(changed_key, 72))

        elif changed_key in ["global_hotkey", "quick_panel_hotkey"]:
            self.bind_global_hotkey()

        elif changed_key == 'accent_preview':
            from fluent_ui import visual
            visual.theme.preview_accent()

        elif changed_key == 'accent_color':
            self._update_background()
            self.quick_panel.update_theme()
            self._sync_theme_button()

        elif changed_key in ["appearance_mode", "light_theme_key", "dark_theme_key"]:
            from qfluentwidgets import setTheme, Theme
            appearance_mode = self.config.get("appearance_mode",
                                              self.config.get("theme_mode", "system"))
            if appearance_mode == "dark":
                setTheme(Theme.DARK,lazy=True)
            elif appearance_mode == "light":
                setTheme(Theme.LIGHT,lazy=True)
            else:
                setTheme(Theme.AUTO,lazy=True)

            self._update_background()
            self.quick_panel.update_theme()

        elif changed_key == "app_icon":
            self.reload_application_icon()

        elif changed_key == "library_rescan":
            self.gallery_interface.sidebar.refresh_list(self.gallery_interface.current_node)
            self.gallery_interface.refresh_content()

        elif changed_key in ["use_system_font"]:
            from fluent_ui.components.feedback import feedback_for
            feedback_for(self.settings_window if getattr(self, 'settings_window', None) else self).notice(
                t("需要重启"), t("字体设置已更改，请重启软件以应用更改。"))

        else:
            self.gallery_interface.on_settings_changed(changed_key)
            self.quick_panel.update_theme()
            if changed_key in ("", "always_on_top"):
                self.apply_window_flags()

    def _init_paste_shortcut(self):
        """全局 Ctrl+V 拦截"""
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self.handle_global_paste)

    def handle_global_paste(self):
        self.gallery_interface.handle_global_paste()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "accent_line"):
            self.accent_line.reposition()

    def nativeEvent(self, eventType, message):
        """监听 Windows 底层消息，处理睡眠唤醒后快捷键失效的问题，以及系统主题切换"""
        try:
            msg = wintypes.MSG.from_address(int(message))
            # WM_POWERBROADCAST = 0x0218
            if msg.message == 0x0218:
                # PBT_APMRESUMEAUTOMATIC = 0x0012 (系统自动唤醒)
                # PBT_APMRESUMESUSPEND = 0x0007 (系统唤醒并恢复交互)
                if msg.wParam == 0x0012 or msg.wParam == 0x0007:
                    # 延迟重新绑定快捷键，确保系统钩子机制已完全恢复
                    QTimer.singleShot(2000, self.bind_global_hotkey)
                    QTimer.singleShot(500, self._reapply_window_flags_after_show)
            # WM_DWMCOMPOSITIONCHANGED = 0x031E
            elif msg.message == 0x031E:
                QTimer.singleShot(50, self.apply_rounded_corners)
            # WM_SETTINGCHANGE = 0x001A
            elif msg.message == 0x001A:
                # 系统设置改变（包括深浅色模式切换）
                appearance_mode = self.config.get("appearance_mode", self.config.get("theme_mode", "system"))
                if appearance_mode == "system":
                    # 延迟一点点执行，确保 qfluentwidgets 已经处理完系统主题切换
                    QTimer.singleShot(100, lambda: self.on_settings_changed("appearance_mode"))
        except Exception:
            pass
        return super().nativeEvent(eventType, message)
