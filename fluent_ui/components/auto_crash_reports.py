"""Startup recovery notification on the existing Softframe dialog surface."""
import threading
from PySide6.QtCore import QObject, Signal, QTimer, QEvent, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel
from services import crash_evidence as sessions
from services.diagnostic_export import generate_pending_reports, report_path, valid_automatic_report
from services.i18n import t
from fluent_ui.components.dialogs import NekoriDialog


class CrashReportDialog(NekoriDialog):
    def __init__(self, owner, candidate):
        super().__init__(owner, '检测到上次运行异常')
        self.candidate=candidate
        self.set_semantic('warning')
        message=('NekoriEmojy 上次记录到了致命错误。' if candidate['assessment']=='fatal_error_recorded'
                 else 'NekoriEmojy 上次可能未正常退出。')
        self.add_hint(message)
        self.add_hint('已将可用的诊断信息保存到本地，可查看报告或打开诊断文件夹。')
        self.status=QLabel(self);self.status.setWordWrap(True);self.add_widget(self.status)
        self.view_button=self.add_button('查看报告',on_click=self._view)
        self.folder_button=self.add_button('打开诊断文件夹',on_click=self._folder)
        self.close_button=self.add_button('关闭本弹窗',role='primary',on_click=self.accept)
        self.setMinimumWidth(500)

    def _open(self, folder=False):
        path=report_path(self.candidate['session']['id'])
        if (not valid_automatic_report(path,self.candidate)
            or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent if folder else path)))):
            self.status.setText(t('无法打开诊断资料，请稍后重试。'))

    def _view(self):self._open()
    def _folder(self):self._open(True)


class AutoCrashReports(QObject):
    processed=Signal(object)

    def __init__(self, app, window):
        super().__init__(window)
        self.window=window;self.dialog=None;self.stopping=threading.Event();self.worker=None
        self.dismissed=set();self.queued=set();self.attempts=0
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self._start)
        self.processed.connect(self._processed)
        window.installEventFilter(self)
        app.aboutToQuit.connect(self.stop)
        self.timer.start(0)

    def stop(self):
        self.stopping.set();self.timer.stop()
        if self.dialog:self.dialog.reject()

    def _start(self):
        if self.stopping.is_set() or self.attempts>=8 or (self.worker and self.worker.is_alive()):return
        self.attempts+=1
        def work():
            result=generate_pending_reports(self.stopping.is_set)
            if not self.stopping.is_set():
                try:self.processed.emit(result)
                except RuntimeError:pass
        self.worker=threading.Thread(target=work,name='diagnostic-report',daemon=True);self.worker.start()

    @Slot(object)
    def _processed(self, result):
        if self.stopping.is_set():return
        self.queued.update(result['ready'])
        if result.get('retry') and self.attempts<8:self.timer.start(500)
        self._show_next()

    def eventFilter(self, watched, event):
        if watched is self.window:
            if event.type()==QEvent.Hide and self.dialog:self.dialog.hide()
            if event.type() in (QEvent.Show,QEvent.WindowStateChange):QTimer.singleShot(0,self._show_next)
        return False

    def _show_next(self):
        if self.stopping.is_set() or not self.window.isVisible() or self.window.isMinimized():return
        if self.dialog:
            if not self.dialog.isVisible():self.dialog.open()
            return
        value=sessions.session_snapshot()
        if not value or value.get('unavailable'):return
        for candidate in value['pending']:
            identity=candidate['session']['id']
            if (candidate.get('assessment')!='fatal_error_recorded'
                or identity not in self.queued or identity in self.dismissed
                or candidate.get('report_state')!='ready' or candidate.get('notification_state')=='dismissed'):continue
            if not valid_automatic_report(report_path(identity),candidate):continue
            self.dialog=CrashReportDialog(self.window,candidate)
            self.dialog.finished.connect(lambda result,i=identity:self._closed(i))
            sessions.update_candidate(identity,notification_state='shown')
            self.dialog.open()
            return

    def _closed(self, identity):
        dialog=self.dialog;self.dialog=None
        if not self.stopping.is_set():
            self.dismissed.add(identity)
            sessions.update_candidate(identity,notification_state='dismissed')
        if dialog:dialog.deleteLater()
        if not self.stopping.is_set():QTimer.singleShot(0,self._show_next)


def install_auto_crash_reports(app, window):
    if not hasattr(window,'_auto_crash_reports'):
        window._auto_crash_reports=AutoCrashReports(app,window)
    return window._auto_crash_reports
