import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from fluent_ui import visual
from fluent_ui.main_window import MainWindow


@pytest.fixture
def case(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'old'))
    monkeypatch.setattr(MainWindow,'_init_global_hotkey',lambda self:None)
    import win32gui,win32con
    monkeypatch.setattr(win32gui,'GetWindowLong',lambda *a:win32con.WS_CAPTION|win32con.WS_THICKFRAME)
    monkeypatch.setattr(win32gui,'SetWindowLong',lambda *a:0)
    monkeypatch.setattr(win32gui,'SetWindowPos',lambda *a:None)
    cfg=ConfigService();cfg.update({'library_path':str(tmp_path/'old'),'auto_check_updates':False,'backup_enabled':False,'global_hotkey':'','quick_panel_hotkey':''})
    i18n_engine.init(cfg);visual.theme.configure(cfg)
    old=StorageService(tmp_path/'old',cfg);new=StorageService(tmp_path/'new',cfg)
    old.create_node('OLD');new.create_node('NEW')
    window=MainWindow(old,ClipboardService(cfg),cfg)
    yield app,window,old,new,cfg
    for storage in {old,new,window.storage}:
        for name,method in [('desktop_imports','shutdown'),('ocr','close'),('backup_service','shutdown')]:
            service=getattr(storage,name,None)
            if service:
                try:getattr(service,method)()
                except RuntimeError:pass
    window.hide();window.deleteLater();app.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()


def assert_bound(window,storage):
    assert window.storage is storage
    assert window.gallery_interface.storage is storage
    assert window.quick_panel.storage is storage
    assert window.settings_window.center.storage is storage
    assert window.gallery_interface.backups.storage is storage
    assert window._window_import_receiver.gallery is window.gallery_interface


def save_to(window, target, **values):
    center = window.setting_interface
    center.pending.update(library_path=target.library_root, **values)
    return center.save()


def test_roundtrip_settings_services_and_representative_signal(case, monkeypatch):
    from PIL import Image
    from services.resource_import import ImportTarget

    app,w,old,new,cfg=case
    a=next(n['id'] for n in old.index.nodes() if n['name']=='OLD')
    b=next(n['id'] for n in new.index.nodes() if n['name']=='NEW')
    source=Path(new.library_root).parent/'representative.gif'
    Image.new('RGB',(24,24),'red').save(source,save_all=True,
        append_images=[Image.new('RGB',(24,24),'blue')],duration=100)
    old.save_file(str(source),target=ImportTarget(a))
    b_path=new.save_file(str(source),target=ImportTarget(b))[0]
    w.gallery_interface.set_node(a)
    departed=w.gallery_interface.renderer.loader.animation_backfill
    events=[]
    original=w.on_settings_changed
    def changed(key):
        events.append((key,w.storage.library_root))
        original(key)
    w.setting_interface.settings_changed.disconnect(original)
    monkeypatch.setattr(w,'on_settings_changed',changed)
    w.setting_interface.settings_changed.connect(changed)
    with new.index.connect(search=False) as db:
        db.execute("UPDATE resources SET metadata_json='{}' WHERE relative_path=?",
                   (new.index.relative_path(b_path),))
    assert save_to(w,new,preview_delay=777,thumbnail_size=110,show_new_resource_markers=False,auto_category_icons=True)
    active=w.storage
    assert_bound(w,active)
    assert active.library_root==new.library_root
    assert departed.cancelled.is_set() and old.ocr._closing and old.desktop_imports._closing
    assert w.gallery_interface.renderer.loader.animation_backfill.timer.isActive()
    assert w.gallery_interface.backups.timer.isActive()
    assert not active.unseen_resource_ids()
    assert old.unseen_resource_ids()
    assert active.node(b)['icon'] and not old.node(a)['icon']
    assert cfg.get('preview_delay')==777 and cfg.get('thumbnail_size')==110
    assert w.gallery_interface.preview_controller.delay==777
    assert w.quick_panel.preview_controller.delay==777
    assert {k for k,_ in events}=={'library_path','preview_delay','thumbnail_size','show_new_resource_markers','auto_category_icons'}
    assert len(events)==5 and all(root==new.library_root for _,root in events)
    w.setting_interface._select_page(1);w.setting_interface._show_tab(1)
    assert w.setting_interface._all_rows['thumbnail_size'][0].value()==110
    w.gallery_interface.set_node(b)
    active.add_recent_image(b_path)
    w.quick_panel._perform_search()
    card=w.quick_panel._all_card_widgets[0]
    active.set_resource_metadata(b_path,{'thumb_frame':1,'thumb_crop':[.1,.2,.7,.8]})
    w.gallery_interface._reload_resource_thumbnail(b_path)
    assert card.frame==1 and card.crop==(.1,.2,.7,.8)
    from time import monotonic, sleep
    deadline=monotonic()+6
    while not card._animated and monotonic()<deadline:
        app.processEvents()
        sleep(.02)
    assert card._animated
    assert active.index.animation_attribute(active.resource_of(b_path)) is True
    departed.changed.emit({card.entry_id:False})
    assert card._animated
    assert save_to(w,old)
    assert w.storage.library_root==old.library_root and w.gallery_interface.current_node==a
    assert_bound(w,w.storage)
    assert old.unseen_resource_ids()


