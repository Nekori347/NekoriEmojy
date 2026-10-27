import json,os,subprocess,sys,time
from pathlib import Path
from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest
from services.config import ConfigService
from services.storage import StorageService
from services.resource_import import ImportTarget
from services.task_recovery import ImportCheckpoint
from services.ocr_service import OcrService


@pytest.fixture
def setup(tmp_path):
    app=QApplication.instance() or QApplication([])
    root=tmp_path/'fault-library';root.mkdir()
    config=ConfigService(root/'app');config.config['ocr_auto']=False
    storage=StorageService(root/'library',config)
    sources=[]
    for i,color in enumerate(['red','green','blue']):
        p=root/f'{i}.png';Image.new('RGB',(32,32),color).save(p);sources.append(str(p))
    (root/'sources.json').write_text(json.dumps(sources))
    return app,root,storage,sources


def kill_at(root,mode):
    marker=root/'reached';marker.unlink(missing_ok=True)
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
    with (root/'child.log').open('w') as log:
        process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('recovery_process.py')),str(root),mode],
                                 env=env,stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+30
            while not marker.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.03)
            assert marker.exists(),(root/'child.log').read_text(errors='replace')
        finally:
            if process.poll() is None:process.kill()
            process.wait(timeout=10)


def run_remaining(storage,sources):
    from fluent_ui.views.gallery_view import ImportThread
    worker=ImportThread(sources,storage,'__library__');worker.job_id='import-test'
    worker.recovery=ImportCheckpoint(storage,'import-test');worker.recovery.resuming=True
    decisions=[]
    def choose(items):decisions.append(items);return ['reuse']*len(items)
    worker.duplicate_batch_resolver=choose;worker.run()
    return worker,decisions


@pytest.mark.parametrize('boundary',['import-before','import-after'])
def test_import_kill_and_recover_without_duplicate_or_automatic_work(setup,boundary):
    app,root,storage,sources=setup;kill_at(root,boundary)
    storage=StorageService(root/'library',storage.config)
    from fluent_ui.components.import_queue import ImportQueue
    queue=ImportQueue(storage,app);owner=QWidget();queue.restore(owner);QTest.qWait(50)
    assert queue.worker is None and queue.requests['import-test'].state=='interrupted'
    worker,decisions=run_remaining(storage,sources)
    assert not worker.recovery_waiting and not decisions
    assert len(storage.index.resources())==3 and len(set(worker.result_paths))==3
    assert all(Path(p).is_file() for p in worker.result_paths)
    worker.recovery.forget();assert not ImportCheckpoint.discover(storage.index)
    queue.shutdown();queue.ocr.close();owner.deleteLater()


def test_directory_manifest_missing_source_and_new_files(setup):
    _,root,storage,sources=setup
    folder=root/'folder';folder.mkdir();nested=folder/'child';nested.mkdir()
    Path(sources[0]).rename(nested/'one.png')
    (root/'sources.json').write_text(json.dumps([str(folder)]))
    kill_at(root,'import-after')
    storage=StorageService(root/'library',storage.config)
    # The committed file and both directory identities survive. New files are
    # not retroactively added to this task's frozen source list.
    Image.new('RGB',(32,32),'yellow').save(folder/'later.png')
    worker,_=run_remaining(storage,[str(folder)])
    assert not worker.recovery_waiting
    assert len(storage.index.resources())==1 and len(storage.index.nodes())==2
    assert len(storage.index.content(next(n['id'] for n in storage.index.nodes() if n['name']=='child')))==1


def wait(app,predicate):
    for _ in range(500):
        app.processEvents();time.sleep(.01)
        if predicate():return
    raise AssertionError('worker did not finish')


@pytest.mark.parametrize('boundary',['ocr-before','ocr-after'])
def test_ocr_kill_resume_preserves_committed_and_manual_results(setup,boundary):
    app,root,storage,sources=setup
    ids=[storage.index.resource(storage.save_file(p)[0])['id'] for p in sources]
    kill_at(root,boundary);storage=StorageService(root/'library',storage.config)
    calls=[]
    class Process:
        def recognize(self,path,*_):calls.append(path);return dict(text='resumed',raw_text='resumed')
        def close(self):pass
    service=OcrService(storage,process=Process())
    assert service.jobs['ocr-test']['state']=='interrupted' and not service.busy
    first=storage.index.resources()[0]['id']
    if boundary=='ocr-before':storage.index.edit_ocr_text(first,'user correction')
    service.resume('ocr-test');wait(app,lambda:not service.busy)
    assert len(calls)==2
    assert storage.index.ocr_info(first)['text']==('recognized' if boundary=='ocr-after' else 'user correction')
    assert service.jobs['ocr-test']['state']=='completed' and not service._items('ocr-test')
    service.close()


