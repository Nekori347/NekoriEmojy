"""Mixed flow layout index and a viewport-sized pool of existing card widgets."""
from bisect import bisect_left, bisect_right
from time import perf_counter
from PySide6.QtCore import QPoint, QRect, Qt, QSignalBlocker, QTimer, QAbstractAnimation
from PySide6.QtWidgets import QWidget, QLabel
from fluent_ui.components.gallery_model import occurrence_id
from fluent_ui.components.gallery_thumbnails import GalleryThumbnails
from fluent_ui.components.emoji_card import EmojiCard
from services.i18n import t


class FlowIndex:
    def __init__(self):
        self.rects = []
        self.tops = []
        self.bottoms = []
        self.height = 36
        self.width = self.size = 0

    def layout(self, entries, width, size, first=0):
        """Only numeric geometry. Resume at the row before an affected range."""
        width = max(60, width)
        if self.width != width or self.size != size:
            first = 0
        self.width, self.size = width, size
        first = min(first, len(entries), len(self.rects))
        if first and first < len(self.rects):
            first = bisect_left(self.tops, self.tops[first])
        # Rebuild the preceding row as insertions can fill it.
        if first:
            first = bisect_left(self.tops, self.tops[first-1])
        y = self.tops[first] if first < len(self.tops) else self.height-20
        if first == 0:
            y = 4
        rects = self.rects[:first]
        index = first
        while index < len(entries):
            entry = entries[index]
            indent = min(entry.get('_depth', 0), 6)*14
            available = max(1, width-24-indent)
            if entry['kind'] == 'node':
                rects.append(QRect(12+indent, y, available, 40))
                index += 1
                y += 44
                continue
            capacity = max(1, (available+4)//(size+4))
            left = 12+indent
            # Keep the inter-image gap dense; balance unused width at both edges.
            gap=4
            left+=round(max(0,available-capacity*size-(capacity-1)*gap)/2)
            stride=size+gap
            parent = entry.get('_parent')
            row_height = size
            column = 0
            while index < len(entries) and column < capacity:
                item = entries[index]
                if item['kind'] != 'resource' or item.get('_parent') != parent:
                    break
                height = size+(22 if item.get('_source_label') else 0)
                rects.append(QRect(round(left+column*stride), y, size, height))
                row_height = max(row_height, height)
                column += 1
                index += 1
            y += row_height+4
        self.rects = rects
        self.tops = [r.top() for r in rects]
        bottom = 0
        self.bottoms = []
        for rect in rects:
            bottom = max(bottom, rect.bottom())
            self.bottoms.append(bottom)
        self.height = max(36, y+4)

    def between(self, top, bottom):
        return range(bisect_left(self.bottoms, top), bisect_right(self.tops, bottom))


class VirtualGallery:
    def __init__(self, gallery):
        self.gallery = gallery
        self.index = FlowIndex()
        self.active = {}
        self.pool = {'node': [], 'resource': []}
        self.loader = GalleryThumbnails(gallery.config, gallery)
        self.updating = False
        self.created = 0
        self._pending = []
        self._batch_timer = QTimer(gallery)
        self._batch_timer.setSingleShot(True)
        self._batch_timer.setInterval(8)
        self._batch_timer.timeout.connect(self._drain)

    def relayout(self, first=0, anchor=None, scroll=None):
        g = self.gallery
        self.updating = True
        try:
            self.index.layout(g._entries, g.scroll_area.viewport().width(),
                              g.config.get('thumbnail_size', 120), first)
            # The viewport already owns the empty area. Making the scroll
            # widget as tall as that moving viewport feeds panel animation
            # back into the scroll range and can toggle the vertical bar.
            g.grid_container.setFixedSize(self.index.width, self.index.height)
            if scroll is not None:
                g.scroll_area.verticalScrollBar().setValue(scroll)
            elif anchor:
                self.restore(anchor)
        finally:
            self.updating = False
        self.sync()

    def retire(self, card):
        if isinstance(card, EmojiCard) and getattr(self.gallery, 'preview_controller', None):
            self.gallery.preview_controller.leave(card)
        card._renderer.hide()
        self.pool[card.content_entry['kind']].append(card)

    def bind(self, card, entry):
        changed = getattr(card, 'content_entry', None) != entry
        card.content_entry = entry
        if isinstance(card, EmojiCard):
            if card.image_path != entry['path']:
                card.set_hovered(False)
                card.clear_resources()
                card.image_path = entry['path']
                card._gallery_thumbnail_key = None
            card.entry_id = entry['id']
            state = 'missing' if entry.get('status') == 'missing' else 'normal'
            if card.property('state') != state:
                card.setProperty('state', state)
                card.setToolTip(t('表情文件缺失') if state == 'missing' else '')
            if card.current_size != self.index.size:
                card.update_size(self.index.size, load_image=False)
                card._gallery_thumbnail_key = None
            label = card._source_label
            source = str(entry.get('_source_label') or '')
            label.setVisible(bool(source))
            if source:
                label.setGeometry(0, self.index.size+4, self.index.size, 18)
                label.setText(label.fontMetrics().elidedText(source, Qt.ElideMiddle, self.index.size))
                label.setToolTip(source)
        else:
            signature = (entry['id'], entry['name'], entry.get('icon'), entry.get('total'),
                         entry.get('children'), entry['id'] in self.gallery._expanded_nodes)
            if getattr(card, '_node_signature', None) != signature:
                card.entry = entry
                card.node_id = entry['id']
                card.set_expanded(entry['id'] in self.gallery._expanded_nodes)
                card.refresh_icon()
                card._node_signature = signature
        with QSignalBlocker(card):
            card.set_selected(self.gallery._entry_key(entry) in self.gallery.selected_keys)

    def acquire(self, entry):
        pool = self.pool[entry['kind']]
        if pool:
            return pool.pop()
        g = self.gallery
        card = g._create_widget(entry, self.index.size)
        if isinstance(card, EmojiCard):
            wrapper = QWidget(g.grid_container)
            card.setParent(wrapper)
            card.move(0, 0)
            card._renderer = wrapper
            card._source_label = QLabel(wrapper)
            card._source_label.setProperty('role', 'data')
            card.gallery_reload = g._reload_resource_thumbnail
        else:
            card.setParent(g.grid_container)
            card._renderer = card
        # Register at creation, before the first scroll/rebind. Qt targets the
        # card/wrapper under the pointer, not only the scroll viewport.
        for surface in {card, card._renderer}:
            surface.setAcceptDrops(True)
            surface.setProperty("galleryDropSurface", True)
            surface.installEventFilter(g)
        self.created += 1
        return card

    def sync(self, *, scroll_only=False):
        if self.updating:
            return
        self._batch_timer.stop()
        g = self.gallery
        top = g.scroll_area.verticalScrollBar().value()
        height = max(100, g.scroll_area.viewport().height())
        rows = self.index.between(max(0, top-height), top+height*2)
        wanted = {occurrence_id(g._entries[i]): i for i in rows}
        for key in list(self.active):
            card = self.active[key]
            if key not in wanted and not getattr(card, '_is_dragging', False):
                self.retire(self.active.pop(key))
        ordered = sorted(wanted, key=lambda key: (
            max(top-self.index.rects[wanted[key]].bottom(),
                self.index.rects[wanted[key]].top()-(top+height), 0), wanted[key]))
        self._wanted = wanted
        if scroll_only:
            # The short drain budget must go to newly exposed cards. If it
            # starts with already-bound cards on every wheel event, a rapid
            # reverse scroll repeatedly prepares the same front of the list
            # while newly visible cards wait behind it.
            self.loader.retain_bound_requests(self.active.values())
            self._pending = [key for key in ordered if not self._scroll_card_bound(key, wanted[key])]
        else:
            self.loader.wanted.clear()
            self._pending = list(ordered)
        self._drain()

    def _scroll_card_bound(self, key, index):
        card = self.active.get(key)
        return (card is not None and card.content_entry is self.gallery._entries[index]
                and card._renderer.isVisible() and card._renderer.geometry() == self.index.rects[index]
                and (not isinstance(card, EmojiCard) or card.current_size == self.index.size)
                and getattr(card, 'is_selected', False) ==
                (self.gallery._entry_key(card.content_entry) in self.gallery.selected_keys))

    def _drain(self):
        """Prepare visible cards first, yielding between small GUI-thread batches."""
        g = self.gallery
        started = perf_counter()
        batch = []
        tree=g.sidebar.tree;navigation=tree.itemDelegate()
        # Keep GUI-only card construction out of the short navigation motion.
        # The selected location/data are already updated; only render prep yields.
        navigation_busy=tree.isVisible() and (navigation._selection_timer.isActive() or
                         navigation._selection_motion.state()==QAbstractAnimation.Running)
        while self._pending and not navigation_busy:
            key = self._pending.pop(0)
            index = self._wanted[key]
            entry = g._entries[index]
            card = self.active.get(key)
            if card is None:
                card = self.acquire(entry)
                self.active[key] = card
            self.bind(card, entry)
            rect = self.index.rects[index]
            if card._renderer.geometry() != rect:
                card._renderer.setGeometry(rect)
            if card._renderer.isHidden():
                card._renderer.show()
            if card.isHidden():
                card.show()
            batch.append(card)
            if perf_counter()-started >= .008:
                break
        # Compatibility list now contains ONLY viewport/buffer renderers.
        g._all_card_widgets = [self.active[key] for key in sorted(self._wanted, key=self._wanted.get)
                               if key in self.active]
        g._loaded_count = len(g._all_card_widgets)
        g._target_load_count = len(self._wanted)
        # Preserve earlier pending decodes without re-keying every active card
        # on every batch. sync() discards obsolete viewport requests above.
        self.loader.request(batch,append=True)
        g._sync_hover_card()
        if self._pending:
            self._batch_timer.start()
            return
        # A small/empty category must not discard the viewport's reusable bank.
        # Its bound depends on visible geometry, never the library item count.
        height = max(100, g.scroll_area.viewport().height())
        columns=max(1,(self.index.width+4)//(self.index.size+4))
        capacities={'resource':max(32,columns*((height*3+self.index.size+3)//(self.index.size+4))),
                    'node':max(32,(height*3+47)//48)}
        for kind,pool in self.pool.items():
            while len(pool) > capacities[kind]:
                pool.pop()._renderer.deleteLater()

    def anchor(self):
        g = self.gallery
        top = g.scroll_area.verticalScrollBar().value()
        candidates = self.index.between(top, top+g.scroll_area.viewport().height())
        if not candidates:
            return None
        i = candidates.start
        return occurrence_id(g._entries[i]), top-self.index.rects[i].top()

    def restore(self, anchor):
        if anchor:
            key, offset = anchor
            for i, entry in enumerate(self.gallery._entries):
                if occurrence_id(entry) == key:
                    self.gallery.scroll_area.verticalScrollBar().setValue(self.index.rects[i].top()+offset)
                    break
