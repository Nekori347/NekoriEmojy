"""Compatibility facade routing existing workers to the owner-local feedback lane."""
from PySide6.QtCore import QObject, Signal
from fluent_ui.components.feedback import feedback_for


class StateToolTipManager(QObject):
    closed = Signal()

    def __init__(self, parent=None, closable=True):
        super().__init__(parent)
        self.host = feedback_for(parent)
        self.title_label = self.host.title_label
        self._closable = closable
        self._tip = self.host.strip

    def is_active(self):
        return self.host.task_active

    def show(self, title, content='', total=None, *, cancellable=True):
        cancel = self.closed.emit if cancellable and self._closable and callable(getattr(self.parent(), '_on_tooltip_closed', None)) else None
        self.host.task(title, content, total=total, cancel=cancel)

    def update(self, content, title=None, current=None, total=None):
        if title is not None:
            self.title_label.setText(title)
        self.host.update_task(current, total, content)

    def finish(self, title=None, content=None, *, outcome='success'):
        self.host.finish(title or '', content or '', outcome=outcome)

    def fail(self, title, content=''):
        self.finish(title, content, outcome='error')

    def cancel(self):
        self.host.task_active = False
        self.host.finish_timer.stop()
        self.host._restore_notice()

    def reposition(self):
        self.host.reposition()
