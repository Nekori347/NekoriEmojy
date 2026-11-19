import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent, QTimer, QUrl, Qt
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
from fluent_ui.components.update_dialog import UpdateDialog
from services.update_service import UpdateService
from services.update_protocol import atomic_json
from test_updates import make_release


class HotfixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        make_release(self.root)
        self.service = UpdateService(self.root)
        self.dialog = UpdateDialog(service=self.service)
        self.dialog._prepared({'version': '1.14.0'})

    def tearDown(self):
        self.dialog.installing = False
        self.dialog.shutdown()
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def test_confirmation_refusal_never_starts_helper(self):
        with patch('fluent_ui.components.update_dialog.dialogs.confirm', return_value=False), patch.object(self.service, 'launch_installer') as launch:
            self.dialog.action()
            launch.assert_not_called()
            self.assertFalse(self.dialog.installing)

    def test_unsaved_settings_refusal_preserves_pending(self):
        from fluent_ui.components.controls import PushButton
        from fluent_ui.views.settings_center import SettingsCenter
        from services.config import ConfigService
        from services.i18n import t

        pending = SettingsCenter(ConfigService(self.root / 'isolated-settings'))
        pending._stage('preview_delay', 850)

        def keep_editing():
            dialog = self.app.activeModalWidget()
            button = next(button for button in dialog.findChildren(PushButton)
                          if button.text() == t('继续编辑'))
            QTest.mouseClick(button, Qt.LeftButton)

        QTimer.singleShot(0, keep_editing)
        with patch('fluent_ui.components.update_dialog.dialogs.confirm', return_value=True), patch.object(self.service, 'launch_installer') as launch:
            self.dialog.action()
            launch.assert_not_called()
            self.assertTrue(pending.has_pending_changes())
            self.assertFalse(self.dialog.installing)

        # Unsaved settings can also appear after the first drain began.
        self.dialog.installing = True
        self.dialog._phase = 'launching'
        self.service.attempt = 'a' * 32
        QTimer.singleShot(0, keep_editing)
        self.dialog._quit(None)
        self.assertEqual(self.dialog._phase, 'cancelling')
        self.assertTrue(pending.has_pending_changes())
        self.assertTrue((self.service.workspace / ('cancel-' + self.service.attempt)).is_file())
        pending.deleteLater()
        self.app.processEvents()

    def test_cooperative_task_finishes_without_blocking_gui(self):
        from fluent_ui.views.gallery_view import ImportThread
        class Task(ImportThread):
            def run(self):
                self.cancel_event.wait(2)
        task = Task([], None, None)
        task.start()
        ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(2)
        with patch('fluent_ui.components.update_dialog.dialogs.confirm', return_value=True), patch('fluent_ui.components.update_dialog.active_tasks', side_effect=lambda:[task] if task.isRunning() else []), patch.object(self.service,'launch_installer',side_effect=OSError('fixture helper failure')):
            self.dialog.action()
            for _ in range(100):
                QTest.qWait(10)
                if not self.dialog.installing:break
        timer.stop()
        self.assertFalse(task.isRunning())
        self.assertTrue(task.cancel_event.is_set())
        self.assertGreater(len(ticks),0)
        self.assertFalse(self.dialog.installing)
        self.assertTrue(self.dialog.action_button.isEnabled())

    def test_task_timeout_retains_prepared_and_never_launches(self):
        import time
        task=type('Busy',(),{'is_alive':lambda _:True})()
        with patch('fluent_ui.components.update_dialog.dialogs.confirm',return_value=True), patch('fluent_ui.components.update_dialog.active_tasks',return_value=[task]), patch.object(self.service,'launch_installer') as launch:
            self.dialog.action();self.dialog._deadline=time.monotonic()-1;self.dialog._poll_handoff()
            launch.assert_not_called()
            self.assertFalse(self.dialog.installing)
            self.assertIsNotNone(self.dialog.prepared)

    def test_markdown_link_and_unsafe_protocols(self):
        d=self.dialog;d._checked({'version':'1.14.0','notes':'# Notes\n\n**Bold**\n\n[Document](https://example.com/path)'})
        d.show();self.app.processEvents()
        cursor=d.notes.document().find('Document');cursor.setPosition(cursor.selectionStart()+2);d.notes.setTextCursor(cursor);d.notes.ensureCursorVisible()
        self.assertEqual(d.notes.anchorAt(d.notes.cursorRect(cursor).center()),'https://example.com/path')
        with patch('fluent_ui.components.update_dialog.QDesktopServices.openUrl',return_value=True) as opened:
            QTest.mouseClick(d.notes.viewport(),Qt.LeftButton,Qt.NoModifier,d.notes.cursorRect(cursor).center())
            opened.assert_called_once_with(QUrl('https://example.com/path'))
            for url in ['file:///C:/Windows/notepad.exe','javascript:alert(1)','http://example.com','https://user:pass@example.com/']:
                d._open_link(QUrl(url))
            self.assertEqual(opened.call_count,1)
        with patch('fluent_ui.components.update_dialog.QDesktopServices.openUrl',return_value=False):
            d._open_link(QUrl('https://example.com/'))
            self.assertIn('浏览器',str(d.status.text()))

    def test_attempt_status_ignores_old_error_and_cancels_by_identity(self):
        self.service.attempt='a'*32
        self.service.helper=type('Running',(),{'poll':lambda _:None})()
        atomic_json(self.service.workspace/'installer-status.json',{'attempt':'b'*32,'state':'failed'})
        self.assertEqual(self.service.install_status(),{})
        self.service.cancel_install()
        self.assertTrue((self.service.workspace/('cancel-'+'a'*32)).is_file())

    def test_launching_keeps_cancel_visible_and_can_restore(self):
        self.dialog.installing=True
        self.dialog._phase='launching'
        self.dialog.show()
        self.dialog._run(lambda _:self.service.cancel.wait(1),lambda _:None)
        self.assertFalse(self.dialog.cancel_button.isHidden())
        self.dialog._cancel_requested()
        for _ in range(100):
            QTest.qWait(10)
            if not self.dialog.installing:break
        self.assertFalse(self.dialog.installing)
        self.assertTrue(self.dialog.later_button.isEnabled())
        self.assertIsNotNone(self.dialog.prepared)

    def test_helper_creation_failure_restores_controls(self):
        self.service.attempt='a'*32
        self.dialog.installing=True
        self.dialog._error('fixture process creation failure')
        self.dialog._poll_handoff()
        self.assertFalse(self.dialog.installing)
        self.assertTrue(self.dialog.action_button.isEnabled())
        self.assertTrue(self.dialog.later_button.isEnabled())

    def test_tasks_started_during_handoff_are_drained_before_quit(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        backup = Mock(pending=True)
        ocr = SimpleNamespace(busy=True, installing=False)
        imports = SimpleNamespace(worker=None, waiting=[object()], _decisions={})
        storage = SimpleNamespace(backup_service=backup, ocr=ocr, desktop_imports=imports)
        self.dialog.installing = True
        self.dialog._phase = 'launching'
        with patch.object(self.dialog, '_active_storage', return_value=storage), \
             patch.object(self.dialog, '_request_exit') as request_exit:
            self.dialog._quit(None)
            self.assertEqual(self.dialog._phase, 'draining')
            backup.cancel.assert_called_once()
            request_exit.assert_not_called()
            backup.pending = False
            ocr.busy = False
            self.dialog._poll_handoff()
            request_exit.assert_not_called()
            imports.waiting.clear()
            self.dialog._poll_handoff()
            request_exit.assert_called_once()

    def test_real_close_veto_cancels_attempt_and_keeps_update_ready(self):
        class Veto(QWidget):
            def closeEvent(self, event):
                event.ignore()
        owner = Veto()
        owner.show()
        self.dialog.show()
        self.dialog.installing = True
        self.dialog._phase = 'launching'
        self.service.attempt = 'a' * 32
        self.dialog._quit(None)
        self.assertTrue(owner.isVisible())
        self.assertTrue(self.dialog.isVisible())
        self.assertEqual(self.dialog._phase, 'cancelling')
        self.assertTrue((self.service.workspace / ('cancel-' + self.service.attempt)).is_file())
        self.dialog._poll_handoff()
        self.assertTrue(self.dialog.action_button.isEnabled())
        self.assertIsNotNone(self.dialog.prepared)
        owner.hide()
        owner.deleteLater()

    def test_update_center_drains_handoff_quit_without_posting_a_second_quit(self):
        from fluent_ui.components.update_center import UpdateCenter
        from unittest.mock import Mock
        center = UpdateCenter(self.app)
        event = QEvent(QEvent.Quit)
        event.update_handoff = True
        service = Mock()
        with patch.object(center, '_running_workers', return_value=[(object(), service)]):
            self.assertTrue(self.app.sendEvent(self.app, event))
        self.assertTrue(event.update_workers_draining)
        self.assertFalse(center._quit_timer.isActive())
        self.assertFalse(event.isAccepted())
        service.cancel.set.assert_called_once()
        self.app.removeEventFilter(center)
        center.deleteLater()

    def test_real_qt_quit_event_loop_exits_while_installing(self):
        code='''import sys,tempfile,json
from pathlib import Path
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import QTimer
from fluent_ui.components.update_dialog import UpdateDialog
from services.update_service import UpdateService
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
owner=QWidget();owner.show()
d=UpdateDialog(owner,UpdateService(Path(tempfile.mkdtemp())));d.installing=True;d.show()
events=[];app.aboutToQuit.connect(lambda:events.append('quit'))
QTimer.singleShot(100,lambda:d._quit(None))
QTimer.singleShot(2000,lambda:(events.append('timeout'),app.exit(3)))
result=app.exec();assert result==0 and events==['quit'],(result,events)
print('REAL_EVENT_LOOP_EXITED')
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('REAL_EVENT_LOOP_EXITED',result.stdout)

if __name__=='__main__':unittest.main()
