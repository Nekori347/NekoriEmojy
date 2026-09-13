import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import io
from pathlib import Path
import os
import subprocess
import sys
import uuid
import pytest
from PIL import Image
from services.library import create_library, open_library, read_db, LibraryBusy
from services.storage import StorageService
from services.identity import IdentityIndex, inspect_bytes, put_identity
from services.importing import ImportInput, ImportPipeline, recover_imports


def png(color='red', size=(19, 23), compress_level=6):
    b=io.BytesIO()
    Image.new('RGBA',size,color).save(b,format='PNG',compress_level=compress_level)
    return b.getvalue()


def test_copy_magic_animation_failures_and_inbox_are_non_destructive(tmp_path):
    context=create_library(tmp_path/'library')
    source=tmp_path/'无扩展名'
    source.write_bytes(png())
    webp=tmp_path/'实际上是webp.gif'
    Image.new('RGB',(20,20),'red').save(webp,format='WEBP',save_all=True,
        append_images=[Image.new('RGB',(20,20),'blue')],duration=[70,90],loop=0,lossless=True)
    bad=tmp_path/'not-an-image.png';bad.write_text('not an image')
    sources=[source,webp,bad]
    before={p:p.read_bytes() for p in sources}
    store=StorageService(context)
    result=ImportPipeline(store).run([ImportInput('file',p) for p in sources], '混合', inbox=True)
    assert result==dict(saved=2,duplicate=0,failed=1)
    assert all(p.read_bytes()==b for p,b in before.items())
    assert len(store.get_all_images())==2
    copied=[Path(p) for p in store.get_all_images() if p.endswith('.webp')][0]
    assert copied.read_bytes()==before[webp]
    with Image.open(copied) as img:
        assert img.n_frames==2
    source.rename(tmp_path/'moved-original')
    assert all(Path(p).is_file() for p in store.get_all_images())
    with read_db(context.db('library')) as conn:
        assert conn.execute('SELECT COUNT(*) FROM import_sources').fetchone()[0]==3


def test_reopen_first_import_only_reads_incoming_and_candidates(tmp_path, monkeypatch):
    context=create_library(tmp_path/'library')
    store=StorageService(context)
    one=store._standardize_and_save(png(),'')[0]
    # 2,000 distinct valid persisted records without using a slow fixture import loop.
    with context.transaction() as conn:
        for i in range(2000):
            name=f'existing-{i}.png'
            path=context.images_dir/name
            data=png(color=(i%256,(i//256)%256,40,255))
            path.write_bytes(data)
            put_identity(conn,path,inspect_bytes(data))
            conn.execute('INSERT INTO "order".item_orders VALUES (?,?)',(name,i+1))
    context2=open_library(context.root)
    reopened=StorageService(context2)
    original=Image.open
    opened=[]
    def observe(fp,*args,**kwargs):
        if isinstance(fp,(str,Path)):
            opened.append(str(fp))
        return original(fp,*args,**kwargs)
    monkeypatch.setattr(Image,'open',observe)
    def no_enumeration(*args,**kwargs):
        raise AssertionError('import must not enumerate whole library')
    monkeypatch.setattr(os,'listdir',no_enumeration)
    saved,duplicate=reopened._standardize_and_save(png('purple'),'')
    assert saved and not duplicate and opened==[]
    same,duplicate=reopened._standardize_and_save(png('red',compress_level=0),'')
    assert duplicate and same==one and opened==[]
    context2.close()


def test_concurrent_duplicate_import_and_shared_categories(tmp_path):
    context=create_library(tmp_path/'library');session=open_library(context.root)
    store=StorageService(session)
    source=tmp_path/'source.png';source.write_bytes(png())
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda i: store.save_file(source, target_category=f'category-{i}'),range(12)))
    assert sum(not duplicate for _,duplicate in results)==1
    assert len({path for path,_ in results})==1
    assert all(len(paths)==1 for paths in store.get_all_categories().values())
    assert len(list(context.images_dir.iterdir()))==1
    session.close()
    other=create_library(tmp_path/'other')
    with pytest.raises(LibraryBusy):
        store.save_file(source)
    assert StorageService(other).get_all_images()==[]


def test_changed_candidate_advances_revision_and_does_not_false_dedup(tmp_path):
    context=create_library(tmp_path/'library');store=StorageService(context)
    source=tmp_path/'source';source.write_bytes(png())
    first=Path(store.save_file(source)[0])
    before=IdentityIndex(context)._rows('SELECT * FROM resource_identity')[0]
    first.write_bytes(png('blue', compress_level=0))
    saved,duplicate=store.save_file(source)
    assert saved and not duplicate and Path(saved)!=first
    row=IdentityIndex(context)._rows('SELECT * FROM resource_identity WHERE image_path=?',(first.name,))[0]
    assert row['resource_id']==before['resource_id'] and row['content_revision']==2
    assert row['file_md5']==hashlib.md5(first.read_bytes()).hexdigest()


def test_failed_commit_restores_file_and_all_database_layers(tmp_path, monkeypatch):
    import services.importing as module
    context=create_library(tmp_path/'library');store=StorageService(context)
    original=module._finish_pending
    def fail(conn,rid):
        original(conn,rid)
        raise OSError('injected database commit failure')
    monkeypatch.setattr(module,'_finish_pending',fail)
    with pytest.raises(OSError):
        store._standardize_and_save(png(),'',target_category='not-committed')
    assert list(context.images_dir.iterdir())==[]
    assert store.get_all_categories()=={} and store.get_all_images()==[]
    with read_db(context.db('library')) as conn:
        assert conn.execute('SELECT COUNT(*) FROM import_journal').fetchone()[0]==0
    assert IdentityIndex(context)._rows('SELECT * FROM resource_identity')==[]


def test_actual_process_interruption_recovers_only_original_pending_import(tmp_path):
    context=create_library(tmp_path/'library')
    source=tmp_path/'source';source.write_bytes(png())
    code='''import os,sys
from services.library import open_library
from services.storage import StorageService
import services.importing as module
session=open_library(sys.argv[1])
module._finish_pending=lambda *args: os._exit(73)
StorageService(session).save_file(sys.argv[2],target_category='recovered')
'''
    process=subprocess.run([sys.executable,'-c',code,str(context.root),str(source)],cwd=Path(__file__).resolve().parents[1],timeout=15)
    assert process.returncode==73
    session=open_library(context.root)
    assert recover_imports(session.context)==1
    store=StorageService(session)
    assert len(store.get_all_images())==1 and len(store.get_all_categories()['recovered'])==1
    assert recover_imports(session.context)==0
    session.close()


def test_delete_failure_restores_files_and_relationships(tmp_path, monkeypatch):
    context=create_library(tmp_path/'library');store=StorageService(context)
    source=tmp_path/'source';source.write_bytes(png())
    path=store.save_file(source,target_category='keep')[0]
    original=context.transaction
    # Fail only deletion of indexed metadata, after moving the managed file aside.
    @contextmanager
    def transaction(**kwargs):
        with original(**kwargs) as conn:
            conn.set_authorizer(lambda op,a,b,*rest: 1 if op==9 and a=='image_metadata' else 0)
            yield conn
    monkeypatch.setattr(type(context),'transaction',lambda self,**kwargs: transaction(**kwargs))
    result=store.delete_images_batch([path])
    assert result['failed']==1 and Path(path).exists()
    assert store.get_all_categories()=={'keep':[path]}


def test_database_identity_gaps_are_incremental_not_hidden_scan(tmp_path):
    context=create_library(tmp_path/'library');store=StorageService(context)
    source=context.images_dir/'old.png';source.write_bytes(png())
    with context.transaction() as conn:
        conn.execute('INSERT INTO features.resource_identity(resource_id,image_path) VALUES (?,?)',(uuid.uuid4().hex,source.name))
        conn.execute('INSERT INTO "order".item_orders VALUES (?,0)',(source.name,))
    index=IdentityIndex(context)
    assert index.pending_count()==1
    assert index.complete_missing(cancel=lambda:True)==1 and index.pending_count()==1
    index.complete_missing()
    assert index.pending_count()==0
    result=ImportPipeline(store).run([ImportInput('url','data:image/png;base64,'+base64.b64encode(png()).decode())])
    assert result['duplicate']==1 and result['saved']==0


def test_mime_adapters_snapshot_html_url_bitmap_and_files():
    from PySide6.QtCore import QMimeData,QUrl
    from PySide6.QtGui import QImage
    from services.image_inputs import snapshot_inputs
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile('C:/source.weird')])
    assert snapshot_inputs(mime)[0].kind=='file'
    mime=QMimeData();mime.setHtml('<img src="https://example.invalid/image?k=a&amp;x=b">')
    assert snapshot_inputs(mime)[0].value=='https://example.invalid/image?k=a&x=b'
    mime=QMimeData();image=QImage(2,2,QImage.Format_RGBA8888);image.fill(0xff223344)
    mime.setHtml('<img src="blob:unavailable">');mime.setImageData(image)
    snapshot=snapshot_inputs(mime)
    image.fill(0)
    assert snapshot[0].kind=='image' and not snapshot[0].value.isNull()

