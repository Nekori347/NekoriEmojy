"""Five result cues at actual transaction boundaries, no desktop/audio output."""
import threading,json,hashlib
from pathlib import Path
from unittest.mock import Mock
import pytest
from PySide6.QtCore import QUrl,Qt,QMimeData,QEventLoop,QTimer
from PySide6.QtTest import QTest
from services.send_sound import EVENT_SOUNDS,SendSound,perceptual_volume
from services.resource_import import ImportTarget
from fluent_ui.components.drop_contract import DragSession,DropTarget,RESOURCE_MIME,NODE_MIME,TAG_MIME,MOVE,INSERT_BEFORE,INTO
from test_phase2_interaction import surface


def voice(surface):
    player=surface.config.ui_sound=Mock()
    for event in EVENT_SOUNDS:surface.config.config[event+'_sound_enabled']=True
    return player


def drag(paths,kind=RESOURCE_MIME):
    mime=QMimeData();mime.setData(kind,json.dumps(paths).encode())
    return DragSession(mime)


def order(storage,node):return storage.entries_of(node)


def test_five_defaults_are_original_assets_and_off_without_resetting_old_config(surface):
    from services.config import ConfigService
    config=surface.config
    for event in EVENT_SOUNDS:
        assert config.get(event+'_sound_enabled') is False and config.get(event+'_sound_path')==''
        assert EVENT_SOUNDS[event].is_file()
    config.config.update(send_sound_enabled=True,send_sound_path='old-custom.wav',import_sound_enabled=True,import_sound_path='old-add.wav',sound_volume=51)
    config._save_config(config.config);reopened=ConfigService(config.base_dir)
    assert reopened.get('send_sound_path')=='old-custom.wav' and reopened.get('import_sound_path')=='old-add.wav'
    assert reopened.get('sound_volume')==51 and all(not reopened.get(e+'_sound_enabled') for e in ('delete','reorder','category'))
    manifest=json.loads((EVENT_SOUNDS['send'].parent/'uisfx-source.json').read_text('utf-8'))
    for event,name in [('delete','reorder'),('reorder','typing'),('category','swipe')]:
        row=manifest['files'][name]
        assert row['wav_sha256']==hashlib.sha256(EVENT_SOUNDS[event].read_bytes()).hexdigest()
        assert row['true_peak_dbfs']<=-3


@pytest.mark.parametrize('mode',['changed','unchanged','cancelled','rejected','failed','button'])
def test_sort_sound_needs_changed_successful_drag_commit(surface,mode):
    s=surface.storage;player=voice(surface);before=order(s,surface.parent);desired=before[1:]+before[:1]
    session=drag(surface.paths[:1]);target=DropTarget(INSERT_BEFORE,MOVE,before[1]['id'],surface.parent,1)
    def commit(*_):
        s.set_content_order(surface.parent,before if mode=='unchanged' else desired)
        if mode=='rejected':return False
        if mode=='failed':raise RuntimeError('post-transaction failure')
    if mode=='cancelled':session.operation.cancel();assert not session.commit(target,commit)
    elif mode=='button':commit()
    else:session.commit(target,commit)
    assert player.play.call_count==int(mode=='changed')
    if mode=='changed':
        player.play.assert_called_once_with(surface.config,event='reorder')
        assert not session.commit(target,commit)


def test_multiple_sort_writes_with_one_session_play_once_after_commit(surface):
    s=surface.storage;player=voice(surface);items=order(s,surface.parent);session=drag(surface.paths[:2])
    def commit(*_):
        s.set_content_order(surface.parent,items[1:]+items[:1])
        player.play.assert_not_called()
        s.set_content_order(surface.parent,list(reversed(items)))
        player.play.assert_not_called()
    assert session.commit(DropTarget(INSERT_BEFORE,MOVE,items[1]['id'],surface.parent),commit)
    player.play.assert_called_once_with(surface.config,event='reorder')


def test_node_reorder_and_reparent_are_distinct(surface):
    s=surface.storage;player=voice(surface)
    first=drag([surface.child],NODE_MIME)
    before=order(s,surface.parent)
    position=0 if before[0]['id']!=surface.child else len(before)
    assert first.commit(DropTarget(INSERT_BEFORE,MOVE,surface.paths[1],surface.parent),
                        lambda *_:s.move_nodes([surface.child],surface.parent,position))
    assert [e['id'] for e in before]!=[e['id'] for e in order(s,surface.parent)]
    player.play.assert_called_once_with(surface.config,event='reorder');player.play.reset_mock()
    second=drag([surface.child],NODE_MIME)
    assert second.commit(DropTarget(INTO,MOVE,surface.other,surface.other),lambda *_:s.move_nodes([surface.child],surface.other))
    player.play.assert_not_called()


