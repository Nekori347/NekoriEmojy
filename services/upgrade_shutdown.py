"""Cooperate with Qt/Windows Restart Manager; never force-close the GUI."""
def install_upgrade_shutdown(app):
    if getattr(app,'_upgrade_shutdown_installed',False):return
    app._upgrade_shutdown_installed=True
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
