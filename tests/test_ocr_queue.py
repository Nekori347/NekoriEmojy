import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import threading
import time
from collections import Counter
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication
import pytest
from services.config import ConfigService
from services.storage import StorageService
from services.ocr_service import OcrService
from services.ocr_data import OCR_VERSION
from services.nekori_package import NekoriPackageService


@pytest.fixture
def app():return QApplication.instance() or QApplication([])


def wait(app,predicate):
    end=time.monotonic()+6
    while time.monotonic()<end:
        app.processEvents()
        if predicate():return
        time.sleep(.01)
    raise AssertionError('OCR queue did not settle')


class Worker:
    def __init__(self):
        self.calls=Counter();self.block_on=None;self.started=threading.Event();self.release=threading.Event()
    def recognize(self,path,thumbnail=0):
        self.calls[path]+=1
        if path==self.block_on:
            self.started.set();self.release.wait(5)
        return dict(text='不要放棄',raw_text='不要放棄')
    def close(self):self.release.set()


@pytest.fixture
def context(tmp_path,app):
    storage=StorageService(tmp_path/'library',ConfigService(tmp_path/'app'))
    worker=Worker();service=OcrService(storage,process=worker)
    root=service.component.root;root.mkdir(parents=True)
    (root/'nekori-ocr.json').write_text(json.dumps(dict(protocol=1,version=OCR_VERSION)),encoding='utf-8')
    for name in ['python.exe','worker.py','python312._pth']:(root/name).write_text('test only')
    yield storage,worker,service
    service.close()


def save(storage,tmp_path,name,color):
    path=tmp_path/name;Image.new('RGB',(30,30),color).save(path)
    return storage.save_file(str(path))[0]


def test_auto_import_then_search_skip_and_manual_race(context,tmp_path,app):
    storage,worker,service=context
    storage.config.set('ocr_auto',True)
    path=save(storage,tmp_path,'one.png','red')
    rid=storage.index.resource(path)['id']
    wait(app,lambda:storage.index.ocr_info(rid)['status']=='ready')
    wait(app,lambda:not service.busy)
    assert path in storage.search_images('放弃')
    assert storage.index.resource(rid)['tags']==''
    service.enqueue([rid]);wait(app,lambda:not service.busy)
    assert worker.calls[path]==1
    worker.block_on=path;worker.release.clear()
    service.enqueue([rid],force=True,overwrite=True)
    wait(app,worker.started.is_set)
    service.edit(rid,'楽しい')
    worker.release.set();wait(app,lambda:not service.busy)
    assert storage.index.ocr_info(rid)['text']=='楽しい'
    assert path in storage.search_images('楽しい')


def test_cancel_supplement_resumes_only_unfinished(context,tmp_path,app):
    storage,worker,service=context
    paths=[save(storage,tmp_path,str(i)+'.png',color) for i,color in enumerate(['red','green','blue'])]
    records=storage.index.resources()
    worker.block_on=storage.index.absolute_path(records[1]);worker.release.clear()
    service.supplement()
    wait(app,worker.started.is_set)
    first=storage.index.absolute_path(records[0])
    service.cancel();wait(app,lambda:not service.busy)
    assert service.summary['state']=='cancelled'
    worker.block_on=None
    service.supplement();wait(app,lambda:not service.busy)
    assert worker.calls[first]==1
    assert all(storage.index.ocr_info(r['id'])['status']=='ready' for r in records)
    service.close()
    reopened=OcrService(storage,process=Worker())
    assert reopened.summary['state']=='completed'
    reopened.close()


def test_package_preserves_manual_empty_and_local_edit_wins(context,tmp_path,app):
    storage,worker,service=context
    path=save(storage,tmp_path,'one.png','red');rid=storage.index.resource(path)['id']
    service.edit(rid,'')
    package=tmp_path/'data.nekori'
    NekoriPackageService(storage).export(package)
    other=StorageService(tmp_path/'other',ConfigService(tmp_path/'otherapp'))
    NekoriPackageService(other).import_package(package)
    imported=other.index.resources()[0]
    assert other.index.ocr_info(imported['id'])['manual']
    assert other.index.ocr_info(imported['id'])['status']=='empty'
    other.index.edit_ocr_text(imported['id'],'user newer')
    NekoriPackageService(other).import_package(package)
    assert other.index.ocr_info(imported['id'])['text']=='user newer'


def test_failure_is_persisted_and_retry_only_processes_failed(context,tmp_path,app,monkeypatch):
    storage,worker,service=context
    path=save(storage,tmp_path,'one.png','red');rid=storage.index.resource(path)['id']
    original=worker.recognize
    def fail(*args,**kwargs):raise RuntimeError('test decoding failure')
    monkeypatch.setattr(worker,'recognize',fail)
    service.enqueue([rid]);wait(app,lambda:not service.busy)
    assert storage.index.ocr_info(rid)['status']=='failed'
    assert storage.index.ocr_info(rid)['error']=='test decoding failure'
    monkeypatch.setattr(worker,'recognize',original)
    service.supplement(failed_only=True);wait(app,lambda:not service.busy)
    assert storage.index.ocr_info(rid)['status']=='ready'
    assert worker.calls[path]==1
