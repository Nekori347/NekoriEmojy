"""One process-local source operation; an event, never a timed input lock."""
from PySide6.QtCore import QObject,Signal,QCoreApplication
from shiboken6 import isValid


class DragActivity(QObject):
    idle=Signal()
    def __init__(self,parent=None):super().__init__(parent);self.operation=None
    def begin(self,operation):
        if self.operation is not None:return False
        self.operation=operation;return True
    def end(self,operation):
        if self.operation is operation:
            self.operation=None;self.idle.emit()


_activity=None
def drag_activity():
    global _activity
    if _activity is None or not isValid(_activity):_activity=DragActivity(QCoreApplication.instance())
    return _activity
