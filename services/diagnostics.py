"""Bounded local diagnostics using Python logging; no upload or private payloads."""
from contextlib import closing
import importlib.metadata
import json
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
import os
from pathlib import Path
import platform
import queue
import re
import sqlite3
import sys
import time
import traceback
import zipfile

from services.library import DATABASES, SCHEMA_VERSION, read_db

MAX_BYTES = 1024 * 1024
BACKUPS = 3
QUEUE_SIZE = 512
_active = None


class _BoundedHandler(QueueHandler):
    def __init__(self, events):
        super().__init__(events)
        self.dropped = 0

    def enqueue(self, record):
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1

    def handleError(self, record):
        self.dropped += 1


class _SafeFileHandler(RotatingFileHandler):
    def handleError(self, record):
        # Never log a logging failure, print private records or break the GUI.
        pass


class Diagnostics:
    def __init__(self, directory, context=None, mode="normal"):
        self.directory = Path(directory)
        self.context = context
        self.mode = mode
        self.detailed_until = 0.0
        self.recent_events = {}
        self._queue = queue.Queue(maxsize=QUEUE_SIZE)
        self._handler = _BoundedHandler(self._queue)
        self._sink = None
        self._listener = None
        self._closed = False
        self.logger = logging.Logger("nekori.session", logging.DEBUG)
        self.logger.propagate = False
        self.logger.addHandler(self._handler)
        if mode != "off":
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                self._sink = _SafeFileHandler(self.directory / "events.log", maxBytes=MAX_BYTES,
                                              backupCount=BACKUPS, encoding="utf-8", delay=True)
                self._sink.setFormatter(logging.Formatter("%(message)s"))
                self._listener = QueueListener(self._queue, self._sink)
                self._listener.start()
            except OSError:
                self.mode = "off"

    def enable_detailed(self, seconds=300):
        self.detailed_until = time.monotonic() + min(max(seconds, 1), 600)

    def event(self, name, *, level="info", elapsed_ms=None, count=None, status=None,
              stage=None, error=None, detailed=False, throttle=0):
        if self._closed or self.mode == "off" or (detailed and time.monotonic() > self.detailed_until):
            return
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", name):
            return
        now = time.monotonic()
        # Fixed event identifiers, never resource names, OCR text or URL values.
        if throttle:
            previous = self.recent_events.get(name, 0)
            if now - previous < throttle:
                return
            if len(self.recent_events) >= 128:
                self.recent_events.clear()
            self.recent_events[name] = now
        record = {"time": time.time(), "event": name,
                  "library_id": self.context.library_id if self.context else None}
        if name == "application.startup" and self.context:
            record["library_location"] = str(self.context.root)
        for key, value in (("elapsed_ms", elapsed_ms), ("count", count), ("status", status), ("stage", stage)):
            if isinstance(value, (bool, int, float)):
                record[key] = value
            elif isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", value):
                record[key] = value
            elif key == "count" and isinstance(value, dict):
                record[key] = {k: v for k, v in list(value.items())[:32]
                               if isinstance(k, str) and re.fullmatch(r"[a-zA-Z0-9_.-]{1,40}", k)
                               and isinstance(v, (int, float))}
        if error is not None:
            # Trace locations are useful; exception messages/locals can contain
            # filenames, tokens, clipboard contents and full OCR transcripts.
            record["error_type"] = type(error).__name__
            record["stack"] = [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                               for f in traceback.extract_tb(error.__traceback__)[-20:]]
        self.logger.log(getattr(logging, level.upper(), logging.INFO), json.dumps(record, ensure_ascii=False))

    def close(self):
        self._closed = True
        self.logger.removeHandler(self._handler)
        if self._listener:
            # QueueListener.stop uses put_nowait; make room without blocking UI.
            while self._queue.full():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                    self._handler.dropped += 1
                except queue.Empty:
                    break
            self._listener.stop()
            self._listener = None
        if self._sink:
            self._sink.close()

    def summary(self):
        report = {"application": "NekoriEmojy", "development_phase": "P1",
                  "python": platform.python_version(), "windows": platform.version(),
                  "schema_supported": SCHEMA_VERSION, "dependencies": {},
                  "log_queue_capacity": QUEUE_SIZE, "log_dropped": self._handler.dropped,
                  "log_max_bytes": MAX_BYTES, "log_backups": BACKUPS,
                  "library": "not_connected", "counts": {}}
        for package in ("PySide6", "PySide6-Fluent-Widgets", "Pillow", "requests"):
            try:
                report["dependencies"][package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                report["dependencies"][package] = "unavailable"
        if self.context:
            report["library"] = {"id": self.context.library_id, "connected": self.context.root.is_dir()}
            counts = (("order", "item_orders", "indexed_images"), ("categories", "categories", "categories"),
                      ("categories", "category_images", "relations"), ("metadata", "image_metadata", "metadata"))
            for database, table, key in counts:
                try:
                    with read_db(self.context.db(database)) as conn:
                        report["counts"][key] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                except (OSError, sqlite3.Error):
                    report["counts"][key] = "unavailable"
            report["schema"] = {}
            for name in DATABASES:
                try:
                    with read_db(self.context.db(name)) as conn:
                        report["schema"][name] = {"version": conn.execute("PRAGMA user_version").fetchone()[0],
                            "tables": [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]}
                except (OSError, sqlite3.Error):
                    report["schema"][name] = "unavailable"
        return report

    def export(self, destination):
        """Only explicitly structured events and aggregate schema/count data."""
        destination = Path(destination)
        # Never replace an existing diagnostic archive or any library file.
        try:
            with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("summary.json", json.dumps(self.summary(), ensure_ascii=False, indent=2))
                for name in ("events.log", *(f"events.log.{i}" for i in range(1, BACKUPS + 1))):
                    path = self.directory / name
                    try:
                        with path.open("rb") as stream:
                            # Enforce the export bound even if a file was modified externally.
                            data = stream.read(MAX_BYTES + 8192)
                        sanitized = []
                        for line in data.decode("utf-8", errors="replace").splitlines():
                            try:
                                record = json.loads(line)
                                if isinstance(record, dict) and re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", str(record.get("event", ""))):
                                    # Local connection paths do not leave the log directory.
                                    allowed = {key: record[key] for key in
                                               ("time", "event", "library_id", "elapsed_ms", "count", "status", "stage", "error_type", "stack")
                                               if key in record}
                                    sanitized.append(json.dumps(allowed, ensure_ascii=False))
                            except ValueError:
                                pass
                        archive.writestr(name, "\n".join(sanitized))
                    except OSError:
                        continue
            return destination
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            self.event("diagnostics.export_failed", level="error", error=exc)
            raise RuntimeError("诊断信息导出失败，请检查目标位置；资源库未受影响。") from exc


def configure(directory, context=None):
    global _active
    if _active:
        _active.close()
    _active = Diagnostics(directory, context)
    return _active


def event(name, **fields):
    try:
        if _active:
            _active.event(name, **fields)
    except Exception:
        pass  # Diagnostics must never turn a successful data operation into a failure.


def install_exception_hooks():
    import threading
    def unhandled(kind, value, tb):
        event("application.unhandled_exception", level="error", error=value.with_traceback(tb))
    sys.excepthook = unhandled
    threading.excepthook = lambda args: unhandled(args.exc_type, args.exc_value, args.exc_traceback)
