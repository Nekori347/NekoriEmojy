import json
import time
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import QEventLoop,QTimer
from services.config import ConfigService
from services.library_index import LibraryIndex
from services.backup_service import BackupService
from test_library_backup import library


def until(predicate,timeout=12000):
    loop=QEventLoop();timer=QTimer();timer.setInterval(10)
    timer.timeout.connect(lambda:loop.quit() if predicate() else None)
    guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(loop.quit)
    timer.start();guard.start(timeout);loop.exec();timer.stop();guard.stop()
    assert predicate(),'Timed out waiting for actual worker state'


def service_at(tmp_path):
    app=QApplication.instance() or QApplication([])
    root,index=library(tmp_path);config=ConfigService(tmp_path/'app')
    config.config['backup_path']=str(tmp_path/'backups')
    storage=SimpleNamespace(config=config,library_root=str(root),index=index)
    parent=QWidget();service=BackupService(storage,parent)
    return app,parent,service


def test_real_worker_pause_resume_verified_success_and_restore(tmp_path):
    app,parent,s=service_at(tmp_path);events=[];s.changed.connect(lambda:events.append(dict(s.state)))
    s.activity.operation('foreground','正在浏览表情库',True)
    assert s.request_backup();until(lambda:s.state['state']=='paused')
    assert not s.state['last_success_at'] and s.state['last_attempt_at']
    assert not list((tmp_path/'backups').glob('*.zip')) if (tmp_path/'backups').exists() else True
    s.activity.operation('foreground','正在浏览表情库',False);s.activity.last_activity=0
    until(lambda:not s.active)
    assert s.state['state']=='success' and Path(s.state['last_valid_location']).is_file()
    success=s.state['last_success_at'];old=s.state['last_valid_location']
    assert any(e['state']=='paused' for e in events) and any(e['state']=='running' for e in events)
    assert s.request_restore(old,tmp_path/'new-library');until(lambda:not s.active)
    assert (tmp_path/'new-library/index.sqlite3').is_file()
    assert s.state['last_success_at']==success and s.state['last_valid_location']==old
    s.shutdown();parent.deleteLater()


def test_cancel_shutdown_and_restart_preserve_last_success(tmp_path):
    app,parent,s=service_at(tmp_path)
    assert s.request_backup();until(lambda:not s.active)
    success=s.state['last_success_at'];location=s.state['last_valid_location']
    s.activity.operation('busy','正在发送表情',True)
    assert s.request_backup();until(lambda:s.state['state']=='paused')
    s.cancel();until(lambda:not s.active)
    assert s.state['last_success_at']==success and s.state['last_valid_location']==location
    assert Path(location).is_file()
    assert s.request_backup();until(lambda:s.state['state']=='paused')
    at=time.monotonic();s.shutdown();assert time.monotonic()-at<1.0
    assert s.state['last_success_at']==success
    parent.deleteLater()


def test_auto_backup_off_by_default_and_enable_does_not_start_immediately(tmp_path):
    app,parent,s=service_at(tmp_path)
    assert not s.config.get('backup_enabled') and not s.active and not s.directory.exists()
    s.state['last_attempt_at']='2020-01-01T00:00:00+00:00'
    s.config.config['backup_enabled']=True;s.configure();s._tick()
    assert s.state['enabled_since'] and not s.active
    assert s.state['last_attempt_at']=='2020-01-01T00:00:00+00:00'
    s.shutdown();parent.deleteLater()


def test_worker_failure_never_advances_success_time(tmp_path):
    app,parent,s=service_at(tmp_path)
    assert s.request_backup();until(lambda:not s.active)
    success=s.state['last_success_at'];location=s.state['last_valid_location']
    assert s.request_restore(location,tmp_path/'library');until(lambda:not s.active)
    assert s.state['state']=='success' and s.operation_error
    assert s.state['last_success_at']==success and s.state['last_valid_location']==location
    s.shutdown();parent.deleteLater()


def test_worker_crash_and_recovered_incomplete_job_do_not_hash_or_advance_success(tmp_path,monkeypatch):
    from services.library_backup import atomic_json
    app,parent,s=service_at(tmp_path)
    assert s.request_backup();until(lambda:not s.active)
    success=s.state['last_success_at'];location=s.state['last_valid_location']
    (Path(s.storage.library_root)/'inbox').mkdir()
    (Path(s.storage.library_root)/'inbox/payload.bin').write_bytes(b'\x00'*(16*1024*1024))
    assert s.request_backup();until(lambda:s.phase=='archive' and s.progress[0]>1024*1024)
    assert int(s.process.processId())==s.worker_info['pid']
    s.process.kill();until(lambda:not s.active)
    assert s.state['state']=='failed' and s.state['last_success_at']==success
    assert Path(location).is_file()
    state={**s.state,'state':'running','active_job':'interrupted-fixture'}
    atomic_json(s.state_path,state);s.shutdown()
    monkeypatch.setattr('services.library_backup.inventory',lambda *_:(_ for _ in ()).throw(AssertionError('Startup must not scan Library')))
    recovered=BackupService(s.storage,parent)
    assert recovered.state['state']=='failed' and recovered.state['last_success_at']==success
    assert recovered.state['last_valid_location']==location and 'active_job' not in recovered.state
    recovered.shutdown();parent.deleteLater()


