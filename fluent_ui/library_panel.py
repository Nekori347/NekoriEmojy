"""Library management entry points; long copies/migrations run off the UI thread."""
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
                              QMessageBox, QApplication, QInputDialog)

from services.library import LibraryBusy, LibraryError, copy_library
from services.legacy_import import migrate_legacy, LegacyConflict
from fluent_ui.library_dialog import LibraryDialog


class LibraryJob(QThread):
    completed = Signal(object, object)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.completed.emit(self.operation(), None)
        except Exception as exc:
            self.completed.emit(None, exc)


def running_window_jobs(window):
    """Include parentless upstream QThreads stored in page attributes/lists."""
    seen = set()
    owners = [window, *(getattr(window, name, None) for name in
               ("gallery_interface", "qq_scan_interface", "tg_sticker_interface", "about_interface"))]
    for owner in owners:
        if owner is None:
            continue
        values = list(vars(owner).values()) + owner.findChildren(QThread)
        for value in values:
            candidates = value if isinstance(value, (list, tuple, set)) else [value]
            for candidate in candidates:
                if isinstance(candidate, QThread) and id(candidate) not in seen:
                    seen.add(id(candidate))
                    if candidate.isRunning():
                        return True
        if getattr(owner, "_inbox_scanning", False):
            return True
    return False


class LibraryPanel(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.session = config.session
        self.job = None
        self.pending = None
        layout = QVBoxLayout(self)
        title = QLabel("资源库与诊断")
        title.setStyleSheet("font-size: 18px; font-weight: 600")
        layout.addWidget(title)
        location = QLabel(str(config.context.root))
        location.setWordWrap(True)
        layout.addWidget(location)
        self.status = QLabel("切换会重新打开主面板；原库的资源和整理结果保留。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = []
        for title, action in (("创建 / 打开 / 重新连接资源库", self.select),
                              ("完整复制并迁移当前库", self.copy_current),
                              ("从旧 SuzuEmojy 只读迁入", self.import_legacy),
                              ("导出诊断信息", self.export_diagnostics)):
            button = QPushButton(title)
            button.clicked.connect(action)
            self.buttons.append(button)
            layout.addWidget(button)

    def _ready(self):
        if (self.job and self.job.isRunning()) or running_window_jobs(self.window()):
            raise LibraryBusy("请等待当前下载、导入或后台任务结束后再操作资源库。")
        if self.session:
            with self.session.maintenance():
                pass

    def _activate(self, context):
        app = QApplication.instance()
        app.bootstrap_store.remember(context)
        app.next_library = str(context.root)
        app.exit(77)

    def select(self):
        try:
            self._ready()
            dialog = LibraryDialog(self)
            if dialog.exec() and dialog.session:
                context = dialog.session.context
                dialog.session.close()
                self._ready()
                self._activate(context)
        except (OSError, LibraryError) as exc:
            QMessageBox.warning(self, "资源库未切换", str(exc))

    def _run(self, operation):
        self._ready()
        # Disable the old UI while maintenance copies run; the worker's lease
        # prevents services from mutating the source during the snapshot.
        self.window().setEnabled(False)
        self._paused_timers = [timer for timer in self.window().findChildren(QTimer) if timer.isActive()]
        for timer in self._paused_timers:
            timer.stop()
        self.job = LibraryJob(operation, self)
        self.job.completed.connect(lambda value, error: setattr(self, "pending", (value, error)))
        self.job.finished.connect(self._completed)
        self.status.setText("正在复制并核验数据，请稍候……")
        self.job.start()

    def _completed(self):
        self.window().setEnabled(True)
        for timer in self._paused_timers:
            timer.start()
        value, error = self.pending
        self.pending = None
        if isinstance(error, LegacyConflict):
            summary = error.report["source_counts"]
            QMessageBox.information(self, "旧来源存在差异", "各来源统计：\n" + str(summary) +
                                    "\n核验报告：" + str(error.report_path))
            choices = {}
            for name in error.report["conflicts"]:
                answer, ok = QInputDialog.getItem(self, "选择恢复来源", name + " 存在差异：", ["JSON", "DB"], editable=False)
                if not ok:
                    self.status.setText("尚未迁入；旧源和核验快照均已保留。")
                    return
                choices[name] = answer.lower()
            source, target = self._legacy_paths
            self._run(lambda: migrate_legacy(source, target, source_closed=True, choices=choices))
        elif error:
            self.status.setText("操作未完成，原库保留。")
            QMessageBox.warning(self, "资源库操作失败", str(error))
        else:
            context = value[0] if isinstance(value, tuple) else value
            if isinstance(value, tuple):
                QMessageBox.information(self, "迁入核验结果", str(value[1]["target_counts"]))
            self._activate(context)

    def copy_current(self):
        try:
            self._ready()
            target = QFileDialog.getExistingDirectory(self, "选择空的迁移目标文件夹")
            if target:
                self._run(lambda: copy_library(self.session, target))
        except (LibraryError, OSError) as exc:
            QMessageBox.warning(self, "资源库未迁移", str(exc))

    def import_legacy(self):
        try:
            self._ready()
            if QMessageBox.question(self, "先关闭旧程序", "请先关闭旧 SuzuEmojy。确认旧程序已关闭后，才可形成一致快照。\n旧程序是否已关闭？") != QMessageBox.Yes:
                return
            source = QFileDialog.getExistingDirectory(self, "选择旧 SuzuEmojy 的 data 文件夹")
            if not source:
                return
            target = QFileDialog.getExistingDirectory(self, "选择空的新资源库文件夹")
            if target:
                self._legacy_paths = source, target
                self._run(lambda: migrate_legacy(source, target, source_closed=True))
        except (LibraryError, OSError) as exc:
            QMessageBox.warning(self, "旧源未迁入", str(exc))

    def export_diagnostics(self):
        target, _ = QFileDialog.getSaveFileName(self, "导出诊断信息", "NekoriEmojy-diagnostics.zip", "ZIP (*.zip)")
        if target:
            try:
                QApplication.instance().diagnostics.export(target)
                self.status.setText("诊断信息已保存到本地。")
            except RuntimeError as exc:
                QMessageBox.warning(self, "导出失败", str(exc))
