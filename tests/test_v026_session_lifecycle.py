from unittest.mock import patch
from services import crash_evidence as c
from services.upgrade_shutdown import SessionEndFilter
from test_auto_crash_reports import isolated, seed, latest, pump, app


def test_only_committed_system_end_completes_session(isolated):
    for msg,wparam,lparam in [(0x11,1,0),(0x16,0,0),(0x16,1,1)]:
        assert not SessionEndFilter.committed(msg,wparam,lparam)
        assert c.session_snapshot()['current']['state']=='running'
    assert SessionEndFilter.committed(0x16,1,0)
    assert c.session_snapshot()['current']['completion']=='system_session_ended'
    c.begin_session()
    assert c.session_snapshot()['pending']==[]


def test_logoff_committed_is_normal(isolated):
    assert SessionEndFilter.committed(0x16,1,0x80000000)
    assert c.session_snapshot()['current']['state']=='completed'


def test_interrupted_only_report_is_saved_without_reminder(isolated,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.auto_crash_reports import AutoCrashReports
    candidate=seed(native=False);identity=candidate['session']['id']
    window=QWidget();window.show();controller=AutoCrashReports(app,window)
    try:
        pump(app,lambda:latest(identity)['report_state']=='ready')
        controller._show_next()
        assert controller.dialog is None
        assert latest(identity)['notification_state']=='pending'
    finally:
        controller.stop();window.close();window.deleteLater();app.processEvents()
