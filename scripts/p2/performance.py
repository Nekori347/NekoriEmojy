"""Synthetic P1/P2 first-import comparison. Never accesses a user's library."""
import io,json,os,subprocess,sys,time,types
from pathlib import Path
from unittest.mock import patch
work=Path(os.environ['P2_WORK_DIR']).resolve();work.mkdir(parents=True,exist_ok=True);repo=Path(__file__).resolve().parents[2]
os.chdir(repo);sys.path.insert(0,str(repo));os.environ['QT_QPA_PLATFORM']='offscreen'
from PIL import Image
from services.library import create_library,open_library
from services.identity import inspect_bytes,put_identity
from services.storage import StorageService
from services.importing import ImportInput
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from fluent_ui.views.gallery_view import ImportThread
app=QApplication([])
count=2000
contexts=[]
for label in ('p1','p2'):
    context=create_library(work/('p2-perf-'+label+'-1'));contexts.append(context)
    with context.transaction() as conn:
        for i in range(count):
            path=context.images_dir/f'asset-{i:04d}.png'
            Image.new('RGBA',(256,256),(i%256,i//256,40,255)).save(path,compress_level=1)
            identity=inspect_bytes(path.read_bytes());put_identity(conn,path,identity)
            conn.execute('INSERT INTO features.image_features(image_path,md5) VALUES (?,?)',(path.name,identity.file_md5))
            conn.execute('INSERT INTO "order".item_orders VALUES (?,?)',(path.name,i))
source=work/'p2-perf-input-1.png';Image.new('RGBA',(256,256),(70,90,200,255)).save(source)
second=work/'p2-perf-input-2.png';Image.new('RGBA',(256,256),(71,91,201,255)).save(second)
old_code=subprocess.run(['git','show','f2da24da625771c1d13f1071eb078ba349af10fb:services/storage.py'],capture_output=True,check=True).stdout.decode('utf-8')
module=types.ModuleType('p1_comparison_storage');exec(compile(old_code,'p1_storage.py','exec'),module.__dict__)
report={'fixture':{'images':count,'dimensions':[256,256],'kinds':['PNG'],'source':'generated solid-color images'},'runs':[]}
import services.hasher as hasher
original=hasher.compute_sync_key
for label,context,cls in [('P1',contexts[0],module.StorageService),('P2',contexts[1],StorageService)]:
    start=time.perf_counter();session=open_library(context.root);store=cls(session);opening=(time.perf_counter()-start)*1000
    scans=[0]
    def counted(path):
        scans[0]+=1
        return original(path)
    timings=[]
    with patch.object(hasher,'compute_sync_key',counted):
        for path in (source,second):
            before=scans[0];start=time.perf_counter();saved,duplicate=store.save_file(path)
            assert saved and not duplicate
            timings.append({'ms':round((time.perf_counter()-start)*1000,2),'sync_key_decodes':scans[0]-before})
    report['runs'].append({'version':label,'open_ms':round(opening,2),'first':timings[0],'second':timings[1]})
    session.close()
# Actual QThread pipeline while a 10ms Qt heartbeat continues.
session=open_library(contexts[1].root);store=StorageService(session)
beats=[];timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(time.perf_counter()));timer.start()
thread=ImportThread([ImportInput('file',source)]*100,store,'benchmark')
result=[];thread.finished.connect(lambda *counts:result.append(counts))
thread.finished.connect(lambda *args:QTimer.singleShot(50,app.quit))
QTimer.singleShot(50,thread.start);QTimer.singleShot(30000,app.quit);app.exec();thread.wait(1000)
report['qt_async_batch']={'operations':100,'result':result,'heartbeat_count':len(beats),'max_heartbeat_gap_ms':round(max((b-a)*1000 for a,b in zip(beats,beats[1:])),2),'platform':app.platformName()}
session.close()
report['limits']=['single synthetic PNG workload, not real-user first-paste latency','OS disk cache not flushed; process service cold, not cold disk','source environment, not final Nuitka artifact']
(work/'p2-import-performance-1.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
