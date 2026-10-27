"""Only allowlisted logs are exported, with user control and cancellation."""
import json
import zipfile
from unittest.mock import Mock
import pytest
from services.diagnostic_export import export_diagnostics
from services.export_control import ExportCancelled
from test_l1_l3_interaction import settings
from test_phase2_interaction import surface,settle
from PySide6.QtWidgets import QApplication


def test_private_logs_only_and_atomic_cancel_failure(tmp_path,monkeypatch):
    app=tmp_path/'app';logs=app/'diagnostics';logs.mkdir(parents=True)
    monkeypatch.setenv('NEKORI_APP_DATA',str(app))
    private='''File "C:\\Users\\PRIVATE_PERSON\\Pictures\\1677134746\\private_image.png"
File "F:\\project\\services\\worker.py", line 9 in run
Authorization: Bearer PRIVATE_BEARER
Cookie: session=PRIVATE_COOKIE; extra=PRIVATE_EXTRA
token="PRIVATE_TOKEN"
QQ 1677134746
https://example.invalid/private?token=PRIVATE_URL
'''
    (logs/'exceptions.log').write_text(private,encoding='utf-8')
    (logs/'fatal-test.log').write_text('native stack',encoding='utf-8')
    (logs/'private.png').write_bytes(b'PRIVATE_IMAGE')
    (app/'config.json').write_text('PRIVATE_CONFIG')
    target=tmp_path/'diagnostics.zip'
    assert export_diagnostics(target)==2
    with zipfile.ZipFile(target) as archive:
        assert len(archive.namelist())==3
        text='\n'.join(archive.read(n).decode() for n in archive.namelist())
        assert all(secret not in text for secret in ('PRIVATE_','1677134746','example.invalid'))
        assert 'worker.py' in text and 'native stack' in text
        assert json.loads(archive.read('environment.json'))['logs']==2
    original=target.read_bytes()
    cancel=Mock(side_effect=[False,False,True])
    with pytest.raises(ExportCancelled):export_diagnostics(target,cancel=cancel)
    assert target.read_bytes()==original and not list(tmp_path.glob('*.part'))
    with monkeypatch.context() as block:
        block.setattr(zipfile.ZipFile,'writestr',Mock(side_effect=OSError('write failure')))
        with pytest.raises(OSError):export_diagnostics(target)
    assert target.read_bytes()==original and not list(tmp_path.glob('*.part'))


def test_settings_view_export_cancel_and_failure(settings,monkeypatch,tmp_path):
    c=settings;c._select_page(4);settle(QApplication.instance())
    from PySide6.QtCore import QUrl
    opened=Mock(return_value=True)
    monkeypatch.setattr('services.crash_evidence.install',lambda:tmp_path)
    monkeypatch.setattr('PySide6.QtGui.QDesktopServices.openUrl',opened)
    c._open_logs();opened.assert_called_once_with(QUrl.fromLocalFile(str(tmp_path)))
    path=tmp_path/'ui-diagnostics.zip'
    monkeypatch.setattr('fluent_ui.views.settings_center.QFileDialog.getSaveFileName',lambda *a:(str(path),'ZIP'))
    success=Mock();failure=Mock();monkeypatch.setattr(c,'show_success',success);monkeypatch.setattr(c,'show_error',failure)
    c._export_diagnostics();assert path.is_file();success.assert_called_once();failure.assert_not_called()
    monkeypatch.setattr('fluent_ui.views.settings_center.QFileDialog.getSaveFileName',lambda *a:('',''))
    c._export_diagnostics();assert success.call_count==1
    monkeypatch.setattr('fluent_ui.views.settings_center.QFileDialog.getSaveFileName',lambda *a:(str(path),'ZIP'))
    monkeypatch.setattr('services.diagnostic_export.export_diagnostics',Mock(side_effect=OSError('offline disk')))
    c._export_diagnostics();failure.assert_called_once()
