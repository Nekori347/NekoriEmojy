from PySide6.QtCore import QAbstractNativeEventFilter


class SessionEndFilter(QAbstractNativeEventFilter):
    """Windows commits shutdown separately from Qt's ordinary Quit event.

    RM's ENDSESSION_CLOSEAPP is deliberately excluded: it requests an app
    upgrade, where the process must still actually return from its event loop.
    """
    @staticmethod
    def committed(message, wparam, lparam):
        if message == 0x16 and wparam and not (lparam & 0x1):
            from services.crash_evidence import complete_session
            return complete_session('system_session_ended')
        return False

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            self.committed(msg.message, msg.wParam, msg.lParam)
        return False, 0


"""Cooperate with Qt/Windows Restart Manager; never force-close the GUI."""
def install_upgrade_shutdown(app):
    if getattr(app,'_upgrade_shutdown_installed',False):return
    app._upgrade_shutdown_installed=True
    app._session_end_filter=SessionEndFilter()
    app.installNativeEventFilter(app._session_end_filter)
    def commit(manager):
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.allWidgets():
            pending=getattr(widget,'has_pending_changes',None)
            if callable(pending) and pending():
                manager.cancel();return
        # Qt owns WM_QUERYENDSESSION/WM_ENDSESSION. Cancel only our current
        # worker here; aboutToQuit performs bounded shutdown only on actual exit.
        for widget in QApplication.allWidgets():
            service=getattr(widget,'backups',None)
            if service is not None:service.cancel()
    app.commitDataRequest.connect(commit)
    app._upgrade_commit=commit
