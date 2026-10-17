"""Settings Center.

Independent window-level page with its own structure: major categories on the
left, second-level tabs on top, grouped sections below with a sticky section
header, and an explicit Save / Discard / Defaults footer. Settings behave here;
this page is not a launcher for other main-window pages.
"""
from services.i18n import t, bind_text, translated
import json
import os

from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QSize
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QScrollArea, QVBoxLayout, QWidget, QStackedWidget,
)
from fluent_ui.icons import Icon as FIF
from qfluentwidgets import InfoBar, InfoBarPosition
from fluent_ui.components.controls import PushButton, SwitchButton, TransparentToolButton, MetaButton

from fluent_ui import visual
from fluent_ui.components.navigation import NavigationItem, TabStrip, ContentPane
from fluent_ui.components import dialogs
from fluent_ui.components.setting_rows import (
    ActionRow, AccentRow, ChoiceRow, InfoRow, HotkeyRow, RangeRow, SettingSection, SwitchRow,
    apply_row_theme, ModeRow, SpatialRow, FullPathRow,
)
from fluent_ui.theme import THEMES
from services.autostart import AutostartService
from services.i18n import SUPPORTED_LANGUAGES, i18n_engine, t, bind_text, translated

PREVIEW_KEYS = {"appearance_mode", "light_theme_key", "dark_theme_key",
                "thumbnail_size", "sidebar_icon_size", "accent_color", "sidebar_mode", "sidebar_show_labels",
                "quick_panel_thumbnail_size", "tag_panel_placement"}
APPEARANCE_KEYS = ("appearance_mode", "accent_color")


