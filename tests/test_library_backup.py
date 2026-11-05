import hashlib
import json
import os
import sqlite3
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from services.library_index import LibraryIndex, ROOT
from services.library_backup import (create_backup,restore_backup,inspect_archive,shared_read,fingerprint,
    BackupError,LibraryChanged,BackupCancelled,output_directory)


class Control:
    def __init__(self):self.events=[];self.callback=None;self.cancel=False
    def checkpoint(self,cost=0):
        if self.cancel:raise BackupCancelled()
    def sql_progress(self):self.checkpoint();return 0
    def progress(self,phase,done,total):
        self.events.append((phase,done,total))
        if self.callback:self.callback(phase,done,total)


def library(tmp_path):
    root=tmp_path/'library';index=LibraryIndex(root);(root/'images').mkdir()
    node=index.create_node('Category');child=index.create_node('Child',node)
    ids=[]
    for i in range(3):
        p=root/'images'/f'{i}.png';Image.new('RGB',(25+i,29),(30+i*50,90,140)).save(p)
        os.utime(p,ns=(1700000000123456700+i*100,1700000000123456700+i*100))
        rid=index.register(p);ids.append(rid);index.add_membership(rid,node)
    index.set_order(node,[('resource',ids[2]),('node',child),('resource',ids[0]),('resource',ids[1])])
    index.set_search_fields(ids[0],tags='标签',ocr_text='OCR text')
    with index.connect() as db:
        db.execute('INSERT INTO recent VALUES (?,?)',(ids[0],123))
        db.execute("INSERT INTO task_checkpoints VALUES ('old','unit','import','{}')")
    return root,index


def job(tmp_path,root,identity='one'):
    return dict(id=identity,library=str(root),destination=str(tmp_path/'backups'),work=str(tmp_path/('work-'+identity)),
                configuration=dict(recent_limit=30,resource_sort='manual',global_hotkey='must not include'),keep=5)


