"""Safe cancellation, failed publication and real task stop controls."""
import json,zipfile,threading
from pathlib import Path
import pytest
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from test_export_scope import export_library
from test_management_mode import management
from services.exchange_export import ExchangeExportService
from services.nekori_package import NekoriPackageService
from services.export_control import ExportCancelled


@pytest.mark.parametrize('native',[False,True])
@pytest.mark.parametrize('existing',[False,True])
def test_cancel_preserves_destination_and_source(export_library,tmp_path,native,existing):
    storage,parent,child,other,paths=export_library
    target=tmp_path/'result.zip'
    if existing:target.write_bytes(b'previous destination')
    before={p:Path(p).read_bytes() for p in paths};relations=storage.index.memberships()
    cancelled=[False];progress=[]
    def update(current,total,message):
        progress.append(message)
        if list(tmp_path.glob('.result.zip.*.part')):cancelled[0]=True
    with pytest.raises(ExportCancelled):
        if native:NekoriPackageService(storage).export(target,update,cancel_check=lambda:cancelled[0])
        else:ExchangeExportService(storage=storage).export_zip(str(target),None,update,cancel_check=lambda:cancelled[0])
    assert target.read_bytes()==b'previous destination' if existing else not target.exists()
    assert not list(tmp_path.glob('*.part')) and not list(tmp_path.glob('.*.part'))
    assert '导出完成' not in progress and '完成' not in progress
    assert storage.index.memberships()==relations
    assert all(Path(p).read_bytes()==value for p,value in before.items())


@pytest.mark.parametrize('native',[False,True])
def test_failure_is_not_cancellation_and_keeps_old_zip(export_library,tmp_path,monkeypatch,native):
    storage,*_=export_library;target=tmp_path/'result.zip';target.write_bytes(b'old')
    original=zipfile.ZipFile.writestr
    def fail(archive,name,*args,**kwargs):
        if name in ('manifest.json','nekori.json'):raise OSError('controlled disk write failure')
        return original(archive,name,*args,**kwargs)
    monkeypatch.setattr(zipfile.ZipFile,'writestr',fail)
    with pytest.raises(OSError,match='controlled'):
        if native:NekoriPackageService(storage).export(target)
        else:ExchangeExportService(storage=storage).export_zip(str(target))
    assert target.read_bytes()==b'old' and not list(tmp_path.glob('.*.part'))


@pytest.mark.parametrize('native',[False,True])
def test_success_publishes_valid_zip(export_library,tmp_path,native):
    storage,*_=export_library;target=tmp_path/'result.zip';target.write_bytes(b'old')
    if native:result=NekoriPackageService(storage).export(target)
    else:result=ExchangeExportService(storage=storage).export_zip(str(target))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert ('nekori.json' if native else 'manifest.json') in archive.namelist()
    assert not list(tmp_path.glob('.*.part'))


@pytest.mark.parametrize('native',[False,True])
def test_real_export_entry_stop_button_cancels_active_zip(management,tmp_path,monkeypatch,native):
    from fluent_ui.components.feedback import feedback_for
    from fluent_ui.views import gallery_view,settings_center
    view,storage,parent,dest,paths,sent=management
    target=tmp_path/('native.zip' if native else 'Source.zip');target.write_bytes(b'previous destination')
    monkeypatch.setattr(gallery_view.QFileDialog,'getExistingDirectory',lambda *a,**k:str(tmp_path))
    monkeypatch.setattr(settings_center.QFileDialog,'getSaveFileName',lambda *a,**k:(str(target),''))
    host=feedback_for(view);host.dock_to_caption(view)
    before={p:Path(p).read_bytes() for p in paths};records=storage.index.resources();order=storage.index.content(parent)
    in_write=threading.Event();release=threading.Event();clicked=[];stages=[]
    method='write' if native else 'writestr';original=getattr(zipfile.ZipFile,method)
    def controlled_write(archive,name,*args,**kwargs):
        asset=native or str(name).startswith('assets/')
        if asset and not in_write.is_set():
            in_write.set()
            if not release.wait(5):raise TimeoutError('stop button not exercised')
        return original(archive,name,*args,**kwargs)
    monkeypatch.setattr(zipfile.ZipFile,method,controlled_write)
    timer=QTimer();timer.setInterval(10)
    def stop():
        job=host.named_tasks.get('legacy')
        if job:stages.append(job['title'])
        if in_write.is_set() and not clicked:
            assert list(tmp_path.glob('.'+target.name+'.*.part'))
            assert host.action_button.isVisible() and host.action_button.property('role')=='danger'
            assert any('写入资源' in title for title in stages)
            clicked.append(True);QTest.mouseClick(host.action_button,Qt.LeftButton);release.set()
    timer.timeout.connect(stop);timer.start()
    if native:
        center=settings_center.SettingsCenter(view.config,storage,parent=view)
        center.export_nekori_package();center.deleteLater()
    else:view.sidebar.export_node(parent)
    timer.stop();release.set()
    assert clicked and not host.task_active
    assert any('导出已停止' in job['title'] for job in host.named_tasks.values())
    assert not any('导出完成' in job['title'] or job['state']=='error' for job in host.named_tasks.values())
    assert target.read_bytes()==b'previous destination' and not list(tmp_path.glob('.*.part'))
    assert all(Path(p).read_bytes()==value for p,value in before.items())
    assert storage.index.resources()==records and storage.index.content(parent)==order
