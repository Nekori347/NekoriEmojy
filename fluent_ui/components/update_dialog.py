from fluent_ui.components import dialogs
"""User-initiated update workflow; background work never touches Qt widgets."""
import gc
import threading

from PySide6.QtCore import QThread, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QMessageBox, QVBoxLayout,
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
        self.notes = TextEdit()
        self.notes.setReadOnly(True)
        self.notes.setFixedHeight(160);self.notes.hide()
        layout.addWidget(self.notes)
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
        self.cancel_button.clicked.connect(self.service.cancel.set)
        channel_url=getattr(self.service,'releases_url',RELEASES_URL)
        self.page_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(channel_url)))
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
        self.cancel_button.setVisible(cancellable)
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
        self.installing = False
        self.later_button.setEnabled(True)
        self._set_modality(Qt.NonModal)
        self.status.setText(t("更新失败，请重试或打开发布页"))
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
        self.notes.setPlainText(release.get('notes',''));self.notes.setVisible(bool(release.get('notes')))
        self.notes.document().setTextWidth(470)
        self.notes.setFixedHeight(max(60,min(200,round(self.notes.document().size().height())+16)))
        self.action_button.setText(t("立即更新"))
        self.action_button.setEnabled(True)
        if release.get('manual_only') or not (self.service.root / MANIFEST).is_file():
            self.action_button.setText(t('获取更新'))
        self.check_button.hide();self.page_button.hide();self._fit_content()

    def _fit_content(self):
        self.layout().activate();self.resize(520,self.layout().sizeHint().height())
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
            if active_tasks():
                self.status.setText(t("请等待导入、导出和后台任务结束后再更新"))
                return
            if not dialogs.confirm(self, t("重启并更新"), t("现在退出软件并安装更新？用户数据将保留。")):
                return
            self.installing = True
            self.later_button.setEnabled(False)
            self._set_modality(Qt.ApplicationModal)
            self.status.setText(t("正在准备重启更新…"))
            self._run(lambda progress: self.service.launch_installer(), self._quit)
        elif self.release and (self.release.get('manual_only') or not (self.service.root / MANIFEST).is_file()):
            QDesktopServices.openUrl(QUrl(self.service.releases_url))
        elif self.release:
            self.progress.setValue(0)
            self.progress.show()
            self.status.setText(t("正在下载并校验更新…"))
            self._run(lambda progress: self.service.download(self.release, progress), self._prepared, True)

    def _quit(self, result):
        # Wait for any work that started while the installer was being prepared.
        # aboutToQuit handlers then release application resources normally.
        for task in active_tasks():
            if isinstance(task, QThread):
                task.wait()
            else:
                task.join()
        QApplication.instance().quit()

    def reject(self):
        if not self.installing:
            super().reject()

    def closeEvent(self, event):
        if self.installing:
            event.ignore()
        else:
            super().closeEvent(event)

    def shutdown(self):
        self.service.cancel.set()
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait()