def tables(path):
    with sqlite3.connect(path) as db:
        return {name:sorted(db.execute('SELECT * FROM "'+name+'"').fetchall(),key=repr)
                for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_exact_backup_restore_keeps_all_tables_identity_order_and_ns_mtime(tmp_path):
    root,index=library(tmp_path);c=Control();j=job(tmp_path,root)
    before=tables(index.path);result=create_backup(j,c);archive=Path(result['location'])
    assert archive.is_file() and archive.with_name(archive.name+'.valid.json').is_file()
    target=tmp_path/'restored'
    restored=restore_backup(dict(j,id='restore',work=str(tmp_path/'restore-work'),archive=str(archive),target=str(target)),c)
    assert restored['committed'] and tables(target/'index.sqlite3')==before
    for source in (root/'images').iterdir():
        copied=target/'images'/source.name
        assert copied.read_bytes()==source.read_bytes() and copied.stat().st_mtime_ns==source.stat().st_mtime_ns
    config=json.loads((target/'backup-settings.json').read_text('utf-8'))
    assert config==dict(recent_limit=30,resource_sort='manual')
    assert tables(index.path)==before


def test_shared_reader_yields_to_replace_and_delete(tmp_path):
    p=tmp_path/'image';p.write_bytes(b'old');replacement=tmp_path/'replacement';replacement.write_bytes(b'new')
    with shared_read(p) as f:
        old=fingerprint(p,f);os.replace(replacement,p)
        assert fingerprint(p)!=old
        if os.name=='nt':
            from services.backup_files import LeaseBroken
            with pytest.raises(LeaseBroken):f.read()
        else:assert f.read()==b'old'
        p.unlink()
        assert not p.exists()


@pytest.mark.parametrize('action',['replace','delete'])
def test_lease_is_revoked_while_archive_consumer_is_paused(tmp_path,action):
    import threading
    p=tmp_path/'image';p.write_bytes(b'a'*(1024*1024))
    replacement=tmp_path/'replacement';replacement.write_bytes(b'new')
    errors=[]
    def writer():
        try:
            if action=='replace':os.replace(replacement,p)
            else:p.unlink()
        except Exception as exc:errors.append(exc)
    with shared_read(p) as f:
        assert len(f.read(256*1024))==256*1024
        # Consumer deliberately does no more reads/close while the writer runs.
        thread=threading.Thread(target=writer);thread.start();thread.join(2)
        completed=not thread.is_alive()
        if completed and os.name=='nt':
            from services.backup_files import LeaseBroken
            with pytest.raises(LeaseBroken):f.read(1)
    thread.join(2)
    assert completed and not errors


@pytest.mark.parametrize('change',['new','delete','replace','external','mtime_reset','sort'])
def test_mutations_are_nonblocking_and_media_changes_cannot_commit(tmp_path,change):
    root,index=library(tmp_path);j=job(tmp_path,root);c=Control();changed=[]
    def mutate(phase,done,total):
        if phase!='archive' or changed:return
        changed.append(True);p=root/'images/0.png'
        if change=='new':
            added=root/'images/new.png';added.write_bytes((root/'images/1.png').read_bytes());index.register(added)
        elif change=='delete':index.forget_resource(index.resource(p)['id']);p.unlink()
        elif change=='replace':
            other=root/'images/replacement.png';other.write_bytes((root/'images/1.png').read_bytes());os.replace(other,p)
        elif change in ('external','mtime_reset'):
            old=p.stat();data=bytearray(p.read_bytes());data[-1]^=1;p.write_bytes(data)
            if change=='mtime_reset':os.utime(p,ns=(old.st_atime_ns,old.st_mtime_ns))
        elif change=='sort':index.set_order(ROOT,list(reversed(index.content(ROOT))))
    c.callback=mutate
    if change=='sort':
        result=create_backup(j,c);assert result['committed']
        assert result['database']['tables']['resources']==3
    else:
        with pytest.raises((LibraryChanged,FileNotFoundError)):create_backup(j,c)
        assert not list((tmp_path/'backups').glob('*.zip'))


def test_old_backup_survives_cancel_failure_and_retention_only_prunes_after_success(tmp_path):
    root,index=library(tmp_path);old=create_backup(job(tmp_path,root),Control());old_path=Path(old['location']);digest=hashlib.sha256(old_path.read_bytes()).hexdigest()
    c=Control();c.callback=lambda *args:setattr(c,'cancel',True) if args[0]=='archive' else None
    with pytest.raises(BackupCancelled):create_backup(job(tmp_path,root,'cancel'),c)
    assert old_path.exists() and hashlib.sha256(old_path.read_bytes()).hexdigest()==digest
    new=create_backup(dict(job(tmp_path,root,'new'),keep=1),Control())
    assert Path(new['location']).exists() and not old_path.exists()


def test_rejects_library_destination_nonempty_restore_and_corrupt_archive(tmp_path):
    root,index=library(tmp_path)
    with pytest.raises(BackupError):output_directory(root,root/'backups')
    result=create_backup(job(tmp_path,root),Control());target=tmp_path/'target';target.mkdir();(target/'keep').write_text('safe')
    with pytest.raises(BackupError):restore_backup(dict(job(tmp_path,root),archive=result['location'],target=str(target)),Control())
    assert (target/'keep').read_text()=='safe'
    corrupt=tmp_path/'corrupt.zip';data=bytearray(Path(result['location']).read_bytes());data[80]^=55;corrupt.write_bytes(data)
    with pytest.raises((BackupError,zipfile.BadZipFile,RuntimeError)):
        inspect_archive(corrupt,tmp_path/'verify-corrupt',Control())


def test_disk_space_failure_preserves_preexisting_valid_backup(tmp_path,monkeypatch):
    from collections import namedtuple
    root,index=library(tmp_path);old=create_backup(job(tmp_path,root),Control());path=Path(old['location']);before=path.read_bytes()
    monkeypatch.setattr('services.library_backup.shutil.disk_usage',lambda *_:namedtuple('Usage','total used free')(100,100,0))
    with pytest.raises(BackupError,match='磁盘'):create_backup(job(tmp_path,root,'full-disk'),Control())
    assert path.read_bytes()==before and not list(path.parent.glob('*.part'))


@pytest.mark.parametrize('bad_name',['../escape','library/../escape','library/C:/escape','library/CON','library/a.'])
def test_untrusted_restore_paths_never_escape_staging(tmp_path,bad_name):
    archive=tmp_path/'unsafe.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(bad_name,b'bad')
    with pytest.raises(BackupError):inspect_archive(archive,tmp_path/'scratch',Control(),restore=tmp_path/'staging')
    assert not (tmp_path/'escape').exists()


def test_sha_mismatch_rejects_restore_even_with_valid_zip_crc(tmp_path):
    root,index=library(tmp_path);old=create_backup(job(tmp_path,root),Control());damaged=tmp_path/'modified.zip'
    with zipfile.ZipFile(old['location']) as src,zipfile.ZipFile(damaged,'w') as dst:
        for name in src.namelist():
            data=src.read(name)
            if name=='library/images/0.png':data=data[:-1]+bytes([data[-1]^1])
            dst.writestr(name,data)
    target=tmp_path/'not-committed'
    with pytest.raises(BackupError,match='校验失败'):
        restore_backup(dict(job(tmp_path,root,'bad-restore'),archive=str(damaged),target=str(target)),Control())
    assert not target.exists() and Path(old['location']).exists()
