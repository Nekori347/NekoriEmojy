"""Reset only a verified private performance case, preserving all original files.

Run after the preceding isolated test process exits. Newly created experiment
files are moved outside images before restoring the catalog; otherwise they
become orphan inputs to the next deduplication scan.
"""
import argparse,json,sqlite3,time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--root',required=True)
root=Path(p.parse_args().root).resolve()
summary=root/'snapshot-summary.json';catalog=root/'catalog-comparison.sqlite3'
assert summary.is_file() and catalog.is_file() and root.name=='real-library-perf'
library=(root/'library').resolve();assert library.parent==root
with sqlite3.connect(f'{catalog.as_uri()}?mode=ro',uri=True) as clean:
    assert clean.execute('SELECT count(*) FROM resources').fetchone()[0]==4175
    known={r[0] for r in clean.execute('SELECT filename FROM resources')}
    cutoff=summary.stat().st_mtime+10
    extras=[f for f in (library/'images').iterdir()
            if f.is_file() and f.name not in known and f.stat().st_birthtime>cutoff]
    if extras:
        destination=root/'experiment-kept-files'/str(time.time_ns());destination.mkdir(parents=True)
        for f in extras:f.rename(destination/f.name)
    with sqlite3.connect(library/'index.sqlite3') as db:
        clean.backup(db)
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print(json.dumps(dict(resources=4175,quarantined=len(extras),integrity='ok')))