@pytest.mark.parametrize('boundary',['persist','prepare','activate'])
def test_failure_restores_disk_and_old_live_widgets(case,monkeypatch,boundary):
    from services import library_switch
    from fluent_ui.components import quick_panel
    app,w,old,new,cfg=case
    gallery=w.gallery_interface;center=w.setting_interface;before=Path(cfg.config_path).read_bytes()
    config=dict(cfg.config)
    candidates=[]
    prepare=library_switch._prepare_views
    def prepared(window,storage):
        assert window.storage is old and window.config.backup_service is gallery.backups
        bundle=prepare(window,storage);candidate=bundle[1]
        candidates.append(candidate)
        assert not candidate.backups.timer.isActive()
        assert not candidate.renderer.loader.animation_backfill.timer.isActive()
        assert window.storage is old and Path(cfg.config_path).read_bytes()==before
        return bundle
    monkeypatch.setattr(library_switch,'_prepare_views',prepared)
    if boundary=='persist':
        def fail(*args):raise OSError('synthetic persistence failure')
        monkeypatch.setattr(cfg,'_save_config',fail)
    elif boundary=='prepare':
        def fail(*args,**kwargs):raise RuntimeError('synthetic QuickPanel construction failure')
        monkeypatch.setattr(quick_panel,'QuickPanel',fail)
    else:
        bind=library_switch._bind
        def fail(window,bundle,page):
            bind(window,bundle,page)
            if bundle[0] is not old:
                assert Path(cfg.config_path).read_bytes()!=before
                raise RuntimeError('synthetic activation failure')
        monkeypatch.setattr(library_switch,'_bind',fail)
    monkeypatch.setattr(center,'show_error',lambda *a:None)
    assert not save_to(w,new,preview_delay=777)
    assert Path(cfg.config_path).read_bytes()==before and cfg.config==config
    assert_bound(w,old)
    assert w.gallery_interface is gallery and w.setting_interface is center
    assert not old.ocr._closing and not old.desktop_imports._closing
    assert not gallery.renderer.loader.animation_backfill.cancelled.is_set()
    assert all(c.renderer.loader.animation_backfill.cancelled.is_set() for c in candidates)
    assert center.pending['preview_delay']==777


def test_same_library_skips_construction_even_when_busy(case,monkeypatch):
    from services import library_setup
    app,w,old,new,cfg=case
    def fail(*args,**kwargs):raise AssertionError('same library must not prepare')
    monkeypatch.setattr(library_setup,'prepare_library',fail)
    gallery=w.gallery_interface
    old.desktop_imports.waiting.append('synthetic')
    try:
        assert save_to(w,old,preview_delay=701)
        assert w.gallery_interface is gallery
        assert_bound(w,old)
    finally:old.desktop_imports.waiting.clear()


