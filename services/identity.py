"""Persistent, versioned identities. No full-library decoding on an import hit.

Pixel MD5 deliberately retains exchange v1's RGBA algorithm; width/height are
additional equality guards. Historical image_features.md5 is never assumed to
have these semantics. Library moves preserve IDs, revisions and valid indexes.
"""
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import uuid
from PIL import Image
from services.library import LibraryError, read_db

ALGORITHM_VERSION = 1


def create_schema(conn):
    conn.execute('''CREATE TABLE features.resource_identity (
        resource_id TEXT PRIMARY KEY, image_path TEXT UNIQUE NOT NULL,
        content_revision INTEGER NOT NULL DEFAULT 1,
        file_md5 TEXT, pixel_md5 TEXT, sync_key TEXT,
        byte_size INTEGER, mtime_ns INTEGER, width INTEGER, height INTEGER,
        format TEXT, animated INTEGER, algorithm_version INTEGER NOT NULL DEFAULT 1,
        state TEXT NOT NULL DEFAULT 'unindexed')''')
    conn.execute('CREATE INDEX features.identity_file ON resource_identity(file_md5, state)')
    conn.execute('CREATE INDEX features.identity_pixel ON resource_identity(pixel_md5, width, height, state)')
    conn.execute('CREATE INDEX features.identity_sync ON resource_identity(sync_key, state)')
    conn.execute('''CREATE TABLE import_journal (
        resource_id TEXT PRIMARY KEY, image_path TEXT NOT NULL, category TEXT)''')
    conn.execute('''CREATE TABLE import_sources (
        source_key TEXT PRIMARY KEY, byte_size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
        outcome TEXT NOT NULL, resource_id TEXT)''')
    conn.execute('CREATE TABLE delete_journal (id TEXT PRIMARY KEY, image_path TEXT NOT NULL, state TEXT NOT NULL)')
    conn.execute('CREATE INDEX "order".order_sort ON item_orders(sort_order)')
    # SQL only. Unknown bytes are not guessed from the old ambiguous MD5 field.
    names = conn.execute('''SELECT image_path FROM features.image_features
        UNION SELECT image_path FROM "order".item_orders
        UNION SELECT image_path FROM metadata.image_metadata
        UNION SELECT image_path FROM categories.category_images''').fetchall()
    conn.executemany('INSERT INTO features.resource_identity(resource_id,image_path) VALUES (?,?)',
                     [(uuid.uuid4().hex, row[0]) for row in names])


@dataclass(frozen=True)
class Identity:
    file_md5: str
    pixel_md5: str | None
    sync_key: str
    byte_size: int
    width: int
    height: int
    format: str
    animated: bool


def inspect_bytes(data):
    with Image.open(io.BytesIO(data)) as img:
        fmt = img.format
        animated = getattr(img, 'n_frames', 1) > 1
        width, height = img.size
        if width <= 0 or height <= 0:
            raise LibraryError('图片尺寸无效。')
        pixel = None if animated else hashlib.md5(img.convert('RGBA').tobytes()).hexdigest()
        # Decode at least the current frame to reject truncated input.
        img.load()
    file_md5 = hashlib.md5(data).hexdigest()
    # GIF v1 sync keys always mean file bytes, including single-frame GIFs.
    sync = f'p:{pixel}' if fmt == 'PNG' and pixel else f'f:{file_md5}'
    return Identity(file_md5, pixel, sync, len(data), width, height, fmt, animated)


def put_identity(conn, path, identity, *, resource_id=None, state='ready', mtime_ns=None):
    path = Path(path)
    old = conn.execute('SELECT resource_id, content_revision, file_md5 FROM features.resource_identity WHERE image_path=?', (path.name,)).fetchone()
    rid = old[0] if old else resource_id or uuid.uuid4().hex
    changed = bool(old and old[2] and old[2] != identity.file_md5)
    revision = old[1] + int(changed) if old else 1
    if changed:
        conn.execute("UPDATE features.image_features SET dhash=NULL,phash=NULL WHERE image_path=?", (path.name,))
    conn.execute('''INSERT INTO features.resource_identity
        (resource_id,image_path,content_revision,file_md5,pixel_md5,sync_key,byte_size,
         mtime_ns,width,height,format,animated,algorithm_version,state)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(image_path) DO UPDATE SET
        content_revision=excluded.content_revision,file_md5=excluded.file_md5,
        pixel_md5=excluded.pixel_md5,sync_key=excluded.sync_key,byte_size=excluded.byte_size,
        mtime_ns=excluded.mtime_ns,width=excluded.width,height=excluded.height,
        format=excluded.format,animated=excluded.animated,
        algorithm_version=excluded.algorithm_version,state=excluded.state''',
        (rid,path.name,revision,identity.file_md5,identity.pixel_md5,identity.sync_key,
         identity.byte_size,path.stat().st_mtime_ns if mtime_ns is None else mtime_ns,
         identity.width,identity.height,identity.format,int(identity.animated),ALGORITHM_VERSION,state))
    return rid


