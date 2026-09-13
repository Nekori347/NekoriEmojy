"""Copy-only import commits and bounded input adapters, shared by every UI entry."""
from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import time
import uuid
from services.identity import IdentityIndex, inspect_bytes, put_identity
from services.library import LibraryError, read_db
from services.diagnostics import event

MAX_INPUT_BYTES = 128 * 1024 * 1024


def add_relations(conn, filenames, category):
    if not category or category in ('全部表情', '未分类'):
        return 0
    conn.execute('''INSERT OR IGNORE INTO categories.categories(name,sort_order)
        VALUES (?, (SELECT COALESCE(MAX(sort_order),-1)+1 FROM categories.categories))''', (category,))
    count = 0
    for filename in dict.fromkeys(filenames):
        count += conn.execute('INSERT OR IGNORE INTO categories.category_images VALUES (?,?)', (category, filename)).rowcount
    return count


def promote(conn, filename):
    conn.execute('''INSERT INTO "order".item_orders(image_path,sort_order)
        VALUES (?, (SELECT COALESCE(MIN(sort_order),0)-1 FROM "order".item_orders))
        ON CONFLICT(image_path) DO UPDATE SET sort_order=excluded.sort_order''', (filename,))


def _finish_pending(conn, rid):
    row = conn.execute('''SELECT j.image_path,j.category,r.file_md5
        FROM import_journal j JOIN features.resource_identity r USING(resource_id)
        WHERE j.resource_id=?''', (rid,)).fetchone()
    if row is None:
        raise LibraryError('导入恢复记录缺失。')
    name, category, md5 = row
    conn.execute('INSERT INTO features.image_features(image_path,md5) VALUES (?,?)', (name, md5))
    conn.execute('INSERT INTO metadata.image_metadata(image_path,keywords) VALUES (?,?)', (name, ''))
    promote(conn, name)
    add_relations(conn, [name], category)
    conn.execute("UPDATE features.resource_identity SET state='ready' WHERE resource_id=?", (rid,))
    conn.execute('DELETE FROM import_journal WHERE resource_id=?', (rid,))


