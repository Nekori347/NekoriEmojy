"""Small shared OCR provenance; no inference dependency in the base app."""
import json
from pathlib import Path

OCR_VERSION = 'rapidocr-3.10.0-ort-1.31.0-v6-small-layout1-frames1'


def source_stamp(index, record):
    path = Path(index.absolute_path(record))
    stat = path.stat()
    metadata = json.loads(record.get('metadata_json') or '{}')
    return dict(path=record['relative_path'],size=stat.st_size,mtime_ns=stat.st_mtime_ns,
                thumbnail=int(metadata.get('thumb_frame',0) or 0))