class IdentityIndex:
    def __init__(self, context):
        self.context = context

    def _rows(self, sql, args=()):
        with read_db(self.context.db('features')) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, args)]

    def pending_count(self):
        return self._rows("SELECT COUNT(*) AS n FROM resource_identity WHERE state='unindexed'")[0]['n']

    def refresh(self, filename, *, force=False, connection=None):
        """Validate one candidate; replacements invalidate hashes and advance revision."""
        path = self.context.resource(filename)
        old = self._rows('SELECT * FROM resource_identity WHERE image_path=?', (path.name,))
        old = old[0] if old else None
        if not path.is_file():
            if connection is not None:
                connection.execute("UPDATE features.resource_identity SET state='missing' WHERE image_path=?", (path.name,))
            else:
                with self.context.transaction() as conn:
                    conn.execute("UPDATE features.resource_identity SET state='missing' WHERE image_path=?", (path.name,))
            return None
        stat = path.stat()
        if old and not force and old['state'] == 'ready' and old['algorithm_version'] == ALGORITHM_VERSION and (old['byte_size'], old['mtime_ns']) == (stat.st_size, stat.st_mtime_ns):
            return old
        data = path.read_bytes()
        identity = inspect_bytes(data)
        after = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise LibraryError('图片正在被其他程序修改，请稍后重试。')
        if connection is not None:
            put_identity(connection, path, identity)
            connection.execute('UPDATE features.image_features SET md5=? WHERE image_path=?', (identity.file_md5, path.name))
            return dict(file_md5=identity.file_md5, pixel_md5=identity.pixel_md5, width=identity.width, height=identity.height, image_path=path.name, sync_key=identity.sync_key)
        with self.context.transaction() as conn:
            put_identity(conn, path, identity)
            conn.execute('''INSERT INTO features.image_features(image_path,md5) VALUES (?,?)
                ON CONFLICT(image_path) DO UPDATE SET md5=excluded.md5''', (path.name, identity.file_md5))
        return self._rows('SELECT * FROM resource_identity WHERE image_path=?', (path.name,))[0]

    def find(self, identity, *, connection=None):
        rows = self._rows('''SELECT * FROM resource_identity WHERE state='ready' AND
            (file_md5=? OR (pixel_md5=? AND width=? AND height=? AND animated=0))
            ORDER BY image_path''', (identity.file_md5, identity.pixel_md5, identity.width, identity.height))
        for row in rows:
            try:
                current = self.refresh(row['image_path'], connection=connection)
            except (OSError, ValueError):
                current = None
            if current and (current['file_md5'] == identity.file_md5 or
                identity.pixel_md5 and current['pixel_md5'] == identity.pixel_md5 and
                (current['width'], current['height']) == (identity.width, identity.height)):
                return self.context.resource(current['image_path'])
        return None

    def complete_missing(self, cancel=lambda: False, progress=lambda done, total: None):
        """Explicit background repair of migration gaps; releases the lock per item.

        No reset of order, relations or metadata. Failed files remain visible and
        can be retried explicitly. Normal reopen with zero gaps performs no scan.
        """
        rows = self._rows("SELECT image_path FROM resource_identity WHERE state='unindexed'")
        for i, row in enumerate(rows):
            if cancel():
                break
            with self.context.lock:
                try:
                    self.refresh(row['image_path'])
                except Exception:
                    with self.context.transaction() as conn:
                        conn.execute("UPDATE features.resource_identity SET state='error' WHERE image_path=?", (row['image_path'],))
            progress(i + 1, len(rows))
        return len(rows)