@pytest.mark.parametrize('task',['import','ocr','backup'])
def test_active_tasks_block_then_allow_save(case,monkeypatch,task):
    app,w,old,new,cfg=case
    monkeypatch.setattr(w.setting_interface,'show_error',lambda *a:None)
    with monkeypatch.context() as patch:
        if task=='import':patch.setattr(old.desktop_imports,'waiting',['active'])
        elif task=='ocr':patch.setattr(old.ocr,'_busy',True)
        else:patch.setattr(old.backup_service,'_retry_at',1)
        assert not save_to(w,new)
        assert_bound(w,old)
    assert w.setting_interface.save()
    assert w.storage.library_root==new.library_root


def test_retirement_failure_keeps_commit_and_continues_cleanup(case,monkeypatch,caplog):
    app,w,old,new,cfg=case
    def fail():raise OSError('retirement test')
    monkeypatch.setattr(w.quick_panel,'shutdown',fail)
    assert save_to(w,new)
    assert w.storage.library_root==new.library_root
    assert cfg.get('library_path')==new.library_root
    assert old.ocr._closing and old.animation_backfill.cancelled.is_set()
    assert 'retirement test' in caplog.text


def test_switch_cancels_running_animation_probe(case, monkeypatch):
    from pathlib import Path
    from threading import Event
    from PIL import Image
    from services import animation_attributes
    from fluent_ui.components.emoji_card import _thumbnail_pool

    app,w,old,new,cfg=case
    source=Path(new.library_root).parent/'old.gif'
    Image.new('RGB',(24,24),'red').save(source,save_all=True,
        append_images=[Image.new('RGB',(24,24),'blue')],duration=100)
    path=old.save_file(str(source))[0]
    record=old.resource_of(path)
    with old.index.connect(search=False) as db:
        db.execute("UPDATE resources SET metadata_json='{}' WHERE id=?", (record['id'],))
    entered=Event()
    release=Event()
    def probe(path):
        entered.set()
        assert release.wait(8)
        return True
    monkeypatch.setattr(animation_attributes,'probe_animation',probe)
    backfill=old.animation_backfill
    backfill.timer.stop()
    backfill._next()
    try:
        assert entered.wait(5)
        assert save_to(w,new)
        assert backfill.cancelled.is_set() and not release.is_set()
    finally:
        release.set()
        _thumbnail_pool.waitForDone(8000)
    assert old.index.animation_attribute(old.resource_of(path)) is None
    assert w.storage.library_root==new.library_root


@pytest.mark.parametrize('boundary', ['prepare', 'persist', 'commit'])
def test_target_ocr_recovery_belongs_to_commit(case, monkeypatch, boundary):
    import json
    from fluent_ui.components import quick_panel

    app, w, old, new, cfg = case
    running = {'id': 'active-ocr', 'state': 'running'}
    complete = {'id': 'complete-ocr', 'state': 'completed'}
    new.index.set_meta('ocr_task_summary', json.dumps(running))
    new.index.set_meta('ocr_task_jobs', json.dumps([running, complete]))
    with new.index.connect(search=False) as db:
        for item in (running, complete):
            db.execute('INSERT INTO task_checkpoints VALUES (?,?,?,?)',
                       (item['id'], 'fixture', 'ocr', '{}'))

    def read_ocr():
        with new.index.connect(search=False) as db:
            checkpoints = [tuple(row) for row in db.execute(
                "SELECT * FROM task_checkpoints WHERE kind='ocr' ORDER BY task_id")]
        return new.index.meta('ocr_task_summary'), new.index.meta('ocr_task_jobs'), checkpoints

    before = read_ocr()
    original = cfg._save_config
    def persist(values):
        assert read_ocr() == before
        if boundary == 'persist':
            raise OSError('controlled config failure')
        original(values)
    monkeypatch.setattr(cfg, '_save_config', persist)
    if boundary == 'prepare':
        def fail(*args, **kwargs):
            assert read_ocr() == before
            raise RuntimeError('controlled candidate failure')
        monkeypatch.setattr(quick_panel, 'QuickPanel', fail)
    assert save_to(w, new) is (boundary == 'commit')
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    if boundary != 'commit':
        assert read_ocr() == before and w.storage is old
    else:
        summary, jobs, checkpoints = read_ocr()
        assert json.loads(summary)['state'] == 'interrupted'
        assert [job['state'] for job in json.loads(jobs)] == ['interrupted', 'completed']
        assert [item[0] for item in checkpoints] == ['active-ocr']
        assert w.storage.ocr._import_callback in w.storage.import_listeners


