"""Bounded launch of unchanged upstream main(), using Qt's offscreen platform.

This is startup evidence, not Windows hit-testing/taskbar/drag-drop acceptance.
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import traceback
from unittest.mock import patch

work = Path(os.environ["P0_WORK_DIR"]).resolve()
source = work / "p0-empty-source"
os.chdir(source)
sys.path.insert(0, str(source))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
assert not (source / "data").exists(), "Must start with no runtime data"

from PySide6.QtCore import QTimer, QSharedMemory, qVersion
from PySide6.QtWidgets import QApplication
import requests
import main as upstream_main

started = time.perf_counter()
result = {"platform": "offscreen", "initial_data_directory_exists": False,
          "qt": qVersion(), "startup_passed": False,
          "external_avatar_request": "disabled in harness",
          "instance_key": "unique test key (user has an existing SuzuEmojy process)",
          "global_hotkey_binding": "disabled in harness to avoid user instance interference",
          "native_window_behaviors": "not tested"}


class IsolatedSharedMemory(QSharedMemory):
    def __init__(self, key, parent=None):
        super().__init__(f"P0_Validation_{os.getpid()}_{key}", parent)


class ObservedApplication(QApplication):
    def exec(self):
        def inspect():
            try:
                windows = [w for w in self.topLevelWidgets()
                           if type(w).__name__ == "MainWindow"]
                assert len(windows) == 1, "Expected a single initialized MainWindow"
                window = windows[0]
                storage = window.storage
                assert Path(storage.data_dir).resolve() == source / "data"
                assert storage.get_all_images() == []
                assert storage.get_all_categories() == {}
                assert window.windowTitle() == "SuzuEmojy"
                names = ("gallery_interface", "setting_interface", "about_interface",
                         "exchange_interface", "qq_scan_interface", "tg_sticker_interface",
                         "quick_panel")
                assert all(getattr(window, name, None) is not None for name in names)
                databases = {}
                for database in sorted((source / "data").glob("*.db")):
                    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
                        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                        assert integrity == "ok"
                        databases[database.name] = integrity
                image_path = work / "p0-empty-window.png"
                assert window.grab().save(str(image_path))
                result.update(startup_passed=True, components=list(names),
                              title=window.windowTitle(), databases=databases,
                              images=0, categories=0,
                              elapsed_to_observation_seconds=time.perf_counter() - started,
                              screenshot=image_path.name)
                if window.hotkey_listener:
                    window.hotkey_listener.stop()
            except Exception:
                result["error"] = traceback.format_exc()
            finally:
                (work / "p0-empty-startup.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self.quit()
        QTimer.singleShot(1500, inspect)
        return super().exec()


upstream_main.QApplication = ObservedApplication
with patch("requests.sessions.Session.request",
           side_effect=requests.ConnectionError("P0: external network disabled")), \
        patch("PySide6.QtCore.QSharedMemory", IsolatedSharedMemory), \
        patch("fluent_ui.main_window.MainWindow.bind_global_hotkey"):
    try:
        upstream_main.main()
    except SystemExit as exit_signal:
        result["application_exit_code"] = exit_signal.code
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if result["startup_passed"] else 1)