def test_missing_and_changed_sources_keep_checkpoint_and_abandon_keeps_data(setup):
    app,root,storage,sources=setup
    job=ImportCheckpoint(storage,'import-test');job.create(sources,ImportTarget(),None,False);job.prepare()
    p=Path(sources[0]);p.rename(root/'disconnected.png')
    worker,_=run_remaining(storage,sources)
    assert worker.recovery_waiting and ImportCheckpoint.discover(storage.index)
    (root/'disconnected.png').rename(p)
    worker,_=run_remaining(storage,sources)
    assert not worker.recovery_waiting and len(storage.index.resources())==3
    from fluent_ui.components.import_queue import ImportQueue
    queue=ImportQueue(storage,app);owner=QWidget();queue.restore(owner)
    queue.abandon('import-test');assert not ImportCheckpoint.discover(storage.index)
    assert len(storage.index.resources())==3
    queue.shutdown();queue.ocr.close();owner.deleteLater()


def test_keep_both_crash_is_not_replayed_and_abandon_is_metadata_only(setup):
    app,root,storage,sources=setup
    saved=storage.save_file(sources[0])[0]
    (root/'sources.json').write_text(json.dumps([sources[0]]))
    kill_at(root,'import-keep');storage=StorageService(root/'library',storage.config)
    from fluent_ui.components.import_queue import ImportQueue
    queue=ImportQueue(storage,app);owner=QWidget();queue.restore(owner)
    assert queue.recovery_block_reason('import-test')
    worker,_=run_remaining(storage,[sources[0]])
    assert worker.recovery_waiting and len(storage.index.resources())==1
    queue.abandon('import-test');assert Path(saved).is_file()
    queue.shutdown();queue.ocr.close();owner.deleteLater()


def test_duplicate_reuse_preserves_other_memberships_and_live_anchor(setup):
    _,root,storage,sources=setup
    a=storage.create_node('A');b=storage.create_node('B')
    old=storage.save_file(sources[0],target=ImportTarget(a))[0]
    rid=storage.index.resource(old)['id'];storage.index.add_membership(rid,b)
    anchor=storage.save_file(sources[2],target=ImportTarget(b))[0]
    anchor_id=storage.index.resource(anchor)['id']
    job=ImportCheckpoint(storage,'import-test')
    job.create([sources[0],sources[1]],ImportTarget(b,0),('resource',anchor_id),False)
    worker,decisions=run_remaining(storage,[sources[0],sources[1]])
    assert len(decisions)==1 and not worker.recovery_waiting
    assert any(e['id']==rid for e in storage.index.content(a))
    content=storage.index.content(b)
    assert sum(e['id']==rid for e in content)==1 and content[-1]['id']==anchor_id
    assert len(storage.index.resources())==3


def test_changed_source_and_explicit_cancel_are_not_silently_recovered(setup):
    app,root,storage,sources=setup
    job=ImportCheckpoint(storage,'import-test');job.create(sources,ImportTarget(),None,False);job.prepare()
    Image.new('RGB',(40,40),'yellow').save(sources[0])
    worker,_=run_remaining(storage,sources)
    assert worker.recovery_waiting and not storage.index.resources()
    from fluent_ui.components.import_queue import ImportQueue
    queue=ImportQueue(storage,app);owner=QWidget();queue.restore(owner);queue.cancel('import-test')
    assert not ImportCheckpoint.discover(storage.index)
    assert all(Path(p).exists() for p in sources)
    queue.shutdown();queue.ocr.close();owner.deleteLater()


def test_recovery_dialog_not_now_continue_and_stable_feedback_identity(surface):
    from PySide6.QtWidgets import QPushButton
    from test_phase2_interaction import settle
    g=surface.g;job=ImportCheckpoint(surface.storage,'dialog-test')
    job.create([surface.paths[0]],ImportTarget(),None,False)
    g.imports.restore(g);g._sync_background_tasks()
    g.ocr.jobs['past-ocr']=dict(id='past-ocr',state='completed',total=1,done=1)
    g._sync_background_tasks();assert 'past-ocr' not in g.feedback_host.named_tasks
    assert g.imports.worker is None
    assert g.feedback_host.named_tasks['dialog-test']['state']=='interrupted'
    g._recovery_options('dialog-test','import')
    dialog=g._recovery_dialog
    assert not dialog.isModal()
    next(b for b in dialog.findChildren(QPushButton) if b.text()=='暂不继续').click()
    assert ImportCheckpoint.discover(surface.storage.index)
    g._recovery_options('dialog-test','import')
    next(b for b in g._recovery_dialog.findChildren(QPushButton) if b.text()=='继续任务').click()
    for _ in range(500):
        settle(surface.app);time.sleep(.01)
        if g.imports._dialogs:
            next(iter(g.imports._dialogs.values())).apply_all.setChecked(True)
            next(iter(g.imports._dialogs.values())).select('reuse')
        if g.imports.requests['dialog-test'].state=='completed':break
    assert g.imports.requests['dialog-test'].state=='completed'
    g._sync_background_tasks()
    assert g.feedback_host.named_tasks['dialog-test']['state']=='success'
    assert not ImportCheckpoint.discover(surface.storage.index)


