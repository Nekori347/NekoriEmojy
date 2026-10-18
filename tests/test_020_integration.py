"""Only the changed integration seams; all data and Qt input remain isolated."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from types import SimpleNamespace
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings
from test_ocr_queue import context,app,wait,save
from pathlib import Path
from PIL import Image


def test_preview_and_main_size_commit_share_state_without_stale_discard(surface,settings):
    g=surface.g;c=settings;g.settings_window=SimpleNamespace(center=c)
    c.settings_changed.connect(g.on_settings_changed)
    c._select_page(1);c._show_tab(1)
    original=surface.config.get('thumbnail_size',120)
    row=c._rows['thumbnail_size'][0]
    row.set_value(180);row.changed.emit();settle(surface.app)
    assert c.pending['thumbnail_size']==180 and g.size_slider.value()==180
    assert surface.config.config['thumbnail_size']==original
    g._commit_thumbnail_size(200)
    assert row.value()==200 and 'thumbnail_size' not in c.pending
    row.set_value(220);row.changed.emit();c.discard()
    assert g.size_slider.value()==200 and surface.config.get('thumbnail_size')==200


def test_opening_window_drops_stale_caption_hover(surface):
    from fluent_ui.window_shell import NekoriWindow,NekoriTitleBar
    from qframelesswindow.titlebar.title_bar_buttons import TitleBarButtonState
    w=NekoriWindow();w.setTitleBar(NekoriTitleBar(w));w.resize(800,600)
    close=w.titleBar.closeBtn
    close.setState(TitleBarButtonState.HOVER)
    w.show();settle(surface.app)
    try:assert close._state==TitleBarButtonState.NORMAL
    finally:w.close();w.deleteLater();settle(surface.app)


def test_force_library_job_preserves_edits_and_job_cancel_is_independent(context,tmp_path,app):
    storage,worker,service=context
    paths=[save(storage,tmp_path,f'{i}.png',color) for i,color in enumerate(['red','blue','green'])]
    ids=[storage.index.resource(p)['id'] for p in paths]
    service.edit(ids[0],'人工修正')
    worker.block_on=paths[1]
    service.supplement(force=True,job_id='old-library');wait(app,worker.started.is_set)
    service.enqueue([ids[2]],job_id='new-import',origin='import')
    service.cancel(job_id='old-library');wait(app,lambda:not service.busy)
    assert service.jobs['old-library']['state']=='cancelled'
    assert service.jobs['new-import']['state']=='completed'
    assert storage.index.ocr_info(ids[0])['text']=='人工修正'
    assert storage.index.ocr_info(ids[2])['status']=='ready'
    service.close()
    from services.ocr_service import OcrService
    reopened=OcrService(storage,process=worker)
    try:assert reopened.jobs['old-library']['state']=='cancelled'
    finally:reopened.close()


def test_force_library_resume_after_restart_keeps_finished_work(context,tmp_path,app):
    from services.ocr_service import OcrService
    storage,worker,service=context
    for i,color in enumerate(['red','green','blue','yellow']):save(storage,tmp_path,f'resume-{i}.png',color)
    records=storage.index.resources();paths=[storage.index.absolute_path(r) for r in records]
    worker.block_on=paths[1];worker.release.clear()
    service.supplement(force=True,job_id='force-resume');wait(app,worker.started.is_set)
    assert storage.index.ocr_info(records[0]['id'])['status']=='ready'
    service.cancel(job_id='force-resume');wait(app,lambda:not service.busy);service.close()
    worker.block_on=None
    reopened=OcrService(storage,process=worker)
    try:
        reopened.supplement(force=True,job_id='force-resume');wait(app,lambda:not reopened.busy)
        assert worker.calls[paths[0]]==1
        assert all(storage.index.ocr_info(r['id'])['status']=='ready' for r in records)
        assert reopened.jobs['force-resume']['state']=='completed'
    finally:reopened.close()


def test_duplicate_keep_skip_and_replace_preserve_identity_and_rollback(context,tmp_path,monkeypatch):
    import hashlib
    from services.resource_import import ImportSkipped,ImportTarget
    storage,_,_=context
    path=save(storage,tmp_path,'red.png','red');rid=storage.index.resource(path)['id']
    node=storage.create_node('目标');storage.index.add_membership(rid,node)
    storage.apply_tags([path],['保留标签'],'add');storage.index.edit_ocr_text(rid,'保留人工文字')
    storage.import_context.duplicate_resolver=lambda *_:'keep'
    kept,duplicate=storage.save_file(str(tmp_path/'red.png'),strict=True)
    assert kept!=path and not duplicate and storage.index.resource(kept)['id']!=rid
    storage.import_context.duplicate_resolver=lambda *_:'skip'
    with pytest.raises(ImportSkipped):storage.save_file(str(tmp_path/'red.png'),strict=True)
    # Direct replacement exercises an actual content change as well as the byte-identical no-op.
    before=Path(path).read_bytes();stamp=Path(path).stat().st_mtime_ns
    assert storage.replace_normalized(path,(before,'.png',hashlib.md5(before).hexdigest()))==path
    assert Path(path).stat().st_mtime_ns==stamp
    blue=tmp_path/'blue.png';Image.new('RGB',(30,30),'blue').save(blue)
    data=blue.read_bytes();normalized=(data,'.png',hashlib.md5(data).hexdigest())
    original=storage.index.connect
    from contextlib import contextmanager
    @contextmanager
    def fail_write():
        with original() as db:
            class Broken:
                def execute(self,sql,args=()):
                    if sql.startswith('UPDATE resources'):raise OSError('injected index failure')
                    return db.execute(sql,args)
            yield Broken()
    monkeypatch.setattr(storage.index,'connect',fail_write)
    with pytest.raises(OSError):storage.replace_normalized(path,normalized)
    monkeypatch.setattr(storage.index,'connect',original)
    assert Path(path).read_bytes()==before
    storage.replace_normalized(path,normalized)
    record=storage.index.resource(path)
    assert record['id']==rid and record['tags']=='保留标签'
    assert storage.index.ocr_info(rid)['text']=='保留人工文字'
    assert any(r['resource_id']==rid and r['node_id']==node for r in storage.index.memberships())
    assert Path(path).read_bytes()==data


def test_real_duplicate_dialog_skip_then_queue_proceeds(context,tmp_path,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.import_queue import ImportQueue
    from services.resource_import import ImportTarget
    storage,_,_=context
    save(storage,tmp_path,'red.png','red')
    blue=tmp_path/'blue.png';Image.new('RGB',(22,22),'blue').save(blue)
    owner=QWidget();owner.show();queue=ImportQueue(storage,app)
    first=queue.submit([str(tmp_path/'red.png'),str(blue)],ImportTarget(),owner)
    second=queue.submit([str(blue)],ImportTarget(),owner)
    try:
        wait(app,lambda:bool(queue._dialogs))
        assert queue.requests[second].state=='waiting'
        next(iter(queue._dialogs.values())).reject()
        wait(app,lambda:queue.requests[first].state=='completed')
        assert queue.requests[first].skipped==1 and queue.requests[first].saved==1
        wait(app,lambda:bool(queue._dialogs))
        queue.cancel(second)
        wait(app,lambda:queue.worker is None)
        assert queue.requests[first].state=='completed' and queue.requests[second].state=='cancelled'
        assert len(storage.index.resources())==2
    finally:queue.shutdown();owner.close();queue.deleteLater();settle(app)


def test_import_files_finish_while_ocr_runs_and_task_keeps_original_id(context,tmp_path,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.import_queue import ImportQueue
    from services.resource_import import ImportTarget
    storage,worker,service=context;storage.ocr=service;storage.config.set('ocr_auto',True)
    # Block every recognition until both file imports have completed.
    recognize=worker.recognize
    def blocked(path,thumbnail=0):
        worker.started.set();worker.release.wait(5);return recognize(path,thumbnail)
    worker.recognize=blocked
    for name,color in [('first','red'),('second','blue')]:Image.new('RGB',(22,22),color).save(tmp_path/(name+'.png'))
    owner=QWidget();owner.show();queue=ImportQueue(storage,app)
    first=queue.submit([str(tmp_path/'first.png')],ImportTarget(),owner)
    second=queue.submit([str(tmp_path/'second.png')],ImportTarget(),owner)
    try:
        wait(app,lambda:len(storage.index.resources())==2 and queue.worker is None)
        assert queue.requests[first].state==queue.requests[second].state=='recognizing'
        assert set(service.jobs)=={first,second}
        assert all(j['origin']=='import' for j in service.jobs.values())
        worker.release.set();wait(app,lambda:all(r.state=='completed' for r in queue.requests.values()))
    finally:worker.release.set();queue.shutdown();owner.close();queue.deleteLater();settle(app)


def test_category_menu_is_lazy_searches_paths_and_selects_parent(surface):
    from fluent_ui.components.category_menu import CategoryTargetMenu
    from PySide6.QtTest import QTest
    chosen=[];menu=CategoryTargetMenu('添加到分类',surface.storage,chosen.append,surface.g)
    try:
        menu.prepare()
        branch=next(m for m in menu._subMenus if m.node==surface.parent)
        assert not branch._prepared and not branch._actions
        branch.prepare();branch._actions[0].trigger();assert chosen==[surface.parent]
        menu.search.setText('Parent/Child');menu._filter.stop();menu._populate('Parent/Child')
        assert len(menu._actions)==2
        menu._actions[-1].trigger();assert chosen[-1]==surface.child
        menu.search.setText('Other');QTest.keyClick(menu.search,Qt.Key_Down);QTest.keyClick(menu.view,Qt.Key_Return)
        assert chosen[-1]==surface.other
    finally:menu.close();menu.deleteLater();settle(surface.app)


def test_search_projection_reuses_snapshot_and_edit_invalidates(context,tmp_path):
    storage,_,_=context;path=save(storage,tmp_path,'one.png','red');rid=storage.index.resource(path)['id']
    first=storage.index.search_texts();assert storage.index.search_texts() is first
    storage.index.edit_ocr_text(rid,'放棄')
    assert storage.index.search_texts() is not first
    assert path in storage.search_images('放弃')


def test_queued_insertion_keeps_stable_anchor_and_request_order(context,tmp_path,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.import_queue import ImportQueue
    from services.resource_import import ImportTarget
    storage,_,_=context;node=storage.create_node('Target')
    red=save(storage,tmp_path,'red.png','red');rid=storage.index.resource(red)['id'];storage.index.add_membership(rid,node)
    owner=QWidget();owner.show();queue=ImportQueue(storage,app)
    ids=[]
    try:
        for name,color in [('blue','blue'),('green','green')]:
            source=tmp_path/(name+'.png');Image.new('RGB',(22,22),color).save(source)
            ids.append(queue.submit([str(source)],ImportTarget(node,0),owner))
        wait(app,lambda:all(queue.requests[k].state=='completed' for k in ids))
        expected=[storage.index.resource(queue.requests[k].paths[0])['id'] for k in ids]+[rid]
        assert [r['id'] for r in storage.index.content(node)]==expected
    finally:queue.shutdown();owner.close();queue.deleteLater();settle(app)


@pytest.mark.parametrize('fmt,extension',[('GIF','gif'),('WEBP','webp'),('PNG','png')])
def test_duplicate_candidates_play_actual_gif_webp_and_apng(app,tmp_path,fmt,extension):
    from fluent_ui.components.duplicate_dialog import DuplicateDialog
    from PySide6.QtWidgets import QWidget
    from PySide6.QtTest import QTest
    source=tmp_path/('animated.'+extension)
    Image.new('RGBA',(32,32),'red').save(source,format=fmt,save_all=True,
        append_images=[Image.new('RGBA',(32,32),'blue')],duration=100,loop=0)
    owner=QWidget();owner.show();choices=[]
    dialog=DuplicateDialog(owner,str(source),str(source),choices.append);dialog.show()
    try:
        before=[p.pixmap().toImage().pixelColor(0,0) for p in dialog.previews]
        wait(app,lambda:all(p.pixmap().toImage().pixelColor(0,0)!=color for p,color in zip(dialog.previews,before)))
        dialog.select('keep');assert choices==['keep']
        assert all(not p.timer.isActive() and p.image is None for p in dialog.previews)
    finally:dialog.close();owner.close();dialog.deleteLater();settle(app)


def test_native_collection_queue_skip_is_local_and_keep_both_remains_independent(context,tmp_path,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.import_queue import ImportQueue
    from services.resource_import import ImportTarget
    from services.nekori_package import NekoriPackageService
    storage,_,_=context;save(storage,tmp_path,'red.png','red');save(storage,tmp_path,'blue.png','blue')
    package=tmp_path/'both.zip';NekoriPackageService(storage).export(package)
    owner=QWidget();owner.show();queue=ImportQueue(storage,app)
    rid=queue.submit([str(package)],ImportTarget(),owner,operation=lambda progress:NekoriPackageService(storage).import_package(package,progress))
    try:
        wait(app,lambda:bool(queue._dialogs));next(iter(queue._dialogs.values())).reject()
        wait(app,lambda:bool(queue._dialogs));next(iter(queue._dialogs.values())).select('keep')
        wait(app,lambda:queue.requests[rid].state=='completed')
        request=queue.requests[rid]
        assert request.skipped==1 and request.saved==1 and request.failed==0
        assert len(storage.index.resources())==3
    finally:queue.shutdown();owner.close();queue.deleteLater();settle(app)


def test_multiple_feedback_rows_update_in_place_do_not_reflow_or_reopen_dismissed(surface):
    host=surface.g.feedback_host;host.dock_to_caption(surface.g)
    geometry=surface.g.scroll_area.geometry();host.upsert_task('one','正在导入表情',current=1,total=3)
    first=host._named_widgets['one'][0]
    host.upsert_task('one','正在导入表情',current=2,total=3)
    host.upsert_task('two','补充识别',current=1,total=6,kind='ocr')
    settle(surface.app)
    assert host._named_widgets['one'][0] is first and len(host._named_widgets)==2
    assert host._caption_ui.panel.isHidden() and host._caption_ui.ear.isVisible()
    assert host._caption_ui.primary=='one'
    host._caption_ui.expand();settle(surface.app)
    assert host._named_widgets['two'][0].y()>first.y()
    assert surface.g.scroll_area.geometry()==geometry
    host.upsert_task('one','导入处理完成',state='success');host.remove_task('one')
    host.upsert_task('one','导入处理完成',state='success')
    assert 'one' not in host._named_widgets
    host.remove_task('two')


def test_shared_update_release_controls_version_and_dot(settings):
    from fluent_ui.components.update_center import update_center
    center=update_center();settings._select_page(4);settings._show_tab(0)
    try:
        center.set_release({'version':'0.2.1'})
        assert settings.btn_update.available and not settings.update_badge.isHidden()
        assert settings.version_label.dot_visible and settings.btn_update.text()=='获取更新'
        assert '0.2.1' in settings.update_badge.text()
        center.set_release(None)
        assert not settings.btn_update.available and settings.update_badge.isHidden()
        assert not settings.version_label.dot_visible and settings.btn_update.text()=='检查更新'
    finally:center.set_release(None)


@pytest.mark.parametrize('language',['zh','en','ja','zh_TW'])
def test_changed_settings_copy_fits_narrow_page_with_semantic_breaks(settings,language):
    from services.i18n import i18n_engine
    from fluent_ui.components.setting_rows import SettingRow
    app=QApplication.instance();c=settings;c.resize(880,680);i18n_engine.set_language(language)
    try:
        for primary,tab in [(1,1),(2,0),(2,1),(3,1),(3,2),(3,3),(4,0)]:
            c._select_page(primary);c._show_tab(tab);settle(app)
            assert c.body_widget.width()<=c.scroll.viewport().width(),(language,primary,tab,c.body_widget.width(),c.scroll.viewport().width())
            for row in c.body_widget.findChildren(SettingRow):
                assert 'MISSING' not in row.title_label.text()+row.hint_label.text()
                if not row.hint_label.isHidden():
                    label=row.hint_label
                    assert label.height()>=label.heightForWidth(label.width()),(language,row.title_label.text(),label.size(),label.heightForWidth(label.width()))
    finally:i18n_engine.set_language('zh')


def test_qq_and_telegram_ui_requests_share_queue_and_report_partial_failure(context,tmp_path,app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.views.qq_scan_view import QQScanInterface
    from fluent_ui.views.tg_sticker_view import TGStickerInterface
    from fluent_ui.components.import_queue import import_queue
    from io import BytesIO
    storage,_,service=context;storage.ocr=service
    owner=QWidget();owner.storage=storage;owner.show()
    files=[]
    for i,color in enumerate(['red','blue']):
        path=tmp_path/(str(i)+'.bmp');Image.new('RGB',(22,22),color).save(path);files.append(str(path))
    qq=SimpleNamespace(_current_worker=None,window=lambda:owner,get_selected_qq=lambda:'123',getSelectedFolder=lambda:'pic',_is_marketface=lambda:False)
    first=QQScanInterface.import_files_with_progress(qq,[*files,str(tmp_path/'absent.bmp')])
    buffer=BytesIO();Image.new('RGB',(22,22),'green').save(buffer,'BMP')
    def download(key):
        if key=='bad':raise OSError('isolated source unavailable')
        return buffer.getvalue()
    downloader=SimpleNamespace(get_file_path=lambda key:key,download_file_bytes=download)
    tg=SimpleNamespace(_has_running_task=lambda:False,window=lambda:owner,
        current_pack=SimpleNamespace(name='Sample'),all_stickers=[SimpleNamespace(index=i,file_id=key) for i,key in enumerate(['good','bad'])],
        _get_configured_downloader=lambda:downloader)
    second=TGStickerInterface._executeImport(tg,None)
    queue=import_queue(storage)
    try:
        wait(app,lambda:queue.requests[first].state=='completed' and queue.requests[second].state=='completed')
        assert queue.requests[first].saved==2 and queue.requests[first].failed==1
        assert 'absent.bmp' in '\n'.join(queue.requests[first].errors)
        assert queue.requests[second].saved==1 and queue.requests[second].failed==1
        assert 'isolated source unavailable' in '\n'.join(queue.requests[second].errors)
        assert len(storage.get_images_by_category('QQ_123_pic'))==2
        assert len(storage.get_images_by_category('TG_Sample'))==1
    finally:queue.shutdown();owner.close();queue.deleteLater();settle(app)
