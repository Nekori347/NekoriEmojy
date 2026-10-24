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
    resources_committed=Signal(object,object)
    duplicate_requested=Signal(object)
    batch_requested=Signal(object)

    def __init__(self,storage,parent):
        super().__init__(parent);self.storage=storage;self.requests={};self.waiting=deque();self.worker=None
        self.current=None;self._closing=False;self._decisions={};self._dialogs={}
        self._pending_batches={}
        self._committed_paths=set();self._committed_parents=set()
        # Merge commits already queued for this GUI turn. No fixed wait or
        # per-file full refresh: the consumer patches the existing projection.
        self._refresh_timer=QTimer(self);self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._flush_committed)
        self.duplicate_requested.connect(self._show_duplicate)
        self.batch_requested.connect(self._show_batch)
        self.ocr=ocr_service(storage);self.ocr.changed.connect(self._ocr_changed)
        parent.aboutToQuit.connect(self.shutdown)

    def restore(self, owner):
        from services.task_recovery import ImportCheckpoint
        for rid,value in ImportCheckpoint.discover(self.storage.index):
            if rid in self.requests:continue
            request=ImportRequest(value['sources'],ImportTarget(value['parent']),owner,id=rid,state='interrupted')
            request.before=tuple(value['before']) if value.get('before') else None
            request.delete_after=value.get('delete_after',False)
            request.phase=value.get('reason','发现未完成任务，请确认后继续')
            with self.storage.index.connect(search=False) as db:
                import json
                units=[json.loads(r[0]) for r in db.execute(
                    "SELECT payload FROM task_checkpoints WHERE task_id=? AND kind='import' AND unit_id!=''",(rid,))]
            files=[u for u in units if not u['directory']]
            request.total=len(files) if value.get('planned') else len(request.sources)
            request.done=sum(u['state'] in {'done','skipped','failed'} for u in files)
            self.requests[rid]=request
        self.changed.emit('')

    def resume(self,rid):
        request=self.requests[rid]
        if request.state not in {'interrupted','waiting_source'}:return
        reason=self.recovery_block_reason(rid)
        if reason:raise RuntimeError(reason)
        request.state='waiting';request.errors=[];request.paths=[]
        self.waiting.append(rid);self.changed.emit(rid);QTimer.singleShot(0,self._next)

    def recovery_block_reason(self,rid):
        import json
        with self.storage.index.connect(search=False) as db:
            rows=[(r[0],json.loads(r[1])) for r in db.execute(
                "SELECT unit_id,payload FROM task_checkpoints WHERE task_id=? AND kind='import'",(rid,))]
        header=next((value for key,value in rows if not key),{})
        if header.get('unsupported'):return '此任务需要重新提供来源，不能安全重放'
        if header.get('delete_after'):return '删除来源任务需人工核对，不能自动重放'
        if any(value.get('state')=='uncertain' for _,value in rows):
            return '保留两者、替换或删除来源的执行结果需人工核对，不能自动重放'
        return ''

    def abandon(self,rid):
        request=self.requests.get(rid)
        if not request or request.state not in {'interrupted','waiting_source'}:return
        from services.task_recovery import ImportCheckpoint
        ImportCheckpoint(self.storage,rid).forget()
        request.state='cancelled';self.changed.emit(rid)

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
        from services.task_recovery import ImportCheckpoint
        portable=operation is None and all(isinstance(s,str) and not s.startswith(('http://','https://')) for s in request.sources)
        checkpoint=ImportCheckpoint(self.storage,request.id)
        checkpoint.create(request.sources if portable else [],target,request.before,delete_after)
        if not portable:
            with self.storage.index.connect(search=False) as db:
                from services.task_recovery import write_checkpoint
                write_checkpoint(db,(request.id,''),unsupported=True)
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
            from services.task_recovery import ImportCheckpoint
            recovery=ImportCheckpoint(self.storage,request.id)
            with self.storage.index.connect(search=False) as db:
                import json
                row=db.execute("SELECT payload FROM task_checkpoints WHERE task_id=? AND unit_id=''",(request.id,)).fetchone()
            header=json.loads(row[0]) if row else {}
            if header.get('unsupported') and request.phase:
                request.state='interrupted';request.phase='此任务需要重新提供来源，不能安全重放';self.worker=None;self.current=None
                self.changed.emit(request.id);continue
            if header and not header.get('unsupported') and not header.get('delete_after'):
                recovery.resuming=bool(request.phase)
                worker.recovery=recovery
            worker.progress.connect(lambda done,total,r=request:self._progress(r,done,total))
            worker.stage.connect(lambda message,r=request:self._stage(r,message))
            worker.committed.connect(self._committed)
            worker.finished.connect(self._finished);self.changed.emit(request.id);worker.start(QThread.LowPriority);return

    def _progress(self,request,done,total):
        request.done=done;request.total=total;self.changed.emit(request.id)

    def _stage(self,request,message):
        request.phase=message;self.changed.emit(request.id)

    def _committed(self,paths,parents):
        self._committed_paths.update(paths);self._committed_parents.update(parents)
        if not self._refresh_timer.isActive():self._refresh_timer.start(0)

    def _flush_committed(self):
        self._refresh_timer.stop()
        if not self._committed_parents:return
        paths=self._committed_paths;parents=self._committed_parents
        self._committed_paths=set();self._committed_parents=set()
        self.resources_committed.emit(paths,parents)

    def _finished(self,saved,duplicates,failed):
        worker=self.worker
        if worker is None:return
        worker.wait();request=self.requests[self.current]
        self._flush_committed()
        request.saved=saved;request.duplicates=duplicates;request.failed=failed
        request.kept=worker.kept_count
        request.paths=list(dict.fromkeys(worker.result_paths));request.errors=list(worker.errors)
        request.result=worker.result
        request.skipped=worker.cancelled_count
        terminal='cancelled' if worker.cancel_event.is_set() else 'failed' if failed and not (saved or duplicates) else 'completed'
        if worker.recovery_waiting:terminal='waiting_source';request.phase=worker.recovery_waiting
        elif self._closing and worker.cancel_event.is_set():terminal='interrupted'
        request.state='finalizing';self.changed.emit(request.id)
        self.files_finished.emit(request)
        request.state=terminal
        if request.paths and self.ocr.available and self.storage.config.get('ocr_auto',False) and terminal=='completed':
            request.state='recognizing'
            ids=[r['id'] for path in request.paths if (r:=self.storage.index.resource(path))]
            self.ocr.enqueue(ids,automatic=True,job_id=request.id,origin='import')
        if request.state=='completed':request.done=request.total
        if terminal in {'completed','failed','cancelled'}:
            from services.task_recovery import ImportCheckpoint
            ImportCheckpoint(self.storage,request.id).forget()
        self.worker=None;self.current=None;worker.deleteLater()
        self.changed.emit(request.id);QTimer.singleShot(0,self._next)

    def _ocr_changed(self):
        for rid,request in tuple(self.requests.items()):
            if request.state not in {'recognizing','ocr_interrupted'}:continue
            job=self.ocr.jobs.get(rid)
            if job:
                request.state=('recognizing' if job['state']=='running' else 'ocr_interrupted'
                    if job['state'] in {'interrupted','waiting_source'} else 'completed'
                    if job['state']=='completed' else 'cancelled')
                if request.state=='completed':request.done=request.total
            self.changed.emit(rid)

    def cancel(self,rid):
        request=self.requests.get(rid)
        if not request:return
        request.state='cancelled'
        if self.current==rid and self.worker:self.worker.cancel()
        from services.task_recovery import ImportCheckpoint
        ImportCheckpoint(self.storage,rid).forget()
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
