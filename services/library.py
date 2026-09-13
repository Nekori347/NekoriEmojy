"""Explicit library ownership, SQLite migrations and verified whole-library copies.

No function in this module discovers, repairs or initializes a missing library
implicitly. Application services retain the context they were constructed with.
"""
from contextlib import contextmanager, closing
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import uuid

FORMAT_VERSION = 1
SCHEMA_VERSION = 3
DATABASES = ("library", "features", "metadata", "categories", "order", "recent")
REQUIRED_TABLES = {"library": ("library_identity", "preferences", "schema_migrations"),
                   "features": ("image_features",), "metadata": ("image_metadata",),
                   "categories": ("categories", "category_images"), "order": ("item_orders",),
                   "recent": ("recent_history",)}


class LibraryError(RuntimeError):
    pass


class LibraryBusy(LibraryError):
    pass


def _notify(name, **fields):
    from services.diagnostics import event
    event(name, **fields)


def program_root():
    if getattr(sys, "frozen", False) or globals().get("__compiled__"):
        binary = Path(sys.executable).resolve().parent
        return binary.parent if binary.name.lower() == "bin" else binary
    return Path(__file__).resolve().parent.parent


def independent_root(path, application_root=None):
    root = Path(path).expanduser().resolve()
    application = Path(application_root or program_root()).resolve()
    # Reject both directions: copying an ancestor would include the program.
    if root.is_relative_to(application) or application.is_relative_to(root):
        raise LibraryError("资源库必须位于程序目录树之外，请选择独立文件夹。")
    return root


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def read_db(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        yield conn


def connect_existing(path):
    """An offline/deleted DB is an error; sqlite's implicit CREATE is forbidden."""
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=5)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True)
class LibraryContext:
    root: Path
    library_id: str
    # An instance identifies an open session as well as the portable library ID.
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    lock: object = field(default_factory=threading.RLock, compare=False, repr=False)

    @property
    def data_dir(self):
        return self.root / "data"

    @property
    def images_dir(self):
        return self.data_dir / "images"

    def db(self, name):
        if name not in DATABASES:
            raise ValueError("Unknown library database")
        return self.data_dir / (name + ".db")

    def resource(self, name):
        path = (self.images_dir / name).resolve()
        if not path.is_relative_to(self.images_dir.resolve()):
            raise LibraryError("资源引用越出当前库。")
        return path

    @contextmanager
    def transaction(self, *, creating=False):
        """Atomic SQL across retained databases; never enable WAL here."""
        uri = self.db("library").as_uri() + ("?mode=rwc" if creating else "?mode=rw")
        with self.lock, closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
            conn.execute("PRAGMA journal_mode=DELETE")
            for name in DATABASES[1:]:
                uri = self.db(name).as_uri() + ("?mode=rwc" if creating else "?mode=rw")
                conn.execute(f'ATTACH DATABASE ? AS "{name}"', (uri,))
                conn.execute(f'PRAGMA "{name}".journal_mode=DELETE')
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise


def _schema_one(conn, library_id):
    statements = (
        "CREATE TABLE library_identity (id TEXT PRIMARY KEY)",
        "CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE features.image_features (image_path TEXT PRIMARY KEY, md5 TEXT, dhash TEXT, phash TEXT, quality_score REAL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE metadata.image_metadata (image_path TEXT PRIMARY KEY, tags TEXT, keywords TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE categories.categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, icon_path TEXT, sort_order INTEGER DEFAULT 0)",
        "CREATE TABLE categories.category_images (category_name TEXT, image_path TEXT, PRIMARY KEY (category_name, image_path))",
        'CREATE TABLE "order".item_orders (image_path TEXT PRIMARY KEY, sort_order INTEGER NOT NULL)',
        "CREATE TABLE recent.recent_history (id INTEGER PRIMARY KEY AUTOINCREMENT, image_path TEXT UNIQUE NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
    )
    for sql in statements:
        conn.execute(sql)
    conn.execute("INSERT INTO library_identity VALUES (?)", (library_id,))


