import json
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication
from services.config import ConfigService
from services.storage import StorageService
from services.suzu_migration import SuzuMigrationService
from fluent_ui.views.gallery_view import ImportThread


def test_migration_remains_busy_through_relations_order_and_reload(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    source=tmp_path/'suzu';images=source/'images';images.mkdir(parents=True)
    for name,color in [('a.png','red'),('b.png','blue')]:Image.new('RGB',(20,20),color).save(images/name)
    (source/'order.json').write_text(json.dumps(['b.png','a.png']),encoding='utf-8')
    (source/'categories.json').write_text(json.dumps({'A':['a.png','b.png'],'B':['a.png']}),encoding='utf-8')
    before={p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()}
    storage=StorageService(tmp_path/'library',config=ConfigService(tmp_path/'app'))
    service=SuzuMigrationService(storage);worker=ImportThread([str(source)],storage,None)
    events=[];last_stage=[''];checks=[]
    def progress(current,total,message=''):
        events.append((current,total,message))
        if total:assert current<total  # worker reserves final UI refresh
    worker.progress.connect(lambda c,t:progress(c,t,last_stage[0]))
    worker.stage.connect(lambda stage:last_stage.__setitem__(0,stage))
    for obj,name,stage in [(storage.index,'add_membership','恢复分类关系'),
                           (storage.index,'reorder_resources','整理资源顺序'),
                           (storage,'force_reload','完成迁移收尾')]:
        original=getattr(obj,name)
        def checked(*args,_original=original,_stage=stage,**kwargs):
            assert last_stage[0]==_stage
            assert events[-1][1]==0
            checks.append(_stage)
            return _original(*args,**kwargs)
        monkeypatch.setattr(obj,name,checked)
    worker.operation=lambda callback:service.migrate_from_data_dir(source,callback)
    worker.run();app.processEvents()
    assert worker.errors==[] and worker.result['resources']==2
    assert set(checks)=={'恢复分类关系','整理资源顺序','完成迁移收尾'}
    assert {p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()}==before
    assert len(storage.get_images_by_category('A'))==2
    assert len(storage.get_images_by_category('B'))==1
