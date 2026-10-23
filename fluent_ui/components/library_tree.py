"""Left navigation: the real recursive category node tree.

The tree is a projection of the single node tree in the library index. Root-level
nodes are the main categories; deeper nodes appear as children. Dragging changes
the real parent/position instead of a UI-only order.
"""
from services.i18n import t, bind_text, translated
import json

from PySide6.QtCore import Qt, QEvent, QTimer, QRect, Signal, QPoint, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QHeaderView, QTreeWidget, QTreeWidgetItem, QStyleOptionViewItem, QStyle,
)

from fluent_ui.components.node_card import NODE_MIME, RESOURCE_MIME, render_node_icon
from fluent_ui.components.drop_contract import (
    APPEND, DropFeedback, DropTarget, EdgeAutoScroller, IMPORT, INSERT_AFTER, INTO,
    INVALID_TARGET, MOVE, TAG_MIME, DragSession, execute_drag, edge_placement, parse_list_payload, parse_node_payload, tag_drop_target,
)
from fluent_ui.visual import DATA_FONT, colors
from services.library_index import ROOT
from fluent_ui.components.section_index import SectionedProjection, SectionHeader, SortProjection
from fluent_ui.icons import Icon as FIF

ALL_RESOURCES = ROOT
# How long a dragged item must rest on a collapsed category before it opens.
HOVER_EXPAND_MS = 700


