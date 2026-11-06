from fluent_ui.components import dialogs
"""User-initiated update workflow; background work never touches Qt widgets."""
import gc
import threading
import time

from PySide6.QtCore import QThread, Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QMessageBox, QVBoxLayout, QTextBrowser,
)
from qfluentwidgets import BodyLabel, isDarkTheme
from fluent_ui.components.softframe import SoftframeProgress as ProgressBar
from fluent_ui.components.controls import TextEdit
from fluent_ui.components.controls import PrimaryPushButton, PushButton

from services.i18n import t
from services.update_service import Cancelled, RELEASES_URL, UpdateService, current_version
from services.update_protocol import MANIFEST
from fluent_ui.visual import colors


class UpdateWorker(QThread):
    progress = Signal(int)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation
        self.result = None
        self.error = None
        self.cancelled = False

    def run(self):
        try:
            self.result = self.operation(self.progress.emit)
        except Cancelled:
            self.cancelled = True
        except Exception as exc:
            self.error = str(exc)


def active_tasks():
    """Include parentless QThreads, as several existing tools own those directly."""
    tasks = []
    for obj in gc.get_objects():
        if isinstance(obj, QThread):
            try:
                if obj != QThread.currentThread() and obj.isRunning():
                    tasks.append(obj)
            except RuntimeError:  # Already-deleted Qt wrapper
                pass
    tasks.extend(th for th in threading.enumerate()
                 if th.name in ("startup-maintenance", "SyncKeyMigrationThread") and th.is_alive())
    return tasks


class UpdateNotes(QTextBrowser):
    """Read-only Markdown using the existing setting control surface."""
    def __init__(self):
        super().__init__()
        from fluent_ui.components.controls import _own_presentation
        from fluent_ui import visual
        _own_presentation(self)
        self.setFont(visual.font())
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.refresh_theme()
        visual.theme.changed.connect(self.refresh_theme)

    def refresh_theme(self):
        from fluent_ui import visual
        self.setStyleSheet(visual.control_style())