def _schema_two(conn, library_id):
    conn.execute("""CREATE TABLE migration_runs (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
        report_path TEXT NOT NULL, completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")


def _schema_three(conn, library_id):
    from services.identity import create_schema
    create_schema(conn)


MIGRATIONS = {1: _schema_one, 2: _schema_two, 3: _schema_three}


def _migrate(context, current, target=SCHEMA_VERSION):
    with context.transaction(creating=current == 0) as conn:
        for version in range(current + 1, target + 1):
            MIGRATIONS[version](conn, context.library_id)
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
            for name in ("main", *DATABASES[1:]):
                conn.execute(f'PRAGMA "{name}".user_version={version}')


def snapshot_databases(context, destination):
    """Caller must hold the application session's exclusive maintenance lease."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in DATABASES:
        target = destination / (name + ".db")
        with read_db(context.db(name)) as source, closing(sqlite3.connect(target)) as backup:
            source.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise LibraryError("数据库快照校验失败。")
        hashes[target.name] = digest(target)
    atomic_json(destination / "snapshot.json", {"library_id": context.library_id, "sha256": hashes})
    return destination


def create_library(path, application_root=None):
    root = independent_root(path, application_root)
    # The selected target may be an empty directory, but never an existing tree.
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise LibraryError("新资源库目标必须为空；已有库请使用“打开资源库”。")
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = root.with_name(root.name + ".creating-" + uuid.uuid4().hex)
    stage.mkdir()
    context = LibraryContext(stage, uuid.uuid4().hex)
    try:
        for name in ("images", "inbox/failed", "cache", "logs", "snapshots", "reports"):
            (context.data_dir / name).mkdir(parents=True)
        _migrate(context, 0)
        atomic_json(stage / "nekori-library.json", {"format": "NekoriEmojy", "version": FORMAT_VERSION,
                                                  "library_id": context.library_id})
        # Empty-target removal cannot remove any user files, even on Windows.
        if root.exists():
            root.rmdir()
        stage.rename(root)
        _notify("library.created", status="complete", count={"schema": SCHEMA_VERSION})
        return LibraryContext(root, context.library_id)
    except BaseException as exc:
        # Retain partial state for diagnosis/retry; it has no valid selected pointer.
        _notify("library.create_failed", level="error", error=exc)
        raise


def inspect_library(path, application_root=None):
    root = independent_root(path, application_root)
    try:
        marker = json.loads((root / "nekori-library.json").read_text(encoding="utf-8"))
        if marker["format"] != "NekoriEmojy" or marker["version"] != FORMAT_VERSION:
            raise LibraryError("不兼容的资源库格式，请使用对应版本程序。")
        identity = uuid.UUID(marker["library_id"]).hex
        context = LibraryContext(root, identity)
        # Exclude escaped inner paths, including junctions, before opening anything.
        for name in ("data", "data/images", *(f"data/{n}.db" for n in DATABASES)):
            child = root / name
            if not child.exists() or not child.resolve().is_relative_to(root):
                raise LibraryError("资源库文件缺失或路径越界，未创建空库。")
        versions = []
        for name in DATABASES:
            with read_db(context.db(name)) as conn:
                versions.append(conn.execute("PRAGMA user_version").fetchone()[0])
                # SQLite parses schema during open; no full image/index scan.
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not set(REQUIRED_TABLES[name]).issubset(tables):
                    raise LibraryError("资源库缺少必要数据表，请保留当前库并检查备份。")
                if versions[-1] >= 3:
                    needed = {"resource_identity"} if name == "features" else {"import_journal", "import_sources", "delete_journal"} if name == "library" else set()
                    if not needed.issubset(tables):
                        raise LibraryError("资源库索引或恢复记录缺失，请保留库并检查备份。")
                if name == "library" and conn.execute("SELECT id FROM library_identity").fetchone() != (identity,):
                    raise LibraryError("库标识与数据库不一致。")
        if len(set(versions)) != 1 or versions[0] < 1:
            raise LibraryError("数据库版本不一致，请保留当前库并检查升级前快照。")
        if versions[0] > SCHEMA_VERSION:
            raise LibraryError("资源库由较新版本创建，请更新程序；未修改此库。")
        return context, versions[0]
    except LibraryError:
        raise
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        raise LibraryError("资源库无法连接，请检查路径、权限或重新选择已有库；未创建空库。") from exc


class LibrarySession:
    """One process owns a library; maintenance excludes registered jobs/writes."""
    def __init__(self, context):
        self.context = context
        self._jobs = 0
        self._closed = False
        self._maintenance = False
        self._guard = threading.RLock()
        self._file = (context.root / ".nekori-session.lock").open("a+b")
        try:
            self._file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._file.close()
            raise LibraryBusy("该资源库正在被另一个 NekoriEmojy 实例使用。") from exc

    @contextmanager
    def task(self):
        with self._guard:
            if self._closed or self._maintenance:
                raise LibraryBusy("原资源库会话已结束，请重新操作。")
            self._jobs += 1
        try:
            yield self.context
        finally:
            with self._guard:
                self._jobs -= 1

    @contextmanager
    def maintenance(self):
        with self._guard:
            if self._closed or self._jobs or self._maintenance:
                raise LibraryBusy("请等待当前资源库任务结束后再切换或迁移。")
            self._maintenance = True
        try:
            with self.context.lock:
                yield self.context
        finally:
            with self._guard:
                self._maintenance = False

    def close(self):
        with self.maintenance():
            self._closed = True
            self._file.close()  # The OS releases the lock even after a process crash.


def open_library(path, application_root=None):
    try:
        context, version = inspect_library(path, application_root)
    except LibraryError as exc:
        _notify("library.open_failed", level="warning", error=exc)
        raise
    session = LibrarySession(context)
    try:
        if version < SCHEMA_VERSION:
            with session.maintenance():
                snapshot_databases(context, context.data_dir / "snapshots" / ("schema-" + uuid.uuid4().hex))
                _migrate(context, version)
                _notify("library.schema_upgraded", count={"from": version, "to": SCHEMA_VERSION}, status="complete")
        _notify("library.opened", count={"schema": SCHEMA_VERSION}, status="connected")
        return session
    except BaseException as exc:
        _notify("library.upgrade_failed", level="error", error=exc)
        session.close()
        raise


def copy_library(session, target, application_root=None):
    """Copy, verify, then return a new context. The source is never deleted."""
    target = independent_root(target, application_root)
    source = session.context.root
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise LibraryError("迁移目标不能与原库互相包含。")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise LibraryError("迁移目标必须为空，不能覆盖已有资源库。")
    stage = target.with_name(target.name + ".copying-" + uuid.uuid4().hex)
    with session.maintenance():
        stage.mkdir(parents=True)
        # Reject links instead of traversing into unrelated folders/drives.
        files = []
        for path in source.rglob("*"):
            if not path.resolve().is_relative_to(source) or path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise LibraryError("库内含链接路径，请先处理后再复制。")
            if path.is_file() and path.name != ".nekori-session.lock":
                files.append(path)
        snapshots = stage / ".database-snapshot"
        snapshot_databases(session.context, snapshots)
        checked = {}
        for path in files:
            relative = path.relative_to(source)
            if relative.parent == Path("data") and any(relative.name == n + ".db" or relative.name.startswith(n + ".db-") for n in DATABASES):
                continue
            dest = stage / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            before = digest(path)
            shutil.copy2(path, dest)
            if digest(dest) != before or digest(path) != before:
                raise LibraryError("复制期间源文件改变或目标校验失败，原库仍保留。")
            checked[relative.as_posix()] = before
        for name in DATABASES:
            dest = stage / "data" / (name + ".db")
            dest.parent.mkdir(parents=True, exist_ok=True)
            (snapshots / dest.name).replace(dest)
            checked[dest.relative_to(stage).as_posix()] = digest(dest)
        (snapshots / "snapshot.json").unlink()
        snapshots.rmdir()
        # Preserve empty categories/inbox/cache directories, too.
        for path in source.rglob("*"):
            if path.is_dir():
                (stage / path.relative_to(source)).mkdir(parents=True, exist_ok=True)
        inspect_library(stage, application_root)
        atomic_json(stage / "data/reports" / ("copy-" + uuid.uuid4().hex + ".json"),
                    {"kind": "whole_library_copy", "library_id": session.context.library_id,
                     "verified_files": len(checked), "sha256": checked, "source_retained": True})
        if target.exists():
            target.rmdir()
        stage.rename(target)
    return LibraryContext(target, session.context.library_id)


class BootstrapStore:
    """Expendable machine-local pointer; contains no library preferences."""
    def __init__(self, directory=None):
        base = directory or os.environ.get("NEKORI_BOOTSTRAP_DIR")
        if base is None:
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "NekoriEmojy"
        self.directory = Path(base).resolve()
        self.path = self.directory / "bootstrap.json"

    def recent(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value.get("recent_library")
        except (OSError, ValueError, AttributeError):
            return None

    def remember(self, context):
        self.directory.mkdir(parents=True, exist_ok=True)
        atomic_json(self.path, {"recent_library": str(context.root)})