def test_post_commit_failures_report_details_and_keep_other_settings(case, monkeypatch, caplog):
    from fluent_ui.views.settings_center import SettingsCenter
    from services.backup_service import BackupService
    from PIL import Image
    from services.resource_import import ImportTarget

    app, w, old, new, cfg = case
    source = Path(new.library_root).parent/'icon.png'
    Image.new('RGB', (20, 20), 'red').save(source)
    node = next(n['id'] for n in new.index.nodes() if n['name'] == 'NEW')
    new.save_file(str(source), target=ImportTarget(node))
    def fail_icon(*args, **kwargs):
        raise OSError('icon file unavailable')
    def fail_backup(*args, **kwargs):
        raise OSError('backup state unavailable')
    feedback = []
    monkeypatch.setattr(StorageService, '_store_node_icon_file', fail_icon)
    monkeypatch.setattr(BackupService, '_recover_interrupted', fail_backup)
    sync = SettingsCenter.sync_external_preference
    def sync_with_failure(self, key, value):
        if key == 'auto_category_icons':
            raise RuntimeError('settings display unavailable')
        sync(self, key, value)
    monkeypatch.setattr(SettingsCenter, 'sync_external_preference', sync_with_failure)
    monkeypatch.setattr(SettingsCenter, 'show_error', lambda self, title, detail: feedback.append((title, detail)))
    assert save_to(w, new, auto_category_icons=True, preview_delay=725, thumbnail_size=100)
    assert w.storage.library_root == new.library_root
    assert w.quick_panel.preview_controller.delay == w.gallery_interface.preview_controller.delay == 725
    assert w.gallery_interface.renderer.index.size == 100
    assert old.ocr._closing and old.animation_backfill.cancelled.is_set()
    assert len(feedback) == 1 and feedback[0][0] == '设置已保存'
    assert 'icon file unavailable' in feedback[0][1] and 'backup state unavailable' in feedback[0][1]
    assert 'settings display unavailable' in feedback[0][1]
    assert 'icon file unavailable' in caplog.text and 'backup state unavailable' in caplog.text
    service = w.gallery_interface.backups
    assert not service.timer.isActive() and service.startup_error == 'backup state unavailable'
    center = w.setting_interface
    center._select_page(3)
    center._show_tab(0)
    assert '备份服务启动失败' in center.backup_status_row.hint_label.text()
    assert 'backup state unavailable' in center.backup_status_row.hint_label.text()


def test_roundtrip_keeps_each_library_scroll_anchor(case):
    from PIL import Image
    from PySide6.QtTest import QTest
    from services.library_index import ROOT

    app, window, old, new, config = case
    config.set('thumbnail_size', 200)
    for color, storage in enumerate((old, new), 1):
        for i in range(40):
            source = Path(storage.library_root).parent / 'sample.png'
            Image.new('RGB', (16, 16), (i, i * 4, color)).save(source)
            storage.save_file(str(source))
    window.gallery_interface.on_images_changed()
    window.resize(760, 590)
    window.show()
    positions = []
    for step, target in enumerate((old, new, old, new)):
        if step:
            assert save_to(window, target)
        gallery = window.gallery_interface
        gallery.set_node(ROOT, force=True)
        QTest.qWait(70)
        bar = gallery.scroll_area.verticalScrollBar()
        assert bar.maximum() > 200
        if step < 2:
            bar.setValue(170 + step * 75)
            positions.append(gallery.renderer.anchor())
        else:
            assert gallery.renderer.anchor() == positions[step - 2]
    assert positions[0][0] != positions[1][0]
