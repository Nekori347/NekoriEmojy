"""Qt MIME snapshots shared by paste and drop; parsing never performs I/O."""
from html.parser import HTMLParser
from urllib.parse import urlparse
from PySide6.QtGui import QImage
from services.importing import ImportInput


class _Images(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'img':
            values = dict(attrs)
            src = values.get('src')
            if src:
                self.sources.append(src)


def can_import(mime):
    return bool(mime and (mime.hasUrls() or mime.hasImage() or mime.hasHtml() or
                         mime.hasText() and urlparse(mime.text().strip()).scheme in ('http','https','data')))


def snapshot_inputs(mime):
    if mime is None:
        return []
    files = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()] if mime.hasUrls() else []
    if files:
        return [ImportInput('file', path) for path in dict.fromkeys(files)]
    sources = []
    if mime.hasHtml():
        parser = _Images()
        parser.feed(mime.html())
        sources = parser.sources
    if not sources and mime.hasUrls():
        sources = [u.toString() for u in mime.urls()]
    if not sources and mime.hasText():
        sources = [mime.text().strip()]
    urls = [src for src in sources if urlparse(src).scheme in ('http', 'https') or src.startswith('data:image/')]
    if urls:
        return [ImportInput('url', src) for src in dict.fromkeys(urls)]
    if mime.hasImage():
        value = mime.imageData()
        image = value.toImage() if hasattr(value, 'toImage') else QImage(value)
        if not image.isNull():
            return [ImportInput('image', image.copy())]
    return []
