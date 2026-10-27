"""Disposable fault-injection process; never points at the persistent Demo."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from services.config import ConfigService
from services.storage import StorageService
from services.task_recovery import ImportCheckpoint
from services.resource_import import ImportTarget

root=Path(sys.argv[1]);mode=sys.argv[2]
assert root.name.startswith('fault-')
app=QApplication([]);config=ConfigService(root/'app');config.config['ocr_auto']=False
storage=StorageService(root/'library',config=config)
def stop():
    (root/'reached').write_text(mode)
    while True:time.sleep(.1)
if mode.startswith('import'):
    from fluent_ui.views.gallery_view import ImportThread
    sources=json.loads((root/'sources.json').read_text())
    job=ImportCheckpoint(storage,'import-test');job.create(sources,ImportTarget(),None,False)
    original=storage.importer._accept
    def accept(*a,**kw):
        if mode in {'import-before','import-keep'}:stop()
        result=original(*a,**kw);stop();return result
    storage.importer._accept=accept
    worker=ImportThread(sources,storage,'__library__');worker.job_id='import-test';worker.recovery=job
    worker.duplicate_batch_resolver=lambda items:['keep' if mode=='import-keep' else 'reuse']*len(items)
    worker.run()
else:
    from services.ocr_service import OcrService
    from services.ocr_data import OCR_VERSION
    class Process:
        def recognize(self,*_):return dict(text='recognized',raw_text='recognized')
        def close(self):pass
    service=OcrService(storage,process=Process())
    component=service.component.root;component.mkdir(parents=True,exist_ok=True)
    (component/'nekori-ocr.json').write_text(json.dumps(dict(protocol=1,version=OCR_VERSION)))
    for n in ['python.exe','worker.py','python312._pth']:(component/n).write_text('test')
    original=storage.index.commit_ocr
    def commit(*a,**kw):
        if mode=='ocr-before':stop()
        result=original(*a,**kw);stop();return result
    storage.index.commit_ocr=commit
    service.enqueue([r['id'] for r in storage.index.resources()],job_id='ocr-test',force=True)
    while True:time.sleep(.1)
