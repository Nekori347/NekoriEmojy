"""Modeless settings window: preview immediately, save explicitly, close to revert."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFileDialog,QLabel,QMessageBox
from qfluentwidgets import PushButton,PrimaryPushButton,BodyLabel
from fluent_ui.views.setting_view import SettingInterface


class SettingsWindow(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window, Qt.Window)
        self.main_window=main_window
        self.config=main_window.config
        self.setWindowTitle('NekoriEmojy 设置')
        self.setWindowIcon(main_window.windowIcon())
        self.setModal(False)
        self.resize(860,780)
        self.setMinimumSize(650,500)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,12)
        self.page=None
        self.page_layout=QVBoxLayout()
        layout.addLayout(self.page_layout,1)
        self.status=BodyLabel('调整即时预览；保存后保留，关闭会撤销未保存的设置。',self)
        self.status.setContentsMargins(20,0,20,0)
        layout.addWidget(self.status)
        buttons=QHBoxLayout();buttons.setContentsMargins(20,0,20,0)
        for title,callback in [('恢复默认',self.reset),('导入设置',self.import_settings),('导出设置',self.export_settings)]:
            button=PushButton(title,self);button.clicked.connect(callback);buttons.addWidget(button)
        buttons.addStretch()
        cancel=PushButton('取消预览',self);cancel.clicked.connect(self.close);buttons.addWidget(cancel)
        save=PrimaryPushButton('保存',self);save.clicked.connect(self.save);buttons.addWidget(save)
        layout.addLayout(buttons)
        self.rebuild_page()
        self.update_theme()

    def update_theme(self):
        from fluent_ui.theme import get_current_background_color
        from qfluentwidgets import isDarkTheme
        from PySide6.QtGui import QPalette, QColor
        palette = self.palette()
        palette.setColor(QPalette.Window, get_current_background_color(self.config))
        palette.setColor(QPalette.WindowText, QColor("white" if isDarkTheme() else "#202020"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def rebuild_page(self):
        if self.page is not None:
            self.page_layout.removeWidget(self.page)
            self.page.hide();self.page.deleteLater()
        self.page=SettingInterface(self.config,self)
        self.main_window.setting_interface=self.page
        self.page.btnBack.hide()
        self.page.settings_changed.connect(self.main_window.on_settings_changed)
        self.page.about_requested.connect(self.main_window.show_about)
        self.page_layout.addWidget(self.page)

    def show_settings(self):
        if not self.isVisible():
            self.config.begin_preview()
            self.rebuild_page()
        self.show();self.raise_();self.activateWindow()

    def refresh_preview(self):
        self.main_window.apply_preferences()
        self.rebuild_page()

    def save(self):
        from services.windows_startup import read_startup, apply_startup, restore_startup
        startup_changed = self.config.get('start_with_windows') != self.config.saved('start_with_windows')
        applied = False
        previous = None
        try:
            if startup_changed:
                previous = read_startup()
                apply_startup(self.config.get('start_with_windows'), self.config.context)
                applied = True
            self.config.save_preview()
        except Exception as exc:
            message = str(exc)
            if applied:
                try:
                    restore_startup(previous)
                except OSError:
                    message += '\n启动项恢复失败，请在 Windows 启动应用中检查 NekoriEmojy。'
            QMessageBox.warning(self, '设置未保存', message)
            return
        self.status.setText('设置已保存。之后的调整仍会先预览。')
        try:
            self.main_window.apply_preferences()
        except Exception as exc:
            QMessageBox.warning(self, '设置已保存', '预览刷新失败，重新打开软件后应用：' + str(exc))

    def reset(self):
        self.config.restore_defaults_preview()
        self.refresh_preview()
        self.status.setText('已预览默认设置，点击保存后生效。图库和分类保留。')

    def import_settings(self):
        source,_=QFileDialog.getOpenFileName(self,'导入设置','','Nekori 设置 (*.json)')
        if not source:return
        try:
            self.config.import_preferences_preview(source)
            self.refresh_preview()
            self.status.setText('已预览导入设置，点击保存后保留。当前资源库未切换。')
        except Exception as exc:
            QMessageBox.warning(self,'设置未导入',str(exc))

    def export_settings(self):
        destination,_=QFileDialog.getSaveFileName(self,'导出设置','NekoriEmojy-settings.json','Nekori 设置 (*.json)')
        if not destination:return
        try:
            self.config.export_preferences(destination)
            self.status.setText('已导出当前预览的偏好；图片、路径及凭据不包含在内。')
        except Exception as exc:
            QMessageBox.warning(self,'设置未导出',str(exc))

    def closeEvent(self,event):
        if self.page.libraryPanel.job and self.page.libraryPanel.job.isRunning():
            event.ignore();return
        self.config.cancel_preview()
        self.main_window.apply_preferences()
        super().closeEvent(event)
