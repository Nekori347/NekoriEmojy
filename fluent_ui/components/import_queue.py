"""A serial desktop import queue around the existing ImportThread/ResourceImporter."""
from collections import deque
from dataclasses import dataclass,field
import threading,uuid
from PySide6.QtCore import QObject,Signal,QTimer,QThread,QEvent
from PySide6.QtWidgets import QApplication
from services.resource_import import ImportTarget
from services.ocr_service import ocr_service
from services.i18n import t


@dataclass
class ImportRequest:
    sources:list
    target:ImportTarget
    owner:object
    delete_after:bool=False
    id:str=field(default_factory=lambda:uuid.uuid4().hex)
    state:str='waiting'
    done:int=0
    total:int=0
    saved:int=0
    duplicates:int=0
    kept:int=0
    conflicts:int=0
    phase:str=''
    skipped:int=0
    failed:int=0
    paths:list=field(default_factory=list)
    errors:list=field(default_factory=list)
    operation:object=None
    result:object=None
    before:tuple|None=None
    kind:str='import'
    background:bool=False


class ImportQueue(QObject):
    changed=Signal(str)
    files_finished=Signal(object)
    duplicate_requested=Signal(object)
    batch_requested=Signal(object)

    def __init__(self,storage,parent):
        super().__init__(parent);self.storage=storage;self.requests={};self.waiting=deque();self.worker=None
        self.current=None;self._closing=False;self._decisions={};self._dialogs={}
        self._pending_batches={}
        self.duplicate_requested.connect(self._show_duplicate)
        self.batch_requested.connect(self._show_batch)
        self.ocr=ocr_service(storage);self.ocr.changed.connect(self._ocr_changed)
        parent.aboutToQuit.connect(self.shutdown)

    def submit(self,sources,target,owner,*,delete_after=False,operation=None,kind='import',background=False):
        request=ImportRequest(list(sources),target,owner,delete_after);request.total=len(request.sources)
        request.operation=operation
        request.kind=kind
        request.background=background
        if background:owner.window().installEventFilter(self)
        if target.insert_position is not None:
            entries=self.storage.index.content(target.parent_node)
            if 0<=target.insert_position<len(entries):
                anchor=entries[target.insert_position];request.before=(anchor['kind'],anchor['id'])
        self.requests[request.id]=request;self.waiting.append(request.id);self.changed.emit(request.id)
        QTimer.singleShot(0,self._next);return request.id

    def _next(self):
        if self.worker or self._closing:return
        while self.waiting:
            request=self.requests[self.waiting.popleft()]
            if request.state=='cancelled':continue
            from fluent_ui.views.gallery_view import ImportThread
            request.state='running';self.current=request.id
            position=None
            if request.before is not None:
                position=next((i for i,e in enumerate(self.storage.index.content(request.target.parent_node))
                               if (e['kind'],e['id'])==request.before),None)
            worker=self.worker=ImportThread(request.sources,self.storage,request.target.parent_node,
                delete_after=request.delete_after,insert_position=position,parent=self)
            worker.job_id=request.id;worker.duplicate_resolver=lambda old,new:self._ask_duplicate(request,old,new)
            worker.duplicate_batch_resolver=lambda candidates:self._ask_batch(request,candidates)
            worker.operation=request.operation
            worker.progress.connect(lambda done,total,r=request:self._progress(r,done,total))
            worker.stage.connect(lambda message,r=request:self._stage(r,message))
            worker.finished.connect(self._finished);self.changed.emit(request.id);worker.start(QThread.LowPriority);return

    def _progress(self,request,done,total):
        request.done=done;request.total=total;self.changed.emit(request.id)

    def _stage(self,request,message):
        request.phase=message;self.changed.emit(request.id)

    def _finished(self,saved,duplicates,failed):
        worker=self.worker
        if worker is None:return
        worker.wait();request=self.requests[self.current]
        request.saved=saved;request.duplicates=duplicates;request.failed=failed
        request.kept=worker.kept_count
        request.paths=list(dict.fromkeys(worker.result_paths));request.errors=list(worker.errors)
        request.result=worker.result
        request.skipped=worker.cancelled_count
        terminal='cancelled' if worker.cancel_event.is_set() else 'failed' if failed and not (saved or duplicates) else 'completed'
        request.state='finalizing';self.changed.emit(request.id)
        self.files_finished.emit(request)
        request.state=terminal
        if request.paths and self.ocr.available and self.storage.config.get('ocr_auto',False) and request.state!='cancelled':
            request.state='recognizing'
            ids=[r['id'] for path in request.paths if (r:=self.storage.index.resource(path))]
            self.ocr.enqueue(ids,automatic=True,job_id=request.id,origin='import')
        if request.state=='completed':request.done=request.total
        self.worker=None;self.current=None;worker.deleteLater()
        self.changed.emit(request.id);QTimer.singleShot(0,self._next)

    def _ocr_changed(self):
        for rid,request in tuple(self.requests.items()):
            if request.state!='recognizing':continue
            job=self.ocr.jobs.get(rid)
            if job and job['state']!='running':
                request.state='completed' if job['state']=='completed' else 'cancelled'
                if request.state=='completed':request.done=request.total
            self.changed.emit(rid)

    def cancel(self,rid):
        request=self.requests.get(rid)
        if not request:return
        request.state='cancelled'
        if self.current==rid and self.worker:self.worker.cancel()
        self.ocr.cancel(job_id=rid)
        for key,(job,event,choice) in list(self._decisions.items()):
            if job==rid:
                choice[0]='skip';event.set()
                if key in self._dialogs:self._dialogs[key].reject()
                self._pending_batches.pop(key,None)
        self.changed.emit(rid)

    def _ask_duplicate(self,request,old,new):
        event=threading.Event();choice=['skip'];key=uuid.uuid4().hex
        self._decisions[key]=(request.id,event,choice)
        self.duplicate_requested.emit((key,request,old,new))
        while not event.wait(.05):
            if self._closing or (self.worker and self.worker.cancel_event.is_set()):break
        self._decisions.pop(key,None);return choice[0]

    def _show_duplicate(self,payload):
        key,request,old,new=payload
        if key not in self._decisions or request.state=='cancelled':return
        from fluent_ui.components.duplicate_dialog import DuplicateDialog
        def decide(choice):
            item=self._decisions.get(key)
            if item:item[2][0]=choice;item[1].set()
            self._dialogs.pop(key,None)
        dialog=DuplicateDialog(request.owner.window(),old,new,decide)
        self._dialogs[key]=dialog;dialog.show()

    def _ask_batch(self,request,candidates):
        event=threading.Event();choice=[None];key=uuid.uuid4().hex
        self._decisions[key]=(request.id,event,choice)
        self.batch_requested.emit((key,request,candidates))
        while not event.wait(.05):
            if self._closing or self.worker.cancel_event.is_set():break
        self._decisions.pop(key,None)
        return choice[0] if isinstance(choice[0],list) else ['skip']*len(candidates)

    def _show_batch(self,payload):
        key,request,candidates=payload
        if key not in self._decisions or request.state=='cancelled':return
        from fluent_ui.components.duplicate_dialog import DuplicateBatchDialog
        request.state='decision';request.conflicts=len(candidates);self.changed.emit(request.id)
        request.saved,request.duplicates,request.failed=self.worker.staged_counts
        request.paths=list(dict.fromkeys(self.worker.result_paths))
        self.files_finished.emit(request)
        def decide(choices):
            item=self._decisions.get(key)
            if item:item[2][0]=choices;item[1].set()
            if request.state!='cancelled':request.state='running';self.changed.emit(request.id)
            self._dialogs.pop(key,None)
        def show():
            dialog=DuplicateBatchDialog(request.owner.window(),candidates,self.storage,decide)
            self._dialogs[key]=dialog;dialog.show()
        owner=request.owner.window()
        if request.background and not (owner.isVisible() and not owner.isMinimized() and owner.isActiveWindow()):
            self._pending_batches[key]=(request,show)
        else:show()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.WindowActivate:
            for key,(request,show) in tuple(self._pending_batches.items()):
                if request.owner.window() is watched:
                    self._pending_batches.pop(key,None)
                    if key in self._decisions and request.state=='decision':show()
        return False

    def shutdown(self):
        self._closing=True
        self._pending_batches.clear()
        if self.worker:self.worker.cancel()
        for _,event,choice in tuple(self._decisions.values()):choice[0]='skip';event.set()
        for dialog in tuple(self._dialogs.values()):dialog.reject()
        if self.worker:self.worker.wait()


def import_queue(storage):
    if not hasattr(storage,'desktop_imports'):storage.desktop_imports=ImportQueue(storage,QApplication.instance())
    return storage.desktop_imports
