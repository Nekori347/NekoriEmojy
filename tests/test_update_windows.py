"""Opt-in native test: set NEKORI_TEST_UPDATER to a compiled updater executable."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from services.update_protocol import MANIFEST, atomic_json, read_manifest, sha256
from test_updates import make_release


@unittest.skipUnless(os.name == "nt" and os.environ.get("NEKORI_TEST_UPDATER"), "compiled Windows updater not supplied")
class NativeUpdateTests(unittest.TestCase):
    def test_native_helper_waits_installs_and_restarts_root_launcher(self):
        from build_nuitka import build_launcher_stub, find_csc
        # Windows can keep the copied executable locked after the verified
        # updater process has exited. Keep fixture cleanup separate.
        with tempfile.TemporaryDirectory(prefix="Nekori 更新验证 ", ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            make_release(root)
            build_launcher_stub(str(root))
            core_source = root / "marker.cs"
            core_source.write_text('using System.IO; class Marker { static void Main() { File.WriteAllText(Path.Combine(System.Environment.CurrentDirectory, "restarted.txt"), "ok"); } }', encoding="utf-8")
            subprocess.run([find_csc(), "/nologo", "/target:winexe", "/out:" + str(root / "bin/NekoriEmojy.exe"), str(core_source)], check=True, capture_output=True)
            helper = Path(os.environ["NEKORI_TEST_UPDATER"]).resolve()
            shutil.copy2(helper, root / "NekoriEmojyUpdater.exe")
            manifest = read_manifest(root)
            manifest["files"] = {name: sha256(root / name) for name in manifest["files"]}
            atomic_json(root / MANIFEST, manifest)
            work = root / ".update"
            stage = work / "stage-native"
            make_release(stage, "1.14.0")
            for name in ("NekoriEmojy.exe", "NekoriEmojyUpdater.exe", "bin/NekoriEmojy.exe"):
                shutil.copy2(root / name, stage / name)
            manifest = read_manifest(stage)
            manifest["files"] = {name: sha256(stage / name) for name in manifest["files"]}
            atomic_json(stage / MANIFEST, manifest)
            atomic_json(work / "ready.json", {"version": "1.14.0", "directory": "stage-native"})
            data = root / "bin/data/config.json"
            data.parent.mkdir(parents=True)
            data.write_text("user data", encoding="utf-8")
            profile = root / "fixture-profile"
            environment = dict(os.environ, NEKORI_APP_DATA=str(profile / "app"),
                               NEKORI_LIBRARY=str(profile / "library"), QT_QPA_PLATFORM="windows")
            (profile / "app").mkdir(parents=True)
            atomic_json(profile / "app/config.json",
                        {"global_hotkey": "", "quick_panel_hotkey": "", "clipboard_search_hotkey": "",
                         "clipboard_import_enabled": False, "backup_enabled": False, "auto_check_updates": False})
            # The actual application creates its MainWindow, tray and Qt event loop.
            # The install root contains only the fixture launcher and marker program.
            script = """
import sys
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from fluent_ui.components.update_dialog import UpdateDialog
from fluent_ui.main_window import MainWindow
from services.update_service import UpdateService
from services.update_protocol import read_manifest
import main

root = Path(sys.argv[1])
sys.argv[:] = [sys.argv[0], '--autostart']
original_init = MainWindow.__init__
def construct(window, *args, **kwargs):
    original_init(window, *args, **kwargs)
    def install():
        app = QApplication.instance()
        assert app.platformName() == 'windows' and window.tray_icon.isVisible()
        d = UpdateDialog(window, UpdateService(root))
        ready = d.service.ready()
        assert ready
        d._prepared(ready)
        original_quit = d._quit
        def ready_to_quit(attempt):
            assert d.service.install_status()['state'] == 'waiting_parent'
            assert read_manifest(root)['version'] != ready['version']
            print('HELPER_WAITING_ON_QT_CORE', flush=True)
            original_quit(attempt)
        d._quit = ready_to_quit
        app.aboutToQuit.connect(lambda: print('QT_ABOUT_TO_QUIT', flush=True))
        with patch('fluent_ui.components.update_dialog.dialogs.confirm', return_value=True):
            d.action()
        QTimer.singleShot(30000, lambda: app.exit(3))
    QTimer.singleShot(0, install)
MainWindow.__init__ = construct
result = main.main()
assert result == 0, result
print('QT_LOOP_RETURNED', flush=True)
"""
            app = subprocess.Popen([sys.executable, "-c", script, str(root)], env=environment,
                                   creationflags=subprocess.CREATE_NO_WINDOW,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = app.communicate(timeout=45)
            output = (stdout + stderr).decode(errors="replace")
            self.assertEqual(app.returncode, 0, output)
            for marker in ("HELPER_WAITING_ON_QT_CORE", "QT_ABOUT_TO_QUIT", "QT_LOOP_RETURNED"):
                self.assertIn(marker, output)
            deadline = time.monotonic() + 30
            while not (root / "restarted.txt").exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue((root / "restarted.txt").exists(), "native restart marker missing")
            self.assertEqual(read_manifest(root, True)["version"], "1.14.0")
            self.assertEqual(data.read_text(), "user data")
            self.assertFalse((work / "journal.json").exists())
            self.assertFalse((work / "ready.json").exists())
            status = json.loads((work / "installer-status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["state"], "complete")
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x00100000, False, status["pid"])
            if handle:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 10000), 0)
                finally:
                    kernel.CloseHandle(handle)
            else:
                self.assertEqual(ctypes.get_last_error(), 87)  # PID already exited.
            print("Native Qt core exited after updater handshake. Fixture restarted at version 1.14.0.")


if __name__ == "__main__":
    unittest.main()
