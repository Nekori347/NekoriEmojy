"""One thread-bound Windows hotkey; no window handle or keyboard hook."""
import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal, Qt, QAbstractNativeEventFilter
from PySide6.QtGui import QKeySequence


def hotkey_parts(text):
    text = '+'.join('Meta' if part.strip().lower() == 'win' else part.strip()
                    for part in text.split('+'))
    sequence = QKeySequence.fromString(text, QKeySequence.PortableText)
    if sequence.count() != 1:
        raise ValueError('快捷键无效，请使用修饰键与一个按键。')
    combination = sequence[0]
    key = combination.key().value
    modifiers = combination.keyboardModifiers()
    mods = sum(value for flag, value in ((Qt.AltModifier, 1), (Qt.ControlModifier, 2),
               (Qt.ShiftModifier, 4), (Qt.MetaModifier, 8)) if modifiers & flag)
    mapping = {Qt.Key_Space: 0x20, Qt.Key_Tab: 9, Qt.Key_Return: 13,
               Qt.Key_Backspace: 8, Qt.Key_Insert: 0x2D, Qt.Key_Delete: 0x2E,
               Qt.Key_Home: 0x24, Qt.Key_End: 0x23, Qt.Key_PageUp: 0x21,
               Qt.Key_PageDown: 0x22, Qt.Key_Left: 0x25, Qt.Key_Up: 0x26,
               Qt.Key_Right: 0x27, Qt.Key_Down: 0x28,
               Qt.Key_Plus: 0xBB, Qt.Key_Equal: 0xBB, Qt.Key_Minus: 0xBD,
               Qt.Key_Comma: 0xBC, Qt.Key_Period: 0xBE, Qt.Key_Slash: 0xBF,
               Qt.Key_Semicolon: 0xBA, Qt.Key_Apostrophe: 0xDE,
               Qt.Key_BracketLeft: 0xDB, Qt.Key_BracketRight: 0xDD,
               Qt.Key_Backslash: 0xDC, Qt.Key_QuoteLeft: 0xC0}
    if ord('0') <= key <= ord('9') or ord('A') <= key <= ord('Z'):
        vk = key
    elif Qt.Key_F1.value <= key <= Qt.Key_F24.value:
        vk = 0x70 + key - Qt.Key_F1.value
    else:
        vk = mapping.get(key)
    if not mods or vk is None:
        raise ValueError('快捷键无效，请使用修饰键与一个按键。')
    if (mods, vk) == (2, ord('V')):
        raise ValueError('请保留 Ctrl+V 用于普通粘贴。')
    return mods, vk


class WindowsHotkey(QObject, QAbstractNativeEventFilter):
    activated = Signal()
    changed = Signal()

    def __init__(self, app):
        QObject.__init__(self, app)
        QAbstractNativeEventFilter.__init__(self)
        self.app = app
        self.binding = None
        self.registration = None
        self.error = ''
        self.api = ctypes.WinDLL('user32', use_last_error=True) if sys.platform == 'win32' else None
        app.installNativeEventFilter(self)
        app.aboutToQuit.connect(self.close)

    def configure(self, enabled, text):
        try:
            binding = hotkey_parts(text) if enabled else None
            if binding == self.binding:
                self.error = ''
                self.changed.emit()
                return True
            registration = 0x4E4B if self.registration != 0x4E4B else 0x4E4C
            if binding is not None:
                if self.api is None:
                    raise ValueError('全局导入快捷键仅支持 Windows。')
                if not self.api.RegisterHotKey(None, registration, binding[0] | 0x4000, binding[1]):
                    raise ValueError('快捷键注册失败，可能已被其它程序占用。')
            if self.registration is not None:
                self.api.UnregisterHotKey(None, self.registration)
            self.registration = registration if binding else None
            self.binding = binding
            self.error = ''
        except ValueError as exc:
            self.error = str(exc)
            self.changed.emit()
            return False
        self.changed.emit()
        return True

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.registration:
                self.activated.emit()
                return True, 0
        return False, 0

    def close(self):
        if self.registration is not None:
            self.api.UnregisterHotKey(None, self.registration)
        self.registration = self.binding = None
        self.app.removeNativeEventFilter(self)