def test_settings_backup_rows_stage_discard_save_and_defaults(surface,monkeypatch):
    from fluent_ui.views.settings_center import SettingsCenter
    center=SettingsCenter(surface.config,surface.storage);center._select_page(3);center._show_tab(0)
    row=center._all_rows['backup_keep'][0];row.set_value(9);row.changed.emit()
    assert center.pending['backup_keep']==9 and surface.config.get('backup_keep')==5
    center.discard();assert row.value()==5
    center._stage('backup_path',str(surface.tmp/'safe-backups'));center._stage('backup_keep',7)
    center._stage('backup_enabled',True);assert center.save()
    reopened=ConfigService(surface.config.base_dir)
    assert reopened.get('backup_enabled') and reopened.get('backup_keep')==7
    assert not center._backup_service.active
    monkeypatch.setattr('fluent_ui.components.dialogs.confirm',lambda *a,**k:True)
    center._restore_page_defaults();assert center.pending['backup_enabled'] is False
    center.discard();assert surface.config.get('backup_enabled') is True
    center._stage('backup_path',str(surface.storage.index.root/'bad'))
    monkeypatch.setattr(center,'show_error',lambda *a,**k:None)
    assert not center.save()
    center.discard();center.close();center.deleteLater()


from test_phase2_interaction import surface


def test_frozen_worker_uses_actual_image_not_synthetic_python_executable(tmp_path,monkeypatch):
    import sys
    from PySide6.QtCore import QProcess
    app,parent,s=service_at(tmp_path);calls=[]
    actual=tmp_path/'frozen/bin/NekoriEmojy.exe'
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'executable',str(actual.with_name('python.exe')))
    monkeypatch.setattr('services.autostart._process_executable',lambda:actual)
    monkeypatch.setattr(QProcess,'start',lambda self,program,args:calls.append((program,args)))
    assert s.request_backup()
    assert calls[0][0]==str(actual) and calls[0][1][0]=='--backup-worker'
    process=s.process;s.process=None;process.deleteLater();s.shutdown();parent.deleteLater()


def test_large_byte_progress_uses_bounded_real_caption_widgets(surface):
    from services.backup_service import backup_service
    host=surface.g.feedback_host;host.dock_to_caption(surface.g)
    s=backup_service(surface.storage,surface.g,host)
    s.job=dict(id='large-progress',mode='backup');s.notification_id='large-progress'
    s.state['state']='running';s.phase='archive';s.detail=''
    s.progress=(4_100_000_000,5_054_527_021);s.diagnostic_details=''
    s._publish();surface.app.processEvents()
    job=host.named_tasks['backup:large-progress']
    assert job['total']==10000 and 0<job['current']<10000
    assert job['count_text']=='4.10 / 5.05 GB'
    assert host.progress.maximum()==10000
    assert host.count_label.text()=='4.10 / 5.05 GB'
    s.shutdown()


def test_nonzero_worker_exit_cannot_publish_done_as_success(tmp_path):
    from PySide6.QtCore import QProcess
    from services.library_backup import atomic_json
    from fluent_ui.components.feedback import FeedbackHost
    app,parent,s=service_at(tmp_path);s.host=FeedbackHost(parent)
    work=tmp_path/'work';location=tmp_path/'archive.zip';location.write_bytes(b'archive')
    result=dict(committed=True,job_id='failed-exit',location=str(location),bytes=7,completed_at='2099-01-01')
    atomic_json(work/'result.json',result);atomic_json(location.with_name(location.name+'.valid.json'),result)
    s.job=dict(id='failed-exit',mode='backup',work=str(work));s.notification_id='failed-exit'
    s.process=QProcess(s);s.outcome=dict(type='done',result=result)
    s._finished(1,QProcess.NormalExit)
    assert s.state['state']=='failed' and not s.state['last_success_at']
    assert s.host.named_tasks['backup:failed-exit']['state']=='error'
    s.shutdown();parent.deleteLater()


def test_changed_attempt_reuses_notice_and_queued_retry_can_be_cancelled(tmp_path):
    from PySide6.QtCore import QProcess
    from fluent_ui.components.feedback import FeedbackHost
    app,parent,s=service_at(tmp_path);s.host=FeedbackHost(parent)
    s.job=dict(id='first-attempt',mode='backup');s.notification_id='logical-request'
    s.process=QProcess(s);s.outcome=dict(type='changed',reason='文件已发生变化')
    s._finished(3,QProcess.NormalExit)
    assert s.pending and not s.active and s.state['state']=='waiting'
    assert not s.request_backup() and len(s.host.named_tasks)==1
    s.cancel()
    assert not s.pending and s.host.named_tasks['backup:logical-request']['state']=='cancelled'
    s.shutdown();parent.deleteLater()