def test_ocr_source_unavailable_waits_then_resumes(setup):
    app,root,storage,sources=setup
    rid=storage.index.resource(storage.save_file(sources[0])[0])['id']
    class Process:
        def recognize(self,*_):return dict(text='restored',raw_text='restored')
        def close(self):pass
    service=OcrService(storage,process=Process())
    from services.ocr_data import OCR_VERSION
    folder=service.component.root;folder.mkdir(parents=True,exist_ok=True)
    (folder/'nekori-ocr.json').write_text(json.dumps(dict(protocol=1,version=OCR_VERSION)))
    for name in ['python.exe','worker.py','python312._pth']:(folder/name).write_text('test')
    path=Path(storage.index.absolute_path(storage.index.resource_by_id(rid)))
    hidden=path.with_suffix('.unavailable');path.rename(hidden)
    service.enqueue([rid],job_id='source-test');wait(app,lambda:service.jobs['source-test']['state']=='waiting_source')
    wait(app,lambda:not service.busy)
    assert service._items('source-test') and service.jobs['source-test']['failed']==0
    hidden.rename(path);service.resume('source-test');wait(app,lambda:not service.busy)
    assert storage.index.ocr_info(rid)['text']=='restored'
    service.close()


@pytest.mark.parametrize('remove_anchor',[False,True])
def test_recovery_preserves_user_order_and_resolves_anchor_or_appends(setup,remove_anchor):
    _,root,storage,sources=setup;node=storage.create_node('Target')
    anchor=storage.index.resource(storage.save_file(sources[2],target=ImportTarget(node))[0])['id']
    extra=root/'extra.png';Image.new('RGB',(32,32),'black').save(extra)
    other=storage.index.resource(storage.save_file(str(extra),target=ImportTarget(node))[0])['id']
    job=ImportCheckpoint(storage,'import-test')
    job.create(sources[:2],ImportTarget(node,0),('resource',anchor),False)
    units=job.prepare();storage.import_context.checkpoint=('import-test',units[0]['id'])
    first=storage.index.resource(storage.save_file(sources[0],target=job.target(units[0]))[0])['id']
    storage.import_context.checkpoint=None
    storage.index.set_order(node,[('resource',anchor),('resource',first),('resource',other)])
    if remove_anchor:storage.index.remove_membership(anchor,node)
    before=[e['id'] for e in storage.index.content(node)]
    worker,_=run_remaining(storage,sources[:2]);assert not worker.recovery_waiting
    after=[e['id'] for e in storage.index.content(node)]
    new=next(r for r in after if r not in before)
    assert [r for r in after if r!=new]==before
    assert after[-1]==new if remove_anchor else after.index(new)+1==after.index(anchor)


def test_delete_after_keeps_existing_live_directory_contract_and_blocks_replay(setup):
    app,root,storage,sources=setup
    folder=root/'incoming';folder.mkdir();inside=folder/'one.png';Path(sources[0]).rename(inside)
    from fluent_ui.components.import_queue import ImportQueue
    queue=ImportQueue(storage,app);owner=QWidget()
    rid=queue.submit([str(folder),sources[1]],ImportTarget(),owner,delete_after=True)
    wait(app,lambda:queue.requests[rid].state in {'completed','failed'})
    assert queue.requests[rid].state=='completed'
    assert inside.is_file() and not Path(sources[1]).exists()
    job=ImportCheckpoint(storage,'delete-test');job.create([str(folder)],ImportTarget(),None,True)
    queue.restore(owner);assert queue.recovery_block_reason('delete-test')
    with pytest.raises(RuntimeError):queue.resume('delete-test')
    queue.abandon('delete-test');queue.shutdown();queue.ocr.close();owner.deleteLater()


# Reuse the existing real gallery fixture for the small UI acceptance above.
from test_phase2_interaction import surface