def commit_image(context, data, extension, category=None):
    """Caller owns context lock. Only tool-created staging/final files are removed."""
    started = time.perf_counter()
    identity = inspect_bytes(data)
    index = IdentityIndex(context)
    existing = index.find(identity)
    if existing is not None:
        with context.transaction() as conn:
            promote(conn, existing.name)
            add_relations(conn, [existing.name], category)
        event('import.committed', status='duplicate', elapsed_ms=round((time.perf_counter()-started)*1000, 2), count={'scanned_library': 0})
        return str(existing), True
    rid = uuid.uuid4().hex
    name = rid + extension
    destination = context.resource(name)
    stage_dir = context.data_dir / 'cache/imports'
    stage_dir.mkdir(parents=True, exist_ok=True)
    stage = stage_dir / (rid + '.part')
    committed = False
    try:
        with stage.open('xb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        with context.transaction() as conn:
            put_identity(conn, destination, identity, resource_id=rid, state='pending', mtime_ns=stage.stat().st_mtime_ns)
            conn.execute('INSERT INTO import_journal VALUES (?,?,?)', (rid, name, category))
        # UUID filename; rename refuses to overwrite an existing file on Windows.
        if destination.exists():
            raise LibraryError('导入文件名冲突，请重试。')
        stage.rename(destination)
        with context.transaction() as conn:
            _finish_pending(conn, rid)
        committed = True
    finally:
        if not committed:
            # A normal exception is rolled back now; a terminated process leaves
            # the journal so recover_imports can finish on its original library.
            with context.transaction() as conn:
                row = conn.execute('SELECT state FROM features.resource_identity WHERE resource_id=?', (rid,)).fetchone()
                if row and row[0] == 'pending':
                    if destination.exists() and hashlib.md5(destination.read_bytes()).hexdigest() == identity.file_md5:
                        destination.unlink()
                    conn.execute('DELETE FROM features.resource_identity WHERE resource_id=?', (rid,))
                    conn.execute('DELETE FROM import_journal WHERE resource_id=?', (rid,))
            if stage.exists():
                stage.unlink()
    event('import.committed', status='saved', elapsed_ms=round((time.perf_counter()-started)*1000, 2), count={'scanned_library': 0, 'bytes': len(data)})
    return str(destination), False


def recover_imports(context):
    """Recover just durable pending operations, never enumerate/hash the library."""
    with context.lock, read_db(context.db('library')) as conn:
        rows = conn.execute('SELECT resource_id,image_path FROM import_journal').fetchall()
    recovered = 0
    for rid, name in rows:
        if uuid.UUID(rid).hex != rid:
            raise LibraryError('导入恢复标识无效。')
        with context.lock:
            destination = context.resource(name)
            stage = context.data_dir / 'cache/imports' / (rid + '.part')
            source = destination if destination.exists() else stage
            if not source.is_file():
                # Retain evidence; explicit retry can report this failed operation.
                continue
            data = source.read_bytes()
            with read_db(context.db('features')) as conn:
                expected = conn.execute('SELECT file_md5 FROM resource_identity WHERE resource_id=?', (rid,)).fetchone()
            if not expected or hashlib.md5(data).hexdigest() != expected[0]:
                continue
            if source == stage:
                stage.rename(destination)
            with context.transaction() as conn:
                _finish_pending(conn, rid)
            recovered += 1
    return recovered


@dataclass(frozen=True)
class ImportInput:
    kind: str
    value: object


def fetch_image(url):
    """Fetch an image response only. No page scraping or reliance on URL suffix."""
    from urllib.parse import urlparse, unquote_to_bytes
    import urllib.request
    import base64
    if url.startswith('data:image/'):
        header, payload = url.split(',', 1)
        if len(payload) > MAX_INPUT_BYTES * 2:
            raise LibraryError('图片超过 128 MiB 导入上限。')
        data = base64.b64decode(payload, validate=True) if header.endswith(';base64') else unquote_to_bytes(payload)
    else:
        if urlparse(url).scheme not in ('http', 'https'):
            raise LibraryError('这个图片链接无法直接获取，请使用复制图片或本地文件。')
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 NekoriEmojy'})
        started = time.monotonic()
        with urllib.request.urlopen(request, timeout=15) as response:
            if urlparse(response.geturl()).scheme not in ('http', 'https'):
                raise LibraryError('图片链接重定向到不支持的位置。')
            chunks, length = [], 0
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                if length > MAX_INPUT_BYTES or time.monotonic() - started > 60:
                    raise LibraryError('图片过大或获取超时，请改用本地文件。')
                chunks.append(chunk)
            data = b''.join(chunks)
    if len(data) > MAX_INPUT_BYTES:
        raise LibraryError('图片超过 128 MiB 导入上限。')
    return data


class ImportPipeline:
    def __init__(self, storage):
        self.storage = storage

    def run(self, inputs, category=None, progress=lambda done, total: None, *, inbox=False):
        counts = {'saved': 0, 'duplicate': 0, 'failed': 0}
        self.errors = []
        session = self.storage.session
        with (session.task() if session else nullcontext()):
            for i, source in enumerate(inputs):
                before = None
                try:
                    if source.kind == 'file':
                        path = Path(source.value)
                        before = path.stat()
                        if before.st_size > MAX_INPUT_BYTES:
                            raise LibraryError('图片超过 128 MiB 导入上限。')
                        with path.open('rb') as stream:
                            data = stream.read(MAX_INPUT_BYTES + 1)
                        if len(data) > MAX_INPUT_BYTES:
                            raise LibraryError('图片超过 128 MiB 导入上限。')
                        after = path.stat()
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            raise LibraryError('源文件正在写入，请稍后重试。')
                        with self.storage.lock:
                            saved, duplicate = self.storage._standardize_and_save(data, '', target_category=category)
                    elif source.kind == 'image':
                        saved, duplicate = self.storage.save_image(source.value, target_category=category)
                    elif source.kind == 'url':
                        data = fetch_image(str(source.value))
                        with self.storage.lock:
                            saved, duplicate = self.storage._standardize_and_save(data, '', target_category=category)
                    else:
                        raise LibraryError('没有可导入的图片载荷。')
                    if not saved:
                        raise LibraryError('图片无法解码或保存；原文件已保留。')
                    outcome = 'duplicate' if duplicate else 'saved'
                    counts[outcome] += 1
                except Exception as exc:
                    outcome = 'failed'
                    saved = None
                    counts['failed'] += 1
                    self.errors.append(type(exc).__name__)
                    event('import.failed', level='warning', stage=source.kind, error=exc)
                if inbox and before is not None:
                    try:
                        key = hashlib.sha256(os.path.normcase(os.path.abspath(source.value)).encode()).hexdigest()
                        with self.storage.context.transaction() as conn:
                            conn.execute("""INSERT OR REPLACE INTO import_sources VALUES (?,?,?,?,
                                (SELECT resource_id FROM features.resource_identity WHERE image_path=?))""",
                                (key, before.st_size, before.st_mtime_ns, outcome, Path(saved).name if saved else ''))
                    except Exception as exc:
                        event('import.inbox_receipt_failed', level='warning', error=exc)
                try:
                    progress(i + 1, len(inputs))
                except Exception as exc:
                    event('import.notification_failed', level='warning', error=exc)
        return counts

def recover_deletions(context):
    with context.lock, read_db(context.db('library')) as conn:
        rows = conn.execute('SELECT id,image_path,state FROM delete_journal').fetchall()
    for op_id, name, state in rows:
        if uuid.UUID(op_id).hex != op_id or state not in ('prepared', 'committed'):
            raise LibraryError('删除恢复标识无效。')
        original = context.resource(name)
        staged = context.data_dir / 'cache/deletions' / op_id
        with context.lock:
            if state == 'prepared':
                if staged.exists():
                    if original.exists():
                        continue  # External conflict: preserve both, never overwrite.
                    staged.rename(original)
            elif staged.exists():
                staged.unlink()
            with context.transaction() as conn:
                conn.execute('DELETE FROM delete_journal WHERE id=?', (op_id,))


def delete_resources(context, filepaths, progress=None, cancel=None):
    names = list(dict.fromkeys(context.resource(path).name for path in filepaths))
    result = dict(requested=len(names), deleted=0, missing_cleaned=0, failed=0, cancelled=0, unprocessed=0, failure_details={})
    stage_dir = context.data_dir / 'cache/deletions'
    stage_dir.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(names), 50):
        if cancel and cancel():
            result['cancelled'] = result['unprocessed'] = len(names) - offset
            break
        chunk = [(uuid.uuid4().hex, name, context.resource(name).is_file()) for name in names[offset:offset+50]]
        committed = False
        try:
            with context.transaction() as conn:
                conn.executemany("INSERT INTO delete_journal VALUES (?,?,'prepared')", [(op_id,name) for op_id,name,_ in chunk])
            for op_id, name, exists in chunk:
                if exists:
                    context.resource(name).rename(stage_dir / op_id)
            with context.transaction() as conn:
                for op_id, name, exists in chunk:
                    for table in ('features.image_features','features.resource_identity','metadata.image_metadata',
                                  'categories.category_images','"order".item_orders','recent.recent_history'):
                        conn.execute(f'DELETE FROM {table} WHERE image_path=?', (name,))
                    conn.execute('UPDATE categories.categories SET icon_path=NULL WHERE icon_path=?', (name,))
                    conn.execute("UPDATE delete_journal SET state='committed' WHERE id=?", (op_id,))
            committed = True
            result['deleted'] += sum(exists for _,_,exists in chunk)
            result['missing_cleaned'] += sum(not exists for _,_,exists in chunk)
        except Exception as exc:
            result['failed'] += len(chunk)
            for _, name, _ in chunk:
                result['failure_details'][name] = type(exc).__name__
        finally:
            try:
                recover_deletions(context)
            except OSError as exc:
                # A committed delete can retain a tool-owned trash file for retry.
                event('import.delete_cleanup_pending', level='warning', error=exc)
        if progress:
            progress(min(offset+50, len(names)), len(names))
    return result