def test_tag_metadata_refresh_during_resource_drop_is_not_a_tag_sort(surface):
    s=surface.storage;player=voice(surface);s.set_tag_order(['a','b'])
    resource=drag(surface.paths[:1])
    assert resource.commit(DropTarget(INSERT_BEFORE,MOVE,'any',surface.parent),lambda *_:s.set_tag_order(['b','a']))
    player.play.assert_not_called()
    tag=drag(['a'],TAG_MIME)
    assert tag.commit(DropTarget(INSERT_BEFORE,MOVE,'b',None),lambda *_:s.set_tag_order(['a','b']))
    player.play.assert_called_once_with(surface.config,event='reorder')


def test_background_membership_change_does_not_turn_noop_node_drop_into_sort(surface,monkeypatch):
    s=surface.storage;player=voice(surface)
    # Child is already last after the fixture's front-inserted resource batch.
    assert s.index.content(surface.parent)[-1]['id']==surface.child
    original=s.index.move_nodes;rid=s.index.resource(surface.paths[3])['id']
    def concurrent_import(nodes,parent,position=None):
        # Deterministic interleaving: another import committed after the UI's
        # old snapshot, before this operation acquired its SQLite transaction.
        s.index.add_membership(rid,parent,position=0)
        return original(nodes,parent,position)
    monkeypatch.setattr(s.index,'move_nodes',concurrent_import)
    session=drag([surface.child],NODE_MIME)
    assert session.commit(DropTarget(INTO,MOVE,surface.parent,surface.parent),lambda *_:s.move_nodes([surface.child],surface.parent))
    assert s.index.content(surface.parent)[-1]['id']==surface.child
    player.play.assert_not_called()


def test_category_copy_move_duplicate_and_batch_contract(surface):
    s=surface.storage;player=voice(surface);paths=[surface.paths[0],surface.paths[1]]
    assert s.move_resources_to(paths,surface.other,copy=True,source_node=surface.parent)==2
    player.play.assert_called_once_with(surface.config,event='category');player.play.reset_mock()
    assert s.move_resources_to(paths,surface.other,copy=True,source_node=surface.parent)==0
    player.play.assert_not_called()
    s.move_resources_to(paths,surface.child,copy=False,source_node=surface.parent)
    player.play.assert_not_called()
    s.remove_images_from_category(paths,surface.other);player.play.assert_not_called()


def test_cross_category_choice_waits_and_arbitrates_one_result(surface):
    from fluent_ui.components.drop_contract import current_drop_operation
    s=surface.storage;player=voice(surface);session=drag(surface.paths[:2])
    assert session.commit(DropTarget(INTO,MOVE,surface.other,surface.other),lambda *_:current_drop_operation().defer())
    player.play.assert_not_called()
    assert session.operation.complete(lambda:s.move_resources_to(surface.paths[:2],surface.other,copy=True,source_node=surface.parent))
    player.play.assert_called_once_with(surface.config,event='category')
    assert not session.operation.complete(lambda:s.move_resources_to(surface.paths[:2],surface.child))


@pytest.mark.parametrize('mode',['success','cancelled','failed','partial','missing','remove_membership'])
def test_delete_batch_only_actual_success_no_membership_sound(surface,monkeypatch,mode):
    s=surface.storage;player=voice(surface);paths=surface.paths[:2]
    calls=[]
    def recycle(path,library):
        assert Path(path).resolve().is_relative_to(surface.tmp.resolve())
        calls.append(path)
        if mode=='failed' or (mode=='partial' and len(calls)==2):raise OSError('test recycle failure')
        Path(path).unlink()
    monkeypatch.setattr('services.recycle_bin.recycle_file',recycle)
    if mode=='missing':paths=[surface.paths[2]]
    if mode=='remove_membership':s.remove_images_from_category(paths,surface.parent)
    else:s.delete_images_batch(paths,cancel_check=lambda:mode=='cancelled')
    assert player.play.call_count==int(mode=='success')
    if mode=='success':player.play.assert_called_once_with(surface.config,event='delete')


def test_confirmation_cancel_never_reaches_delete_sound(surface,monkeypatch):
    player=voice(surface)
    monkeypatch.setattr('fluent_ui.components.dialogs.confirm',lambda *_args,**_kwargs:False)
    ids=surface.storage.index.resource_ids(surface.paths[:2])
    surface.g._delete_resource_ids(ids)
    assert len(surface.storage.index.resource_records(ids))==2
    player.play.assert_not_called()


