import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest
from services.config import ConfigService
from services.storage import StorageService
from services.resource_import import ImportTarget
from fluent_ui.views.gallery_view import ImportThread


def image(path,color):
    path.parent.mkdir(parents=True,exist_ok=True)
    Image.new('RGB',(40,30),color).save(path)
    return str(path)


def test_batch_defers_duplicates_keeps_normal_work_and_real_memberships(tmp_path):
    app=QApplication.instance() or QApplication([])
    storage=StorageService(tmp_path/'library',config=ConfigService(tmp_path/'app'))
    old=storage.save_file(image(tmp_path/'old.png','red'))[0]
    node=storage.create_node('Target')
    sources=[image(tmp_path/'alias.png','red'),image(tmp_path/'normal.png','blue'),
             image(tmp_path/'same-name'/'old.png','green'),image(tmp_path/'again.png','red'),
             image(tmp_path/'skip.png','red'),str(tmp_path/'missing.png')]
    worker=ImportThread(sources,storage,node)
    batches=[];results=[]
    def choose(candidates):
        batches.append(candidates)
        # No decision interrupted the ordinary blue/green imports.
        assert len(storage.index.resources())==3
        assert len(storage.index.content(node))==2
        return ['keep','reuse','skip']
    worker.duplicate_batch_resolver=choose
    worker.finished.connect(lambda *r:results.append(r))
    worker.run();app.processEvents()
    assert len(batches)==1 and len(batches[0])==3
    assert results==[(3,1,1)] and worker.kept_count==1 and worker.cancelled_count==1
    assert len(storage.index.resources())==4
    members=[e['id'] for e in storage.index.content(node)]
    assert storage._resource_id(old) in members and len(members)==4
    # Reusing again in the same category doesn't duplicate membership.
    worker=ImportThread([sources[0]],storage,node)
    worker.duplicate_batch_resolver=lambda candidates:['reuse']
    worker.run();assert len(storage.index.content(node))==4


def test_batch_dialog_individual_and_all_choices(tmp_path):
    from services.resource_import import DuplicateCandidate
    from fluent_ui.components.duplicate_dialog import DuplicateBatchDialog
    app=QApplication.instance() or QApplication([])
    storage=StorageService(tmp_path/'library',config=ConfigService(tmp_path/'app'))
    path=storage.save_file(image(tmp_path/'old.png','red'))[0]
    incoming=image(tmp_path/'incoming.png','red')
    candidates=[DuplicateCandidate(path,incoming,ImportTarget()) for _ in range(3)]
    owner=QWidget();choices=[]
    dialog=DuplicateBatchDialog(owner,candidates,storage,choices.append)
    dialog.select('reuse');assert dialog.choices==['reuse']
    dialog.apply_all.setChecked(True);dialog.select('keep')
    assert choices==[['reuse','keep','keep']]
    assert all(p.image is None for p in dialog.previews)
    dialog.deleteLater();owner.deleteLater();app.processEvents()


def test_queue_one_waiting_batch_then_cancel_keeps_completed_imports(tmp_path,monkeypatch):
    from fluent_ui.components.import_queue import ImportQueue
    from fluent_ui.components.duplicate_dialog import DuplicateBatchDialog
    app=QApplication.instance() or QApplication([])
    config=ConfigService(tmp_path/'app');config.config['ocr_auto']=False
    storage=StorageService(tmp_path/'library',config=config)
    storage.save_file(image(tmp_path/'old.png','red'))
    node=storage.create_node('Target');owner=QWidget();queue=ImportQueue(storage,app)
    monkeypatch.setattr(queue,'_show_duplicate',lambda *_:None)
    shown=[]
    original=DuplicateBatchDialog.show
    def show(dialog):
        shown.append(dialog);original(dialog)
    monkeypatch.setattr(DuplicateBatchDialog,'show',show)
    rid=queue.submit([image(tmp_path/'copy.png','red'),image(tmp_path/'new.png','blue')],ImportTarget(node),owner)
    for _ in range(500):
        QTest.qWait(10)
        if shown:break
    assert len(shown)==1 and queue.requests[rid].state=='decision'
    assert len(storage.index.content(node))==1
    queue.cancel(rid)
    for _ in range(500):
        QTest.qWait(10)
        if queue.worker is None:break
    assert queue.worker is None and queue.requests[rid].state=='cancelled'
    assert len(storage.index.content(node))==1
    queue.shutdown();owner.deleteLater();queue.deleteLater();app.processEvents()
