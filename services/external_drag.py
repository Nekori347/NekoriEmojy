"""Internal drags carry resource paths; external file drops receive disposable copies."""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QMetaType, QMimeData, QUrl

from services.app_paths import app_data_dir


class ResourceDragMimeData(QMimeData):
    """Materialize only when a target requests file URLs/text, not for internal moves.

    Keep exports beyond QDrag.exec(): chat clients may open dropped files later.
    Old exports are reclaimed on the next process's first external export.
    Never use hard links or fall back to the managed source on copy failure.
    """
    _cleaned_roots = set()

    def __init__(self, paths):
        super().__init__()
        from fluent_ui.components.drop_contract import RESOURCE_MIME
        paths = tuple(paths)
        self.setData(RESOURCE_MIME, json.dumps(paths).encode('utf-8'))
        self._sources = tuple(path for path in paths if os.path.isfile(path))
        self._exports = None
        self.error = None

    def formats(self):
        formats = super().formats()
        return formats + ['text/uri-list', 'text/plain'] if self._sources else formats

    def hasFormat(self, mime_type):
        if mime_type in ('text/uri-list', 'text/plain'):
            return bool(self._sources)
        return super().hasFormat(mime_type)

    def _files(self):
        if self._exports is not None:
            return self._exports
        self._exports = []
        try:
            root = app_data_dir() / 'cache' / 'external_drag'
            root.mkdir(parents=True, exist_ok=True)
            if root not in self._cleaned_roots:
                self._cleaned_roots.add(root)
                cutoff = time.time() - 7 * 24 * 60 * 60
                for folder in root.glob('drag-*'):
                    if (folder.is_dir() and not folder.is_symlink()
                            and folder.resolve().parent == root.resolve()
                            and folder.stat().st_mtime < cutoff):
                        shutil.rmtree(folder, ignore_errors=True)
            folder = Path(tempfile.mkdtemp(prefix='drag-', dir=root))
            exports = []
            for i, source in enumerate(self._sources):
                # Separate directories preserve original names even for duplicate basenames.
                destination = folder / str(i) / Path(source).name
                destination.parent.mkdir()
                shutil.copyfile(source, destination)
                exports.append(str(destination))
            self._exports = exports
        except OSError as error:
            self.error = error
        return self._exports

    def retrieveData(self, mime_type, preferred_type):
        if mime_type == 'text/uri-list':
            urls = [QUrl.fromLocalFile(path) for path in self._files()]
            if preferred_type.id() == QMetaType.QVariantList:
                return urls
            return QByteArray(b''.join(bytes(url.toEncoded()) + b'\r\n' for url in urls))
        if mime_type == 'text/plain':
            text = os.pathsep.join(self._files())
            return QByteArray(text.encode('utf-8')) if preferred_type.id() == QMetaType.QByteArray else text
        return super().retrieveData(mime_type, preferred_type)
