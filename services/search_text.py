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
    with _lock:
        return _converter.convert(text)


def search_projection(text):
    raw = str(text or '').casefold()
    folded = normalize_search(raw)
    return raw if folded == raw else raw + '\n' + folded
