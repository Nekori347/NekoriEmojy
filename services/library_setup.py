"""Read-only library identification and confirm-time initialization.

No first-run flag: a usable existing catalog is the authority. Only new,
empty targets belong to the rollback below; existing library data is never removed.
"""
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager,closing
from pathlib import Path


class LibraryLocationError(ValueError):
    pass


NOT_LIBRARY = '未找到 Nekori 表情库。\n可以将其中的表情导入现有表情库，或选择其他目录。'
NOT_EMPTY = '此目录已有其他文件。请选择空目录，或连接已有表情库。'


@contextmanager
def read_database(path):
    # A source WAL is copied so SQLite cannot create/update source SHM files.
    with tempfile.TemporaryDirectory(prefix='nekori-library-check-') as temporary:
        wal=Path(str(path)+'-wal');source=path
        if wal.exists():
            source=Path(temporary)/path.name;shutil.copyfile(path,source)
            shutil.copyfile(wal,Path(str(source)+'-wal'))
            uri=source.as_uri()+'?mode=ro'
        else:uri=path.as_uri()+'?mode=ro&immutable=1'
        with closing(sqlite3.connect(uri,uri=True)) as db:yield db


def identify_library(directory):
    """Recognize supported catalogs without opening a source DB for writing."""
    root=Path(directory).expanduser().resolve()
    if not root.is_dir():raise LibraryLocationError(NOT_LIBRARY)
    path=root/'index.sqlite3'
    if path.is_file():
        try:
            with read_database(path) as db:
                version=db.execute('PRAGMA user_version').fetchone()[0]
                from services.library_index import SCHEMA_VERSION,ROOT
                if version not in (0,1,2,SCHEMA_VERSION):
                    raise LibraryLocationError('此表情库的版本暂不受支持。请使用兼容的 Nekori 版本。')
                columns={r[1] for r in db.execute('PRAGMA table_info(resources)')}
                if not {'id','filename','relative_path','display_name','tags','ocr_text','metadata_json','status','created_at'}<=columns:
                    raise LibraryLocationError(NOT_LIBRARY)
                if version==SCHEMA_VERSION:
                    if not db.execute("SELECT value FROM library_meta WHERE key='library_id'").fetchone():raise LibraryLocationError(NOT_LIBRARY)
                    if not db.execute('SELECT id FROM nodes WHERE id=?',(ROOT,)).fetchone():raise LibraryLocationError(NOT_LIBRARY)
                    for table in ('content','recent'):db.execute('SELECT * FROM '+table+' LIMIT 0')
                return 'catalog'
        except sqlite3.Error as error:raise LibraryLocationError(NOT_LIBRARY) from error
    # The existing internal-adoption format predates index.sqlite3. Require its
    # complete, typed metadata set, never merely an images directory.
    if (root/'images').is_dir():
        try:
            categories=json.loads((root/'categories.json').read_text('utf-8'))
            order=json.loads((root/'order.json').read_text('utf-8'))
            metadata=json.loads((root/'metadata.json').read_text('utf-8'))
            if (isinstance(categories,dict) and all(isinstance(k,str) and isinstance(v,list) and all(isinstance(p,str) for p in v) for k,v in categories.items())
                    and isinstance(order,list) and all(isinstance(p,str) for p in order)
                    and isinstance(metadata,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in metadata.items())):
                return 'legacy'
        except (OSError,ValueError):pass
        try:
            expected={'order.db': ['SELECT image_path FROM item_orders ORDER BY sort_order'],
                      'categories.db': ['SELECT name,sort_order,id,icon_path FROM categories','SELECT category_name,image_path FROM category_images'],
                      'metadata.db': ['SELECT image_path,keywords FROM image_metadata']}
            if all((root/name).is_file() for name in expected):
                for name,queries in expected.items():
                    with read_database(root/name) as db:
                        for query in queries:db.execute(query+' LIMIT 0')
                return 'legacy'
        except (OSError,sqlite3.Error):pass
    raise LibraryLocationError(NOT_LIBRARY)


def check_target(directory,mode):
    root=Path(directory).expanduser().resolve()
    if mode=='connect':identify_library(root);return 'connect'
    if mode!='create':raise ValueError(mode)
    if root.exists():
        if not root.is_dir():raise LibraryLocationError(NOT_EMPTY)
        if any(root.iterdir()):
            identify_library(root)
            return 'connect'
    return 'create'


@contextmanager
def prepare_library(directory,mode,config):
    """Initialize after confirmation; undo only this call's new empty target."""
    from services.storage import StorageService
    root=Path(directory).expanduser().resolve();mode=check_target(root,mode)
    created_dirs=[];owned_index=False
    new_subdirs=[path for path in (root/'inbox/failed',root/'inbox',root/'images') if not path.exists()]
    try:
        if mode=='create':
            parent=root
            while not parent.exists():created_dirs.append(parent);parent=parent.parent
            root.mkdir(parents=True,exist_ok=True)
        if mode=='create' or not (root/'index.sqlite3').exists():
            # Also own the new index when adopting supported legacy metadata;
            # its pre-existing files and directories never belong to rollback.
            fd=os.open(root/'index.sqlite3',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.close(fd);owned_index=True
        storage=StorageService(library_path=root,config=config)
        # Includes the FeatureDB initialization which historically logs errors.
        with storage.index.connect(search=False) as db:db.execute('SELECT image_path FROM image_features LIMIT 0')
        yield storage
    except Exception:
        if owned_index:
            for name in ('index.sqlite3-wal','index.sqlite3-shm','index.sqlite3'):
                try:(root/name).unlink(missing_ok=True)
                except OSError:pass
            for path in new_subdirs:
                try:path.rmdir()
                except OSError:pass
        for path in created_dirs:
            try:path.rmdir()
            except OSError:pass
        raise


def commit_library(config,directory,mode):
    with prepare_library(directory,mode,config) as storage:
        values={**config.config,'library_path':storage.library_root}
        config._save_config(values)
        config.config.clear();config.config.update(values)
        return storage


def startup_location(config):
    """Return (path, needs_ui, recovery); never create a directory here."""
    from services.app_paths import selected_library
    root=selected_library(config)
    if config.load_error:return root,True,True
    try:
        identify_library(root)
        return root,not config.config_existed and not bool(os.environ.get('NEKORI_LIBRARY')),False
    except (OSError,ValueError):
        # Explicit automation/Demo roots may create empty isolated libraries.
        # A nonempty/corrupt root is never silently initialized, even in a Demo.
        if os.environ.get('NEKORI_LIBRARY') and not config.load_error:
            if not root.exists() or (root.is_dir() and not any(root.iterdir())):return root,False,False
        recovery=bool(config.get('library_path') or config.load_error or config.config_existed)
        return root,True,recovery
