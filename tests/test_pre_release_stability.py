import json
from unittest.mock import Mock
import pytest
from services.config import ConfigService
from services import acrylic_policy as policy
from test_settings_ia import settings

@pytest.mark.parametrize('build,expected',[(19044,True),(19045,True),(22000,False),(26100,False)])
def test_os_build_boundary(monkeypatch,build,expected):
    from types import SimpleNamespace
    monkeypatch.setattr(policy.sys,'platform','win32')
    monkeypatch.setattr(policy.sys,'getwindowsversion',lambda:SimpleNamespace(build=build))
    assert policy.is_windows10()==expected

@pytest.mark.parametrize('ack',[False,True])
def test_old_config_is_not_consent_and_confirmed_choice_survives(tmp_path,monkeypatch,ack):
    monkeypatch.setattr(policy,'is_windows10',lambda:True)
    tmp_path.joinpath('config.json').write_text(json.dumps(dict(window_acrylic_enabled=True,win10_acrylic_confirmed=ack)))
    config=ConfigService(tmp_path)
    assert config.default_config['window_acrylic_enabled'] is False
    assert config.get('window_acrylic_enabled') is ack
    assert policy.allowed(config) is ack
    assert config.get('ui_animations_enabled') is True

def test_win11_default_unchanged(tmp_path,monkeypatch):
    monkeypatch.setattr(policy,'is_windows10',lambda:False)
    config=ConfigService(tmp_path)
    assert config.get('window_acrylic_enabled') is True and policy.allowed(config)

def test_confirmation_cancel_save_and_discard(settings,monkeypatch):
    app,center,config=settings.app,settings.center,settings.config
    monkeypatch.setattr(policy,'is_windows10',lambda:True)
    config.config.update(window_acrylic_enabled=False,win10_acrylic_confirmed=False)
    confirm=Mock(return_value=False)
    monkeypatch.setattr('fluent_ui.views.settings_center.dialogs.confirm',confirm)
    center._stage('window_acrylic_enabled',True)
    assert not center.pending.get('window_acrylic_enabled')
    confirm.return_value=True;center._stage('window_acrylic_enabled',True)
    assert center.pending['window_acrylic_enabled'] and not config.get('win10_acrylic_confirmed')
    center.discard();assert not config.get('window_acrylic_enabled')
    confirm.reset_mock();center._stage('window_acrylic_enabled',True);assert confirm.called
    monkeypatch.setattr('fluent_ui.visual.theme.apply_material_preference',lambda:None)
    assert center.save() and config.get('win10_acrylic_confirmed')
    reopened=ConfigService(config.base_dir);assert policy.allowed(reopened)
    center._stage('window_acrylic_enabled',False);assert center.save()
    assert not policy.allowed(config)

def test_installer_is_not_forced_or_auto_restarted():
    from pathlib import Path
    source=(Path(__file__).parents[1]/'scripts/build_distribution.py').read_text('utf-8')
    assert 'CloseApplications=yes' in source and 'CloseApplications=force' not in source
    assert 'RestartApplications=no' in source and 'taskkill' not in source

def test_qt_upgrade_commit_veto_and_bounded_worker_stop(monkeypatch):
    from PySide6.QtWidgets import QApplication,QWidget
    from services.upgrade_shutdown import install_upgrade_shutdown
    app=QApplication.instance() or QApplication([]);install_upgrade_shutdown(app)
    w=QWidget();w.has_pending_changes=lambda:True;w.backups=Mock();manager=Mock()
    app._upgrade_commit(manager);manager.cancel.assert_called_once();w.backups.cancel.assert_not_called()
    w.has_pending_changes=lambda:False;manager.reset_mock();app._upgrade_commit(manager)
    manager.cancel.assert_not_called();w.backups.cancel.assert_called_once();w.deleteLater()


def test_import_cannot_supply_consent(settings,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    s=settings
    monkeypatch.setattr(policy,'is_windows10',lambda:True)
    s.config.config.update(window_acrylic_enabled=False,win10_acrylic_confirmed=False)
    s.center._select_page(1);s.center._show_tab(0)
    file=s.tmp/'old-settings.json';file.write_text(json.dumps(dict(window_acrylic_enabled=True,win10_acrylic_confirmed=True)))
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(file),''))
    confirm=Mock(return_value=False);monkeypatch.setattr('fluent_ui.views.settings_center.dialogs.confirm',confirm)
    s.center._import_settings();assert confirm.called
    assert not s.center.pending.get('window_acrylic_enabled')
    assert 'win10_acrylic_confirmed' not in s.center.pending
    row=s.center._all_rows['window_acrylic_enabled'][0]
    assert row.value() is False
