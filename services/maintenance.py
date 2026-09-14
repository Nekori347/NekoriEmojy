"""Explicit identity maintenance. It never resets human organization or deletes assets."""
from contextlib import nullcontext
from services.library import LibrarySession, read_db
from services.identity import IdentityIndex


def identity_report(library, *, repair=False, verify_all=False, progress=lambda done, total: None, cancel=lambda: False):
    session = library if isinstance(library, LibrarySession) else None
    context = session.context if session else library
    failed = 0
    with (session.task() if session else nullcontext()):
        index = IdentityIndex(context)
        if repair:
            query = "SELECT image_path FROM resource_identity WHERE state != 'pending'"
            if not verify_all:
                query += " AND state IN ('unindexed','error','missing')"
            rows = index._rows(query)
            for done, row in enumerate(rows, 1):
                if cancel():
                    break
                with context.lock:
                    try:
                        index.refresh(row['image_path'], force=verify_all)
                    except Exception:
                        failed += 1
                        with context.transaction() as conn:
                            conn.execute("UPDATE features.resource_identity SET state='error' WHERE image_path=?", (row['image_path'],))
                progress(done, len(rows))
        with read_db(context.db('features')) as conn:
            states = dict(conn.execute('SELECT state,COUNT(*) FROM resource_identity GROUP BY state'))
            keys = conn.execute("""SELECT COALESCE(pixel_md5,file_md5),width,height FROM resource_identity
                WHERE state='ready' GROUP BY COALESCE(pixel_md5,file_md5),width,height HAVING COUNT(*)>1""").fetchall()
            groups = [list(row[0] for row in conn.execute("""SELECT image_path FROM resource_identity
                WHERE state='ready' AND COALESCE(pixel_md5,file_md5)=? AND width=? AND height=? ORDER BY image_path""", key)) for key in keys]
        return {'states': states, 'duplicates': groups, 'failed': failed, 'cancelled': cancel()}


def similar_report(library, *, progress=lambda done, total: None, cancel=lambda: False):
    """Keep the upstream perceptual comparison as an explicit, non-destructive job."""
    from services.feature_db import FeatureDB
    from services.deduplicator import Deduplicator
    from services.hasher import extract_all_hashes
    session = library if isinstance(library, LibrarySession) else None
    context = session.context if session else library
    db = FeatureDB(context.db('features'))
    failed = 0
    with (session.task() if session else nullcontext()):
        index = IdentityIndex(context)
        rows = index._rows("SELECT image_path FROM resource_identity WHERE state!='pending'")
        valid = []
        for done, row in enumerate(rows, 1):
            if cancel():
                break
            name = row['image_path']
            with context.lock:
                try:
                    if index.refresh(name) is None:
                        continue
                    current = db.get_feature(name)
                    if not current or not current.get('phash') or not current.get('dhash'):
                        values = extract_all_hashes(context.resource(name))
                        if not values or not db.save_feature(name, values['md5'], values['dhash'], values['phash']):
                            failed += 1
                            continue
                    valid.append(name)
                except Exception:
                    failed += 1
            progress(done, len(rows))
        groups = Deduplicator(db).find_duplicate_groups(image_paths=valid, progress_callback=progress, cancel_callback=cancel)
        report = identity_report(library)
        report.update(duplicates=groups, kind='similar', failed=failed, cancelled=cancel())
        return report
