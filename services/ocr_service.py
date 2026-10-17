"""A single, cancelable library OCR queue. Existing storage remains authoritative."""
from collections import deque
import json
from pathlib import Path
import threading
import time
from PySide6.QtCore import QObject,Signal
from services.ocr_component import OcrComponent,OcrProcess
from services.ocr_data import OCR_VERSION,source_stamp


class OcrService(QObject):
    changed=Signal()
    text_changed=Signal(str)
    imported=Signal(str)
    component_finished=Signal(bool,str)

    def __init__(self,storage,parent=None,process=None):
        super().__init__(parent)
        self.storage=storage
        self.config=storage.config
        self.component=OcrComponent(self.config.base_dir)
        self.process=process or OcrProcess(self.component)
        self._condition=threading.Condition()
        self._queue=deque();self._pending=set()
        self._thread=None;self._closing=False;self._generation=0;self._busy=False
        self._install_thread=None;self._install_busy=False;self._install_cancel=threading.Event()
        self.install_state='';self.install_error='';self.download=(0,0)
        self.summary=json.loads(storage.index.meta('ocr_task_summary','{}'))
        if self.summary.get('state')=='running':
            self.summary['state']='interrupted';self._save_summary()
        self.imported.connect(self._auto_enqueue)
        self._import_callback=self.imported.emit
        storage.import_listeners.append(self._import_callback)
        self.component_finished.connect(self._on_component_finished)

    @property
    def available(self):return self.component.installed and not self.installing

    @property
    def installing(self):return self._install_busy

    @property
    def busy(self):return self._busy or bool(self._queue)

    def _save_summary(self):
        self.storage.index.set_meta('ocr_task_summary',json.dumps(self.summary,ensure_ascii=False))

    def _auto_enqueue(self,rid):
        if not self._closing and self.config.get('ocr_auto',False) and self.available:
            self.enqueue([rid],automatic=True)

    def enqueue(self,resource_ids,*,force=False,overwrite=False,automatic=False):
        if self._closing:return
        if not self.available:raise RuntimeError('请先安装 OCR 组件')
        with self._condition:
            if not self.busy:
                self.summary=dict(state='running',done=0,total=0,failed=0,skipped=0,error='')
            for rid in dict.fromkeys(resource_ids):
                if rid in self._pending:continue
                self._pending.add(rid)
                self._queue.append((rid,force,overwrite,automatic,self._generation))
                self.summary['total']=self.summary.get('total',0)+1
            self._save_summary()
            self._ensure_thread()
            self._condition.notify_all()
        self.changed.emit()

    def supplement(self,failed_only=False):
        """Resolve the library on the worker, not thousands of stats on the GUI."""
        self.enqueue(['__failed__' if failed_only else '__scan__'])

    def _ensure_thread(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread=threading.Thread(target=self._run,name='NekoriOCR',daemon=True)
            self._thread.start()

    def _run(self):
        while not self._closing:
            with self._condition:
                if not self._queue:
                    self._busy=False
                    if self.summary.get('state')=='running':
                        self.summary['state']='completed';self._save_summary();self.changed.emit()
                    self._condition.wait(timeout=30)
                    if not self._queue:
                        self.process.close()
                        continue
                if self._closing:break
                rid,force,overwrite,automatic,generation=self._queue.popleft()
                self._pending.discard(rid);self._busy=True
            if rid in {'__scan__','__failed__'}:
                records=self.storage.index.resources()
                ids=[r['id'] for r in records if rid!='__failed__' or self.storage.index._ocr_state(r)['status']=='failed']
                with self._condition:
                    if generation!=self._generation:continue
                    self.summary['total']-=1
                    for key in ids:
                        if key not in self._pending:
                            self._pending.add(key);self._queue.append((key,False,False,False,generation))
                            self.summary['total']+=1
                    self._save_summary()
                self.changed.emit();continue
            outcome='skipped';error='';state=None;stamp=None
            try:
                if generation!=self._generation:continue
                if automatic and not self.config.get('ocr_auto',False):continue
                record=self.storage.index.resource_by_id(rid)
                if not record:continue
                state=self.storage.index._ocr_state(record)
                if state.get('manual') and not overwrite:continue
                stamp=source_stamp(self.storage.index,record)
                if not force and state['status'] in {'ready','empty'} and state.get('source')==stamp and state.get('version')==OCR_VERSION:
                    continue
                result=self.process.recognize(self.storage.index.absolute_path(record),stamp['thumbnail'])
                if generation!=self._generation:continue
                current=self.storage.index.resource_by_id(rid)
                if not current or source_stamp(self.storage.index,current)!=stamp:continue
                if self.storage.index.commit_ocr(rid,result,revision=state['revision'],source=stamp,
                                               version=OCR_VERSION,overwrite=overwrite):
                    outcome='done';self.text_changed.emit(rid)
            except Exception as exc:
                if generation!=self._generation or self._closing:continue
                outcome='failed';error=str(exc)
                if state is not None:
                    self.storage.index.commit_ocr(rid,{},revision=state['revision'],source=stamp,
                        version=OCR_VERSION,overwrite=overwrite,error=error)
                self.process.close()
            finally:
                with self._condition:
                    if generation==self._generation:
                        self.summary[outcome]=self.summary.get(outcome,0)+1
                        if error:self.summary['error']=error
                        self._save_summary()
                self.changed.emit()
        self.process.close()

    def edit(self,rid,text):
        self.storage.index.edit_ocr_text(rid,text)
        self.text_changed.emit(rid);self.changed.emit()

    def cancel(self,state='cancelled'):
        with self._condition:
            was_busy=self.busy
            self._generation+=1;self._queue.clear();self._pending.clear()
            if was_busy:self.summary['state']=state
            elif not self.summary:self.summary['state']='idle'
            self._save_summary();self._condition.notify_all()
        self.process.close();self.changed.emit()

    def install(self,source=None):
        if self.installing:return
        self.cancel()
        self._install_cancel.clear();self.install_error='';self.install_state='installing';self._install_busy=True
        def progress(state,done,total):
            self.install_state=state;self.download=(done,total);self.changed.emit()
        def run():
            try:
                self.component.install(source,progress,self._install_cancel)
                self.install_state='installed';self._install_busy=False;self.component_finished.emit(True,'')
            except InterruptedError:
                self.install_state='cancelled';self.install_error='';self._install_busy=False
                self.component_finished.emit(False,'')
            except Exception as exc:
                self.install_state='failed';self.install_error=str(exc);self._install_busy=False
                self.component_finished.emit(False,str(exc))
        self._install_thread=threading.Thread(target=run,name='NekoriOCRInstall',daemon=True)
        self._install_thread.start();self.changed.emit()

    def _on_component_finished(self,ok,error):
        if ok:self.config.set('ocr_auto',True)
        self.changed.emit()

    def uninstall(self):
        self.cancel()
        self.component.uninstall()
        self.config.set('ocr_auto',False)
        self.install_state='';self.changed.emit()

    def close(self):
        self._closing=True;self._install_cancel.set()
        if self._import_callback in self.storage.import_listeners:
            self.storage.import_listeners.remove(self._import_callback)
        self.cancel('interrupted' if self.busy else self.summary.get('state','idle'))
        if self._thread:self._thread.join(timeout=4)
        if self._install_thread:self._install_thread.join(timeout=2)


def ocr_service(storage):
    service=getattr(storage,'ocr',None)
    if service is None:
        from PySide6.QtCore import QCoreApplication
        app=QCoreApplication.instance()
        storage.ocr=service=OcrService(storage,app)
        if app:app.aboutToQuit.connect(service.close)
    return service
