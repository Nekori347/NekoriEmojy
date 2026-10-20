"""Gallery-owned cache/queue. Renderer recycling never owns decode lifetime."""
import hashlib
import json
import os
from pathlib import Path
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QPixmap, QPixmapCache
from fluent_ui.components.emoji_card import ThumbnailCache, _ThumbnailLoadTask, _thumbnail_pool


class GalleryThumbnails(QObject):
    def __init__(self, config, parent):
        super().__init__(parent)
        self.cache_dir = Path(config.base_dir)/'cache'/'thumbnails'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.revisions = {}
        self.wanted = {}
        self.running = {}
        self.serial = 0
        self.decodes = self.disk_hits = self.memory_hits = 0
        ThumbnailCache()

    def invalidate(self, paths):
        for path in paths:
            self.revisions.pop(path, None)

    def key(self, entry, size):
        path = entry['path']
        if path not in self.revisions:
            try:
                stat = os.stat(path)
                self.revisions[path] = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                self.revisions[path] = (0, 0)
        metadata = json.loads(entry.get('resource', {}).get('metadata_json') or '{}')
        frame = int(metadata.get('thumb_frame', 0) or 0)
        tier = next((n for n in (128, 192, 256, 384) if n >= size-16), 384)
        identity = (ThumbnailCache.library_identity(), entry['id'], self.revisions[path], tier, frame)
        digest = hashlib.sha256(repr(identity).encode()).hexdigest()
        return 'gallery:'+digest, tier, frame, self.cache_dir/(digest+'.png')

    def request(self, cards, *, append=False):
        """Viewport replaces queued requests; incremental batches can append."""
        wanted = self.wanted if append else {}
        for card in cards:
            entry = card.content_entry
            if entry['kind'] != 'resource':
                continue
            key, tier, frame, disk = self.key(entry, card.current_size)
            card.frame = frame
            if getattr(card, '_gallery_thumbnail_key', None) == key and card._is_loaded:
                continue
            pixmap = QPixmap()
            if QPixmapCache.find(key, pixmap):
                self.memory_hits += 1
                self.attach(card, key, pixmap)
                continue
            wanted.setdefault(key, [entry['path'], tier, frame, disk, []])[4].append(card)
        self.wanted = wanted
        self.dispatch()

    def attach(self, card, key, pixmap):
        size = max(10, card.current_size-8)
        from PySide6.QtCore import Qt
        # Display inset only: cache identity, decode tiers and queue stay intact.
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        card.setPixmap(pixmap)
        card._gallery_thumbnail_key = key
        card._is_loaded = True
        card._loaded_size = card.current_size

    def dispatch(self):
        active_keys = {value[0] for value in self.running.values()}
        for key, (path, tier, frame, disk, cards) in self.wanted.items():
            if len(self.running) >= 2:
                break
            if key in active_keys:
                continue
            self.serial += 1
            task = _ThumbnailLoadTask(path, tier, self.serial, frame, cache_file=str(disk))
            task.signals.finished.connect(self.completed)
            self.running[self.serial] = (key, task)
            if disk.exists():
                self.disk_hits += 1
            else:
                self.decodes += 1
            _thumbnail_pool.start(task, 1)

    @Slot(str, object, int, int)
    def completed(self, path, image, serial, size):
        key, task = self.running.pop(serial)
        request = self.wanted.pop(key, None)
        if image is not None and not image.isNull():
            pixmap = QPixmap.fromImage(image)
            QPixmapCache.insert(key, pixmap)
            if request:
                for card in request[4]:
                    # A renderer may now belong to a different occurrence.
                    if self.key(card.content_entry, card.current_size)[0] == key:
                        self.attach(card, key, pixmap)
        self.dispatch()
