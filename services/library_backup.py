"""Exact Library snapshots and verified restores. No Qt or GUI-thread work.

An optimistic snapshot is accepted only when file versions remain unchanged
across inventory, SQLite online backup, copying and the final source audit.
Catalog writes may proceed after the SQLite snapshot. Media changes invalidate
this attempt rather than locking imports/deletion for the duration of a backup.
"""
import ctypes
import errno
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import time
import uuid
import zipfile
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

FORMAT = 'nekori-library-backup'
VERSION = 1
CHUNK = 256 * 1024
MEDIA = {'.png','.apng','.jpg','.jpeg','.gif','.webp','.webm','.tgs','.bmp','.tiff','.ogg','.wav'}
ROOT = '__library__'
CONFIG_KEYS = ('recent_limit','resource_sort','show_new_resource_markers','thumbnail_size',
               'gallery_node_icon_size','sidebar_mode','sidebar_show_labels','sidebar_icon_size',
               'tag_panel_placement','tag_panel_expanded','tag_panel_horizontal_extent','tag_panel_vertical_extent')


class BackupError(Exception):pass
class LibraryChanged(BackupError):pass
class BackupCancelled(BackupError):pass


def utc_now():return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path);path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, separators=(',',':'));f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


def safe_relative(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise BackupError('备份包含不安全的文件路径')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('','.','..') for p in value.split('/')):
        raise BackupError('备份包含不安全的文件路径')
    for part in path.parts:
        if part.rstrip(' .') != part or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            raise BackupError('备份包含不安全的文件路径')
    return path.as_posix()


def output_directory(library, value=''):
    root=Path(library).resolve()
    target=Path(value).expanduser().resolve() if value else root.with_name(root.name+' Backups')
    if target==root or target.is_relative_to(root):raise BackupError('备份目录不能位于当前表情库内')
    return target


@contextmanager
def shared_read(path):
    """Windows READ|WRITE|DELETE sharing: an open reader never pins a pathname."""
    if os.name != 'nt':
        with open(path,'rb',buffering=0) as f:yield f
        return
    from services.backup_files import LeasedReader,LeaseBroken
    try:
        with LeasedReader(path) as f:yield f
    except LeaseBroken as exc:raise LibraryChanged(str(exc)) from exc


def fingerprint(path, stream=None):
    if stream is None:
        with shared_read(path) as f:return fingerprint(path,f)
    s=os.fstat(stream.fileno())
    change=s.st_ctime_ns
    if os.name=='nt':
        import msvcrt
        from ctypes import wintypes as W
        class Basic(ctypes.Structure):
            _fields_=[('creation',ctypes.c_longlong),('access',ctypes.c_longlong),
                      ('write',ctypes.c_longlong),('change',ctypes.c_longlong),('attributes',W.DWORD)]
        info=Basic();api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.GetFileInformationByHandleEx.argtypes=[W.HANDLE,ctypes.c_int,W.LPVOID,W.DWORD]
        if not api.GetFileInformationByHandleEx(msvcrt.get_osfhandle(stream.fileno()),0,ctypes.byref(info),ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        change=info.change
        if not change:raise BackupError('此文件系统无法提供可核对的文件版本')
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,change]


def inventory(root, control):
    files={};folded=set();root=Path(root)
    def visit(folder):
        with os.scandir(folder) as entries:
            for entry in entries:
                control.checkpoint(4096)
                p=Path(entry.path);relative=p.relative_to(root).as_posix()
                if folder==root and entry.name in {'cache','.cache','tmp','logs','backups','.backups'}:continue
                if relative in {'index.sqlite3','index.sqlite3-wal','index.sqlite3-shm'}:continue
                if entry.name.endswith(('.nekori-backup.zip','.nekori-backup.zip.part','.nekori-backup.zip.valid.json')):continue
                s=entry.stat(follow_symlinks=False)
                if entry.is_symlink() or getattr(s,'st_file_attributes',0)&0x400:
                    raise BackupError('表情库内含有链接文件或目录，无法确认完整备份')
                if stat.S_ISDIR(s.st_mode):visit(p)
                elif stat.S_ISREG(s.st_mode):
                    name=safe_relative(relative)
                    if name.casefold() in folded:raise BackupError('表情库中存在大小写冲突的路径')
                    folded.add(name.casefold());files[name]=fingerprint(p)
    visit(root)
    return files