def test_delete_worker_marshals_audio_to_gui_thread(surface,monkeypatch):
    player=voice(surface);threads=[];player.play.side_effect=lambda *a,**kw:threads.append(threading.get_ident())
    monkeypatch.setattr('services.recycle_bin.recycle_file',lambda path,library:Path(path).unlink())
    worker=threading.Thread(target=lambda:surface.storage.delete_images_batch(surface.paths[:1]));worker.start();worker.join()
    QTest.qWait(10)
    assert threads==[threading.get_ident()]


def test_new_import_into_category_has_one_import_cue_not_category(surface):
    from PIL import Image
    player=voice(surface);sources=[]
    for i in range(3):
        path=surface.tmp/f'fresh-cue-{i}.png';Image.new('RGB',(21,23),(25+i*50,110,150)).save(path);sources.append(str(path))
    queue=surface.g.imports;rid=queue.submit(sources,ImportTarget(surface.other),surface.g)
    loop=QEventLoop();timeout=QTimer();timeout.setSingleShot(True);timeout.timeout.connect(loop.quit)
    def changed(_identity):
        if queue.worker is None and queue.requests[rid].state in {'completed','failed','cancelled'}:loop.quit()
    queue.changed.connect(changed);timeout.start(20000);loop.exec();timeout.stop();queue.changed.disconnect(changed)
    assert queue.requests[rid].saved==3
    player.play.assert_called_once_with(surface.config,event='import')


def test_five_previews_share_voice_custom_path_volume_and_stop(surface,tmp_path):
    player=SendSound();player.effect=effect=Mock();effect.source.return_value=QUrl()
    custom=tmp_path/'custom.wav';custom.write_bytes(EVENT_SOUNDS['send'].read_bytes())
    for event,default in EVENT_SOUNDS.items():
        player.play(surface.config,event=event);assert not effect.play.called
        player.play(surface.config,event=event,preview=True,path='',volume=36)
        assert effect.setSource.call_args.args[0]==QUrl.fromLocalFile(str(default.resolve()))
        assert player.preview_event==event
        assert effect.setVolume.call_args.args[0]==perceptual_volume(36)
        effect.play.reset_mock()
    player.play(surface.config,event='category',preview=True,path=str(custom),volume=36)
    assert effect.setSource.call_args.args[0]==QUrl.fromLocalFile(str(custom.resolve()))
    player.stop_preview();assert player.preview_event==''
    effect.play.reset_mock();player.play(surface.config,event='delete',preview=True,path=str(tmp_path/'missing.wav'))
    effect.play.assert_not_called()


def test_five_sound_settings_save_discard_defaults_and_reopen(surface,monkeypatch):
    from fluent_ui.views.settings_center import SettingsCenter
    center=SettingsCenter(surface.config,surface.storage);center._select_page(2);center._show_tab(2)
    assert len(center._sound_rows)==5
    for event in EVENT_SOUNDS:
        center._stage(event+'_sound_enabled',True);center._set_sound(event,event+'-custom.wav')
    center._stage('sound_volume',43)
    player=surface.config.ui_sound=Mock();center._preview_sound('category')
    player.play.assert_called_once_with(surface.config,event='category',preview=True,path='category-custom.wav',volume=43)
    center.discard();assert not center.pending and all(not surface.config.get(e+'_sound_enabled') for e in EVENT_SOUNDS)
    for event in EVENT_SOUNDS:
        center._stage(event+'_sound_enabled',True);center._set_sound(event,event+'-custom.wav')
    assert center.save()
    for event in EVENT_SOUNDS:center._set_sound(event,'')
    assert all(surface.config.get(e+'_sound_path')==e+'-custom.wav' for e in EVENT_SOUNDS)
    center.discard()
    center.close();center.deleteLater();QTest.qWait(5)
    reopened=SettingsCenter(surface.config,surface.storage);reopened._select_page(2);reopened._show_tab(2)
    assert all(reopened._sound_rows[e].path_field.value()==e+'-custom.wav' for e in EVENT_SOUNDS)
    monkeypatch.setattr('fluent_ui.components.dialogs.confirm',lambda *_a,**_kw:True)
    reopened._restore_page_defaults();assert all(reopened.pending.get(e+'_sound_enabled') is False for e in EVENT_SOUNDS)
    reopened.discard();reopened.close();reopened.deleteLater()