class SettingsCenter(QWidget):
    settings_changed = Signal(str)
    back_requested = Signal()
    about_requested = Signal()

    def __init__(self, config_service, storage_service=None, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsCenter")
        self.config = config_service
        self.storage = storage_service
        self.autostart = AutostartService()
        self.pending = {}
        self._preview_backup = {}
        self.preview_enabled = bool(self.config.get("settings_preview", True))
        self._rows = {}
        self._all_rows = {}
        self._accent_commit_timer = QTimer(self)
        self._accent_commit_timer.setSingleShot(True)
        self._accent_commit_timer.setInterval(160)
        self._accent_commit_timer.timeout.connect(lambda: self.settings_changed.emit("accent_color"))
        self._pages = []
        self._page_widgets = {}
        self._build()
        self._select_page(0)
        visual.theme.changed.connect(self.refresh_theme)
        i18n_engine.language_changed.connect(self.refresh_texts)

    # ==================================================================
    # Construction
    # ==================================================================
    def _build(self):
        from fluent_ui.presentation.settings import build_settings
        build_settings(self)

    def _build_footer(self):
        from fluent_ui.presentation.settings import DecisionBar
        from fluent_ui.presentation.tools import WrapCommands
        footer=DecisionBar(self);footer.setObjectName('SettingsFooter')
        preview=QWidget(footer);preview_layout=QHBoxLayout(preview);preview_layout.setContentsMargins(0,0,0,0);preview_layout.setSpacing(6)
        self.preview_switch=translated(PushButton,'实时预览',preview);self.preview_switch.setCheckable(True);self.preview_switch.setChecked(self.preview_enabled)
        from fluent_ui.icons import Icon
        self.preview_switch.setIcon(Icon.EYE if self.preview_enabled else Icon.EYE_OFF)
        self.preview_switch.toggled.connect(self._on_preview_toggled)
        self.preview_switch.toggled.connect(lambda checked:self.preview_switch.setIcon(Icon.EYE if checked else Icon.EYE_OFF))
        preview_layout.addWidget(self.preview_switch)
        actions=QWidget(footer);action_layout=WrapCommands(actions);action_layout.setContentsMargins(0,0,0,0);action_layout.setSpacing(8)
        self.btn_defaults=translated(MetaButton,'本页默认',actions);self.btn_defaults.clicked.connect(self._restore_page_defaults)
        self.btn_discard=translated(MetaButton,'放弃修改',actions);self.btn_discard.setProperty('command','discard');self.btn_discard.clicked.connect(self.discard)
        self.btn_save=translated(MetaButton,'保存',actions);self.btn_save.setProperty('command','save');self.btn_save.clicked.connect(self.save)
        for button in (self.btn_defaults,self.btn_discard,self.btn_save):action_layout.addWidget(button)
        self.btn_import=translated(PushButton,'导入设置',footer);self.btn_import.clicked.connect(self._import_settings);self.btn_import.hide()
        self.btn_export=translated(PushButton,'导出设置',footer);self.btn_export.clicked.connect(self._export_settings);self.btn_export.hide()
        footer.preview=preview;footer.actions=actions
        return footer

    def _apply_style(self):
        if not getattr(self,'_typography_initialized',False):
            visual.apply_typography(self);self._typography_initialized=True
        self.setStyleSheet(visual.settings_style())
        apply_row_theme(self)
        self.sticky.setStyleSheet(f"background: {visual.colors()['surface']}; color: {visual.colors()['text_secondary']}; padding: 6px 12px; border: none; border-radius: 0;")
        if hasattr(self, "_tabs"):
            self._style_tabs()

    # ==================================================================
    # Declarative page content
    # ==================================================================
    def _library_path(self):
        return self.storage.library_root if self.storage else self.config.get("library_path", "")

    def _icon_pages(self):
        return [
            ('常规', [('启动与窗口', self._page_startup), ('托盘', self._page_tray), ('语言', self._page_language), ('配置与重置', self._page_settings_file)]),
            ('外观', [('主题', self._page_theme), ('表情库', self._page_gallery_display), ('快速面板', self._page_quick_panel), ('软件图标', self._page_app_icon)]),
            ('交互', [('快捷键', self._page_hotkeys), ('发送', self._page_send), ('悬停预览', self._page_hover_preview)]),
            ('表情与数据', [('表情库', self._page_library), ('文字识别', self._page_ocr), ('表情合集', self._page_packages), ('Suzu 迁移', self._page_migration)]),
            ('关于', [('软件信息', self._page_about)]),
        ]

    def _select_page(self, index):
        if index < 0:
            return
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(index)
        self.nav.blockSignals(False)
        self._current_page = index
        self._rebuild_tabs()

    def _rebuild_tabs(self):
        pages = self._icon_pages()
        if not self.nav.count():
            for name, _ in pages:
                self.nav.addItem(QListWidgetItem(t(name)))
        self.nav.setFixedWidth(min(245, max(175, max(self.nav.fontMetrics().horizontalAdvance(t(name)) for name, _ in pages)+44)))
        group_name, tabs = pages[max(0, min(self._current_page, len(pages) - 1))]
        self.tab_bar.set_tabs([t(name) for name, _ in tabs])
        self._tabs = tabs
        self._show_tab(0)

    def _show_tab(self, index):
        index = max(0, min(index, len(self._tabs)-1))
        title, builder = self._tabs[index]
        key = builder.__name__
        if key not in self._page_widgets:
            if self._page_widgets:
                self.scroll = QScrollArea(self)
                self.scroll.setWidgetResizable(True)
                self.scroll.setFrameShape(QFrame.NoFrame)
                self.scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
                self.scroll.viewport().setObjectName('SettingsViewport')
                self.scroll.verticalScrollBar().valueChanged.connect(self._update_sticky_header)
                self.body_widget = QWidget()
                self.body_widget.setObjectName('SettingsBody')
                self.body_layout = QVBoxLayout(self.body_widget)
                self.body_layout.setContentsMargins(10,12,10,10)
                self.body_layout.setSpacing(12)
                self.scroll.setWidget(self.body_widget)
                self.page_stack.addWidget(self.scroll)
                self.sticky = QLabel('', self.scroll.viewport())
                self.sticky.hide()
            self._reset_visible()
            builder()
            visual.apply_typography(self.body_widget)
            self.body_layout.addStretch()
            self._page_widgets[key] = (self.scroll, self.body_widget, self.body_layout, self.sticky, self._rows, self._sections)
        self.scroll, self.body_widget, self.body_layout, self.sticky, self._rows, self._sections = self._page_widgets[key]
        self.page_stack.setCurrentWidget(self.scroll)
        self._page_rows = title
        self._current_tab = index
        for key, (row, default) in self._rows.items():
            row.set_value(self.pending.get(key, self._autostart_enabled() if key == 'autostart' else self.config.get(key, default)))
        self._style_tabs()
        self._apply_style()
        self._update_sticky_header()

    def refresh_texts(self, *_):
        self.nav.blockSignals(True)
        for index, (name, _) in enumerate(self._icon_pages()):
            self.nav.item(index).setText(t(name))
        self.nav.blockSignals(False)
        self.tab_bar.set_tabs([t(name) for name, _ in self._tabs], self._current_tab)
        self._set_dirty(bool(self.pending))
        self._update_sticky_header()

    def _style_tabs(self):
        self.tab_bar.blockSignals(True)
        self.tab_bar.setCurrentIndex(getattr(self, '_current_tab', 0))
        self.tab_bar.blockSignals(False)
        self.tab_bar.update()

    def _show_settings_tools(self):
        from fluent_ui.components.safe_round_menu import SafeRoundMenu
        from qfluentwidgets import Action
        menu = SafeRoundMenu(parent=self)
        for title, callback in (("导入设置…", self._import_settings), ("导出设置…", self._export_settings), ("恢复全部默认…", self._restore_all_defaults)):
            action = translated(Action, title, self)
            action.setEnabled(not self.pending or callback == self._export_settings)
            action.triggered.connect(callback)
            menu.addAction(action)
        menu.exec(self.btn_tools.mapToGlobal(self.btn_tools.rect().bottomLeft()))

    def _section(self, title):
        labels = {"STARTUP": "启动", "WINDOW": "窗口", "LANGUAGE": "语言", "TRAY": "托盘", "CURRENT LIBRARY": "当前表情库", "MAINTENANCE": "维护", "APPEARANCE": "外观", "THEME": "主题", "GALLERY": "表情库", "SIDEBAR": "分类栏", "PREVIEW": "悬停预览", "HOVER PREVIEW": "悬停预览", "QUICK PANEL": "快速面板", "GLOBAL HOTKEYS": "全局快捷键", "SENDING": "发送", "APPLICATION ICON": "软件图标", "NEKORI PACKAGE": "Nekori 表情合集", "SUZU SHARE PACKAGE": "Suzu 分享包", "SUZU MIGRATION": "Suzu 单向迁移", "SETTINGS FILE": "设置文件", "APPLICATION": "软件信息"}
        section = SettingSection(labels.get(title, title), self.body_widget)
        self.body_layout.addWidget(section)
        self._sections.append(section)
        return section

    def _track(self, row, key, default, handler=None):
        self._rows[key] = (row, default)
        self._all_rows[key] = (row, default)
        row.set_pending(key in self.pending)
        row.changed.connect(handler or (lambda r=row, k=key: self._stage(k, r.value())))
        return row

    def _reset_visible(self):
        """Rows belong to the tab currently built; stale widgets must not be touched."""
        self._rows = {}
        self._sections = []

    # -- pages ---------------------------------------------------------
    def _page_startup(self):
        section = self._section("STARTUP")
        row = SwitchRow("开机自启动", "登录 Windows 后自动启动到托盘；移动程序后请重新开启。",
                        "autostart", self._autostart_enabled())
        self._rows["autostart"] = (row, False)
        self._all_rows["autostart"] = (row, False)
        row.changed.connect(lambda: self._on_autostart_toggled(row))
        section.add_row(row)

        section = self._section("WINDOW")
        for title, hint, key, default in (
            ("主窗口始终置顶", "让 Nekori 始终显示在其他窗口之上。", "always_on_top", True),
            ("粘贴后自动隐藏主面板", "复制并尝试粘贴后隐藏主面板，仍可用快捷键呼出。",
             "hide_main_after_paste", False),
            ("在任务栏显示应用图标", "关闭后不再占用任务栏入口，仍驻留托盘；下次显示主窗口或重启后生效。",
             "show_taskbar_icon", True),
        ):
            section.add_row(self._track(
                SwitchRow(title, hint, key, self.config.get(key, default), self), key, default))

    def _page_tray(self):
        section = self._section("TRAY")
        # Every rebindable gesture picks from the same action set with the same
        # component; only the trigger differs. The right button is fixed, so it
        # shows a read-only row instead of a selector.
        options = [("toggle_main", "切换主面板"), ("show_main", "显示主面板"),
                   ("toggle_quick", "切换快速面板"), ("show_quick", "显示快速面板"),
                   ("open_settings", "打开设置"), ("none", "无操作")]
        for key, title, hint, default in (
            ("tray_left_click", "左键单击",
             "单击托盘图标时执行此操作。", "toggle_main"),
            ("tray_left_double_click", "左键双击",
             "双击托盘图标时执行此操作。", "toggle_main"),
            ("tray_middle_click", "中键单击",
             "按下鼠标中键时执行此操作。", "none"),
        ):
            row = ChoiceRow(title, hint, key, self.config.get(key, default), options, self)
            section.add_row(self._track(row, key, default))
        section.add_row(InfoRow("右键单击", "右键固定打开托盘菜单，不能重新绑定。", t("打开菜单（固定）")))

    def _autostart_enabled(self):
        try:
            return bool(self.autostart.is_enabled())
        except OSError:
            return False

    def _on_autostart_toggled(self, row):
        self._stage('autostart', row.value())

    def _page_language(self):
        section = self._section("LANGUAGE")
        options = [(code, label) for code, label in SUPPORTED_LANGUAGES]
        row = ChoiceRow("界面语言", "更改软件的显示语言。", "language",
                        self.config.get("language", "zh"), options, self)
        self._rows["language"] = (row, "zh")
        self._all_rows['language'] = (row, 'zh')
        row.changed.connect(lambda: self._apply_language(row.value()))
        section.add_row(row)

    def _apply_language(self, code):
        if code:
            self._stage('language', code)

    def _page_ocr(self):
        if self.storage is None:return
        from fluent_ui.components.ocr_controls import OcrSettings
        self.ocr_controls=OcrSettings(self)

    def _page_library(self):
        section = self._section("CURRENT LIBRARY")
        self.library_info = FullPathRow("当前表情库", "表情和分类保存在以下目录；可选中文字复制完整路径。", self._library_path(), self)
        self._all_rows['library_path']=(self.library_info,'')
        section.add_row(self.library_info)
        section.add_row(ActionRow(
            "选择 / 重新连接表情库",
            "保存后需要重启程序才会切换到新的表情库。",
            [("选择文件夹…", self._choose_library, True)], self))

        section = self._section("MAINTENANCE")
        section.add_row(ActionRow(
            "检查表情状态", "检查表情文件是否仍然存在。\n找不到的表情会标记为已失效，不会删除记录。",
            [("立即检查", self._check_library, False)], self))
        section.add_row(ActionRow(
            "在文件管理器中打开", "直接查看表情库中的真实表情文件。",
            [("打开表情库目录", self._open_library, False)], self))

    def _choose_library(self):
        directory = QFileDialog.getExistingDirectory(self, t("选择或重新连接表情库"), self._library_path())
        if not directory:
            return
        try:
            from services.library_index import LibraryIndex
            LibraryIndex(directory)
        except Exception as exc:
            self.show_error(t("连接失败"), str(exc))
            return
        self._stage("library_path", directory)
        self.library_info.set_value(directory)
        self.library_info.set_hint(t('保存并重启后，将使用下面的表情库。'))

    def _check_library(self):
        if not self.storage:
            return
        self.storage.cleanup_dead_links()
        self.settings_changed.emit("library_rescan")
        missing = sum(1 for r in self.storage.index.resources() if r["status"] == "missing")
        self.show_success(t("检查完成"), t('已失效的表情：{value_0} 项').format(value_0=missing))

    def _open_library(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._library_path()))

    def _page_theme(self):
        section = self._section("APPEARANCE")
        section.add_row(self._track(ModeRow(
            "界面模式", "", "appearance_mode", self.config.get("appearance_mode", "system"),
            [("system", "跟随系统"), ("light", "浅色"), ("dark", "深色")], self),
            "appearance_mode", "system"))
        row = AccentRow(self.pending.get('accent_color', self.config.get('accent_color', visual.DEFAULT_ACCENT)), self)
        section.add_row(self._track(row, 'accent_color', visual.DEFAULT_ACCENT))

    def _page_gallery_display(self):
        section = self._section("GALLERY")
        section.add_row(self._track(
            RangeRow("缩略图大小", "调整表情缩略图大小。\n也可按住 Ctrl 并滚动滚轮调整。",
                     "thumbnail_size", self.config.get("thumbnail_size", 120), 60, 300, 10, self),
            "thumbnail_size", 120))

        section = self._section("SIDEBAR")
        mode = self._track(ModeRow(
            "分类显示方式", "也可以通过侧边栏顶部的视图切换按钮快速切换。", "sidebar_mode",
            self.config.get('sidebar_mode', 'tree'), [('tree', '分类树'), ('categorized_icons', '分类图标')], self),
            'sidebar_mode', 'tree')
        section.add_row(mode)
        self.icon_options = SettingSection('图标视图选项', self)
        self.icon_options.add_row(self._track(SwitchRow(
            "显示分类图标名称", "", 'sidebar_show_labels', self.config.get('sidebar_show_labels', True), self),
            'sidebar_show_labels', True))
        section.add_row(self.icon_options)
        mode.changed.connect(lambda: self.icon_options.setEnabled(mode.value() == 'categorized_icons'))
        self.icon_options.setEnabled(mode.value() == 'categorized_icons')
        section.add_row(self._track(
            RangeRow("侧边栏图标大小", "左侧分类树图标尺寸。",
                     "sidebar_icon_size", self.config.get("sidebar_icon_size", 20), 14, 48, 1, self),
            "sidebar_icon_size", 20))
        section.add_row(self._track(SpatialRow(
            "标签面板位置", "点击示意窗口的边缘，将标签栏放到对应一侧。", 'tag_panel_placement',
            self.config.get('tag_panel_placement', 'bottom'), self),
            'tag_panel_placement', 'bottom'))

    def _page_quick_panel(self):
        section = self._section("QUICK PANEL")
        section.add_row(self._track(RangeRow('快速面板缩略图大小', '', 'quick_panel_thumbnail_size',
            self.config.get('quick_panel_thumbnail_size', 72), 40, 200, 6, self), 'quick_panel_thumbnail_size', 72))
        section.add_row(self._track(
            RangeRow("面板宽度", "快速调用面板的宽度。", "quick_panel_width",
                     self.config.get("quick_panel_width", 360), 250, 800, 10, self),
            "quick_panel_width", 360))
        section.add_row(self._track(
            RangeRow("面板高度", "快速调用面板的高度。", "quick_panel_height",
                     self.config.get("quick_panel_height", 480), 150, 1000, 10, self),
            "quick_panel_height", 480))
        section.add_row(self._track(
            RangeRow("最近使用上限", "快速面板中保留的最近使用表情数量。", "recent_limit",
                     self.config.get("recent_limit", 30), 1, 999, 1, self, count_only=True),
            "recent_limit", 30))


    def _page_app_icon(self):
        section = self._section("APPLICATION ICON")
        self.icon_preview = QLabel(self)
        self.icon_preview.setFixedSize(72, 72)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setStyleSheet(
            f"border: 1px solid {visual.colors()['border']};")
        self._refresh_icon_preview()
        from fluent_ui.components.setting_rows import SettingRow
        row = SettingRow("当前软件图标", "用于主窗口、任务栏和托盘。\n动图使用已选的缩略图帧；未选择时使用第一帧。", self)
        row.add_control(self.icon_preview)
        section.add_row(row)
        from fluent_ui.components.interaction_controls import DropDownButton
        from fluent_ui.components.safe_round_menu import SafeRoundMenu
        from qfluentwidgets import Action
        self.icon_change = DropDownButton(self)
        bind_text(self.icon_change, '更改', 'setText')
        menu = SafeRoundMenu(parent=self.icon_change)
        for text, callback in [('从本地文件选择…', self._pick_app_icon_file),
                               ('从表情库选择…', self._pick_app_icon_resource), ('恢复默认', self._reset_app_icon)]:
            action = translated(Action, text, parent=menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.icon_change.setMenu(menu)
        row.add_control(self.icon_change)

    def _refresh_icon_preview(self):
        from PySide6.QtGui import QPixmap
        from services.app_icon import ApplicationIconService
        path = ApplicationIconService(self.config).current_path()
        if os.path.exists(path):
            self.icon_preview.setPixmap(
                QPixmap(path).scaled(self.icon_preview.size()-QSize(12,12), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _apply_icon_change(self):
        self._refresh_icon_preview()
        self.settings_changed.emit("app_icon")

    def _pick_app_icon_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("选择程序图标"), "", t("表情 (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.ico)"))
        if not path:
            return
        self._set_icon(path)

    def _pick_app_icon_resource(self):
        if not self.storage:
            return
        images = self.storage.get_all_images()
        if not images:
            self.show_error(t("表情库为空"), t("请先导入表情"))
            return
        choices = [(p, os.path.basename(p)) for p in images[:400]]
        from fluent_ui.components.dialogs import choose_item
        path, ok = choose_item(self.window(), "选择程序图标", "选择表情", choices, code="ICON")
        if ok:
            self._set_icon(path)

    def _set_icon(self, path):
        from services.app_icon import ApplicationIconService
        try:
            frame=int(self.storage.resource_metadata(path).get('thumb_frame',0) or 0) if self.storage else 0
            ApplicationIconService(self.config).set_from_image(path,frame=frame)
        except Exception as exc:
            self.show_error(t("设置图标失败"), str(exc))
            return
        self._apply_icon_change()
        self.show_success(t("程序图标已更新"))

    def _reset_app_icon(self):
        from services.app_icon import ApplicationIconService
        # Replacing the application icon replaces a visible identity choice, and
        # the previous image is not restored by Discard, so it is confirmed.
        if not dialogs.confirm(self.window(), t("恢复默认图标"),
                               t("恢复为程序自带的软件图标？"),
                               ok_text=t("恢复默认"), danger=True, code="APPICON/RESET",
                               hint=t("当前使用的自定义图标会被替换，原表情文件不受影响。")):
            return
        ApplicationIconService(self.config).reset()
        self._apply_icon_change()
        self.show_success(t("已恢复默认图标"))

    def _page_hotkeys(self):
        section = self._section("GLOBAL HOTKEYS")
        section.add_row(self._track(
            HotkeyRow("唤醒快捷键", "全局显示 / 隐藏主面板。", "global_hotkey",
                      self.config.get("global_hotkey", "ctrl+shift+e"), self),
            "global_hotkey", "ctrl+shift+e"))
        section.add_row(self._track(
            HotkeyRow("快速面板快捷键", "全局呼出快速表情面板。", "quick_panel_hotkey",
                      self.config.get("quick_panel_hotkey", "alt+2"), self),
            "quick_panel_hotkey", "alt+2"))
        section = self._section('Esc 隐藏面板')
        for key, title in (('esc_hide_main', '主面板'), ('esc_hide_quick', '快速面板')):
            row = SwitchRow(title, '按 Esc 隐藏面板，程序会继续在托盘运行。',
                            key, self.config.get(key, False), self)
            section.add_row(self._track(row, key, False))

    def _page_send(self):
        section = self._section("SENDING")
        section.add_row(self._track(ModeRow('主面板单击表情',
            '选择表情：单击选中，按 Enter 发送。\n快速发送：单击即可发送。\n也可将表情拖到聊天窗口发送。\n快速面板始终为单击发送。',
            'gallery_click_action', self.config.get('gallery_click_action', 'select'),
            [('select', '选择表情'), ('send', '快速发送')], self), 'gallery_click_action', 'select'))
        section.add_row(self._track(
            SwitchRow("发送时将静态图转为 GIF",
                      "复制静态图时转为单帧 GIF，避免在聊天软件中显示为超大原图。",
                      "convert_static_to_gif", self.config.get("convert_static_to_gif", True), self),
            "convert_static_to_gif", True))

    def _page_packages(self):
        section = self._section("NEKORI PACKAGE")
        section.add_row(ActionRow(
            "导出 Nekori 原生表情合集",
            "保存全部表情，以及分类、图标、标签与排列顺序。",
            [("导出…", self.export_nekori_package, True)], self))
        section.add_row(ActionRow(
            "导入 Nekori 原生表情合集",
            "恢复表情合集中的内容与排列顺序。\n已有表情会合并分类与标签，不会重复保存。",
            [("导入…", self.import_nekori_package, True)], self))

        section = self._section("SUZU SHARE PACKAGE")
        section.add_row(ActionRow(
            "导入 Suzu 分享包",
            "导入 Suzu 分享的表情与标签。\nSuzu 格式不包含完整分类与排列顺序。",
            [("导入…", self.import_suzu_share, False)], self))

        section.add_row(ActionRow('导出 Suzu 分享包', '导出为兼容 Suzu 的分享格式，不包含完整 NekoriEmojy 分类和排序信息。',
            [('导出全部…', lambda: self._legacy_share('all')), ('选择分类…', lambda: self._legacy_share('categories'))], self))
        section.add_row(ActionRow('拆分表情合集', '将表情 ZIP 拆分为不超过 100MB 的分享包。',
            [('拆分…', lambda: self._legacy_share('split'))], self))

    def export_nekori_package(self):
        from services.nekori_package import NekoriPackageService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        path, _ = QFileDialog.getSaveFileName(
            self, t("导出 Nekori 表情合集"), "NekoriEmojy.nkpkg.zip", t("Nekori 表情合集 (*.zip)"))
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        service = NekoriPackageService(self.storage)
        try:
            manifest = run_exchange_task(
                self.window(), "正在导出 Nekori 表情合集",
                lambda progress: service.export(path, progress))
        except Exception as exc:
            self.show_error(t("导出失败"), str(exc))
            return
        self.show_success(t("导出完成"), t('表情 {value_0} 项，分类 {value_1} 个\n{value_2}').format(value_0=manifest['resources'], value_1=manifest['nodes'], value_2=path))

    def import_nekori_package(self):
        from services.nekori_package import NekoriPackageService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        path, _ = QFileDialog.getOpenFileName(
            self, t("导入 Nekori 表情合集"), "", t("Nekori 表情合集 (*.zip)"))
        if not path:
            return
        service = NekoriPackageService(self.storage)
        try:
            report = run_exchange_task(
                self.window(), "正在导入 Nekori 表情合集",
                lambda progress: service.import_package(path, progress))
        except Exception as exc:
            self.show_error(t("导入失败"), str(exc))
            return
        self.settings_changed.emit("library_rescan")
        self.show_success(t("导入完成"),
                          t('表情 {value_0} 项，分类 {value_1} 个，跳过重复 {value_2} 项').format(value_0=report['resources'], value_1=report['nodes'], value_2=report['duplicates']))

    def import_suzu_share(self):
        from services.exchange_import import ExchangeImportService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        path, _ = QFileDialog.getOpenFileName(self, t("导入 Suzu 分享包"), "", t("表情合集 (*.zip)"))
        if not path:
            return
        service = ExchangeImportService(storage=self.storage)
        try:
            saved, skipped = run_exchange_task(
                self.window(), "正在导入共享表情合集",
                lambda progress: service.import_zip(path, progress))
        except Exception as exc:
            self.show_error(t("导入失败"), str(exc))
            return
        self.storage.force_reload()
        self.settings_changed.emit("library_rescan")
        self.show_success(t("导入完成"), t('新增 {value_0} 项，跳过 {value_1} 项').format(value_0=saved, value_1=skipped))

    def _page_migration(self):
        section = self._section("Suzu 数据兼容")
        section.add_row(ActionRow(
            "Suzu 迁移",
            "复制 Suzu 中的表情、分类与标签。\n导入前可预览，Suzu 中的内容保持不变。",
            [("开始迁移", self._start_migration, True)], self))

    def _start_migration(self):
        source, accepted = dialogs.choose_item(self.window(), t('开始迁移'), t('选择迁移来源'),
            [('running', t('从运行中的 Suzu 迁移')), ('package', t('从 Suzu 表情压缩包迁移'))])
        if accepted:
            (self.migrate_from_suzu_data if source == 'running' else self.migrate_from_suzu_package)()

    def migrate_from_suzu_data(self):
        from services.suzu_migration import SuzuMigrationService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        from fluent_ui.components.suzu_instance_dialog import SuzuInstanceDialog
        service = SuzuMigrationService(self.storage)
        dialog = SuzuInstanceDialog(self.window(), service)
        if not dialog.exec() or not dialog.selected_data_dir:
            return
        directory = dialog.selected_data_dir
        try:
            report = run_exchange_task(
                self.window(), "正在从 Suzu 数据迁移",
                lambda progress: service.migrate_from_data_dir(directory, progress))
        except Exception as exc:
            self.show_error(t("迁移失败"), str(exc))
            return
        self.settings_changed.emit("library_rescan")
        summary = t('表情 {value_0} 项，分类 {value_1} 个，跳过重复 {value_2} 项，缺失 / 失败 {value_3} 项').format(value_0=report['resources'], value_1=report['nodes'], value_2=report['duplicates'], value_3=report.get('skipped', 0))
        self.feedback_host.notice(t('迁移完成'), summary, error=bool(report.get('skipped')) and not report['resources'])

    def migrate_from_suzu_package(self):
        path, _ = QFileDialog.getOpenFileName(self, t("选择 Suzu 表情压缩包"), "", t("表情合集 (*.zip)"))
        if not path:
            return
        from services.suzu_migration import SuzuMigrationService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        service = SuzuMigrationService(self.storage)
        try:
            preview = run_exchange_task(self.window(), t('迁移预览'), lambda progress: service.preview_package(path, progress))
            if not dialogs.confirm(self.window(), t('迁移预览'),
                t('表情 {value_0} 项，分类 {value_1} 个').format(value_0=preview['resources'], value_1=preview['nodes'])
                + '\n' + '、'.join(preview['categories']), ok_text=t('开始迁移')):
                return
            report = run_exchange_task(
                self.window(), "正在从 Suzu 压缩包迁移",
                lambda progress: service.migrate_from_package(path, progress))
        except Exception as exc:
            self.show_error(t("迁移失败"), str(exc))
            return
        self.settings_changed.emit("library_rescan")
        self.feedback_host.notice(t("迁移完成"),
                          t('表情 {value_0} 项，分类 {value_1} 个').format(value_0=report['resources'], value_1=report['nodes']))

    def _page_settings_file(self):
        section = self._section("SETTINGS FILE")
        self.export_hint = ActionRow(
            "导出设置", "把当前应用设置写入一个 JSON 文件。",
            [("导出…", self._export_settings, True)], self)
        section.add_row(self.export_hint)
        import_row = ActionRow(
            "导入设置", "从 JSON 文件恢复应用设置。",
            [("导入…", self._import_settings, False)], self)
        reset_row = ActionRow(
            "恢复全部默认", "把所有应用设置恢复到程序默认值；不会改动表情库内容。",
            [("恢复全部默认", self._restore_all_defaults, False)], self)
        section.add_row(import_row)
        section.add_row(reset_row)
        self._dirty_blocked_actions = [import_row.controls.itemAt(0).widget(), reset_row.controls.itemAt(0).widget()]
        self._set_dirty(bool(self.pending))

    def _page_about(self):
        from services.update_service import current_version
        section = self._section("APPLICATION")
        self.version_row=InfoRow('版本','NekoriEmojy','v'+current_version())
        self.btn_update=PushButton(FIF.CLOUD_DOWNLOAD,t('检查更新'),self.version_row)
        self.btn_update.clicked.connect(self._open_updates);self.version_row.add_control(self.btn_update)
        section.add_row(self.version_row)
        self.update_badge=TransparentToolButton(FIF.CLOUD_DOWNLOAD,self.version_row)
        self.update_badge.setFixedSize(22,22);self.version_row.add_control(self.update_badge)
        self.update_badge.clicked.connect(self._open_updates);self.update_badge.hide()
        from fluent_ui.components.update_center import update_center
        state=update_center();state.changed.connect(self._sync_update_status);self._sync_update_status()
        section.add_row(ActionRow(
            "关于 NekoriEmojy", "查看版本、作者与项目信息。",
            [("查看详情", self.about_requested.emit, True)], self))

    def _open_updates(self):
        from fluent_ui.components.update_center import update_center
        update_center().open(self.window())

    def _sync_update_status(self):
        if not hasattr(self,'update_badge'):return
        from fluent_ui.components.update_center import update_center
        release=update_center().release
        self.update_badge.setVisible(bool(release))
        self.update_badge.setToolTip(t('可用更新')+(' · v'+release['version'] if release else ''))

    # ==================================================================
    # Save / discard / defaults / settings file
    # ==================================================================
    def _stage(self, key, value):
        saved = self._autostart_enabled() if key == 'autostart' else self.config.config.get(key, self.config.default_config.get(key))
        if key == 'accent_color':
            from PySide6.QtGui import QColor
            saved, value = QColor(saved).name(), QColor(value).name()
        if value == saved:
            self.pending.pop(key, None)
        else:
            self.pending[key] = value
        if key in PREVIEW_KEYS and self.preview_enabled:
            if value == saved:
                self.config.preview_values.pop(key, None)
                self._preview_backup.pop(key, None)
            else:
                self._preview_backup.setdefault(key, saved)
                self.config.preview_values[key] = value
            if key == 'accent_color':
                self.settings_changed.emit('accent_preview')
                self._accent_commit_timer.start()
            else:
                self.settings_changed.emit(key)
        self._set_dirty(bool(self.pending))

    def sync_external_preference(self, key, value):
        """An explicit main-window shortcut commits its value and refreshes cached controls."""
        self.pending.pop(key, None)
        self._preview_backup.pop(key, None)
        self.config.preview_values.pop(key, None)
        row = self._all_rows.get(key, (None,))[0]
        if row is not None:
            row.set_value(value)
        if key == 'sidebar_mode' and hasattr(self, 'icon_options'):
            self.icon_options.setEnabled(value == 'categorized_icons')
        self._set_dirty(bool(self.pending))

    def _on_row_changed(self, key):
        row = self._rows.get(key, (None, None))[0]
        if row is not None:
            self._stage(key, row.value())

    def _on_preview_toggled(self, enabled):
        self._accent_commit_timer.stop()
        self.preview_enabled = bool(enabled)
        # This is a preference of the editor itself, not an unsaved setting.
        self.config.set('settings_preview',self.preview_enabled)
        self.pending.pop('settings_preview',None)
        for key, value in self._preview_backup.items():
            self.config.preview_values[key] = self.pending.get(key, value) if enabled else value
            if not enabled:
                self.config.preview_values.pop(key, None)
            self.settings_changed.emit(key)
        if enabled:
            for key, value in list(self.pending.items()):
                if key in PREVIEW_KEYS and key not in self._preview_backup:
                    self._stage(key, value)
        self._set_dirty(bool(self.pending))

    def _set_dirty(self, dirty):
        self._dirty = bool(dirty)
        for key,(row,_) in self._all_rows.items():row.set_pending(key in self.pending)
        self.dirty_label.setText(t("未保存的修改") if dirty else "")
        valid = self._hotkeys_valid(self.pending)
        self.btn_save.setEnabled(dirty and valid)
        self.btn_discard.setEnabled(dirty)
        self.btn_import.setEnabled(not dirty)
        self.btn_defaults.setEnabled(not dirty)
        for button in getattr(self, '_dirty_blocked_actions', []):
            button.setEnabled(not dirty)
        if hasattr(self, 'export_hint'):
            self.export_hint.set_hint(t('未保存修改不会包含在导出文件中。') if dirty else '')

    def has_pending_changes(self):
        return bool(self.pending)

    def save(self):
        self._accent_commit_timer.stop()
        keys = dict(self.pending)
        if not keys:
            return True
        if not self._hotkeys_valid(keys):
            return False
        original = dict(self.config.config)
        original.update(self._preview_backup)
        autostart_before = self._autostart_enabled()
        try:
            if 'autostart' in keys:
                self.autostart.set_enabled(keys['autostart'])
            self.config.config.update({k: v for k, v in keys.items() if k != 'autostart'})
            self.config._save_config(self.config.config)
        except (OSError, RuntimeError) as error:
            self.config.config.update(original)
            if 'autostart' in keys:
                self.autostart.set_enabled(autostart_before)
            self.show_error(t('保存失败'), str(error))
            return False
        self.pending.clear()
        self.config.preview_values.clear()
        self._preview_backup.clear()
        for key in keys:
            if key == 'language':
                i18n_engine.set_language(keys[key])
            self.settings_changed.emit(key)
        self._set_dirty(False)
        self.show_success(t('设置已保存'))
        return True

    def _hotkeys_valid(self, keys):
        main = keys.get("global_hotkey", self.config.get("global_hotkey", ""))
        quick = keys.get("quick_panel_hotkey", self.config.get("quick_panel_hotkey", ""))
        normalize = lambda text: '+'.join(sorted(part.strip().lower() for part in text.split('+')))
        conflict = bool(main and quick and normalize(main) == normalize(quick))
        for key in ('global_hotkey', 'quick_panel_hotkey'):
            row = self._all_rows.get(key, (None,))[0]
            if row is not None:
                row.set_hint(t('唤醒快捷键与快速面板快捷键不能相同') if conflict else '')
                row.hint_label.setStyleSheet(f'color: {visual.colors()["danger"]};' if conflict else '')
        return not conflict

    def discard(self):
        self._accent_commit_timer.stop()
        for key, value in self._preview_backup.items():
            self.config.preview_values.pop(key, None)
            self.settings_changed.emit(key)
        self._preview_backup.clear()
        self.pending.clear()
        for key, (row, default) in self._all_rows.items():
            if key == "autostart":
                row.set_value(self._autostart_enabled())
                continue
            value = self.config.get(key, default)
            row.set_value(default if value is None else value)
        self.preview_enabled = bool(self.config.get("settings_preview", True))
        self.preview_switch.blockSignals(True)
        self.preview_switch.setChecked(self.preview_enabled)
        from fluent_ui.icons import Icon
        self.preview_switch.setIcon(Icon.EYE if self.preview_enabled else Icon.EYE_OFF)
        self.preview_switch.blockSignals(False)
        self._set_dirty(False)
        if hasattr(self, 'library_info'):
            self.library_info.set_value(self._library_path())
            self.library_info.set_hint(t('保存后重启切换表情库。'))
        if hasattr(self, 'icon_options'):
            self.icon_options.setEnabled(self.config.get('sidebar_mode', 'tree') == 'categorized_icons')
        self.show_success(t("已放弃修改"))

    def _restore_page_defaults(self):
        if self.pending:
            return
        # Overwrites every row on this page at once, so the values the user
        # already changed here would be gone before they notice.
        if not dialogs.confirm(self.window(), t("恢复本页默认"),
                               t("把本页设置恢复为程序默认值？"),
                               ok_text=t("恢复默认"), danger=True, code="SETTINGS/PAGE",
                               hint=t("本页已修改的值会被覆盖；保存前仍可放弃修改。")):
            return
        defaults = self._default_config()
        for key, (row, _default) in list(self._rows.items()):
            if key == "app_icon":
                continue
            if key not in defaults:
                continue
            row.set_value(defaults[key])
            self._stage(key, defaults[key])
        self._set_dirty(bool(self.pending))
        self.show_success(t("已恢复本页默认值"), t("点击保存后生效"))

    def _restore_all_defaults(self):
        if self.pending:
            return
        if not dialogs.confirm(self.window(), t("恢复全部默认"),
                               t("把所有应用设置恢复为程序默认值？"),
                               ok_text=t("恢复默认"), danger=True, code="SETTINGS",
                               hint=t("表情库内容、分类、标签与排序不会受影响。")):
            return
        defaults = self._default_config()
        for key, value in defaults.items():
            self._stage(key, value)
        for key, (row, _) in self._all_rows.items():
            if key in defaults:
                row.set_value(defaults[key])
        self.show_success(t('默认值已载入'), t('点击保存后生效'))

    def _default_config(self):
        return dict(self.config.default_config, autostart=False)

    def _export_settings(self):
        path, _ = QFileDialog.getSaveFileName(self, t("导出设置"), "NekoriEmojy-settings.json",
                                              "JSON (*.json)")
        if not path:
            return
        snapshot = dict(self.config.config)
        # Window position is machine state, not a preference: exporting it
        # would move the window of whoever imports these settings.
        payload = {k: v for k, v in snapshot.items()
                   if k not in ("window_geometry", "window_screen")}
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4, ensure_ascii=False)
        except OSError as exc:
            self.show_error(t("导出失败"), str(exc))
            return
        self.show_success(t("设置已导出"), path)

    def _import_settings(self):
        if self.pending:
            return
        path, _ = QFileDialog.getOpenFileName(self, t("导入设置"), "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            self.show_error(t("导入失败"), str(exc))
            return
        if not isinstance(payload, dict):
            self.show_error(t("导入失败"), t("设置文件格式不正确"))
            return
        defaults = self._default_config()
        values = {k: v for k, v in payload.items() if k in defaults and type(v) is type(defaults[k])}
        if values.get('appearance_mode', 'system') not in ('system', 'light', 'dark') or any(values.get(k, 'nekori') not in THEMES for k in ('light_theme_key', 'dark_theme_key')):
            self.show_error(t('导入失败'), t('主题设置值不受支持'))
            return
        from PySide6.QtGui import QColor
        if 'accent_color' in values and not QColor(values['accent_color']).isValid():
            self.show_error(t('导入失败'), t('主题色无效'))
            return
        ranges = {'thumbnail_size': (60, 300), 'quick_panel_thumbnail_size': (40, 200), 'sidebar_icon_size': (14, 48), 'quick_panel_width': (250, 800), 'quick_panel_height': (150, 1000), 'recent_limit': (1, 999), 'preview_size': (100, 800), 'preview_delay': (100, 3000)}
        if any(k in values and not low <= values[k] <= high for k, (low, high) in ranges.items()):
            self.show_error(t('导入失败'), t('设置文件中的数值超出界面允许范围'))
            return
        for key, value in values.items():
            self._stage(key, value)
        for key, (row, _) in self._all_rows.items():
            if key in values:
                row.set_value(values[key])
        self.show_success(t('设置已载入'), t('{value_0} 项待保存，可放弃修改').format(value_0=len(values)))

    # ==================================================================
    # Sticky header, navigation guard, status
    # ==================================================================
    def _update_sticky_header(self, *_):
        sections = sorted((s for s in self.body_widget.findChildren(SettingSection) if s.isVisible()),key=lambda s:s.header.mapTo(self.body_widget,QPoint()).y())
        if not sections:
            self.sticky.hide()
            return
        offset = self.scroll.verticalScrollBar().value()
        if offset == 0:
            self.sticky.hide()
            return
        current = sections[0]
        for section in sections:
            if section.header.mapTo(self.body_widget,QPoint()).y() <= offset:
                current = section
            else:
                break
        if current.header.mapTo(self.body_widget,QPoint()).y() > offset or current.is_collapsed():
            self.sticky.hide()
            return
        self.sticky.setText(current.sections_key())
        self.sticky.setFixedSize(self.scroll.viewport().width(),32)
        following=[s.header.mapTo(self.body_widget,QPoint()).y()-offset for s in sections if s.header.mapTo(self.body_widget,QPoint()).y()>offset]
        self.sticky.move(0,min(0,min(following)-32) if following else 0)
        self.sticky.show()
        self.sticky.raise_()

    def confirm_close(self):
        if not self.has_pending_changes():
            return True
        dialog = dialogs.NekoriDialog(self.window(), t('有未保存的设置'), code='SETTINGS')
        dialog.add_hint(t('保存这些修改，或放弃修改后关闭设置。'))
        result = {'action': 'cancel'}
        def finish(action):
            result['action'] = action
            dialog.accept()
        dialog.add_button(t('继续编辑'), on_click=dialog.reject)
        dialog.add_button(t('放弃修改'), on_click=lambda: finish('discard'))
        dialog.add_button(t('保存并关闭'), role='primary', on_click=lambda: finish('save'))
        dialog.exec()
        if result['action'] == 'save':
            return self.save()
        if result['action'] == 'discard':
            self.discard()
            return True
        return False

    def _go_back(self):
        self.back_requested.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_autostart()
        QTimer.singleShot(0, self._update_sticky_header)

    def _sync_autostart(self):
        row = self._rows.get("autostart", (None, None))[0]
        if row is not None and "autostart" not in self.pending:
            row.set_value(self._autostart_enabled())

    def show_success(self, title, content=""):
        if getattr(title, 'source', str(title)) not in {'设置已保存', '已放弃修改', '程序图标已更新', '已恢复默认图标',
                                                      '默认值已载入', '设置已载入', '已恢复本页默认值', '导入完成'}:
            self.feedback_host.toast(title, content)

    def show_error(self, title, content=""):
        self.feedback_host.notice(title, content, error=True)

    def refresh_theme(self):
        self._apply_style()
        self._update_sticky_header()

    def _page_hover_preview(self):
            section = self._section("HOVER PREVIEW")
            section.add_row(self._track(
                RangeRow("预览浮窗大小", "鼠标悬停时弹出的大图尺寸。", "preview_size",
                         self.config.get("preview_size", 320), 100, 800, 10, self),
                "preview_size", 320))
            section.add_row(self._track(
                RangeRow("预览延迟", "鼠标停留多久后弹出预览。", "preview_delay",
                         self.config.get("preview_delay", 500), 100, 3000, 50, self),
                "preview_delay", 500))
            section.add_row(self._track(
                ModeRow("表情预览位置", "固定：停靠在表情区右下角，被遮挡时移到左下；浮动：跟随鼠标。",
                          "preview_position", self.config.get("preview_position", "floating"),
                          [("fixed", "固定"), ("floating", "浮动")], self),
                "preview_position", "floating"))

    def _legacy_share(self, action):
        owner = self.window().owner
        if action == 'all':
            owner.gallery_interface._export_all_exchange_package(owner=self.window())
        elif action == 'categories':
            owner.gallery_interface._export_selected_categories_exchange_package(owner=self.window())
        else:
            owner.exchange_interface._split_package(owner=self.window())
