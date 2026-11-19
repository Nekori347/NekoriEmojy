"""Intrinsic animation enrichment: bounded probes, no thumbnail metadata."""
import json
import os
import sqlite3
from threading import Event
from contextlib import nullcontext
from PIL import Image
from PySide6.QtCore import QObject, Signal, QTimer, QRunnable, QCoreApplication, Slot


def probe_animation(path):
    """Two actual animation frames; APNG's optional poster is not animation."""
    try:
        with Image.open(path) as image:
            second = 2 if image.format == 'PNG' and image.info.get('default_image') else 1
            try:
                image.seek(second)
                return True
            except EOFError:
                return False
    except (OSError, ValueError):
        return None


def store_import_animation(storage, path, animated=None):
    """Persist an operation-local decode; return missing identity, never probe."""
    record = storage.index.resource(path)
    if not record or storage.index.animation_attribute(record) is not None:
        return None
    if type(animated) is bool and storage.index.set_animation_attribute(record, animated):
        return None
    return record['id']


class _Signals(QObject):
    completed = Signal(object, str, bool)


class _Batch(QRunnable):
    def __init__(self, index, cursor, cancelled, lock=None, targets=None):
        super().__init__()
        self.index, self.cursor, self.cancelled = index, cursor, cancelled
        self.lock = lock
        self.targets = targets
        self.signals = _Signals()

    def run(self):
        changed = {}; cursor = self.cursor; more = False
        try:
            if self.targets is None:
                with self.index.connect() as db:
                    rows = [dict(row) for row in db.execute(
                        "SELECT id,relative_path,metadata_json,status FROM resources WHERE id>? ORDER BY id LIMIT 16", (cursor,))]
                more = len(rows) == 16
            else:
                rows = [record for value in self.targets if (record := self.index.resource(value))]
            updates = []
            for record in rows:
                if self.cancelled.is_set():
                    more = False
                    break
                cursor = record['id']
                if record['status'] == 'missing' or self.index.animation_attribute(record) is not None:
                    continue
                try:
                    path = self.index.absolute_path(record)
                    before = os.stat(path)
                    animated = probe_animation(path)
                    after = os.stat(path)
                    if (animated is not None and not self.cancelled.is_set()
                            and (before.st_mtime_ns, before.st_size) == (after.st_mtime_ns, after.st_size)):
                        updates.append((record, animated, path, after.st_mtime_ns, after.st_size))
                except (OSError, ValueError, sqlite3.Error):
                    continue  # Missing/corrupt/busy resources remain unknown, retry next startup.
            # Replacements use Storage.lock. Verify source stamps again inside
            # that boundary; never publish the old file's probe onto new bytes.
            with self.lock if self.lock is not None else nullcontext():
                valid = []
                for record, animated, path, mtime, size in updates:
                    if self.cancelled.is_set():
                        break
                    try:
                        current = os.stat(path)
                        if (current.st_mtime_ns, current.st_size) == (mtime, size):
                            valid.append((record, animated))
                    except OSError:
                        continue
                if valid and not self.cancelled.is_set():
                    changed = self.index.set_animation_attributes(valid)
        except sqlite3.Error:
            pass  # Catalog unavailable; no UI/launch failure or retry loop.
        try:
            self.signals.completed.emit(changed, cursor, more)
        except RuntimeError:
            pass  # Gallery was retired; no retained Qt receiver.


class AnimationBackfill(QObject):
    """One finite, low-priority catalog pass belonging to the current gallery."""
    changed = Signal(object)
    requested = Signal(str)

    def __init__(self, storage, parent, *, start=True):
        super().__init__(parent)
        self.storage = storage
        self.cancelled = Event()
        self.cursor = ''
        self.scan_more = True
        self.pending = set()
        self.task = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._next)
        self.requested.connect(self._request)
        cancelled = self.cancelled
        self.destroyed.connect(lambda *_: cancelled.set())
        app = QCoreApplication.instance()
        if app:
            app.aboutToQuit.connect(self.stop)
        if start:
            self.start()

    def start(self):
        self.timer.start(1500)

    def stop(self):
        self.cancelled.set()
        self.timer.stop()
        self.pending.clear()

    @Slot(str)
    def _request(self, identity):
        if self.cancelled.is_set():
            return
        self.pending.add(identity)
        if self.task is None and not self.timer.isActive():
            self.timer.start(100)

    def _next(self):
        if self.cancelled.is_set() or self.task is not None:
            return
        if not self.pending and not self.scan_more:
            return
        # Imports take precedence over optional catalog enrichment.
        imports = getattr(self.storage, 'desktop_imports', None)
        if imports and getattr(imports, 'worker', None) is not None:
            self.timer.start(500)
            return
        from fluent_ui.components.emoji_card import _thumbnail_pool
        targets = tuple(sorted(self.pending)[:16]) if self.pending else None
        if targets:
            self.pending.difference_update(targets)
        self.task = _Batch(self.storage.index, self.cursor, self.cancelled, self.storage.lock, targets)
        self.task.signals.completed.connect(self._completed)
        _thumbnail_pool.start(self.task, -1)

    def _completed(self, changed, cursor, more):
        targeted = self.task.targets is not None
        self.task = None
        if self.cancelled.is_set():
            return
        if not targeted:
            self.cursor = cursor
            self.scan_more = more
        # A rebind may invalidate an observed result after commit but before
        # this queued callback runs. Its target is already waiting in pending.
        for identity in changed.keys() & self.pending:
            record = self.storage.index.resource_by_id(identity)
            if not record or self.storage.index.animation_attribute(record) is not changed[identity]:
                del changed[identity]
        if changed:
            self.changed.emit(changed)
        if self.pending or self.scan_more:
            self.timer.start(100)


def apply_animation(record, animated):
    """Update an existing projection without changing representative-frame state."""
    try:
        metadata = json.loads(record.get('metadata_json') or '{}')
    except (ValueError, TypeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    if animated is None:
        metadata.pop('animation', None)
    else:
        metadata['animation'] = {'v': 1, 'animated': animated}
    record['metadata_json'] = json.dumps(metadata)