class LibraryTree(QTreeWidget):
    node_selected = Signal(str)
    node_reparented = Signal(str, str, object)     # node_id, parent_id, position
    resources_dropped = Signal(str, list, QPoint)    # node_id, paths, global drop position
    files_dropped = Signal(str, list)              # node_id, local paths
    node_menu_requested = Signal(str, QPoint, str)   # node_id, global pos, 'into' / 'before' / 'after'
    blank_menu_requested = Signal(QPoint)
    tags_dropped = Signal(str, list)
    nodes_dropped = Signal(list, str, object)

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.sidebar = parent
        self.setColumnCount(3)
        from fluent_ui.components.navigation import NavigationItem
        self.setItemDelegate(NavigationItem(self))
        self.setMouseTracking(True)
        self._hovered_index = None
        self.setFocusPolicy(Qt.TabFocus)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(False)
        self.setIndentation(0)
        self.setUniformRowHeights(False)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        # The shared overlay draws the drop, so Qt's own indicator is off: two
        # indicators disagreeing about the same drop is worse than none.
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.header().resizeSection(1, 48)
        self.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.header().resizeSection(2, 28)
        self._icon_size = 18
        self._pending_select = ALL_RESOURCES
        self.display_sort = 'manual'
        self._drag_session = None
        self._node_records = {}
        self.section_projection = SectionedProjection()
        self.section_headers = {}
        self.feedback = DropFeedback(self.viewport())
        self.scroller = EdgeAutoScroller(self)
        self._hover_expand_item = None
        self._hover_expand_timer = QTimer(self)
        self._hover_expand_timer.setSingleShot(True)
        self._hover_expand_timer.setInterval(HOVER_EXPAND_MS)
        self._hover_expand_timer.timeout.connect(self._expand_hovered)

        self.itemClicked.connect(self._on_item_activated)
        self.itemActivated.connect(self._on_item_activated)
        self.customContextMenuRequested.connect(self._on_context_menu)

    # -- construction --------------------------------------------------
    def set_icon_size(self, size):
        self._icon_size = max(14, int(size))
        self.setIconSize(QSize(self._icon_size, self._icon_size))
        self.doItemsLayout()
        self.viewport().update()

    def drawBranches(self, painter, rect, index):
        # Indentation carries ancestry; the row owns its only selected stripe.
        pass

    def paintEvent(self,event):
        self._selection_layer_painted=False
        super().paintEvent(event)

    def drawRow(self, painter, option, index):
        # QTreeView's native row panel also paints the branch/selection gutter.
        # Own the complete row instead, including its finite depth indentation.
        if not self._selection_layer_painted:
            self.itemDelegate().paint_selection_layer(painter)
            self._selection_layer_painted=True
        depth, ancestor = 0, index.parent()
        while ancestor.isValid():
            depth += 1
            ancestor = ancestor.parent()
        row = QStyleOptionViewItem(option)
        row.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus | QStyle.State_MouseOver)
        if self._hovered_index == index.siblingAtColumn(0):
            row.state |= QStyle.State_MouseOver
        if self.selectionModel().isSelected(index.siblingAtColumn(0)):
            row.state |= QStyle.State_Selected
        if self.hasFocus() and self.currentIndex().siblingAtColumn(0) == index.siblingAtColumn(0):
            row.state |= QStyle.State_HasFocus
        row.rect = QRect(min(depth*6, 24), option.rect.top(),
                         self.viewport().width()-min(depth*6, 24), option.rect.height())
        self.itemDelegate().paint(painter, row, index.siblingAtColumn(0))

    def mouseMoveEvent(self,event):
        index=self.indexAt(event.position().toPoint()).siblingAtColumn(0)
        if index!=self._hovered_index:
            self._hovered_index=index;self.viewport().update()
        super().mouseMoveEvent(event)

    def viewportEvent(self,event):
        if event.type()==QEvent.Leave:
            self._hovered_index=None;self.viewport().update()
        return super().viewportEvent(event)

    def _span_rows(self):
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        rows = QTreeWidgetItemIterator(self)
        while rows.value():
            rows.value().setFirstColumnSpanned(True)
            rows += 1

    def chevron_rect(self, item):
        row = self.visualItemRect(item)
        return QRect(self.viewport().width()-28, row.top(), 28, row.height()) if item.childCount() else QRect()

    def keyPressEvent(self, event):
        item=self.currentItem()
        if item and item.childCount():
            if event.key()==Qt.Key_Space or (event.key()==Qt.Key_Right and not item.isExpanded()) or (event.key()==Qt.Key_Left and item.isExpanded()):
                item.setExpanded(not item.isExpanded())
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        self._chevron_pressed = item if event.button() == Qt.LeftButton and item and item.childCount() and self.chevron_rect(item).contains(event.position().toPoint()) else None
        if self._chevron_pressed:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        item = getattr(self, '_chevron_pressed', None)
        self._chevron_pressed = None
        if item:
            if self.chevron_rect(item).contains(event.position().toPoint()):
                item.setExpanded(not item.isExpanded())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    @property
    def current_node_id(self):
        item = self.currentItem()
        return (item.data(0, Qt.UserRole) if item else None) or ALL_RESOURCES

    def refresh(self, select=None):
        scroll = self.verticalScrollBar().value()
        self._hovered_index = None
        target = select or self._pending_select or ALL_RESOURCES
        expanded = self._expanded_ids() if self.topLevelItemCount() else set(self.sidebar.gallery_view._saved_view_state.get('sidebar_expanded', []))
        self.end_drag_session()
        self.blockSignals(True)
        self.clear()
        self._node_records.clear()
        self.section_headers.clear()
        counts = self.storage.node_counts()
        self.sidebar.sync_root(counts.get(ROOT, {}).get('resources', 0))
        self.header().resizeSection(1, max(32, max((self.fontMetrics().horizontalAdvance(str(c['resources'])) for c in counts.values()), default=0) + 14))
        # A refresh owns one consistent node snapshot. Recursing through
        # child_nodes() opened a new SQLite connection for every category.
        children_by_parent = {}
        for node in self.storage.index.nodes():
            children_by_parent.setdefault(node['parent_id'] or ROOT, []).append(node)
        self._refresh_children = children_by_parent
        try:
            children = self._children(ALL_RESOURCES)
            section_starts = {index: key for key, index in self.section_projection.positions.items()}
            for index, node in enumerate(children):
                if index in section_starts:
                    key = section_starts[index]
                    header = QTreeWidgetItem([key, ''])
                    header.setData(0, SectionHeader.ROLE, key)
                    header.setFlags(Qt.ItemIsEnabled)
                    self.addTopLevelItem(header)
                    header.setFirstColumnSpanned(True)
                    self.section_headers[key] = header
                item = self._build(node, counts)
                self.addTopLevelItem(item)
                self._restore_expanded(item, expanded)
        finally:
            del self._refresh_children
        self._span_rows()
        self.blockSignals(False)
        self.select_node(target)
        self.doItemsLayout()
        self.verticalScrollBar().setValue(scroll)

    def _index_of(self, parent_item, node_id):
        for i in range(parent_item.childCount()):
            if parent_item.child(i).data(0, Qt.UserRole) == node_id:
                return i
        return -1

    def _build(self, node, counts):
        item = self._make_item(node, counts)
        for child in self._children(node["id"]):
            item.addChild(self._build(child, counts))
        return item

    def _children(self, node_id):
        from fluent_ui.components.section_index import SortProjection
        snapshot = getattr(self, '_refresh_children', None)
        children = snapshot.get(node_id, []) if snapshot is not None else self.storage.child_nodes(node_id)
        self._node_records.update((node['id'], node) for node in children)
        # Only outer parents are projected. Every inner order stays manual.
        if node_id != ROOT:
            return children
        mode = {'name_asc': SortProjection.A_Z, 'name_desc': SortProjection.Z_A}.get(self.display_sort, SortProjection.MANUAL)
        self.section_projection = SectionedProjection(children, mode, name=lambda node: node['name'])
        return self.section_projection.items

    def set_display_sort(self, mode):
        self.display_sort = mode
        self.refresh(select=self.current_node_id)

    def _make_item(self, node, counts, pinned=False):
        stats = counts.get(node["id"], {"resources": 0, "children": 0}) if not pinned else \
            {"resources": counts.get(ROOT, {}).get("resources", 0),
             "children": counts.get(ROOT, {}).get("children", 0)}
        item = QTreeWidgetItem([node.get("name", ""), str(stats["resources"])])
        item.setData(0, Qt.UserRole, node["id"])
        item.setData(0, Qt.UserRole + 1, bool(pinned))
        item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        mono = QFont(DATA_FONT.split(",")[0].strip())
        mono.setPixelSize(10)
        item.setFont(1, mono)
        item.setForeground(1, QColor(colors()["muted"]))
        item.setSizeHint(0, QSize(0, self._row_height()))
        if pinned:
            item.setToolTip(0, t('表情库全部表情 · {value_0} 项').format(value_0=stats['resources']))
        else:
            item.setToolTip(0, t('{value_0}\n{value_1} 个子分类 · {value_2} 项直接内容').format(value_0=node.get('name',''), value_1=stats['children'], value_2=stats['resources']))
        item.setIcon(0, FIF.TILES.icon() if pinned else self._node_icon(node))
        if pinned:
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            item.setFlags(flags)
        return item

    def _row_height(self):
        return max(34, self._icon_size + 16)

    def _node_icon(self, node):
        pixmap = QPixmap(render_node_icon(self.storage, node, self._icon_size))
        if pixmap.isNull():
            return QIcon()
        return QIcon(pixmap)

    def _expanded_ids(self):
        result = set()
        def walk(item):
            if item.isExpanded():
                result.add(item.data(0, Qt.UserRole))
            for i in range(item.childCount()):
                walk(item.child(i))
        for i in range(self.topLevelItemCount()):
            walk(self.topLevelItem(i))
        return result

    def _restore_expanded(self, item, expanded):
        if item is None:
            return
        if item.data(0, Qt.UserRole) in expanded:
            item.setExpanded(True)
        for i in range(item.childCount()):
            self._restore_expanded(item.child(i), expanded)

    # -- selection -----------------------------------------------------
    def select_node(self, node_id, reveal=False):
        scroll = self.verticalScrollBar().value()
        self._pending_select = node_id or ALL_RESOURCES
        item = self._find_item(self._pending_select)
        if item is None:
            self._pending_select = ALL_RESOURCES
            self.blockSignals(True)
            self.clearSelection()
            self.setCurrentItem(None)
            self.blockSignals(False)
        self.sidebar.sync_root()
        if item is not None:
            self.blockSignals(True)
            ancestors = []
            ancestor = item.parent()
            while ancestor is not None:
                ancestors.append((ancestor, ancestor.isExpanded()))
                if reveal:
                    ancestor.setExpanded(True)
                ancestor = ancestor.parent()
            if self.currentItem() is not item:
                self.setCurrentItem(item)
            if reveal:
                self.scrollToItem(item)
            else:
                for ancestor, expanded in ancestors:
                    ancestor.setExpanded(expanded)
                # Qt's setCurrentItem scrolls even when the caller only wants
                # to restore selection after a data refresh.
                self.doItemsLayout()
                self.verticalScrollBar().setValue(scroll)
            self.blockSignals(False)

    def _find_item(self, node_id, parent=None):
        if parent is None:
            for i in range(self.topLevelItemCount()):
                found = self._find_item(node_id, self.topLevelItem(i))
                if found is not None:
                    return found
            return None
        if parent.data(0, Qt.UserRole) == node_id:
            return parent
        for i in range(parent.childCount()):
            found = self._find_item(node_id, parent.child(i))
            if found is not None:
                return found
        return None

    def patch_nodes(self, node_ids, parent_id):
        """Move existing tree items after the database commit; keep their renderers."""
        current = self.current_node_id
        selected = [item.data(0, Qt.UserRole) for item in self.selectedItems()]
        expanded = self._expanded_ids()
        moved = {}
        self.blockSignals(True)
        for node_id in node_ids:
            item = self._find_item(node_id)
            if item is None:
                continue
            source = item.parent()
            if source is None:
                item = self.takeTopLevelItem(self.indexOfTopLevelItem(item))
            else:
                item = source.takeChild(source.indexOfChild(item))
            moved[node_id] = item
            if node_id in self._node_records:
                self._node_records[node_id]['parent_id'] = parent_id
        parent_item = None if parent_id == ROOT else self._find_item(parent_id)
        siblings = [node['id'] for node in self.storage.child_nodes(parent_id)]
        for node_id in siblings:
            item = moved.get(node_id)
            if item is None:
                continue
            slot = siblings.index(node_id)
            if parent_item is None:
                self.insertTopLevelItem(slot, item)
            else:
                parent_item.insertChild(slot, item)
                parent_item.setExpanded(True)
            self._restore_expanded(item, expanded)
        self._span_rows()
        self.blockSignals(False)
        self.select_node(current)
        self.clearSelection()
        for node_id in selected:
            item = self._find_item(node_id)
            if item is not None:
                item.setSelected(True)

    def _on_item_activated(self, item, _column=0):
        if item is None or item.data(0, SectionHeader.ROLE):
            return
        self._pending_select = item.data(0, Qt.UserRole)
        self.node_selected.emit(self._pending_select)

    # -- drag & drop ---------------------------------------------------
    def mimeData(self, items):
        """Drag an existing node so it can be dropped onto another one.

        Without this override the tree drags Qt's generic item-model data and
        the drop handlers below never see NODE_MIME, which is why categories
        could be created but never re-parented by dragging.
        """
        mime = super().mimeData(items)
        from services.manual_order import selection_block
        selected = {item.data(0, Qt.UserRole) for item in items if item is not None} - {None, ALL_RESOURCES}
        order = []
        def visit(item):
            node_id = item.data(0, Qt.UserRole)
            order.append(node_id)
            for index in range(item.childCount()):
                visit(item.child(index))
        for index in range(self.topLevelItemCount()):
            visit(self.topLevelItem(index))
        ids = selection_block(order, selected, {key: node.get('parent_id') for key, node in self._node_records.items()})
        if ids:
            mime.setData(NODE_MIME, json.dumps(ids).encode('utf-8'))
        return mime

    def startDrag(self, supported_actions):
        mime = self.mimeData(self.selectedItems())
        if not mime.hasFormat(NODE_MIME):
            return
        item = self.currentItem()
        pixmap = item.icon(0).pixmap(32, 32) if item else QPixmap()
        execute_drag(self, mime, pixmap, self.end_drag_session)

    def begin_drag_session(self, mime):
        self.end_drag_session()
        self._drag_session = DragSession(mime, {
            key: value.get('parent_id') or ROOT for key, value in self._node_records.items()})
        return self._drag_session.supported

    def end_drag_session(self):
        self._drag_session = None
        self.feedback.clear()
        self.scroller.stop()
        self._schedule_hover_expand(None)

    def _is_descendant(self, candidate_id, node_id):
        """Whether `candidate_id` sits inside `node_id`'s subtree."""
        current = candidate_id
        seen = set()
        while current and current != ALL_RESOURCES and current not in seen:
            if current == node_id:
                return True
            seen.add(current)
            current = self._parent_of(current)
        return False

    def _resolve_drop(self, pos):
        """Return (mode, item) where mode is 'into', 'before', 'after' or 'root'."""
        item = self.itemAt(pos)
        if item is None:
            return "root", None
        if item.data(0, Qt.UserRole + 1):
            return "into", item
        rect = self.visualItemRect(item)
        ratio = (pos.y() - rect.top()) / max(1, rect.height())
        if ratio < 0.3:
            return "before", item
        if ratio > 0.7:
            return "after", item
        return "into", item

    def _dragged_kind(self, mime):
        if mime.hasFormat(TAG_MIME):
            return TAG_MIME, None
        for mime_type, effect in ((RESOURCE_MIME, MOVE), (NODE_MIME, MOVE)):
            if mime.hasFormat(mime_type):
                return mime_type, effect
        if mime.hasUrls():
            return 'urls', IMPORT
        return None, None

    def _resolve_target(self, pos, mime):
        """Resolve a tree point into the shared drop contract.

        `placement` decides everything downstream: INTO reparents, BEFORE /
        AFTER reorder among siblings, and the row's own top and bottom edges are
        the only place a sibling insertion exists -- the middle of a row always
        means "inside this category".
        """
        kind, effect = self._dragged_kind(mime)
        if kind is None:
            return INVALID_TARGET, None
        item = self.itemAt(pos)
        if item is None:
            if kind == TAG_MIME:
                return INVALID_TARGET, None
            if kind == NODE_MIME and self.display_sort != 'manual':
                return INVALID_TARGET, None
            return DropTarget(APPEND, effect, None, ALL_RESOURCES), None
        node_id = item.data(0, Qt.UserRole)
        rect = self.visualItemRect(item)
        if node_id is None:
            return INVALID_TARGET, None
        return self.resolve_category_target(node_id, (pos.y()-rect.top())/max(1, rect.height()), mime), rect

    def resolve_category_target(self, node_id, ratio, mime):
        """Geometry-independent category drop resolver used by both modes."""
        kind, effect = self._dragged_kind(mime)
        if kind is None:
            return INVALID_TARGET
        if kind == TAG_MIME:
            return tag_drop_target(node_id, category=True) if node_id != ROOT else INVALID_TARGET
        if kind == NODE_MIME:
            payload = tuple(parse_node_payload(mime.data(NODE_MIME)))
            if self._drag_session is None or self._drag_session.payload != payload:
                self.begin_drag_session(mime)
            if not payload or self.display_sort != 'manual':
                return INVALID_TARGET
        if node_id == ROOT:
            # The pinned "all resources" row is the library, not a category:
            # there is nothing to sit next to it.
            return DropTarget(INTO, effect, ALL_RESOURCES, ALL_RESOURCES)
        if kind == NODE_MIME and self.display_sort != 'manual':
            # A temporary display order means the rows on screen are not the
            # manual slots a reparent would write into.
            return INVALID_TARGET
        if kind != NODE_MIME:
            # A resource or a file only ever goes *into* a category.
            return DropTarget(INTO, effect, node_id, node_id)
        placement = edge_placement(ratio)
        parent = node_id if placement == INTO else self._parent_of(node_id)
        for source in self._drag_session.payload:
            if node_id == source or self._is_descendant(parent, source):
                return INVALID_TARGET
        if placement == INTO:
            return DropTarget(INTO, effect, node_id, node_id)
        parent = self._parent_of(node_id)
        index = self._sibling_index(parent, node_id, placement,
                                    set(self._drag_session.payload))
        return DropTarget(placement, effect, node_id, parent, index)

    def _sibling_index(self, parent, target_node, placement, moving):
        streams = self._drag_session.streams if self._drag_session else {}
        if parent not in streams:
            streams[parent] = [entry['id'] for entry in self.storage.index.content(parent)]
        from services.manual_order import insertion_position
        return insertion_position(streams[parent], moving, target_node, placement == INSERT_AFTER)

    def _track(self, event):
        pos = event.position().toPoint()
        self.scroller.track(pos)
        target, rect = self._resolve_target(pos, event.mimeData())
        if not target.valid:
            self.feedback.clear()
            self._schedule_hover_expand(None)
            event.ignore()
            return None
        event.acceptProposedAction()
        if target.placement == INTO:
            self.feedback.show_target(INTO, rect)
        elif rect is None:
            # APPEND in the blank area below the tree: mark the end of the list.
            last = self.topLevelItem(self.topLevelItemCount()-1) if self.topLevelItemCount() else None
            anchor = self.visualItemRect(last) if last is not None else QRect(0, 0, self.viewport().width(), 1)
            self.feedback.show_target(APPEND, anchor)
        else:
            self.feedback.show_target(target.placement, rect)
        self._schedule_hover_expand(self.itemAt(pos) if target.placement == INTO else None)
        return target

    def _schedule_hover_expand(self, item):
        """Resting on a collapsed category opens it, so a drag can go deeper."""
        collapsed = item is not None and item.childCount() and not item.isExpanded()
        if not collapsed:
            self._hover_expand_item = None
            self._hover_expand_timer.stop()
            return
        if self._hover_expand_item is item and self._hover_expand_timer.isActive():
            return
        self._hover_expand_item = item
        self._hover_expand_timer.start()

    def _expand_hovered(self):
        if self._hover_expand_item is not None:
            self._hover_expand_item.setExpanded(True)

    def dragEnterEvent(self, event):
        # Enter occurs over the source itself or empty space. MIME admission
        # must not depend on whether that first point is a legal destination.
        if self.begin_drag_session(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.end_drag_session()
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        self._track(event)

    def dropEvent(self, event):
        try:
            if self._drag_session is None:
                event.ignore()
                return
            pos = event.position().toPoint()
            target, _rect = self._resolve_target(pos, event.mimeData())
            if self._drag_session and self.commit_target(target, event.mimeData(), self.viewport().mapToGlobal(pos)):
                event.acceptProposedAction()
            else:
                event.ignore()
        finally:
            self.end_drag_session()

    def commit_target(self, target, mime, global_pos):
        if self._drag_session is None:
            return False
        return self._drag_session.commit(target, lambda resolved, block:
                                        self._commit_target(resolved, mime, global_pos, block))

    def _commit_target(self, target, mime, global_pos, block):
        if mime.hasFormat(TAG_MIME):
            self.tags_dropped.emit(target.container_id, parse_list_payload(mime.data(TAG_MIME)))
            return
        if mime.hasFormat(NODE_MIME):
            self.nodes_dropped.emit(block, target.container_id, target.index)
            return
        if mime.hasFormat(RESOURCE_MIME):
            paths = parse_list_payload(mime.data(RESOURCE_MIME))
            if paths:
                self.resources_dropped.emit(target.container_id or ALL_RESOURCES, paths,
                                            global_pos)
            return
        if mime.hasUrls():
            local = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            if local:
                self.files_dropped.emit(target.container_id or ALL_RESOURCES, local)

    def _parent_of(self, node_id):
        if node_id == ALL_RESOURCES:
            return ALL_RESOURCES
        if self._drag_session is not None:
            return self._drag_session.parents.get(node_id, ROOT)
        node = self._node_records.get(node_id) or self.storage.node(node_id)
        return (node or {}).get("parent_id") or ALL_RESOURCES

    # -- context menu --------------------------------------------------
    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        global_pos = self.viewport().mapToGlobal(pos)
        if item is None:
            self.blank_menu_requested.emit(global_pos)
            return
        node_id = item.data(0, Qt.UserRole)
        if node_id in (None, ALL_RESOURCES):
            self.blank_menu_requested.emit(global_pos)
            return
        # Same vertical semantics as a drop: the top and bottom edges of a row
        # mean "next to this category", the middle means "inside it".
        self.node_menu_requested.emit(node_id, global_pos,
                                      self._resolve_drop(pos)[0])
