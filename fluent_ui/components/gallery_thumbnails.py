"""Gallery-owned cache/queue. Renderer recycling never owns decode lifetime."""
import hashlib
import os
from pathlib import Path
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QPixmap, QPixmapCache
from fluent_ui.components.emoji_card import ThumbnailCache, _ThumbnailLoadTask, _thumbnail_pool


class GalleryThumbnails(QObject):
    def __init__(self, config, parent):
        super().__init__(parent)
        self.storage = parent.storage
        self.cache_dir = Path(config.base_dir)/'cache'/'thumbnails'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.revisions = {}
        self.wanted = {}
        self.running = {}
        self.serial = 0
        self.decodes = self.disk_hits = self.memory_hits = 0
        ThumbnailCache()
        from services.animation_attributes import AnimationBackfill
        self.animation_backfill = AnimationBackfill(self.storage, self, start=not getattr(parent, '_defer_background', False))
        self.storage.animation_backfill = self.animation_backfill
        self.animation_backfill.changed.connect(self.animation_changed)

    def animation_changed(self, changed):
        from services.animation_attributes import apply_animation
        gallery = self.parent()
        # Cached categories and collapsed projections share resource identity,
        # but may carry distinct dicts. Update them without invalidating layouts.
        groups = [gallery._entries, *gallery.entry_model.direct.values()]
        groups.extend(snapshot[0] for snapshot in gallery.entry_model.snapshots.values() if snapshot[0] is not None)
        for entries in groups:
            for entry in entries:
                if entry['kind'] == 'resource' and entry['id'] in changed:
                    apply_animation(entry['resource'], changed[entry['id']])
        for card in gallery.renderer.active.values():
            if card.content_entry['kind'] == 'resource' and card.entry_id in changed:
                card._animated = changed[card.entry_id]
                card.update()

    def invalidate(self, paths):
        for path in paths:
            self.revisions.pop(path, None)

    def retain_bound_requests(self, cards):
        """Drop offscreen requests without restarting decodes still in view."""
        active = set(cards)
        for key, request in list(self.wanted.items()):
            path = request[0]
            request[4][:] = [card for card in request[4]
                             if card in active and card.content_entry['path'] == path]
            if not request[4]:
                del self.wanted[key]

    def key(self, entry, size):
        path = entry['path']
        if path not in self.revisions:
            try:
                stat = os.stat(path)
                self.revisions[path] = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                self.revisions[path] = (0, 0)
        frame = self.storage.representative_frame(entry.get('resource') or path)
        tier = next((n for n in (128, 192, 256, 384) if n >= size-16), 384)
        identity = (os.path.normcase(str(self.storage.index.root)), entry['id'], self.revisions[path], tier, frame)
        crop = self.storage.representative_crop(entry.get('resource') or path)
        if crop is not None:
            identity += (tuple(crop),)
        digest = hashlib.sha256(repr(identity).encode()).hexdigest()
        return 'gallery:'+digest, tier, frame, self.cache_dir/(digest+'.png')

    def request(self, cards, *, append=False):
        """Viewport replaces queued requests; incremental batches can append."""
        wanted = self.wanted if append else {}
        for card in cards:
            entry = card.content_entry
            if entry['kind'] != 'resource':
                continue
            card._animated = self.storage.index.animation_attribute(entry.get('resource') or {}) is True
            key, tier, frame, disk = self.key(entry, card.current_size)
            card.frame = frame
            crop = self.storage.representative_crop(entry.get('resource') or entry['path'])
            card.crop = crop
            if getattr(card, '_gallery_thumbnail_key', None) == key and card._is_loaded:
                continue
            pixmap = QPixmap()
            if QPixmapCache.find(key, pixmap):
                self.memory_hits += 1
                self.attach(card, key, pixmap)
                continue
            wanted.setdefault(key, [entry['path'], tier, frame, disk, [], crop])[4].append(card)
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
        for key, (path, tier, frame, disk, cards, crop) in self.wanted.items():
            if len(self.running) >= 2:
                break
            if key in active_keys:
                continue
            self.serial += 1
            task = _ThumbnailLoadTask(path, tier, self.serial, frame, cache_file=str(disk), crop=crop)
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
