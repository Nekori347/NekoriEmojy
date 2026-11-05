"""Qt coordinator: scheduling/pressure/state only; all Library I/O is a worker."""
import hashlib
import json
import os
import sys
import time
import uuid
import weakref
from datetime import datetime,timezone
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QTimer,QProcess,QProcessEnvironment,QEvent
from PySide6.QtWidgets import QApplication,QWidget
from services.backup_activity import activity_for
from services.library_backup import atomic_json,output_directory,CONFIG_KEYS,utc_now

STATUS_TEXT={'never':'尚未备份','waiting':'等待开始','running':'正在备份',
             'paused':'因前台繁忙暂缓','success':'备份成功','failed':'备份失败'}
PHASE_TEXT={'inventory':'正在核对文件清单','archive':'正在保存备份','verify':'正在校验完整备份','restore':'正在恢复到新表情库'}
SETTINGS_KEYS={'backup_enabled','backup_interval_hours','backup_path','backup_keep'}


def backup_service(storage,parent=None,host=None):
    import shiboken6
    service=getattr(storage.config,'backup_service',None)
    if service is None or not shiboken6.isValid(service):
        service=BackupService(storage,parent or QApplication.instance())
        storage.config.backup_service=service
    if host is not None:service.host=host
    if isinstance(parent,QWidget):service.attach(parent)
    return service