class UpdateDialog(dialogs.NekoriDialog):
    release_changed=Signal(object)
    check_state_changed=Signal(str)
    def __init__(self, parent=None, service=None):
        super().__init__(parent,t('软件更新'))
        # Status/download work is non-modal from the FIRST show. Changing a
        # visible modal dialog's property leaves Qt's modal stack registered.
        self.setWindowModality(Qt.NonModal)
        self.service = service or UpdateService()
        self.worker = None
        self.release = None
        self.prepared = None
        self.installing = False
        self._allow_update_close = False
        self._quitting = False
        self._phase = ''
        self._exit_tasks = []
        self._exit_backups = []
        self._handoff_timer = QTimer(self)
        self._handoff_timer.setInterval(100)
        self._handoff_timer.timeout.connect(self._poll_handoff)
        self._checking = False
        self.setWindowTitle(t("软件更新"))
        self.setObjectName("updateDialog")
        self.setStyleSheet("QDialog#updateDialog { background: " + colors()['window_base'] + "; }")
        self.resize(500, 240)
        layout = self.body
        from PySide6.QtWidgets import QLabel
        self.current_label=QLabel(t('当前版本')+'：v'+current_version(self.service.root));layout.addWidget(self.current_label)
        self.latest_label=QLabel();layout.addWidget(self.latest_label);self.latest_label.hide()
        self.status = QLabel(t('正在检查更新…'))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.notes = UpdateNotes()
        self.notes.anchorClicked.connect(self._open_link)
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(160);self.notes.hide()
        layout.addWidget(self.notes, 1)
        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.check_button = PushButton(t("检查更新"))
        self.action_button = PrimaryPushButton(t("下载更新"))
        self.action_button.setEnabled(False)
        self.cancel_button = PushButton(t("取消下载"))
        self.cancel_button.hide()
        self.page_button = PushButton(t("打开发布页"))
        self.later_button = PushButton(t("稍后"))
        row.addWidget(self.check_button);row.addStretch()
        for button in (self.page_button,self.cancel_button,self.later_button,self.action_button):row.addWidget(button)
        self.page_button.hide()
        self.check_button.clicked.connect(self.check)
        self.action_button.clicked.connect(self.action)
        self.cancel_button.clicked.connect(self._cancel_requested)
        channel_url=getattr(self.service,'releases_url',RELEASES_URL)
        self.page_button.clicked.connect(lambda: self._open_link(QUrl(channel_url)))
        self.page_button.setEnabled(bool(channel_url))
        self.later_button.clicked.connect(self.close)
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def open_manual(self):
        self.show()
        self.raise_()
        self.activateWindow()
        if self.worker is not None:
            return
        try:
            self.prepared = self.service.ready()
        except Exception as exc:
            self._error(str(exc))
            return
        if self.prepared:
            self._prepared(self.prepared)
        else:
            self.check()

    def _run(self, operation, finished, cancellable=False):
        if self.worker is not None:
            return
        self.service.cancel.clear()
        self.check_button.setEnabled(False)
        self.action_button.setEnabled(False)
        self.cancel_button.setVisible(cancellable or self.installing)
        self.worker = UpdateWorker(operation, self)
        self.worker.progress.connect(self.progress.setValue)

        def complete():
            worker = self.worker
            self.worker = None
            self.check_button.setEnabled(True)
            self.cancel_button.hide()
            self.progress.hide()
            if worker.cancelled:
                self.status.setText(t("下载已取消"))
                self.action_button.setEnabled(self.release is not None)
            elif worker.error:
                self._error(worker.error)
            else:
                finished(worker.result)
            worker.deleteLater()
        self.worker.finished.connect(complete)
        self.worker.start()

    def _error(self, error):
        if self._checking:
            self._checking=False;self.release=None;self.check_state_changed.emit('error')
        if self.installing and getattr(self.service, 'attempt', None):
            self._cancel_handoff(error)
            return
        self._restore_error(error)

    def _restore_error(self, error, cancelled=False):
        self._handoff_timer.stop()
        self._phase = ''
        self._allow_update_close = False
        self.installing = False
        self.later_button.setEnabled(True)
        self.check_button.setEnabled(True)
        self.cancel_button.hide()
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText(t('取消下载'))
        self._set_modality(Qt.NonModal)
        self.status.setText(t('更新已取消，已下载的更新包将保留。') if cancelled else t("更新失败，请重试或打开发布页"))
        self.notes.setPlainText(error)
        self.notes.show();self.page_button.show();self._fit_content()
        self.action_button.setEnabled(self.release is not None or self.prepared is not None)

    def check(self):
        if self.worker is not None:
            return
        if not getattr(self.service,'channel_available',True):
            self.status.setText(t('当前为开发版，暂未提供公开更新。'));self.notes.clear()
            self.release_changed.emit(None)
            return
        self.release = None
        self._checking=True;self.check_state_changed.emit('checking')
        self.status.setText(t("正在检查更新…"))
        self._run(lambda progress: self.service.check(), self._checked)

    def _checked(self, release):
        self._checking=False
        self.release=release
        self.release_changed.emit(release)
        if not release:
            unpublished=getattr(self.service,'last_check_status','')=='unpublished'
            self.status.setText(t('目前没有可用的发布版本。') if unpublished else t('暂未发现可用更新'))
            if unpublished:self.check_state_changed.emit('unpublished')
            self.notes.clear()
            self.notes.hide();self.latest_label.hide();self.action_button.setEnabled(False)
            self.check_button.show();self.page_button.hide();self._fit_content()
            return
        self.release = release
        self.prepared = None
        self.latest_label.setText(t('最新可用版本')+'：v'+release['version']);self.latest_label.show()
        self.status.setText(t('有可用更新') if release.get('notes') else t('有可用更新，暂未获取更新说明。'))
        self.notes.setMarkdown(release.get('notes',''));self.notes.setVisible(bool(release.get('notes')))
        self.action_button.setText(t("下载更新"))
        self.action_button.setEnabled(True)
        if release.get('manual_only') or not (self.service.root / MANIFEST).is_file():
            self.action_button.setText(t('获取更新'))
        self.check_button.hide();self.page_button.show();self._fit_content()

    def _fit_content(self):
        self.layout().activate()
        area = self.screen().availableGeometry()
        if self.release and self.release.get('notes'):
            self.resize(min(760, area.width()-32), min(640, area.height()-48))
        else:
            self.resize(min(600, area.width()-32), self.layout().sizeHint().height())
        if self.parentWidget():dialogs.center_on_owner(self,self.parentWidget())

    def _set_modality(self, modality):
        if self.windowModality()==modality:return
        visible=self.isVisible()
        if visible:self.hide()
        self.setWindowModality(modality)
        if visible:self.show()

    def _prepared(self, item):
        self.prepared = item
        self.status.setText("v" + item["version"] + " · " + t("更新已准备好，点击重启后安装"))
        self.action_button.setText(t("重启并更新"))
        self.action_button.setEnabled(True)

    def action(self):
        if self.worker is not None:
            return
        if self.prepared:
            if not dialogs.confirm(self, t("重启并更新"), t("现在退出软件并安装更新？用户数据将保留。")):
                return
            # Ask the existing settings transaction before starting any helper.
            for widget in QApplication.allWidgets():
                pending = getattr(widget, 'has_pending_changes', None)
                if callable(pending) and pending():
                    confirm = getattr(widget, 'confirm_close', None)
                    if not callable(confirm) or not confirm():
                        return
            self.installing = True
            self._allow_update_close = False
            self.later_button.setEnabled(False)
            self._set_modality(Qt.ApplicationModal)
            self.check_button.setEnabled(False)
            self.action_button.setEnabled(False)
            self.cancel_button.setText(t('取消更新'))
            self.cancel_button.show()
            self.status.setText(t('正在结束后台任务…'))
            self._exit_tasks = active_tasks()
            for task in self._exit_tasks:
                if isinstance(task, QThread):
                    task.requestInterruption()
            self._exit_backups = []
            for widget in QApplication.allWidgets():
                backup = getattr(widget, 'backups', None)
                if backup is not None and backup not in self._exit_backups:
                    self._exit_backups.append(backup)
                    backup.cancel()
            self._deadline = time.monotonic() + 15
            self._phase = 'tasks'
            self._handoff_timer.start()
            self._poll_handoff()
        elif self.release and (self.release.get('manual_only') or not (self.service.root / MANIFEST).is_file()):
            QDesktopServices.openUrl(QUrl(self.service.releases_url))
        elif self.release:
            self.progress.setValue(0)
            self.progress.show()
            self.status.setText(t("正在下载并校验更新…"))
            self._run(lambda progress: self.service.download(self.release, progress), self._prepared, True)

    def _open_link(self, url):
        if not url.isValid() or url.scheme().lower() != 'https' or not url.host() or url.userInfo():
            self.status.setText(t('无法打开此链接：仅支持安全的 HTTPS 链接。'))
        elif not QDesktopServices.openUrl(url):
            self.status.setText(t('无法打开浏览器，请复制链接后手动打开。'))

    def _cancel_requested(self):
        if self.installing:
            self._cancel_handoff(t('更新已取消，已下载的更新包将保留。'), cancelled=True)
        else:
            self.service.cancel.set()

    def _cancel_handoff(self, reason, cancelled=False):
        self._failure_reason = reason
        self._cancel_is_user = cancelled
        self.service.cancel.set()
        self.service.cancel_install()
        self._phase = 'cancelling'
        self._cancel_deadline = time.monotonic() + 5
        self.status.setText(t('正在取消更新交接…'))
        self.cancel_button.setEnabled(False)
        self._handoff_timer.start()

    def _poll_handoff(self):
        if self._phase == 'tasks':
            running = []
            for task in self._exit_tasks:
                try:
                    if task.isRunning() if isinstance(task, QThread) else getattr(task, 'is_alive', lambda: True)():
                        running.append(task)
                except RuntimeError:
                    pass
            if running or any(backup.active for backup in self._exit_backups):
                if time.monotonic() >= self._deadline:
                    self._restore_error(t('后台任务尚未安全结束，请稍后重试更新。'))
                return
            if active_tasks():
                self._restore_error(t('后台任务尚未安全结束，请稍后重试更新。'))
                return
            self._phase = 'launching'
            self.status.setText(t('正在准备重启更新…'))
            self._run(lambda progress: self.service.launch_installer(), self._quit)
        elif self._phase == 'cancelling':
            if self.worker is not None:
                return
            state = self.service.install_status()
            if not self.service.attempt or state.get('state') in {'cancelled', 'failed', 'complete'}:
                self.cancel_button.setEnabled(True)
                self._restore_error(self._failure_reason, cancelled=self._cancel_is_user)
            elif time.monotonic() >= self._cancel_deadline:
                self._restore_error(t('更新助手尚未退出，请稍后重试；已下载的更新包将保留。'))
                self.action_button.setEnabled(False)

    def _quit(self, result):
        if self._phase == 'cancelling':
            self.service.cancel_install()
            return
        if active_tasks():
            self._cancel_handoff(t('后台任务尚未安全结束，请稍后重试更新。'))
            return
        self._phase = 'exiting'
        self._allow_update_close = True
        self._set_modality(Qt.NonModal)
        self.hide()
        QApplication.instance().quit()
        # Runs only if some other window vetoed the real Qt Quit event.
        QTimer.singleShot(0, self._exit_refused)

    def _exit_refused(self):
        if not self._quitting:
            self.show()
            self._cancel_handoff(t('程序未能退出，更新包已保留。请关闭未完成的操作后重试。'))

    def reject(self):
        if not self.installing or self._allow_update_close:
            super().reject()

    def closeEvent(self, event):
        if self.installing and not self._allow_update_close:
            event.ignore()
        else:
            super().closeEvent(event)

    def shutdown(self):
        self._quitting = True
        self._handoff_timer.stop()
        self.service.cancel.set()
        # UpdateCenter's Quit filter drains update workers before aboutToQuit.
