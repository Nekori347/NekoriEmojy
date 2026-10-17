"""One optional, fixed offline runtime; install/uninstall never touches a library."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from services.ocr_data import OCR_VERSION
from services.update_protocol import sha256

MANIFEST='nekori-ocr.json'


def component_child(root,name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:
        raise ValueError('OCR 组件路径无效')
    target=Path(root)/name
    if not target.resolve().is_relative_to(Path(root).resolve()):raise ValueError('OCR 组件路径无效')
    return target


def child_environment():
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','VIRTUAL_ENV','CONDA'))}
    env['PYTHONNOUSERSITE']='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    return env


class OcrComponent:
    def __init__(self,app_dir):
        self.base=Path(app_dir)/'components'
        self.root=self.base/'ocr'

    @staticmethod
    def verify(root,full=False):
        root=Path(root)
        value=json.loads((root/MANIFEST).read_text(encoding='utf-8'))
        if not isinstance(value,dict) or value.get('version')!=OCR_VERSION or value.get('protocol')!=1:
            raise ValueError('OCR 组件版本不匹配')
        for name in ('python.exe','worker.py','python312._pth'):
            if not (root/name).is_file():raise ValueError('OCR 组件不完整')
        if full:
            for name,digest in value['files'].items():
                if sha256(component_child(root,name))!=digest:raise ValueError('OCR 组件校验失败')
        return value

    @property
    def installed(self):
        try:self.verify(self.root);return True
        except (OSError,ValueError,KeyError):return False

    @staticmethod
    def release():
        path=Path(__file__).resolve().parents[1]/'ocr-component.json'
        return json.loads(path.read_text(encoding='utf-8'))

    def install(self,source=None,progress=lambda *args:None,cancel=None):
        cancel=cancel or threading.Event()
        self.base.mkdir(parents=True,exist_ok=True)
        work=self.base/('ocr-install-'+uuid.uuid4().hex)
        work.mkdir()
        stage=work/'payload'
        try:
            archive=Path(source) if source else work/'download.zip'
            if not source:
                import requests
                release=self.release()
                if not release.get('url') or not release.get('sha256'):
                    raise ValueError('在线组件尚未发布，请选择本地组件包。')
                progress('downloading',0,0)
                with requests.get(release['url'],stream=True,timeout=(8,20)) as response:
                    response.raise_for_status()
                    total=int(response.headers.get('Content-Length',0));done=0
                    with archive.open('wb') as f:
                        for block in response.iter_content(256*1024):
                            if cancel.is_set():raise InterruptedError()
                            f.write(block);done+=len(block);progress('downloading',done,total)
                if sha256(archive)!=release['sha256']:raise ValueError('OCR 组件校验失败')
            progress('installing',0,0)
            with zipfile.ZipFile(archive) as z:
                entries=z.infolist()
                for number,info in enumerate(entries):
                    if cancel.is_set():raise InterruptedError()
                    target=component_child(stage,info.filename.rstrip('/'))
                    if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(info) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
                    if number%32==0:progress('installing',number+1,len(entries))
            progress('checking',0,0)
            self.verify(stage,full=True)
            process=subprocess.Popen([str(stage/'python.exe'),'-I',str(stage/'worker.py'),'--check'],
                cwd=stage,env=child_environment(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline=time.monotonic()+90
            try:
                while True:
                    if cancel.is_set():raise InterruptedError()
                    if time.monotonic()>deadline:raise TimeoutError('OCR 组件启动超时')
                    try:stdout,stderr=process.communicate(timeout=.2);break
                    except subprocess.TimeoutExpired:pass
                if process.returncode or '"ready": true' not in stdout:
                    raise ValueError('OCR 组件无法启动：'+stderr[-500:])
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=5)
            if cancel.is_set():raise InterruptedError()
            # Installer is entered only after the old worker has been stopped.
            if self.root.exists():shutil.rmtree(self.root)
            stage.replace(self.root)
            progress('installed',1,1)
        finally:
            shutil.rmtree(work,ignore_errors=True)

    def uninstall(self):
        if self.root.exists():shutil.rmtree(self.root)


class OcrProcess:
    """One persistent JSON-line worker, lazily started and closed on idle/cancel."""
    def __init__(self,component):
        self.component=component
        self.process=None
        self.messages=queue.Queue()
        self._guard=threading.Lock()
        self.log=None

    def start(self):
        with self._guard:
            if self.process and self.process.poll() is None:return
            self.component.verify(self.component.root)
            root=self.component.root
            self.messages=queue.Queue()
            self.log=(self.component.base/'ocr-worker.log').open('w',encoding='utf-8')
            self.process=subprocess.Popen([str(root/'python.exe'),'-I',str(root/'worker.py')],cwd=root,
                env=child_environment(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,
                text=True,encoding='utf-8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            process=self.process;messages=self.messages
            def reader():
                try:
                    for line in process.stdout:messages.put(json.loads(line))
                except Exception as exc:messages.put({'error':str(exc)})
                finally:messages.put({'error':'OCR 进程已停止'})
            threading.Thread(target=reader,daemon=True).start()
        try:ready=self.messages.get(timeout=90)
        except queue.Empty:raise TimeoutError('OCR 组件启动超时') from None
        if not ready.get('ready'):raise RuntimeError(ready.get('error','OCR 组件无法启动'))

    def recognize(self,path,thumbnail=0):
        self.start()
        self.process.stdin.write(json.dumps(dict(path=str(path),thumbnail=thumbnail),ensure_ascii=True)+'\n')
        self.process.stdin.flush()
        try:result=self.messages.get(timeout=120)
        except queue.Empty:raise TimeoutError('识别超时，请重试') from None
        if result.get('error'):raise RuntimeError(result['error'])
        return result

    def close(self):
        with self._guard:
            process,self.process=self.process,None
            if process:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
                for stream in (process.stdin,process.stdout):
                    if stream:stream.close()
            if self.log:self.log.close();self.log=None