class BackupService(QObject):
    changed=Signal()
    completed=Signal(object)
    pressure=Signal()

    def __init__(self,storage,parent=None):
        super().__init__(parent);self.storage=storage;self.config=storage.config
        self.library=Path(storage.library_root).resolve();self.host=None;self.roots=[]
        key=hashlib.sha256(str(self.library).casefold().encode()).hexdigest()[:24]
        self.directory=Path(self.config.base_dir)/'backups'/key
        self.state_path=self.directory/'state.json'
        self.state=dict(state='never',last_success_at='',last_attempt_at='',last_error='',last_valid_location='',enabled_since='')
        try:self.state.update(json.loads(self.state_path.read_text('utf-8')))
        except (OSError,ValueError,TypeError):pass
        self.process=None;self.job=None;self.outcome=None;self.buffer=b'';self.error_buffer=b''
        self.phase='';self.progress=(0,0);self.detail='';self.operation_error='';self._pause='';self._closing=False
        self._retry_at=0.0;self._retry_count=0;self._prior_state=None
        self.activity=activity_for(self.library)
        self._notify=lambda:self.pressure.emit()
        self.activity.notify=self._notify;self.pressure.connect(self._pressure)
        self._last_tick=time.monotonic();self._wal_stamp=None
        self._recover_interrupted()
        app=QApplication.instance()
        if app:
            app.installEventFilter(self);app.aboutToQuit.connect(self.shutdown)
        self.timer=QTimer(self);self.timer.setInterval(250);self.timer.timeout.connect(self._tick);self.timer.start()
        self.configure()
        if parent is not None:parent.destroyed.connect(self.shutdown)

    @property
    def active(self):return self.process is not None

    @property
    def pending(self):return self.active or bool(self._retry_at)

    @property
    def destination(self):return output_directory(self.library,self.config.get('backup_path',''))

    def attach(self,widget):
        if not any(r() is widget for r in self.roots):self.roots.append(weakref.ref(widget))

    def eventFilter(self,obj,event):
        if self.active and isinstance(obj,QWidget) and event.type() in {
            QEvent.Wheel,QEvent.MouseButtonPress,QEvent.MouseButtonDblClick,QEvent.KeyPress,QEvent.MouseMove}:
            import shiboken6
            for ref in self.roots:
                root=ref()
                if root is not None and shiboken6.isValid(root) and (obj is root or root.isAncestorOf(obj)):
                    self.activity.pulse('正在浏览或操作表情库');break
        return False

    def configure(self):
        self._config_signature=tuple(self.config.get(key) for key in sorted(SETTINGS_KEYS))
        enabled=bool(self.config.get('backup_enabled',False))
        if enabled and not self.state.get('enabled_since'):
            self.state['enabled_since']=utc_now();self._persist()
        elif not enabled and self.state.get('enabled_since'):
            self.state['enabled_since']='';self._persist()
        self.changed.emit()

    def _persist(self):atomic_json(self.state_path,self.state)

    def _recover_interrupted(self):
        old=self.state.get('active_job')
        if not old:return
        work=self.directory/('job-'+old)
        try:mode=json.loads((work/'job.json').read_text('utf-8')).get('mode','backup')
        except (OSError,ValueError,TypeError):mode='backup'
        if mode=='restore':
            prior=self.state.get('restore_prior_state') or {**self.state,'state':'success' if self.state.get('last_success_at') else 'never'}
            self.state.update(prior)
            self.detail='上次恢复未完成，原表情库不受影响'
            try:
                receipt=json.loads((work/'result.json').read_text('utf-8'))
                if receipt.get('committed') and receipt['job_id']==old and (Path(receipt['location'])/'index.sqlite3').is_file():
                    self.detail='备份已恢复到新的表情库'
            except (OSError,ValueError,KeyError):pass
            self.state.pop('restore_prior_state',None);self.state.pop('active_job',None);self._persist();return
        # Small receipts only: no Library enumeration/hash on application startup.
        try:
            receipt=json.loads((self.directory/('job-'+old)/'result.json').read_text('utf-8'))
            location=Path(receipt['location'])
            valid=json.loads(location.with_name(location.name+'.valid.json').read_text('utf-8'))
            if receipt.get('committed') and receipt['job_id']==old and receipt==valid and location.stat().st_size==receipt['bytes']:
                self.state.update(state='success',last_success_at=receipt['completed_at'],last_valid_location=str(location),last_error='')
            else:raise ValueError('Uncommitted task')
        except (OSError,ValueError,KeyError):
            self.state.update(state='failed',last_error='上次备份未完成，之前的有效备份不受影响')
        self.state.pop('active_job',None);self._persist()

    def _busy_reason(self):
        from services.drag_activity import drag_activity
        if drag_activity().operation is not None:return '正在拖动表情'
        queue=getattr(self.storage,'desktop_imports',None)
        if queue is not None and (queue.worker is not None or queue.waiting):return '正在导入表情'
        if self.host is not None and any(not key.startswith('backup:') and value.get('state')=='running'
                                         for key,value in self.host.named_tasks.items()):return '正在处理其他后台任务'
        return self.activity.busy()

    def _pressure(self):
        if self.active:
            self._pause=self._busy_reason()
            self._command(dict(pause=self._pause))

    def _tick(self):
        if self._closing:return
        if tuple(self.config.get(key) for key in sorted(SETTINGS_KEYS))!=getattr(self,'_config_signature',None):self.configure()
        now=time.monotonic();late=now-self._last_tick-.25;self._last_tick=now
        if self.active:
            if late>.12:self.activity.pulse('正在等待界面恢复空闲')
            try:
                s=(self.library/'index.sqlite3-wal').stat();stamp=(s.st_size,s.st_mtime_ns)
                if self._wal_stamp is not None and stamp!=self._wal_stamp:self.activity.pulse('正在更新表情库')
                self._wal_stamp=stamp
            except OSError:pass
            reason=self._busy_reason()
            if reason!=self._pause:
                self._pause=reason;self._command(dict(pause=reason))
            return
        if self._retry_at and now>=self._retry_at and not self._busy_reason():
            self._retry_at=0;self.request_backup(retry=True);return
        if not self.config.get('backup_enabled',False):return
        anchors=[self.state.get(k) for k in ('last_attempt_at','enabled_since') if self.state.get(k)]
        if not anchors:return
        try:elapsed=(datetime.now(timezone.utc)-max(datetime.fromisoformat(v) for v in anchors)).total_seconds()
        except (ValueError,TypeError):return
        if elapsed>=int(self.config.get('backup_interval_hours',24))*3600:
            if self._busy_reason():
                if self.state['state']!='waiting':self.state['state']='waiting';self.changed.emit()
            else:self.request_backup()

    def request_backup(self,*,retry=False):
        if self.active or self._closing or self._retry_at and not retry:return False
        self.destination  # Validate before creating any files/process.
        if not retry:self._retry_count=0;self.notification_id=uuid.uuid4().hex
        job=dict(mode='backup',destination=str(self.destination),keep=int(self.config.get('backup_keep',5)),
                 configuration={k:self.config.config[k] for k in CONFIG_KEYS if self.config.config.get(k) is not None})
        return self._start(job)

    def request_restore(self,archive,target):
        if self.pending or self._closing:return False
        self.notification_id=uuid.uuid4().hex
        self._prior_state=dict(self.state)
        return self._start(dict(mode='restore',archive=str(Path(archive).resolve()),target=str(Path(target).resolve())))

    def _start(self,job):
        identity=uuid.uuid4().hex;work=self.directory/('job-'+identity)
        job.update(id=identity,library=str(self.library),work=str(work))
        path=work/'job.json';atomic_json(path,job)
        self.job=job;self.outcome=None;self.buffer=b'';self.error_buffer=b'';self.progress=(0,0)
        self.operation_error='';self.diagnostic_details='';self._cancel_requested=False
        if job['mode']=='restore':self.state['restore_prior_state']=self._prior_state
        self.state.update(state='waiting',active_job=identity)
        if job['mode']=='backup':self.state['last_attempt_at']=utc_now()
        self._persist();self.activity.tracking=True
        self._pause=self._busy_reason();self.phase='inventory';self.detail=self._pause
        process=self.process=QProcess(self)
        environment=QProcessEnvironment.systemEnvironment();environment.insert('PYTHONIOENCODING','utf-8');environment.insert('PYTHONUNBUFFERED','1')
        process.setProcessEnvironment(environment)
        source=Path(__file__).resolve().parents[1];process.setWorkingDirectory(str(source))
        frozen=bool(getattr(sys,'frozen',False) or globals().get('__compiled__'))
        # Source workers use only stdlib. Avoid the venv redirector process so
        # QProcess cancellation/kill always targets the actual worker PID.
        if frozen:
            from services.autostart import _process_executable
            executable=str(_process_executable())
        else:executable=getattr(sys,'_base_executable',sys.executable)
        if not frozen and executable.lower().endswith('pythonw.exe'):
            executable=str(Path(executable).with_name('python.exe'))
        args=['--backup-worker',str(path)] if frozen else ['-m','services.backup_worker','--job',str(path)]
        process.readyReadStandardOutput.connect(self._read)
        process.readyReadStandardError.connect(self._read_error)
        process.started.connect(lambda:self._command(dict(pause=self._pause,cancel=self._cancel_requested)))
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        process.start(executable,args);self._publish();return True

    def _command(self,value):
        if self.process is not None:self.process.write((json.dumps(value,ensure_ascii=False)+'\n').encode('utf-8'))

    def cancel(self):
        queued=bool(self._retry_at);self._retry_at=0;self._cancel_requested=True
        self._command(dict(cancel=True))
        if queued and not self.active:
            self.state['state']='success' if self.state.get('last_success_at') else 'never'
            self.detail='备份已取消';self._persist();self._publish(final='cancelled')

    def _read_error(self):
        if self.process:self.error_buffer=(self.error_buffer+bytes(self.process.readAllStandardError()))[-32000:]

    def _read(self):
        if self.process is None:return
        self.buffer+=bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:message=json.loads(line)
            except ValueError:continue
            kind=message.get('type')
            if kind=='started':self.state['state']='running';self.worker_info=message
            elif kind=='waiting':self.state['state']='waiting';self.detail=message['reason']
            elif kind=='paused':self.state['state']='paused';self.detail=message['reason']
            elif kind=='resumed':self.state['state']='running';self.detail=''
            elif kind=='progress':
                self.phase=message['phase'];self.progress=(message['done'],message['total'])
                if self.state['state'] not in {'paused','waiting'}:self.state['state']='running'
            elif kind in {'done','failed','changed','cancelled'}:self.outcome=message
            self._publish()

    def _process_error(self,error):
        if error==QProcess.FailedToStart:
            self.outcome=dict(type='failed',reason='无法启动备份工作进程',details=self.process.errorString() if self.process else '')
            self._finished(-1,QProcess.CrashExit)

    def _finished(self,code,status):
        if self.process is None:return
        self._read();self._read_error();process=self.process;self.process=None
        outcome=self.outcome or dict(type='failed',reason='备份工作进程意外退出',details=self.error_buffer.decode('utf-8','replace'))
        kind=outcome['type'];mode=self.job['mode'];result=outcome.get('result',{})
        self.diagnostic_details=outcome.get('details','')
        if kind=='done' and mode=='backup':
            try:
                location=Path(result['location'])
                receipt=json.loads((Path(self.job['work'])/'result.json').read_text('utf-8'))
                marker=json.loads(location.with_name(location.name+'.valid.json').read_text('utf-8'))
                if receipt!=result or marker!=result or result['job_id']!=self.job['id'] or location.stat().st_size!=result['bytes']:
                    raise ValueError('Invalid committed receipt')
            except (OSError,ValueError,KeyError):
                kind='failed';outcome=dict(type=kind,reason='备份提交记录校验失败，未更新成功时间')
        if kind=='done' and (code!=0 or not result.get('committed')):
            kind='failed';outcome=dict(type=kind,reason='备份工作进程意外退出')
        if mode=='restore':
            self.state.clear();self.state.update(self._prior_state or {})
            if kind=='done' and code==0 and result.get('committed'):
                self.last_result=result;self.detail='备份已恢复到新的表情库'
            elif kind=='cancelled' or self._closing:self.detail='恢复已取消，原表情库不受影响'
            else:
                self.operation_error=outcome.get('reason','恢复失败')
                self.detail='恢复未完成，原表情库不受影响'
        elif kind=='done' and code==0 and result.get('committed'):
            self.last_result=result
            if mode=='backup':
                self.state.update(state='success',last_success_at=result['completed_at'],last_valid_location=result['location'],last_error='')
            else:self.state.update(self._prior_state or {});self.detail='备份已恢复到新的表情库'
        elif kind=='changed' and not self._closing and self._retry_count<3 and mode=='backup':
            self._retry_count+=1;self._retry_at=time.monotonic()+2
            self.state['state']='waiting';self.detail=outcome['reason']
        elif kind=='cancelled' or self._closing:
            self.state['state']='success' if self.state.get('last_success_at') else 'never'
            self.detail='备份已取消'
        else:
            self.state.update(state='failed',last_error=outcome.get('reason','备份失败'))
            self.detail=self.state['last_error']
        self.state.pop('active_job',None);self._persist();self.activity.tracking=False
        self._publish(final=kind);self.completed.emit(outcome);process.deleteLater()

    def _publish(self,final=None):
        self.changed.emit()
        if self.host is None or self.job is None:return
        from services.i18n import t
        state=self.state['state'];title=t('恢复表情库' if self.job['mode']=='restore' else '表情库备份')
        feedback_state={'never':'cancelled','waiting':'waiting','running':'running','paused':'waiting','success':'success','failed':'error'}[state]
        if final=='cancelled':feedback_state='cancelled'
        if final=='done':feedback_state='success'
        if final=='failed' or final=='changed' and self.job['mode']=='restore':feedback_state='error'
        done,total=self.progress
        # Qt progress bars are signed 32-bit. Keep byte totals in the service,
        # normalize only the presentation and retain readable actual sizes.
        scaled=max(0,min(10000,int(done*10000//total))) if total>0 else 0
        count_text=f'{done/1_000_000_000:.2f} / {total/1_000_000_000:.2f} GB' if total>0 else None
        self.host.upsert_task('backup:'+getattr(self,'notification_id',self.job['id']),title,current=scaled,total=10000 if total>0 else 0,count_text=count_text,state=feedback_state,kind='export',
            content=t(self.detail or PHASE_TEXT.get(self.phase,STATUS_TEXT[state])) if state in {'running','paused','waiting'} else t(self.detail or STATUS_TEXT[state]),
            phase=t(PHASE_TEXT.get(self.phase,'')) if self.active else '',cancel=self.cancel if self.pending else None,
            resume=(lambda:self.request_backup()) if state=='failed' and not self.active and self.job['mode']=='backup' else None,
            details=(getattr(self,'last_result',{}).get('location',self.state.get('last_valid_location','')) if feedback_state=='success' else self.diagnostic_details or getattr(self,'operation_error','') or self.state.get('last_error','')))

    def shutdown(self):
        if self._closing:return
        self._closing=True;self.timer.stop();self._retry_at=0
        process=self.process
        if process is not None:
            self._command(dict(cancel=True))
            if not process.waitForFinished(150):
                process.terminate()
                if not process.waitForFinished(100):process.kill();process.waitForFinished(100)
        self.activity.tracking=False
        if self.activity.notify is self._notify:self.activity.notify=None
        if not self.active and self.state['state']=='waiting':
            self.state['state']='success' if self.state.get('last_success_at') else 'never'
            self.detail='备份已取消';self._persist()
