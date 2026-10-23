"""Run exchange services off the GUI thread and retain workers until completion."""

from services.i18n import t, bind_text, translated
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QEventLoop
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout, QPlainTextEdit


class ExchangeWorker(QThread):
    progress = Signal(int, int, str)

    def __init__(self, operation, parent=None, *, cancellable=False):
        super().__init__(parent)
        self.operation = operation
        self.cancellable = cancellable
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = (self.operation(self.progress.emit, self.isInterruptionRequested)
                           if self.cancellable else self.operation(self.progress.emit))
        except Exception as exc:
            self.error = exc
            from services.export_control import ExportCancelled
            if not isinstance(exc,ExportCancelled):
                import sys
                from services.crash_evidence import record_task_failure
                record_task_failure(f'exchange:{id(self)}','exchange',exc_info=sys.exc_info())


from fluent_ui.components.dialogs import NekoriDialog


class ExchangeTaskDialog(NekoriDialog):
    def __init__(self, parent, title, operation):
        super().__init__(parent, title, code="DATA")
        bind_text(self, title, 'setWindowTitle')
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setMinimumWidth(380)
        layout = self.body
        self.label = translated(QLabel, title, self)
        self.label.setWordWrap(True)
        self.bar = QProgressBar(self)
        from fluent_ui import visual
        c = visual.colors()
        self.bar.setStyleSheet(f"QProgressBar {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; height: 12px; color: {c['text']}; }} QProgressBar::chunk {{ background: {visual.accent()}; border-radius: 5px; }}")
        self.bar.setRange(0, 0)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setMaximumBlockCount(300)
        self.details.setMaximumHeight(140)
        self.details.hide()
        layout.addWidget(self.details)
        self._title = title
        self.add_button(t('查看详情'), on_click=lambda: self.details.setVisible(not self.details.isVisible()))
        self.worker = ExchangeWorker(operation, self)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.accept)

    def update_progress(self, current, total, message):
        bind_text(self.label, t('{value_0} · {value_1} / {value_2}').format(value_0=t(self._title), value_1=current, value_2=total))
        self.details.appendPlainText(str(message))
        self.bar.setRange(0, max(total, 1))
        self.bar.setValue(current)

    def reject(self):
        # Do not destroy a worker or interrupt a database transaction via Escape.
        pass

    def closeEvent(self, event):
        event.ignore()


def run_exchange_task(parent, title, operation, *, cancellable=False):
    from fluent_ui.components.feedback import feedback_for
    host = feedback_for(parent)
    if host.task_active:
        raise RuntimeError(t('已有任务正在运行'))
    worker = ExchangeWorker(operation, parent, cancellable=cancellable)
    cancel = worker.requestInterruption if cancellable else None
    host.task(t(title), cancel=cancel)
    def progress(current, total, message):
        if cancellable:
            # Keep the real phase first: the caption elides long titles and
            # otherwise hides the phase behind the fixed "export package" text.
            host.upsert_task('legacy', str(message), current=current,
                             total=total, content=t(title) + '\n' + str(message), cancel=cancel)
        else:
            host.update_task(current, total, message)
    worker.progress.connect(progress)
    loop = QEventLoop(parent)
    worker.finished.connect(loop.quit)
    QTimer.singleShot(0, worker.start)
    try:
        loop.exec()
    finally:
        worker.wait()
    error, result = worker.error, worker.result
    worker.deleteLater()
    loop.deleteLater()
    # The calling operation owns its result wording and error details. Remove
    # only this progress item, so it cannot also emit a duplicate result notice.
    host.task_active=False;host._cancel=host._action=None;host.finish_timer.stop()
    if hasattr(host,'_caption_ui'):host.remove_task('legacy')
    else:host.strip.hide();host._restore_notice()
    if error is not None:
        raise error
    return result
