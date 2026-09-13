"""Exercise two actual P1 application sessions with independent synthetic libraries."""
import json
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch

work = Path(os.environ["P2_WORK_DIR"]).resolve()
work.mkdir(parents=True, exist_ok=True)
repo = Path(__file__).resolve().parents[2]
os.chdir(repo)
sys.path.insert(0, str(repo))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["NEKORI_BOOTSTRAP_DIR"] = str(work / "p2-gui-bootstrap-1")
from services.library import create_library, digest
from services.storage import StorageService
first = create_library(work / "p2-gui-first-1")
second = create_library(work / "p2-gui-second-1")
StorageService(first).add_category("first-only")
StorageService(second).add_category("second-only")
protected = {p: digest(p) for p in (repo / "data").rglob("*") if p.is_file()}
sys.argv = [str(repo / "main.py"), "--library", str(first.root)]

from PySide6.QtCore import QTimer, QSharedMemory
from PySide6.QtWidgets import QApplication
import main
import requests

report = {"platform": "offscreen", "sessions": [], "native_interaction": "not tested",
          "hotkeys": "disabled in harness", "avatar_network": "disabled in harness"}

class IsolatedSharedMemory(QSharedMemory):
    def __init__(self, key, parent=None):
        super().__init__(f"P2_Smoke_{os.getpid()}_{key}", parent)


class ObservedApplication(QApplication):
    def exec(self):
        def inspect():
            try:
                windows = [w for w in self.topLevelWidgets() if type(w).__name__ == "MainWindow"]
                assert len(windows) == 1
                window = windows[0]
                expected = first if not report["sessions"] else second
                assert window.storage.context.root == expected.root
                assert window.windowTitle() == "NekoriEmojy"
                assert hasattr(window.setting_interface, "libraryPanel")
                assert set(window.storage.get_all_categories()) == {"first-only" if expected is first else "second-only"}
                assert Path(window.clipboard.cache_dir).is_relative_to(expected.root)
                assert all(digest(path) == value for path, value in protected.items())
                report["sessions"].append({"library": "first" if expected is first else "second", "title": window.windowTitle(), "library_panel": True})
                if expected is first:
                    # Exercise the same activation path used by the settings UI.
                    window.setting_interface.libraryPanel._activate(second)
                else:
                    assert window.grab().save(str(work / "p2-gui-second-window.png"))
                    self.quit()
            except Exception:
                report["error"] = traceback.format_exc()
                self.next_library = None
                self.quit()
        QTimer.singleShot(1800, inspect)
        return super().exec()

main.QApplication = ObservedApplication
with patch("requests.sessions.Session.request", side_effect=requests.ConnectionError("isolated harness")), \
     patch("PySide6.QtCore.QSharedMemory", IsolatedSharedMemory), \
     patch("fluent_ui.main_window.MainWindow.bind_global_hotkey"):
    try:
        main.main()
    except Exception:
        report["error"] = traceback.format_exc()
report["passed"] = len(report["sessions"]) == 2 and "error" not in report
(work / "p2-startup.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
sys.exit(0 if report["passed"] else 1)
