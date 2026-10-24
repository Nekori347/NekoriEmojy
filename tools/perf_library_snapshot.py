"""Read-only live SQLite snapshot + one private performance copy; no app imports.

Usage: python tools/perf_library_snapshot.py SOURCE NEW_DESTINATION
Reports contain aggregate counts, never resource names/content. Does not promise
filesystem atomicity: verifies catalog file size/mtime before and after copying.
"""
import collections
import json
import shutil
import sqlite3
import sys
from pathlib import Path


def snapshot(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if target.exists() or source == target or target.is_relative_to(source):
        raise ValueError('Destination must be a new directory outside source')
    files = [p for p in source.rglob('*') if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    if shutil.disk_usage(target.parent).free < size + 512 * 1024**2:
        raise RuntimeError('Insufficient free space')
    target.mkdir()
    with sqlite3.connect((source/'index.sqlite3').as_uri()+'?mode=ro', uri=True) as db:
        with sqlite3.connect(target/'index.sqlite3') as backup:
            db.backup(backup, pages=256)
    with sqlite3.connect(target/'index.sqlite3') as db:
        records = list(db.execute('SELECT id, relative_path FROM resources'))
        counts = {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                  for table in ('resources', 'nodes', 'content')}
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    stamps = {}
    missing = 0
    for identity, relative in records:
        path = (source/relative).resolve()
        if not path.is_relative_to(source):
            raise ValueError('Catalog path escapes source')
        try:
            st = path.stat(); stamps[identity] = (relative, st.st_size, st.st_mtime_ns)
        except FileNotFoundError:
            missing += 1
    # Never copy a live SQLite/WAL/SHM file over the consistent online backup.
    formats, byte_counts = collections.Counter(), collections.Counter()
    for path in files:
        relative = path.relative_to(source)
        if relative.parts[0] in ('index.sqlite3', 'index.sqlite3-wal', 'index.sqlite3-shm'):
            continue
        dest = target/relative; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        formats[path.suffix.lower()] += 1; byte_counts[path.suffix.lower()] += dest.stat().st_size
    changed = unavailable = 0
    for relative, length, modified in stamps.values():
        try:
            now = (source/relative).stat(); copied = (target/relative).stat()
            changed += (now.st_size, now.st_mtime_ns) != (length, modified)
            unavailable += copied.st_size != length
        except FileNotFoundError:
            unavailable += 1
    result = dict(catalog=counts, integrity=integrity, source_missing=missing,
                  changed_during_copy=changed, copy_unavailable=unavailable,
                  files=dict(formats), bytes=dict(byte_counts), total_source_bytes=size,
                  method='SQLite mode=ro online backup; file copy2; catalog identity/size/mtime verification')
    (target.parent/'snapshot-summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    if integrity != 'ok' or changed or unavailable:
        raise RuntimeError('Snapshot verification failed; see private summary')
    return result


def inventory(target):
    """Private aliases/selection plan plus aggregate report, no image export."""
    from PIL import Image
    target=Path(target).resolve();meta={};groups=collections.defaultdict(list)
    with sqlite3.connect(target/'index.sqlite3') as db:
        rows=list(db.execute('SELECT id,relative_path FROM resources'))
        for identity,relative in rows:
            path=target/relative
            with Image.open(path) as im:
                meta[identity]=dict(id=identity,relative=relative,fmt=im.format,w=im.width,h=im.height,bytes=path.stat().st_size)
        for node,identity in db.execute("SELECT parent_id,resource_id FROM content WHERE resource_id IS NOT NULL AND parent_id!='__library__'"):
            if identity in meta:groups[node].append(meta[identity])
    largest=sorted((v for v in meta.values() if v['fmt']=='GIF'),key=lambda v:v['bytes'],reverse=True)[:12]
    for row in largest:
        with Image.open(target/row['relative']) as im:row['frames']=im.n_frames
    static=max(groups,key=lambda n:sum(m['fmt']=='PNG' for m in groups[n]))
    animated=max((n for n in groups if len(groups[n])>=30),key=lambda n:(sum(m['fmt']=='GIF' for m in groups[n])/len(groups[n]),len(groups[n])),default=static)
    plan=dict(static=static,animated=animated,largest=largest,resources=meta)
    (target.parent/'private-plan.json').write_text(json.dumps(plan),encoding='utf-8')
    with sqlite3.connect(target/'index.sqlite3') as source,sqlite3.connect(target.parent/'catalog-comparison.sqlite3') as db:source.backup(db)
    counts=collections.Counter(m['fmt'] for m in meta.values())
    summary=dict(resources=len(meta),formats=dict(counts),largest=[{k:m[k] for k in ('fmt','w','h','bytes','frames')} for m in largest])
    (target.parent/'inventory.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


if __name__ == '__main__':
    print(json.dumps(snapshot(*sys.argv[1:3])))
    if '--inventory' in sys.argv:print(json.dumps(inventory(sys.argv[2])))
