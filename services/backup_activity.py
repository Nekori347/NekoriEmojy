"""Small, thread-safe foreground pressure signal shared by catalog and Qt host."""
import threading
import time

_activities = {}
_lock = threading.Lock()


class BackupActivity:
    def __init__(self):
        self.tracking = False
        self.last_activity = 0.0
        self.reason = ''
        self.writers = 0
        self.operations = {}
        self.notify = None
        self._lock = threading.Lock()

    def pulse(self, reason='正在使用表情库'):
        if not self.tracking:return
        with self._lock:
            self.last_activity = time.monotonic()
            self.reason = reason
        if self.notify:self.notify()

    def writer(self, active):
        if active and not self.tracking:return
        with self._lock:
            self.writers += 1 if active else -1
            self.writers = max(0, self.writers)
            self.last_activity = time.monotonic()
            self.reason = '正在更新表情库'
        if active and self.notify:self.notify()

    def busy(self, idle_seconds=2.0):
        with self._lock:
            if self.operations:return next(iter(self.operations.values()))
            return self.reason if self.writers or time.monotonic()-self.last_activity < idle_seconds else ''

    def operation(self,key,reason,active):
        with self._lock:
            if active:self.operations[key]=reason
            else:self.operations.pop(key,None)
            self.last_activity=time.monotonic();self.reason=reason
        if active and self.notify:self.notify()


def activity_for(root):
    from pathlib import Path
    key = str(Path(root).resolve()).casefold()
    with _lock:
        if key not in _activities:_activities[key] = BackupActivity()
        return _activities[key]
