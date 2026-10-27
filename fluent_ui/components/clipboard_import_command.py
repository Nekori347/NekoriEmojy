"""Wire the system shortcut to the same clipboard command and import queue."""
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication
from services.import_hotkey import WindowsHotkey
from services.library_index import ROOT
from services.i18n import t


class ClipboardImportCommand(QObject):
    def __init__(self, window, config, tray):
        super().__init__(window)
        self.window, self.config, self.tray = window, config, tray
        self.gallery = window.gallery_interface
        self.request_id = None
        self.hotkey = WindowsHotkey(QApplication.instance())
        config.clipboard_import_command = self
        self.hotkey.changed.connect(lambda: window.settings_window.center._hotkeys_valid(
            window.settings_window.center.pending))
        # Native callbacks only enqueue this command; clipboard work stays out
        # of the Windows message filter.
        self.hotkey.activated.connect(self.trigger, Qt.QueuedConnection)
        self.gallery.imports.changed.connect(self.task_changed)
        window.settings_window.center.settings_changed.connect(self.settings_changed)
        self.settings_changed('clipboard_import_hotkey')

    def configure(self, values):
        from services.import_hotkey import hotkey_parts
        get = lambda key, default: values.get(key, self.config.get(key, default))
        enabled = get('clipboard_import_enabled', True)
        text = get('clipboard_import_hotkey', 'ctrl+alt+v')
        if enabled:
            try:
                parts = hotkey_parts(text)
                for key in ('global_hotkey', 'quick_panel_hotkey'):
                    try: same = parts == hotkey_parts(get(key, ''))
                    except ValueError: same = False
                    if same:raise ValueError('导入快捷键不能与唤醒或快速面板快捷键相同。')
            except ValueError as exc:
                self.hotkey.error = str(exc)
                self.hotkey.changed.emit()
                return False
        return self.hotkey.configure(enabled, text)

    def settings_changed(self, key):
        if key in {'clipboard_import_hotkey', 'clipboard_import_enabled'}:
            self.configure({})
            if self.hotkey.error:
                self.feedback(t(self.hotkey.error))

    def feedback(self, message):
        if self.window.isVisible() and not self.window.isMinimized():
            self.gallery.feedback_host.toast(message)
        else:
            self.tray.showMessage('NekoriEmojy', message)

    def trigger(self):
        request = self.gallery.imports.requests.get(self.request_id)
        if request and request.state not in {'completed', 'failed', 'cancelled'}:
            self.feedback(t('剪贴板导入仍在进行，请先完成当前任务。'))
            return
        self.request_id = self.gallery.paste_clipboard_to(ROOT, background=True, notify=self.feedback)

    def task_changed(self, key):
        if key != self.request_id:
            return
        request = self.gallery.imports.requests.get(key)
        if request and request.state == 'decision':
            self.feedback(t('重复表情等待处理，请打开 Nekori 继续。'))
        elif request and request.state in {'completed', 'failed', 'cancelled'}:
            self.feedback(t('导入失败') if request.state == 'failed' else t('导入处理已停止')
                          if request.state == 'cancelled' else t('导入处理完成'))


def install_clipboard_import(window, config, tray):
    window.clipboard_import_command = ClipboardImportCommand(window, config, tray)
