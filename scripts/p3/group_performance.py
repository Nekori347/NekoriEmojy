import json,os,sys,time
from pathlib import Path
from unittest.mock import patch
work=Path(os.environ['P3_WORK_DIR']).resolve();work.mkdir(parents=True,exist_ok=True);repo=Path(__file__).resolve().parents[2];os.chdir(repo);sys.path.insert(0,str(repo))
root=work/'performance';root.mkdir(exist_ok=False);os.environ['QT_QPA_PLATFORM']='offscreen'
from PIL import Image
from services.library import create_library,LibrarySession
from services.identity import inspect_bytes,put_identity
from services.category_groups import CategoryGroups
from services.storage import StorageService
from services.config import ConfigService
from services.clipboard import ClipboardService
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,QThread
from PySide6.QtTest import QTest
from qfluentwidgets import qconfig
import requests
context=create_library(root/'library')
with context.transaction() as conn:
    conn.execute("INSERT INTO categories.categories(name,sort_order) VALUES ('大分类',0)")
    for i in range(2000):
        path=context.images_dir/f'asset-{i:04d}.png';Image.new('RGB',(256,256),(i%256,i//256,40)).save(path)
        info=inspect_bytes(path.read_bytes());put_identity(conn,path,info)
        conn.execute('INSERT INTO features.image_features(image_path,md5) VALUES (?,?)',(path.name,info.file_md5))
        conn.execute('INSERT INTO "order".item_orders VALUES (?,?)',(path.name,i))
        conn.execute('INSERT INTO categories.category_images VALUES (?,?)',('大分类',path.name))
groups=CategoryGroups(context)
for i in range(4):
    group=groups.create('大分类',f'分组{i+1}')
    groups.add(group,[context.resource(f'asset-{j:04d}.png') for j in range(i*500,(i+1)*500)])
app=QApplication([]);app.setQuitOnLastWindowClosed(False);qconfig.file=context.data_dir/'cache'/'qt-state.json'
session=LibrarySession(context);config=ConfigService(session);store=StorageService(session)
from services.i18n import i18n_engine
i18n_engine.init(config)
beats=[];timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(time.perf_counter()))
errors=[]
sys.excepthook=lambda *exc:errors.append(str(exc[1]))
with patch('requests.sessions.Session.request',side_effect=requests.ConnectionError('isolated')),patch('fluent_ui.main_window.MainWindow.bind_global_hotkey'):
    from fluent_ui.main_window import MainWindow
    window=MainWindow(store,ClipboardService(config),config);window.resize(1000,730);window.show();QTest.qWait(800)
    g=window.gallery_interface
    ordinary_count=len(g._all_card_widgets)
    timer.start();start=time.perf_counter();beats.append(start)
    g.set_category('大分类')
    sync_ms=(time.perf_counter()-start)*1000
    while g._is_loading and time.perf_counter()-start<35:QTest.qWait(10)
    elapsed=(time.perf_counter()-start)*1000;QTest.qWait(100);timer.stop()
    report={'synthetic_png_count':2000,'groups':4,'group_size':500,'ordinary_initial_cards':ordinary_count,'group_initial_cards':len(g._all_card_widgets),'sync_switch_ms':round(sync_ms,2),'group_initial_complete_ms':round(elapsed,2),'max_10ms_heartbeat_gap_ms':round(max((b-a)*1000 for a,b in zip(beats,beats[1:])),2),'qt_errors':errors,'platform':'offscreen','build':'source'}
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
    for thread in window.findChildren(QThread):thread.wait(5000)
    window.settings_window.close();window.close();window.quick_panel.close();QTest.qWait(50)
session.close()
