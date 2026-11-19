"""Saved-candidate reporting and real Qt reminders, never user resources."""
import json
import os
from pathlib import Path
import threading
import time
import zipfile
import pytest
from services import crash_evidence as c
from services import diagnostic_export as exports


@pytest.fixture
def isolated(tmp_path,monkeypatch):
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'library'))
    monkeypatch.setattr(c,'_session',None);monkeypatch.setattr(c,'_session_ready',True)
    c.begin_session()
    return tmp_path


def seed(text='synthetic trace', native=True, **fields):
    import uuid
    value=c.session_snapshot();session=dict(value['current'],id=uuid.uuid4().hex)
    candidate=dict(session=session,assessment='possible_abnormal_exit',
        evidence_kind='native_trace' if native else 'none',evidence=[dict(kind='native',text=text)] if native else [],
        capture_state='ready',capture_started=time.time(),capture_checks=6,native_complete=True,
        report_state='new',notification_state='pending')
    candidate.update(fields);value['pending'].append(candidate)
    c._atomic_sessions(c.app_data_dir()/'diagnostics',value)
    return candidate


def latest(identity):return next(x for x in c.session_snapshot()['pending'] if x['session']['id']==identity)


def test_no_abnormal_candidate_no_report(isolated):
    assert exports.generate_pending_reports()['ready']==[]
    assert not (c.app_data_dir()/'diagnostics/reports').exists()


def test_valid_report_from_saved_evidence_without_original_logs(isolated):
    candidate=seed();identity=candidate['session']['id']
    assert exports.generate_pending_reports()['ready']==[identity]
    path=exports.report_path(identity)
    assert exports.valid_automatic_report(path,candidate)
    with zipfile.ZipFile(path) as archive:
        data=json.loads(archive.read('report.json'))
        assert data['session_id']==identity and data['session_environment']['python']
        assert archive.read('evidence/0.txt')==b'synthetic trace'
    assert latest(identity)['report_state']=='ready'
    assert latest(identity)['notification_state']=='pending'
    before=path.stat().st_mtime_ns
    exports.generate_pending_reports();assert path.stat().st_mtime_ns==before
    assert len(list(path.parent.glob('*.zip')))==1


def test_missing_native_stack_is_explicit(isolated):
    candidate=seed(native=False);exports.generate_pending_reports()
    with zipfile.ZipFile(exports.report_path(candidate['session']['id'])) as archive:
        assert not json.loads(archive.read('report.json'))['native_stack_available']
        assert b'No native stack' in archive.read('README.txt')


@pytest.mark.parametrize('failure',['mkdir','zip','publish'])
def test_report_failure_keeps_retryable_candidate(isolated,monkeypatch,failure):
    candidate=seed();identity=candidate['session']['id']
    with monkeypatch.context() as patch:
        if failure=='mkdir':
            folder=c.app_data_dir()/'diagnostics/reports';folder.write_text('blocked')
        elif failure=='zip':patch.setattr(exports.zipfile,'ZipFile',lambda *a,**kw:(_ for _ in ()).throw(OSError('synthetic')))
        else:
            original=os.replace
            def fail_report(a,b):
                if str(b).endswith('.zip'):raise OSError('synthetic')
                return original(a,b)
            patch.setattr(os,'replace',fail_report)
        assert exports.generate_pending_reports()['ready']==[]
    assert latest(identity)['report_state']=='failed'
    assert latest(identity)['notification_state']=='pending'
    if failure=='mkdir':(c.app_data_dir()/'diagnostics/reports').unlink()
    assert exports.generate_pending_reports()['ready']==[identity]


def test_published_zip_state_failure_reconciles_without_rewrite(isolated,monkeypatch):
    candidate=seed();identity=candidate['session']['id']
    with monkeypatch.context() as patch:
        patch.setattr(c,'update_candidate',lambda *a,**kw:False)
        exports.generate_pending_reports()
    path=exports.report_path(identity);stamp=path.stat().st_mtime_ns
    assert latest(identity)['report_state']=='new'
    assert exports.generate_pending_reports()['ready']==[identity]
    assert path.stat().st_mtime_ns==stamp