def test_schema_two_upgrade_queues_unknown_identities_without_reading_images(tmp_path, monkeypatch):
    import services.library as library
    root=tmp_path/'old'
    (root/'data/images').mkdir(parents=True)
    context=library.LibraryContext(root,uuid.uuid4().hex)
    library._migrate(context,0,target=2)
    library.atomic_json(root/'nekori-library.json',dict(format='NekoriEmojy',version=1,library_id=context.library_id))
    path=context.images_dir/'old.png';path.write_bytes(png())
    with context.transaction() as conn:
        conn.execute('INSERT INTO features.image_features(image_path,md5) VALUES (?,?)',(path.name,'ambiguous-historical-value'))
    with monkeypatch.context() as patcher:
        patcher.setattr(Image,'open',lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('no image scan during open')))
        session=open_library(root)
    index=IdentityIndex(session.context)
    assert index.pending_count()==1
    store=StorageService(session)
    assert store.get_all_images()==[store._to_abspath(path.name)]
    index.complete_missing()
    assert index.pending_count()==0
    assert store._standardize_and_save(png(),'')[1]
    session.close()


def test_exchange_and_daily_import_share_persistent_dedup(tmp_path, monkeypatch):
    from services.exchange_export import ExchangeExportService
    from services.exchange_import import ExchangeImportService
    context=create_library(tmp_path/'source-library');store=StorageService(context)
    store._standardize_and_save(png(),'')
    archive=tmp_path/'exchange.zip'
    ExchangeExportService(context).export_zip(archive)
    target=create_library(tmp_path/'target-library')
    assert ExchangeImportService(target).import_zip(archive)==(1,0)
    assert StorageService(target)._standardize_and_save(png(),'')[1]
    assert ExchangeImportService(target).import_zip(archive)==(0,1)


def test_wrong_dimensions_do_not_collide_on_equal_flat_rgba_bytes(tmp_path):
    context=create_library(tmp_path/'library');store=StorageService(context)
    first,duplicate=store._standardize_and_save(png(size=(4,6)),'')
    second,duplicate=store._standardize_and_save(png(size=(6,4)),'')
    assert second!=first and not duplicate
    assert len(store.get_all_images())==2
