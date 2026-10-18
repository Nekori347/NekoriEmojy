import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.autostart import AutostartService, should_start_hidden


class AutostartTests(unittest.TestCase):
    def setUp(self):
        self.service = AutostartService()
        self.service.supported = True
        self.registry = MagicMock()
        self.key = self.registry.OpenKey.return_value.__enter__.return_value
        self.registry.REG_SZ = 1
        self.registry.REG_BINARY = 3
        self.registry.QueryValueEx.return_value = ('', 1)
        self.patcher = patch.dict(sys.modules, winreg=self.registry)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_enable_writes_only_current_user_run(self):
        self.registry.QueryValueEx.return_value = ('"C:\\应用 程序\\app.exe" --autostart', 1)
        with patch.object(self.service, 'command', return_value='"C:\\应用 程序\\app.exe" --autostart'):
            self.service.set_enabled(True)
        self.registry.CreateKeyEx.assert_called_once_with(
            self.registry.HKEY_CURRENT_USER, self.service.RUN_KEY,
            0, self.registry.KEY_SET_VALUE)
        self.registry.SetValueEx.assert_called_once_with(
            self.registry.CreateKeyEx.return_value.__enter__.return_value,
            'NekoriEmojy', 0, 1, '"C:\\应用 程序\\app.exe" --autostart')

    def test_disable_removes_only_our_value_and_is_idempotent(self):
        self.service.set_enabled(False)
        self.registry.DeleteValue.assert_called_once_with(self.key, 'NekoriEmojy')
        self.registry.DeleteValue.side_effect = FileNotFoundError
        self.service.set_enabled(False)

    def test_permission_errors_are_not_silenced(self):
        self.registry.OpenKey.side_effect = PermissionError('denied')
        with self.assertRaises(PermissionError):
            self.service.is_enabled()
        with self.assertRaises(PermissionError):
            self.service.set_enabled(False)
        self.registry.CreateKeyEx.side_effect = PermissionError('denied')
        with self.assertRaises(PermissionError):
            self.service.set_enabled(True)

    def test_status_checks_real_command_including_moved_install(self):
        with patch.object(self.service, 'command', return_value='current --autostart'):
            self.registry.QueryValueEx.return_value = ('current --autostart', 1)
            self.assertTrue(self.service.is_enabled())
            self.registry.QueryValueEx.return_value = ('old --autostart', 1)
            self.assertFalse(self.service.is_enabled())
            self.registry.QueryValueEx.side_effect = FileNotFoundError
            self.assertFalse(self.service.is_enabled())

    def test_source_command_uses_pythonw_and_absolute_script(self):
        with patch.object(sys, 'executable', r'C:\运行 环境\python.exe'), \
                patch.object(sys, 'frozen', False, create=True), \
                patch.object(Path, 'is_file', return_value=True):
            command = self.service.command()
        self.assertTrue(command.startswith('"C:\运行 环境\\pythonw.exe" '))
        self.assertIn(str(Path(__file__).resolve().parent.parent / 'main.py'), command)
        self.assertTrue(command.endswith(' --autostart'))

    def test_frozen_command_does_not_use_python_or_script(self):
        with patch.object(sys, 'executable', r'C:\程序 目录\SuzuEmojy.exe'), \
                patch.object(sys, 'frozen', True, create=True), \
                patch('services.autostart._process_executable', return_value=Path(r'C:\程序 目录\SuzuEmojy.exe')):
            self.assertEqual(self.service.command(), '"C:\程序 目录\\SuzuEmojy.exe" --autostart')

    def test_startup_visibility(self):
        self.assertTrue(should_start_hidden(['app', '--autostart'], True))
        self.assertFalse(should_start_hidden(['app'], True))
        self.assertFalse(should_start_hidden(['app', '--autostart'], False))

    def test_nuitka_command(self):
        with patch.object(sys, 'executable', r'C:\错误 占位\python.exe'), \
                patch.object(sys, 'frozen', False, create=True), \
                patch('services.autostart.__compiled__', True, create=True), \
                patch('services.autostart._process_executable', return_value=Path(r'C:\程序 目录\SuzuEmojy.exe')):
            self.assertEqual(self.service.command(), '"C:\程序 目录\\SuzuEmojy.exe" --autostart')

    def test_repair_is_narrow_and_never_clears_system_disable(self):
        for value, expected in [
            ('"C:\\当前 安装\\python.exe" --autostart', True),
            ('"C:\\另一 安装\\python.exe" --autostart', False),
            ('"C:\\当前 安装\\SuzuEmojy.exe" --autostart', False),
        ]:
            with self.subTest(value=value), patch('services.autostart.__compiled__', True, create=True), \
                    patch('services.autostart._process_executable', return_value=Path(r'C:\当前 安装\SuzuEmojy.exe')), \
                    patch('services.autostart._package_launcher', return_value=None):
                self.registry.QueryValueEx.return_value = (value, 1)
                self.registry.SetValueEx.reset_mock()
                self.assertEqual(self.service.repair_registration(), expected)
                self.assertEqual(self.registry.SetValueEx.call_count, int(expected))
                self.registry.DeleteValue.assert_not_called()


class AutostartUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_failed_toggle_stays_pending_and_save_reports_failure(self):
        import tempfile
        from pathlib import Path
        from services.config import ConfigService
        from fluent_ui.views.setting_view import SettingInterface
        with tempfile.TemporaryDirectory() as directory, patch('fluent_ui.views.settings_center.AutostartService') as factory:
            config = ConfigService(directory)
            original = Path(config.config_path).read_bytes()
            service = factory.return_value
            service.supported = True
            service.is_enabled.return_value = False
            view = SettingInterface(config)
            service.set_enabled.assert_not_called()
            row = view._rows['autostart'][0]
            row.set_value(True)
            row.changed.emit()
            service.set_enabled.assert_not_called()
            self.assertTrue(view.pending['autostart'])
            view.pending['thumbnail_size'] = 170
            service.set_enabled.side_effect = PermissionError('isolated denied registry write')
            with patch.object(view, 'show_error') as error:
                self.assertFalse(view.save())
                error.assert_called_once()
            service.set_enabled.assert_called_once_with(True)
            self.assertEqual(Path(config.config_path).read_bytes(), original)
            self.assertNotIn('autostart', view.pending)
            self.assertFalse(row.value())
            self.assertEqual(view.pending['thumbnail_size'], 170)
            self.assertTrue(view.save())
            self.assertEqual(config.get('thumbnail_size'), 170)
            service.set_enabled.assert_called_once_with(True)
            view.deleteLater()

    def test_config_failure_rolls_back_applied_autostart_and_keeps_pending(self):
        import tempfile
        from pathlib import Path
        from services.config import ConfigService
        from fluent_ui.views.setting_view import SettingInterface
        for rollback_fails in (False, True):
            with self.subTest(rollback_fails=rollback_fails), tempfile.TemporaryDirectory() as directory, patch('fluent_ui.views.settings_center.AutostartService') as factory:
                config = ConfigService(directory)
                original = dict(config.config)
                disk = Path(config.config_path).read_bytes()
                service = factory.return_value
                service.supported = True
                service.is_enabled.return_value = False
                service.set_enabled.side_effect = [None, PermissionError('isolated rollback denied') if rollback_fails else None]
                view = SettingInterface(config)
                view.pending.update(autostart=True, thumbnail_size=170)
                with patch.object(config, '_save_config', side_effect=OSError('isolated disk full')), patch.object(view, 'show_error') as error:
                    self.assertFalse(view.save())
                    error.assert_called_once()
                self.assertEqual(config.config, original)
                self.assertEqual(Path(config.config_path).read_bytes(), disk)
                self.assertTrue(view.pending)
                self.assertNotIn('autostart', view.pending)
                self.assertEqual([c.args[0] for c in service.set_enabled.call_args_list], [True, False])
                view.deleteLater()


if __name__ == '__main__':
    unittest.main()
