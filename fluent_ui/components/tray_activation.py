"""Tray gestures → tray actions: one action set, one dispatcher, one timing rule.

Every rebindable gesture (left click, left double click, middle click) picks one
member of the same `TrayAction` set and runs it through the same
`execute_tray_action`, so no gesture has its own copy of "show the window"
logic. The right button is not a gesture here at all: it always opens the
context menu.

Left single click waits for the platform double-click interval so a double
click can cancel it; the interval comes from the system, never a constant.
Middle click is not part of that pair and runs immediately.
"""
from enum import Enum

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon


class TrayGesture(str, Enum):
    """The tray gestures a user can rebind."""

    LEFT_CLICK = 'left_click'
    LEFT_DOUBLE_CLICK = 'left_double_click'
    MIDDLE_CLICK = 'middle_click'


class TrayAction(str, Enum):
    """What a gesture does. Shared by every gesture; the trigger is not behaviour."""

    TOGGLE_MAIN = 'toggle_main'
    SHOW_MAIN = 'show_main'
    TOGGLE_QUICK = 'toggle_quick'
    SHOW_QUICK = 'show_quick'
    OPEN_SETTINGS = 'open_settings'
    NONE = 'none'

    @classmethod
    def parse(cls, value, default=None):
        default = default if default is not None else cls.NONE
        if isinstance(value, cls):
            return value
        text = str(value).strip().lower()
        if '.' in text:
            text = text.rsplit('.', 1)[-1]
        text = LEGACY_ACTIONS.get(text, text)
        try:
            return cls(text)
        except ValueError:
            return default


# Values stored by the earlier two-setting tray model.
LEGACY_ACTIONS = {
    'main': TrayAction.TOGGLE_MAIN.value,
    'quick': TrayAction.TOGGLE_QUICK.value,
}


def execute_tray_action(window, action):
    """The single dispatcher every gesture goes through."""
    action = TrayAction.parse(action)
    if action is TrayAction.TOGGLE_MAIN:
        window.toggle_window(from_tray=True)
    elif action is TrayAction.SHOW_MAIN:
        window.show_main_panel()
    elif action is TrayAction.TOGGLE_QUICK:
        window.toggle_quick_panel(capture_target=False, from_tray=True)
    elif action is TrayAction.SHOW_QUICK:
        window.show_quick_panel(from_tray=True)
    elif action is TrayAction.OPEN_SETTINGS:
        window.show_settings()


class TrayActivation(QObject):
    """Route system tray activations to the configured gesture callbacks."""

    def __init__(self, gestures, context, parent=None):
        super().__init__(parent)
        # ActivationReason → callable, so adding a gesture never adds a branch.
        self.gestures = dict(gestures)
        self.context = context
        self.state = 'idle'
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.finish)

    def interval(self):
        """The platform's double-click interval; never a hardcoded constant."""
        return QApplication.styleHints().mouseDoubleClickInterval()

    def activate(self, reason):
        if reason == QSystemTrayIcon.Context:
            self.timer.stop()
            self.state = 'idle'
            self.context()
        elif reason == QSystemTrayIcon.MiddleClick:
            # Independent of the single / double pair: press it, get it, now.
            self.run(reason)
        elif reason == QSystemTrayIcon.DoubleClick:
            self.timer.stop()
            self.state = 'double-release'
            self.run(reason)
            self.timer.start(self.interval())
        elif reason == QSystemTrayIcon.Trigger:
            # Windows may deliver the second button-up after DoubleClick.
            if self.state == 'double-release':
                self.state = 'idle'
                self.timer.stop()
                return
            self.state = 'pending-single'
            self.timer.start(self.interval())

    def finish(self):
        """The wait elapsed: this really was a single click."""
        pending = self.state == 'pending-single'
        self.state = 'idle'
        if pending:
            self.run(QSystemTrayIcon.Trigger)

    def run(self, reason):
        callback = self.gestures.get(reason)
        if callback is not None:
            callback()
