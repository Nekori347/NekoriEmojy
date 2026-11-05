"""One opt-in native shortcut, independent of the main/quick panel hooks."""
from PySide6.QtCore import QObject,Qt
from PySide6.QtWidgets import QApplication
from services.import_hotkey import WindowsHotkey,hotkey_parts


class ClipboardSearchCommand(QObject):
    def __init__(self,window,config):
        super().__init__(window);self.window=window;self.config=config
        self.hotkey=WindowsHotkey(QApplication.instance(),base_id=0x4E50)
        config.clipboard_search_command=self
        self.hotkey.activated.connect(window.search_clipboard_text,Qt.QueuedConnection)
        center=window.settings_window.center
        self.hotkey.changed.connect(lambda:center._hotkeys_valid(center.pending))
        center.settings_changed.connect(self.settings_changed)
        self.configure({})

    def configure(self,values):
        get=lambda k,d='':values.get(k,self.config.get(k,d))
        text=get('clipboard_search_hotkey')
        if text:
            try:
                binding=hotkey_parts(text)
                for key in ('global_hotkey','quick_panel_hotkey','clipboard_import_hotkey'):
                    if key=='clipboard_import_hotkey' and not get('clipboard_import_enabled',True):continue
                    other=get(key)
                    if other and binding==hotkey_parts(other):raise ValueError('快捷键不能与其它功能相同。')
            except ValueError as error:
                self.hotkey.error=str(error);self.hotkey.changed.emit();return False
        return self.hotkey.configure(bool(text),text)

    def settings_changed(self,key):
        if key=='clipboard_search_hotkey':self.configure({})