def check_space(directory, required):
    if shutil.disk_usage(directory).free < required+64*1024*1024:
        raise BackupError('磁盘剩余空间不足，请选择其他备份位置或释放空间')


def validate_database(path, names, control):
    """Validate whole SQLite and its actual identity/tree/membership contracts."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.set_progress_handler(lambda:control.sql_progress(),10000)
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise BackupError('备份数据库完整性检查失败')
        if db.execute('PRAGMA foreign_key_check').fetchone():raise BackupError('备份数据库关系检查失败')
        if db.execute('PRAGMA user_version').fetchone()[0]!=3:raise BackupError('不支持此表情库数据库版本')
        nodes={r[0]:(r[1],r[2]) for r in db.execute('SELECT id,parent_id,icon FROM nodes')}
        resources={r[0]:(r[1],r[2]) for r in db.execute('SELECT id,relative_path,status FROM resources')}
        if ROOT not in nodes or nodes[ROOT][0] is not None:raise BackupError('表情库根分类无效')
        missing=[]
        for rid,(relative,status_) in resources.items():
            relative=safe_relative(relative)
            if relative not in names:
                if status_!='missing':raise LibraryChanged('存在找不到的表情文件，请先检查表情状态')
                missing.append(relative)
        for nid,(parent,icon) in nodes.items():
            control.checkpoint()
            seen={nid};ancestor=parent
            while ancestor is not None:
                if ancestor in seen or ancestor not in nodes:raise BackupError('分类树存在循环或失效关系')
                seen.add(ancestor);ancestor=nodes[ancestor][0]
            if icon and Path(icon).suffix.lower() in MEDIA:
                icon=safe_relative(icon)
                relative=icon if icon.startswith('category_icons/') else 'images/'+icon
                if relative not in names:raise LibraryChanged('分类图标缺失，无法完成备份')
        seen_nodes=set();root_resources=set()
        for parent,rid,nid in db.execute('SELECT parent_id,resource_id,node_id FROM content'):
            if parent not in nodes or (rid is None)==(nid is None):raise BackupError('分类成员关系无效')
            if rid is not None:
                if rid not in resources:raise BackupError('分类包含失效的资源关系')
                if parent==ROOT:root_resources.add(rid)
            else:
                if nid in seen_nodes or nid not in nodes or nodes[nid][0]!=parent:raise BackupError('分类父级与顺序记录不一致')
                seen_nodes.add(nid)
        if root_resources!=resources.keys() or seen_nodes!=nodes.keys()-{ROOT}:
            raise BackupError('表情库包含未归属的资源或分类')
        row=db.execute("SELECT value FROM library_meta WHERE key='library_id'").fetchone()
        if not row:raise BackupError('表情库缺少身份信息')
        try:uuid.UUID(row[0])
        except (ValueError,TypeError,AttributeError):raise BackupError('表情库身份信息无效')
        counts={t:db.execute('SELECT count(*) FROM "'+t.replace('"','""')+'"').fetchone()[0]
                for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return dict(library_id=row[0],tables=counts,missing=missing)


def snapshot_database(root, destination, control):
    with closing(sqlite3.connect((root/'index.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=.2)) as source:
        with closing(sqlite3.connect(destination)) as target:
            source.backup(target,pages=64,progress=lambda *_:control.checkpoint(),sleep=.05)
            target.execute('PRAGMA journal_mode=DELETE')


def digest_stream(stream, control, output=None):
    digest=hashlib.sha256();size=0
    while True:
        control.checkpoint()
        block=stream.read(CHUNK)
        if not block:break
        control.checkpoint(len(block))
        digest.update(block);size+=len(block)
        if output is not None:output.write(block)
    return digest.hexdigest(),size


def inspect_archive(archive, scratch, control, *, restore=None):
    """Full streaming verification; extract only DB unless restoring to staging."""
    scratch=Path(scratch);scratch.mkdir(parents=True,exist_ok=True)
    with shared_read(archive) as handle,zipfile.ZipFile(handle) as pack:
        infos=pack.infolist();names=[i.filename for i in infos]
        if len(names)!=len({n.casefold() for n in names}):raise BackupError('备份含有重复或冲突的路径')
        for item in infos:
            safe_relative(item.filename)
            if stat.S_ISLNK(item.external_attr>>16):raise BackupError('备份含有不支持的链接')
        if 'manifest.json' not in names or pack.getinfo('manifest.json').file_size>32*1024*1024:
            raise BackupError('备份清单缺失或过大')
        manifest=json.loads(pack.read('manifest.json'))
        if manifest.get('format')!=FORMAT or manifest.get('version')!=VERSION:raise BackupError('不支持此备份格式')
        files=manifest['files']
        expected={'manifest.json','configuration.json'}|{'library/'+safe_relative(n) for n in files}
        if set(names)!=expected:raise BackupError('备份文件与清单不一致')
        if pack.getinfo('configuration.json').file_size>1024*1024:raise BackupError('备份配置资料过大')
        configuration=json.loads(pack.read('configuration.json'))
        if configuration!=manifest['configuration']:raise BackupError('备份配置与清单不一致')
        database=None;total=sum(f['size'] for f in files.values());done=0
        for name,metadata in files.items():
            control.checkpoint()
            item=pack.getinfo('library/'+name)
            if not isinstance(metadata['size'],int) or metadata['size']<0 or item.file_size!=metadata['size']:
                raise BackupError('备份文件大小与清单不一致')
            if not isinstance(metadata['mtime_ns'],int):raise BackupError('备份文件时间信息无效')
            target=Path(restore)/name if restore is not None else scratch/'verify.sqlite3' if name=='index.sqlite3' else None
            if target is not None:
                target.parent.mkdir(parents=True,exist_ok=True)
            with pack.open(item) as source:
                if target is not None:
                    with target.open('xb') as out:digest,size=digest_stream(source,control,out)
                else:digest,size=digest_stream(source,control)
            if size!=metadata['size'] or digest!=metadata['sha256']:raise BackupError('备份文件校验失败，归档可能已损坏')
            if target is not None:
                os.utime(target,ns=(metadata['mtime_ns'],metadata['mtime_ns']))
                if target.stat().st_mtime_ns!=metadata['mtime_ns']:raise BackupError('目标文件系统无法精确恢复文件时间')
                if restore is not None:
                    # Verify the actual destination, not just the bytes read
                    # from the archive on their way to the output stream.
                    with shared_read(target) as copied:output_hash,output_size=digest_stream(copied,control)
                    if output_size!=size or output_hash!=digest:raise BackupError('恢复后的文件校验失败，未提交新表情库')
            if name=='index.sqlite3':database=target
            done+=size;control.progress('verify' if restore is None else 'restore',done,total)
        if database is None:raise BackupError('备份中没有表情库数据库')
        details=validate_database(database,files,control)
        if details!=manifest['database']:raise BackupError('数据库记录与备份清单不一致')
        return manifest


def create_backup(job, control):
    root=Path(job['library']).resolve();folder=output_directory(root,job.get('destination',''))
    folder.mkdir(parents=True,exist_ok=True)
    token=job['id'];work=Path(job['work']).resolve();work.mkdir(parents=True,exist_ok=True)
    control.progress('inventory',0,0)
    initial=inventory(root,control)
    snapshot=work/'snapshot.sqlite3'
    snapshot_database(root,snapshot,control)
    if inventory(root,control)!=initial:raise LibraryChanged('备份准备期间文件已变化，等待空闲后重试')
    database=validate_database(snapshot,initial,control)
    total=sum(v[2] for v in initial.values())+snapshot.stat().st_size
    check_space(folder,total+max(16*1024*1024,len(initial)*1024))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem='Nekori-'+uuid.UUID(database['library_id']).hex+'-'+stamp+'-'+token
    final=folder/(stem+'.nekori-backup.zip');partial=final.with_name(final.name+'.part')
    manifest=dict(format=FORMAT,version=VERSION,created_at=utc_now(),job_id=token,
                  database=database,configuration={k:v for k,v in job.get('configuration',{}).items() if k in CONFIG_KEYS},files={})
    all_files={**initial,'index.sqlite3':fingerprint(snapshot)};done=0
    try:
        with partial.open('xb') as raw:
            with zipfile.ZipFile(raw,'w',allowZip64=True) as pack:
                for name,version in all_files.items():
                    control.checkpoint();path=snapshot if name=='index.sqlite3' else root/name
                    info=zipfile.ZipInfo('library/'+name)
                    info.compress_type=zipfile.ZIP_STORED if Path(name).suffix.lower() in MEDIA else zipfile.ZIP_DEFLATED
                    info._compresslevel=6
                    with shared_read(path) as source:
                        if fingerprint(path,source)!=version:raise LibraryChanged('备份期间文件已变化，等待空闲后重试')
                        with pack.open(info,'w',force_zip64=True) as dest:digest,size=digest_stream(source,control,dest)
                        if fingerprint(path,source)!=version or fingerprint(path)!=version:
                            raise LibraryChanged('备份期间文件已变化，等待空闲后重试')
                    manifest['files'][name]=dict(size=size,sha256=digest,mtime_ns=version[3])
                    done+=size;control.progress('archive',done,total)
                pack.writestr('configuration.json',json.dumps(manifest['configuration'],ensure_ascii=False))
                pack.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
            raw.flush();os.fsync(raw.fileno())
        inspect_archive(partial,work/'verification',control)
        if inventory(root,control)!=initial:raise LibraryChanged('备份期间文件已变化，等待空闲后重试')
        control.checkpoint()
        # Windows rename refuses an existing destination, unlike os.replace.
        if final.exists():raise BackupError('备份文件名已存在，未覆盖原文件')
        os.rename(partial,final)
        receipt=dict(committed=True,job_id=token,library_id=database['library_id'],location=str(final),
                     bytes=final.stat().st_size,completed_at=utc_now(),files=len(all_files),database=database)
        atomic_json(final.with_name(final.name+'.valid.json'),receipt)
        atomic_json(work/'result.json',receipt)
        prune_backups(folder,database['library_id'],max(1,int(job.get('keep',5))),final)
        return receipt
    except BaseException:
        try:
            if partial.exists():partial.unlink()
        except OSError:pass  # Identifiable .part, never a valid committed backup.
        raise


def prune_backups(folder, library_id, keep, newest):
    valid=[]
    for marker in folder.glob('Nekori-*.nekori-backup.zip.valid.json'):
        try:
            record=json.loads(marker.read_text('utf-8'));archive=folder/marker.name[:-len('.valid.json')]
            if not isinstance(record,dict):continue
            if record.get('committed') and record.get('library_id')==library_id and record.get('location')==str(archive) and archive.stat().st_size==record['bytes']:
                valid.append((record['completed_at'],archive,marker))
        except (OSError,ValueError,KeyError):continue
    for _,archive,marker in sorted(valid,reverse=True)[keep:]:
        if archive==newest:continue
        try:archive.unlink();marker.unlink()
        except OSError:pass  # Retention never invalidates a newly verified backup.


def restore_backup(job, control):
    archive=Path(job['archive']).resolve();target=Path(job['target']).resolve();source=Path(job['library']).resolve()
    if target==source or target.is_relative_to(source) or source.is_relative_to(target):
        raise BackupError('请恢复到独立的新目录，不要覆盖当前表情库')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):raise BackupError('恢复目标必须是空目录')
    target.parent.mkdir(parents=True,exist_ok=True)
    work=Path(job['work']);work.mkdir(parents=True,exist_ok=True)
    with shared_read(archive) as handle,zipfile.ZipFile(handle) as pack:
        check_space(target.parent,sum(i.file_size for i in pack.infolist()))
    staging=target.with_name('.'+target.name+'.'+job['id']+'.restore.part')
    staging.mkdir()  # Never reuses or clears an existing directory.
    try:
        manifest=inspect_archive(archive,work/'verification',control,restore=staging)
        atomic_json(staging/'backup-settings.json',manifest['configuration'])
        control.checkpoint()
        if target.exists():target.rmdir()  # Fails if another writer populated it.
        os.rename(staging,target)
        result=dict(committed=True,job_id=job['id'],location=str(target),completed_at=utc_now(),
                    database=manifest['database'],files=len(manifest['files']))
        atomic_json(work/'result.json',result)
        return result
    except BaseException:
        # Explicitly owned staging only; keep failed restore evidence identifiable.
        raise
