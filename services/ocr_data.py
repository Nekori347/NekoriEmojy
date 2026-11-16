"""Small shared OCR provenance; no inference dependency in the base app."""
from pathlib import Path

OCR_VERSION = 'rapidocr-3.10.0-ort-1.31.0-v6-small-layout1-frames1'


def source_stamp(index, record):
    path = Path(index.absolute_path(record))
    stat = path.stat()
    return dict(path=record['relative_path'],size=stat.st_size,mtime_ns=stat.st_mtime_ns,
                thumbnail=index.representative_frame(record))
