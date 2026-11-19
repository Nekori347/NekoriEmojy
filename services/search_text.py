"""One cached search equivalence, shared by Gallery and Quick Panel.

Only the search projection is converted. Stored names, tags and OCR stay intact.
"""
from functools import lru_cache
import threading
from opencc import OpenCC

_converter = OpenCC('t2s')
_lock = threading.Lock()


@lru_cache(maxsize=16384)
def normalize_search(text):
    text = str(text or '').casefold()
    if text.isascii():
        return text
    with _lock:
        return _converter.convert(text)


def search_projection(text, *fields):
    # Spaces delimit fields in the index and are OpenCC phrase boundaries.
    parts = (text, *fields)
    raw = ' '.join(parts).casefold()
    folded = ' '.join(normalize_search(part) for part in parts)
    return raw if folded == raw else raw + '\n' + folded
