"""Run exchange services off the GUI thread and retain workers until completion."""

from services.i18n import t, bind_text, translated
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QEventLoop
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout, QPlainTextEdit


class ExchangeWorker(QThread):
    progress = Signal(int, int, str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.operation(self.progress.emit)
        except Exception as exc:
            self.error = exc


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


def run_exchange_task(parent, title, operation):
    from fluent_ui.components.feedback import feedback_for
    host = feedback_for(parent)
    if host.task_active:
        raise RuntimeError(t('已有任务正在运行'))
    host.task(t(title))
    worker = ExchangeWorker(operation, parent)
    worker.progress.connect(lambda current, total, message: host.update_task(current, total, message))
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
    host.finish(t(title), str(error) if error else '', outcome='error' if error else 'success')
    if error is not None:
        raise error
    return result