def test_cancel_during_report_leaves_candidate_and_no_published_zip(isolated,monkeypatch):
    candidate=seed();identity=candidate['session']['id'];cancel=threading.Event()
    original=exports.zipfile.ZipFile.writestr
    def interrupted(self,*args,**kw):
        result=original(self,*args,**kw);cancel.set();return result
    with monkeypatch.context() as patch:
        patch.setattr(exports.zipfile.ZipFile,'writestr',interrupted)
        exports.generate_pending_reports(cancel.is_set)
    assert not exports.report_path(identity).exists()
    assert latest(identity)['notification_state']=='pending'
    assert exports.generate_pending_reports()['ready']==[identity]


def test_corrupt_state_degrades(isolated):
    (c.app_data_dir()/'diagnostics/sessions.json').write_text('{bad')
    assert exports.generate_pending_reports()['ready']==[]


def test_multiple_candidates_and_concurrent_startup_workers(isolated,monkeypatch):
    ids=[seed()['session']['id'] for _ in range(3)]
    entered=threading.Event();release=threading.Event();original=exports.export_automatic_report
    def delayed(*a,**kw):entered.set();assert release.wait(3);return original(*a,**kw)
    with monkeypatch.context() as patch:
        patch.setattr(exports,'export_automatic_report',delayed)
        worker=threading.Thread(target=exports.generate_pending_reports);worker.start();assert entered.wait(3)
        assert exports.generate_pending_reports()['busy']
        release.set();worker.join(3);assert not worker.is_alive()
    assert all(latest(i)['report_state']=='ready' for i in ids)


def test_retention_preserves_unnotified_and_unknown_files(isolated):
    candidate=seed();identity=candidate['session']['id'];folder=exports.report_path(identity).parent;folder.mkdir()
    unknown=folder/'user-report.zip';unknown.write_bytes(b'private user file')
    pinned=seed();pinned_path=exports.export_automatic_report(pinned)
    for i in range(10):
        p=folder/('session-'+f'{i:032x}'+'.zip');p.write_bytes(b'x'*100);os.utime(p,(i,i))
    exports.generate_pending_reports()
    owned=list(folder.glob('session-*.zip'))
    assert len(owned)<=exports.REPORT_LIMIT
    assert sum(p.stat().st_size for p in owned)<=exports.REPORT_TOTAL_BYTES
    assert pinned_path.exists() and unknown.read_bytes()==b'private user file'


def test_privacy_no_library_or_network(isolated,monkeypatch):
    candidate=seed(r'C:\private\PERSONAL.png'+'\nhttps://private.test/a?token=SECRET\nCookie: SECRET\nAuthorization: Bearer SECRET')
    import urllib.request
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('network')))
    library=isolated/'library';library.mkdir();sentinel=library/'private.png';sentinel.write_bytes(b'sentinel')
    exports.generate_pending_reports()
    with zipfile.ZipFile(exports.report_path(candidate['session']['id'])) as archive:
        text=''.join(archive.read(n).decode('utf-8') for n in archive.namelist())
    assert all(x not in text for x in ['PERSONAL','private.test','SECRET'])
    assert sentinel.read_bytes()==b'sentinel' and list(library.iterdir())==[sentinel]


def test_delayed_native_writer_is_pinned_and_refreshed(isolated):
    candidate=seed(native=False,capture_state='collecting',capture_checks=0,native_complete=False)
    native=c.app_data_dir()/'diagnostics'/candidate['session']['native_log'];native.write_bytes(b'')
    first=exports.generate_pending_reports();assert first['retry'] and not first['ready']
    c.maintain(native.parent,native_slots=0);assert native.exists()
    native.write_text('Windows fatal exception: access violation\nlate synthetic native stack')
    Path(str(native)+'.done').write_bytes(b'done')
    identity=candidate['session']['id'];assert exports.generate_pending_reports()['ready']==[identity]
    updated=latest(identity);assert updated['native_complete']
    assert updated['assessment']=='fatal_error_recorded'
    with zipfile.ZipFile(exports.report_path(identity)) as archive:
        assert b'late synthetic native stack' in archive.read('evidence/0.txt')


