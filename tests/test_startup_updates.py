"""Startup checks share the real service, UI worker and saved preferences."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import threading
import time
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
from fluent_ui.components.update_center import UpdateCenter
from services.config import ConfigService
from services.update_service import UpdateService
from test_l1_l3_interaction import settings
from test_phase2_interaction import surface, settle


def wait(app, predicate):
    for _ in range(400):
        app.processEvents()
        if predicate():return
        QTest.qWait(5)
    raise AssertionError('update did not complete')


@pytest.mark.parametrize('outcome',['available','current','error','unpublished'])
def test_background_results_and_persistent_throttle(tmp_path, monkeypatch, outcome):
    app=QApplication.instance() or QApplication([])
    config=ConfigService(tmp_path/'app')
    center=UpdateCenter(app)
    service=UpdateService()
    release={'version':'0.3.0','notes':'test','date':'','size':0,'manual_only':True} if outcome=='available' else None
    entered=threading.Event();gate=threading.Event()
    response=Mock(status_code=404 if outcome=='unpublished' else 200)
    response.json.return_value={'tag_name':'v0.3.0' if outcome=='available' else 'v0.2.1','body':'test','assets':[]}
    from unittest.mock import MagicMock
    context=MagicMock();context.__enter__.return_value=response
    def get(*args,**kwargs):
        entered.set();gate.wait(2)
        if outcome=='error':raise OSError('offline')
        return context
    monkeypatch.setattr('services.update_service.requests.get',get)
    service.check=Mock(wraps=service.check)
    service.download=Mock(side_effect=AssertionError('automatic download'))
    monkeypatch.setattr(center,'service',lambda:service)
    try:
        before=time.perf_counter();center.check_on_startup(config)
        assert time.perf_counter()-before < .2
        wait(app,entered.is_set)
        # GUI dispatch remains available while the simulated HTTP is blocked.
        w=QWidget();w.show();app.processEvents();assert w.isVisible();w.close()
        assert config.get('auto_update_status')=='checking'
        gate.set();wait(app,lambda:center.auto_worker is None)
        assert center.state==outcome
        assert center.release==release
        assert not center.dialogs,'background check opened a dialog'
        assert config.get('auto_update_status')==outcome
        config=ConfigService(tmp_path/'app')
        center.check_on_startup(config)
        service.check.assert_called_once()
        service.download.assert_not_called()
        # Manual checks still use the same service without the daily gate.
        from fluent_ui.components.update_dialog import UpdateDialog
        dialog=UpdateDialog(service=service)
        dialog.open_manual();wait(app,lambda:dialog.worker is None)
        assert service.check.call_count==2
        dialog.close();dialog.deleteLater()
    finally:
        gate.set();center.shutdown();center.deleteLater();app.processEvents()


def test_disabled_then_due_check(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    config=ConfigService(tmp_path/'app');config.set('auto_check_updates',False)
    center=UpdateCenter(app);factory=Mock(return_value=UpdateService())
    factory.return_value.check=Mock(return_value=None)
    monkeypatch.setattr(center,'service',factory)
    center.check_on_startup(config);factory.assert_not_called()
    config.update({'auto_check_updates':True,'auto_update_last_attempt':time.time()-86401})
    center.check_on_startup(config);wait(app,lambda:center.auto_worker is None)
    factory.return_value.check.assert_called_once();center.deleteLater()


def test_auto_check_setting_uses_existing_save_and_discard(settings):
    c=settings
    c._select_page(4)
    row=c._all_rows['auto_check_updates'][0]
    assert c.config.get('auto_check_updates') is True
    row.set_value(False);row.changed.emit()
    assert c.pending['auto_check_updates'] is False
    assert c.config.get('auto_check_updates') is True
    c.discard();assert row.value() is True
    row.set_value(False);row.changed.emit();c.save()
    assert ConfigService(c.config.base_dir).get('auto_check_updates') is False