def test_unfinished_writer_has_bounded_retry_and_explicit_uncertainty(isolated):
    candidate=seed(native=False,capture_state='collecting',capture_checks=0,native_complete=False)
    identity=candidate['session']['id']
    for _ in range(6):assert exports.generate_pending_reports()['retry']
    assert exports.generate_pending_reports()['ready']==[identity]
    assert not latest(identity)['native_complete']
    with zipfile.ZipFile(exports.report_path(identity)) as archive:
        assert b'completion was not confirmed' in archive.read('README.txt')


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def pump(app, predicate, timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        app.processEvents()
        if predicate():return
        time.sleep(.01)
    assert predicate()


def test_hidden_startup_deferred_once_and_actions(isolated,app,monkeypatch):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components import auto_crash_reports as ui
    candidate=seed(assessment='fatal_error_recorded',evidence_kind='fatal_signature');identity=candidate['session']['id'];window=QWidget()
    controller=ui.AutoCrashReports(app,window)
    try:
        pump(app,lambda:latest(identity)['report_state']=='ready')
        assert not window.isVisible() and controller.dialog is None
        window.show();pump(app,lambda:controller.dialog is not None and controller.dialog.isVisible())
        dialog=controller.dialog;assert dialog.parentWidget() is window
        opened=[];monkeypatch.setattr(ui.QDesktopServices,'openUrl',lambda url:opened.append(url.toLocalFile()) or True)
        dialog.view_button.click();dialog.folder_button.click()
        assert [Path(x) for x in opened]==[exports.report_path(identity),exports.report_path(identity).parent]
        dialog.close_button.click();pump(app,lambda:latest(identity)['notification_state']=='dismissed')
        window.hide();window.show();app.processEvents();assert controller.dialog is None
        controller._processed({'ready':[identity],'retry':False});assert controller.dialog is None
        assert exports.report_path(identity).exists()
    finally:controller.stop();window.close();window.deleteLater();app.processEvents()


def test_dialog_shutdown_does_not_acknowledge(isolated,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.auto_crash_reports import AutoCrashReports
    candidate=seed(assessment='fatal_error_recorded',evidence_kind='fatal_signature');identity=candidate['session']['id'];window=QWidget();window.show();controller=AutoCrashReports(app,window)
    pump(app,lambda:controller.dialog is not None)
    controller.stop();assert latest(identity)['notification_state']=='shown'
    window.close();window.deleteLater();app.processEvents()


def test_four_language_real_dialogs(isolated,app,monkeypatch):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.auto_crash_reports import CrashReportDialog
    from services.i18n import i18n_engine
    candidate=seed(assessment='fatal_error_recorded',evidence_kind='fatal_signature');exports.generate_pending_reports();window=QWidget();window.resize(700,400);window.show()
    try:
        for lang in ['zh','en','ja','zh_TW']:
            i18n_engine.load_language(lang);dialog=CrashReportDialog(window,candidate);dialog.open();app.processEvents()
            assert dialog.view_button.text() and dialog.folder_button.text() and dialog.close_button.text()
            if lang=='en':assert dialog.view_button.text()=='View report'
            dialog.grab().save(str(isolated/f'reminder-{lang}.png'))
            (isolated/'qt-platform.json').write_text(json.dumps({'platform':app.platformName(),'language':lang}))
            assert dialog.isVisible();dialog.reject();dialog.deleteLater();app.processEvents()
    finally:i18n_engine.load_language('zh');window.close();window.deleteLater();app.processEvents()


def test_hard_exit_during_zip_write_recovers(isolated):
    import subprocess,sys
    candidate=seed();identity=candidate['session']['id']
    code=r"""
import os
from services import diagnostic_export as exports
original=exports.zipfile.ZipFile.writestr
def interrupted(self,*a,**kw):
 original(self,*a,**kw)
 os._exit(23)
exports.zipfile.ZipFile.writestr=interrupted
exports.generate_pending_reports()
"""
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=Path(__file__).resolve().parents[1],
                          env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,timeout=10)
    assert result.returncode==23
    assert not exports.report_path(identity).exists()
    assert latest(identity)['report_state']=='new'
    assert exports.generate_pending_reports()['ready']==[identity]
    assert not list(exports.report_path(identity).parent.glob('*.part'))


def test_report_size_limit_failure_is_retryable(isolated,monkeypatch):
    candidate=seed();identity=candidate['session']['id']
    with monkeypatch.context() as patch:
        patch.setattr(exports,'REPORT_BYTES',100)
        assert exports.generate_pending_reports()['ready']==[]
    assert latest(identity)['report_state']=='failed'
    assert not exports.report_path(identity).exists()
    assert exports.generate_pending_reports()['ready']==[identity]


def test_legacy_task01_candidate_is_rechecked(isolated):
    candidate=seed(native=False)
    value=c.session_snapshot();value['pending'][0]={k:candidate[k] for k in ['session','assessment','evidence_kind','evidence']}
    c._atomic_sessions(c.app_data_dir()/'diagnostics',value)
    assert exports.generate_pending_reports()['retry']
    assert latest(candidate['session']['id'])['capture_state']=='collecting'


def test_owner_hide_does_not_acknowledge_and_reopens(isolated,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.auto_crash_reports import AutoCrashReports
    candidate=seed(assessment='fatal_error_recorded',evidence_kind='fatal_signature');identity=candidate['session']['id'];window=QWidget();window.show();controller=AutoCrashReports(app,window)
    try:
        pump(app,lambda:controller.dialog is not None)
        dialog=controller.dialog;window.hide();app.processEvents()
        assert latest(identity)['notification_state']=='shown'
        window.show();pump(app,lambda:dialog.isVisible())
        assert controller.dialog is dialog
        dialog.reject();pump(app,lambda:latest(identity)['notification_state']=='dismissed')
    finally:controller.stop();window.close();window.deleteLater();app.processEvents()


def test_slow_or_failed_generation_does_not_block_qt(isolated,app,monkeypatch):
    from PySide6.QtWidgets import QWidget
    from PySide6.QtCore import QTimer
    from fluent_ui.components.auto_crash_reports import AutoCrashReports
    seed(assessment='fatal_error_recorded',evidence_kind='fatal_signature');entered=threading.Event();release=threading.Event()
    def blocked(*a,**kw):
        entered.set();assert release.wait(3);raise PermissionError('synthetic report denied')
    monkeypatch.setattr(exports,'export_automatic_report',blocked)
    window=QWidget();controller=AutoCrashReports(app,window);ticks=[]
    timer=QTimer();timer.timeout.connect(lambda:ticks.append(True));timer.start(5)
    try:
        pump(app,entered.is_set)
        pump(app,lambda:len(ticks)>3)
        assert controller.dialog is None
        release.set();pump(app,lambda:not controller.worker.is_alive())
        app.processEvents();window.show();app.processEvents()
        assert controller.dialog is None and window.isVisible()
    finally:release.set();timer.stop();controller.stop();window.close();window.deleteLater();app.processEvents()


def test_late_completion_updates_same_report_identity(isolated):
    candidate=seed(native=False,native_complete=False,capture_checks=6)
    identity=candidate['session']['id'];exports.generate_pending_reports()
    path=exports.report_path(identity)
    with zipfile.ZipFile(path) as archive:assert not json.loads(archive.read('report.json'))['native_writer_complete']
    Path(str(c.app_data_dir()/'diagnostics'/candidate['session']['native_log'])+'.done').write_bytes(b'done')
    exports.generate_pending_reports()
    with zipfile.ZipFile(path) as archive:assert json.loads(archive.read('report.json'))['native_writer_complete']
    assert len(list(path.parent.glob('*.zip')))==1


def test_orphaned_owned_staging_is_bounded_unknown_files_preserved(isolated):
    candidate=seed();folder=exports.report_path(candidate['session']['id']).parent;folder.mkdir()
    for i in range(12):(folder/('.session-'+f'{i:032x}'+'.zip.part')).write_bytes(b'partial')
    unknown=folder/'user.zip.part';unknown.write_bytes(b'private')
    exports.generate_pending_reports()
    assert not list(folder.glob('.session-*.zip.part'))
    assert unknown.read_bytes()==b'private'
