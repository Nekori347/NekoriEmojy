"""The tag panel: a projection of the tags the current location uses.

Presentation only. Every data question -- which tags exist, in what order, what
a drop means -- is answered by `TagModel` and the shared drop contract, so the
panel can later be collapsed, moved into the sidebar or turned into a drawer
without touching tag semantics. Its height is the user's, not this file's.

The chips are painted rather than built: a library can carry hundreds of tags,
and one widget per tag would make the panel the heaviest thing on screen for a
list the user mostly reads.
"""
import json

from PySide6.QtCore import QMimeData, QPoint, QRect, QRectF, QSize, Qt, Signal, QEvent
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QFrame, QHBoxLayout, QLabel, QSizePolicy,
    QScrollArea, QVBoxLayout, QWidget,
)

from qfluentwidgets import Action
from fluent_ui.icons import Icon as FIF
from fluent_ui.components.controls import TransparentToolButton

from fluent_ui import visual
from fluent_ui.components import dialogs
from fluent_ui.components.navigation import SortCycleButton, CompactTitleLabel
from fluent_ui.components.panel_host import EdgeDockPanelChrome, TagPanelPlacement
from fluent_ui.components.drop_contract import (
    APPLY_TAG, APPEND, EdgeAutoScroller, DropFeedback, DropTarget, INVALID_TARGET, INTO,
    INSERT_AFTER, MOVE, RESOURCE_MIME, TAG_MIME, axis_ratio, parse_list_payload,
    split_placement, DragSession, execute_drag, tag_drop_target,
)
from fluent_ui.components.safe_round_menu import SafeRoundMenu
from services.i18n import bind_text, t, translated, i18n_engine
from fluent_ui.components.tag_model import EMPTY, EXISTS, SPACE
from fluent_ui.components.section_index import (
    SectionContentLayout, SectionIndexModel, SectionNavigator, SectionedProjection,
    SectionHeader, SortProjection,
)


class TagFlow(QWidget):
    """Painted tag chips: selection, block drag, reorder drop, tag apply drop."""

    filter_requested = Signal(str)
    selection_changed = Signal(list)
    context_requested = Signal(object, QPoint)      # tag name or None, global position
    reorder_requested = Signal(list, object, str)   # moving block, target tag, placement
    apply_requested = Signal(list, str)             # resource paths, tag
    manual_required = Signal()                      # reorder attempted outside MANUAL order
    drag_hint_cleared = Signal(object)

    CHIP_HEIGHT = 22
    CHIP_GAP = 4
    PAD = 4
    MIN_CHIP = 46

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(visual.font())
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self._items = []
        self._rects = []
        self._section_headers = []
        self.sections_enabled = False
        self.projection = SectionedProjection()
        # Which axis the section groups flow along; owned by the host, derived
        # from the panel placement, never from this widget's own proportions.
        self.section_content = SectionContentLayout(
            horizontal=True, padding=self.PAD, gap=self.CHIP_GAP,
            chip_height=self.CHIP_HEIGHT, min_chip=self.MIN_CHIP)
        self._drag_session = None
        self._content_height = self.CHIP_HEIGHT + self.PAD*2
        self.active_filters = set()
        self._filter_click = None
        self._selected = []
        self._anchor = None
        self._hovered = -1
        self._touched = set()
        self._press_pos = None
        self._pending_collapse = None
        self._dragging = False
        self._manual_warned = False
        self.feedback = DropFeedback(self)
        self.scroller = EdgeAutoScroller(self.parent_scroll_area())

    def parent_scroll_area(self):
        widget = self.parentWidget()
        while widget is not None and not isinstance(widget, QScrollArea):
            widget = widget.parentWidget()
        return widget or self

    # -- content -------------------------------------------------------
    def set_items(self, items, selected=None):
        names = {item.name for item in items}
        self._items = list(items)
        keep = [name for name in (selected if selected is not None else self._selected)
                if name in names]
        # The block a drag carries is the visible order, not click order.
        self._selected = [item.name for item in self._items if item.name in set(keep)]
        if self._anchor not in names:
            self._anchor = None
        self._touched.intersection_update(names)
        self._relayout()

    def selected(self):
        return list(self._selected)

    def count(self):
        return len(self._items)

    def selected_block(self):
        from services.manual_order import selection_block
        return selection_block(self._items_names(), self._selected)

    def _chip_width(self, item):
        metrics = self.fontMetrics()
        width = metrics.horizontalAdvance(item.name)+22
        if item.count:
            width += metrics.horizontalAdvance(str(item.count))+7
        return max(self.MIN_CHIP, width)

    def set_section_axis(self, horizontal):
        """Section groups flow along the panel's placement axis."""
        if self.section_content.horizontal == horizontal:
            return
        self.section_content.horizontal = horizontal
        self._relayout()

    def _relayout(self):
        headers, rects, height = self.section_content.build(
            self._items, self.projection, self.width(), self._chip_width)
        self._rects = rects
        self._section_headers = headers
        self._content_height = height
        self.setMinimumHeight(self._content_height)
        self.update()

    def sizeHint(self):
        return QSize(self.width() or 320, self._content_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def heightForWidth(self, width):
        return self._content_height

    # -- painting ------------------------------------------------------
    def paintEvent(self, event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        c=visual.colors();metrics=self.fontMetrics()
        for key,header in self._section_headers:SectionHeader.paint(painter,header,key)
        for index,item in enumerate(self._items):
            rect=self._rects[index]
            active=item.name in self.active_filters
            managed=item.name in self._selected
            hovered=index==self._hovered
            painter.setBrush(QColor(c['selected'] if active else c['hover'] if hovered else c['surface']))
            painter.setPen(QPen(QColor(c['accent'] if active else c['border']),1))
            r=QRectF(rect).adjusted(.5,.5,-.5,-.5)
            from fluent_ui.presentation.tag_shape import tag_path
            path=tag_path(r)
            painter.drawPath(path)
            if active:
                painter.setPen(QPen(QColor(c['accent']),2,Qt.SolidLine,Qt.RoundCap))
                painter.drawLine(rect.left()+28,rect.top()+3,min(rect.right()-12,rect.left()+44),rect.top()+3)
            if managed:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(c['text_secondary']),1,Qt.DashLine))
                painter.drawPath(path)
            x=rect.left()+12;available=max(0,rect.right()-x-5)
            text_width=metrics.horizontalAdvance(item.name)
            show_count=item.count and text_width+metrics.horizontalAdvance(str(item.count))+7<=available
            painter.setPen(QColor(c['text']))
            painter.drawText(QRect(x,rect.top(),available,rect.height()),Qt.AlignVCenter,metrics.elidedText(item.name,Qt.ElideRight,available))
            if show_count:
                painter.setFont(visual.font('data'))
                painter.setPen(QColor(c['muted']))
                painter.drawText(QRect(x+text_width+7,rect.top(),available-text_width-7,rect.height()),Qt.AlignVCenter,str(item.count))
                painter.setFont(self.font())
        painter.end()

    def refresh_theme(self):
        self.update()

    # -- hit testing ----------------------------------------------------
    def _index_at(self, pos):
        for index, rect in enumerate(self._rects):
            if rect.contains(pos):
                return index
        return -1

    # -- selection ------------------------------------------------------
    def _set_selection(self, names):
        self._selected = [item.name for item in self._items if item.name in set(names)]
        self.update()
        self.selection_changed.emit(list(self._selected))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._press_pos = event.position().toPoint()
        self._dragging = False
        self._pending_collapse = None
        self._filter_click = None
        index = self._index_at(self._press_pos)
        if index < 0:
            self._set_selection([])
            self._anchor = None
            self._touched.clear()
            return
        name = self._items[index].name
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            wanted = set(self._selected)
            wanted.symmetric_difference_update({name})
            self._set_selection(wanted)
            self._anchor, self._touched = name, set()
        elif modifiers & Qt.ShiftModifier and self._anchor in self._items_names():
            keys = self._items_names()
            start, end = keys.index(self._anchor), keys.index(name)
            low, high = min(start, end), max(start, end)
            wanted = set(keys[low:high+1])
            # Only the range the previous shift click added is replaced, so the
            # anchor stays put and dragging the range keeps growing.
            self._set_selection((set(self._selected)-self._touched) | wanted)
            self._touched = wanted
        else:
            # A normal click filters only on release. The current management
            # block stays intact in case this gesture becomes a drag.
            self._filter_click = name
            self._anchor, self._touched = name, set()

    def _items_names(self):
        return [item.name for item in self._items]

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._filter_click and not self._dragging:
            index = self._index_at(event.position().toPoint())
            if index >= 0 and self._items[index].name == self._filter_click:
                self.filter_requested.emit(self._filter_click)
        self._filter_click = None
        self._pending_collapse = None
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        hovered = self._index_at(pos)
        if hovered != self._hovered:
            self._hovered = hovered
            self.update()
        self.setToolTip(self._items[hovered].name if hovered >= 0 else '')
        if not (event.buttons() & Qt.LeftButton) or self._press_pos is None:
            return super().mouseMoveEvent(event)
        if (pos-self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        if self._filter_click and self._filter_click not in self._selected:
            self._set_selection([self._filter_click])
        self._filter_click = None
        self._start_drag()

    def leaveEvent(self, event):
        self._hovered = -1
        self.update()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        index = self._index_at(event.pos())
        name = self._items[index].name if index >= 0 else None
        if name is not None and name not in self._selected:
            self._set_selection([name])
            self._anchor = name
        self.context_requested.emit(name, self.mapToGlobal(event.pos()))

    # -- drag source ----------------------------------------------------
    def _start_drag(self):
        block = self.selected_block()
        if not block:
            return
        self._dragging = True
        mime = QMimeData()
        mime.setData(TAG_MIME, json.dumps(block).encode('utf-8'))
        try:
            execute_drag(self, mime, self._drag_pixmap(block), self.end_drag_session,
                         QPoint(20, self.CHIP_HEIGHT//2))
        finally:
            self._dragging = False
            self._press_pos = None
            self._pending_collapse = None

    def end_drag_session(self):
        if self._drag_session is not None:
            self.drag_hint_cleared.emit(self._drag_session)
        self._drag_session = None
        self.feedback.clear()
        self.scroller.stop()

    def _drag_pixmap(self, block):
        text = block[0] if len(block) == 1 else f"{block[0]} +{len(block)-1}"
        metrics = QFontMetrics(self.font())
        width = min(240, metrics.horizontalAdvance(text)+24)
        pixmap = QPixmap(width, self.CHIP_HEIGHT)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = visual.colors()
        painter.setBrush(QColor(palette['surface_raised']))
        painter.setPen(QPen(QColor(visual.accent()), 1))
        painter.drawRoundedRect(QRectF(pixmap.rect()).adjusted(.5, .5, -.5, -.5),
                                visual.CONTROL_RADIUS/2, visual.CONTROL_RADIUS/2)
        painter.setPen(QColor(palette['text']))
        painter.drawText(pixmap.rect(), Qt.AlignCenter,
                         metrics.elidedText(text, Qt.ElideRight, width-16))
        painter.end()
        return pixmap

    # -- drop target ----------------------------------------------------
    def dragEnterEvent(self, event):
        self.end_drag_session()
        self._manual_warned = False
        self._drag_session = DragSession(event.mimeData())
        if self._drag_session.supported and self._drag_session.kind in (TAG_MIME, RESOURCE_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self._track(event)

    def dragLeaveEvent(self, event):
        self.end_drag_session()
        super().dragLeaveEvent(event)

    def _resolve(self, pos, mime):
        """Returns (DropTarget, rect the indicator is measured from)."""
        index = self._index_at(pos)
        if mime.hasFormat(RESOURCE_MIME):
            if index < 0:
                # Resources land *on* a tag; blank panel space has no tag.
                return INVALID_TARGET, None
            name = self._items[index].name
            return tag_drop_target(name), self._rects[index]
        if mime.hasFormat(TAG_MIME):
            if not getattr(self, 'manual_order', True):
                return INVALID_TARGET, None
            moving = parse_list_payload(mime.data(TAG_MIME))
            if index >= 0 and self._items[index].name in moving:
                return INVALID_TARGET, None
            if index < 0:
                if not self._rects:
                    return INVALID_TARGET, None
                return (DropTarget(APPEND, MOVE, None, None, len(self._items)),
                        self._rects[-1])
            placement = split_placement(axis_ratio(self._rects[index], pos, horizontal=True))
            step = 1 if placement == INSERT_AFTER else 0
            return (DropTarget(placement, MOVE, self._items[index].name, None, index+step),
                    self._rects[index])
        return INVALID_TARGET, None

    def _track(self, event):
        pos = event.position().toPoint()
        self.scroller.track(self.mapTo(self.parent_scroll_area().viewport(), pos))
        target, rect = self._resolve(pos, event.mimeData())
        if not target.valid:
            # A projected order has no slot to drop into. Say so once per drag
            # instead of silently refusing; never switch back to MANUAL.
            moving = parse_list_payload(event.mimeData().data(TAG_MIME)) if event.mimeData().hasFormat(TAG_MIME) else []
            index = self._index_at(pos)
            attempt = bool(moving and index >= 0 and self._items[index].name not in moving)
            if index < 0 and moving and self._rects:
                last = self._rects[-1]
                attempt = last.top() <= pos.y() <= last.bottom() and pos.x() > last.right() and self._items[-1].name not in moving
            if (not self._manual_warned and not getattr(self, 'manual_order', True) and attempt):
                self._manual_warned = True
                self.manual_required.emit()
            elif not attempt and self._drag_session is not None:
                self.drag_hint_cleared.emit(self._drag_session)
            self.feedback.clear()
            event.ignore()
            return
        event.acceptProposedAction()
        placement = INTO if target.placement == INTO else target.placement
        self.feedback.show_target(placement, rect, vertical=True)

    def dropEvent(self, event):
        try:
            target, _rect = self._resolve(event.position().toPoint(), event.mimeData())
            if self._drag_session and self._drag_session.commit(target, self._commit_target):
                event.acceptProposedAction()
            else:
                event.ignore()
        finally:
            self.end_drag_session()

    def _commit_target(self, target, block):
        if target.effect == APPLY_TAG:
            self.apply_requested.emit(block, target.target_id)
        elif target.effect == MOVE:
            self.reorder_requested.emit(block, target.target_id, target.placement)


class TagPanel(QWidget):
    """Tag presentation; placement, extent and collapsed state are the host's."""

    message_requested = Signal(str, str, bool)      # title, content, is_error
    tags_changed = Signal()
    filter_requested = Signal(str)
    apply_requested = Signal(list, str)             # resource paths, tag
    toggle_collapse_requested = Signal()            # the host owns the state

    UNBOUNDED = 16777215            # Qt's QWIDGETSIZE_MAX, not exported by PySide6

    def __init__(self, model, config=None, parent=None):
        super().__init__(parent)
        self.model = model
        self.config = config
        self.sort_mode = SortProjection(config.get('tag_sort', 'manual') if config else 'manual')
        self._source_items = []
        self._placement = TagPanelPlacement.BOTTOM
        self.collapsed = False
        self._collapsed_horizontal = True
        self._collapsed_ready = False
        self.collapsed_metrics = visual.TAG_COLLAPSED_METRICS
        self.setObjectName('TagPanel')
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.chrome = EdgeDockPanelChrome(self)
        layout.addWidget(self.chrome, 1)
        self.expanded_body = QWidget(self)
        expanded_layout = QVBoxLayout(self.expanded_body)
        expanded_layout.setContentsMargins(2,0,2,0)
        expanded_layout.setSpacing(visual.COMPACT_CONTROLS.spacing)

        self.header = header = QWidget(self.expanded_body)
        header.installEventFilter(self)
        header.setStyleSheet('background: transparent;')
        row = self.header_row = QHBoxLayout(header)
        m = visual.COMPACT_CONTROLS
        row.setContentsMargins(8,1,6,1)
        row.setSpacing(m.spacing)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header.setFixedHeight(30)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_position_menu)
        self.title_label = title = translated(CompactTitleLabel, '标签', header)
        title.setProperty('role', 'section')
        title.setStyleSheet('padding: 0px;')
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row.addWidget(title, 1)
        self.count_label = QLabel('', header)
        self.count_label.setProperty('role', 'data')
        row.addWidget(self.count_label)
        # The same three-state control the sidebar and the gallery use, so
        # clicking cycles MANUAL -> A_Z -> Z_A -> MANUAL with one shared rule.
        self.btn_sort = SortCycleButton('标签显示排序', header)
        self.btn_sort.set_mode(self.sort_mode)
        self.btn_sort.mode_changed.connect(self._on_sort_cycled)
        row.addWidget(self.btn_sort)
        self.btn_collapse=EdgeDockPanelChrome(self,expanded=True)
        self.btn_collapse.setFixedSize(24,24);row.addWidget(self.btn_collapse)
        self.btn_new = TransparentToolButton(FIF.NEW_TAG, header)
        bind_text(self.btn_new, '新建标签', 'setToolTip')
        bind_text(self.btn_new, '新建标签', 'setAccessibleName')
        self.btn_new.setFixedSize(m.action_extent, m.action_extent)
        self.btn_new.setIconSize(QSize(m.icon, m.icon))
        self.btn_new.clicked.connect(lambda: self.create_tag())

        expanded_layout.addWidget(header)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        self.flow = TagFlow(self.scroll)
        self.scroll.setWidget(self.flow)
        self.scroll.viewport().setAcceptDrops(True)
        self.scroll.viewport().installEventFilter(self)
        # QScrollArea.setWidget enables autoFillBackground on its content.
        # Keep the flow and navigator on the same inherited Panel surface.
        self.flow.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)

        self.index_view = SectionNavigator(self)
        self.index_view.section_requested.connect(self._jump_section)
        self.axis_strip=QWidget(self.expanded_body)
        self.axis_layout=QBoxLayout(QBoxLayout.TopToBottom,self.axis_strip)
        self.axis_layout.setContentsMargins(0,0,0,0);self.axis_layout.setSpacing(0)
        self.btn_new.setParent(self.axis_strip);self.axis_layout.addWidget(self.btn_new)
        self.axis_layout.addWidget(self.index_view);self.axis_layout.addStretch(1)
        self.flow_area=QWidget(self.expanded_body)
        self.index_layout=QBoxLayout(QBoxLayout.LeftToRight,self.flow_area)
        self.index_layout.setContentsMargins(0,0,0,0);self.index_layout.setSpacing(0)
        self.index_layout.addWidget(self.scroll,1);self.index_layout.addWidget(self.axis_strip)
        expanded_layout.addWidget(self.flow_area,1)
        self.index_body=QWidget(self)
        whole=QVBoxLayout(self.index_body);whole.setContentsMargins(0,0,0,0);whole.setSpacing(0)
        whole.addWidget(self.expanded_body)
        layout.addWidget(self.index_body,1)
        # A starting value only. TagPanelHost is the authority: it derives both
        # axes from the placement and re-asserts them at every geometry
        # boundary, so the panel never decides them from its own size.
        self.apply_placement_axis(True)

        self.flow.filter_requested.connect(self.filter_requested)
        self.flow.selection_changed.connect(self._on_selection)
        self.flow.context_requested.connect(self._show_context_menu)
        self.flow.reorder_requested.connect(self._reorder)
        self.flow.apply_requested.connect(self._apply_to_resources)

        self.setMinimumSize(110, 84)
        self.set_collapsed(False, True)
        i18n_engine.language_changed.connect(self._refresh_header)

    # -- collapsed presentation ----------------------------------------
    def collapsed_extent(self):
        """Theme chrome metrics determine thickness, independently of content."""
        return self.collapsed_metrics.extent

    def set_collapsed(self, collapsed, horizontal=None, *, transitioning=False):
        """Host-fed presentation only; all collapsed edges share one rail."""
        collapsed = bool(collapsed)
        horizontal = self._collapsed_horizontal if horizontal is None else bool(horizontal)
        if self._collapsed_ready and (collapsed, horizontal, transitioning) == (self.collapsed, self._collapsed_horizontal, getattr(self, '_transitioning', False)):
            return
        self.collapsed, self._collapsed_horizontal = collapsed, horizontal
        self._transitioning = transitioning
        self._collapsed_ready = True
        self.chrome.setVisible(collapsed)
        self.index_body.setVisible(not collapsed)
        if transitioning:
            # Keep the current dock extent legal until the host animates it.
            extent = self.collapsed_extent()
            self.setMinimumSize(2*extent, extent) if horizontal else self.setMinimumSize(extent, 2*extent)
            self.setMaximumSize(self.UNBOUNDED, self.UNBOUNDED)
        elif collapsed:
            extent = self.collapsed_extent()
            # Fixed on the dock axis in both directions: neither the splitter's
            # remembered size nor any content minimum can thicken the strip.
            if horizontal:
                self.setMinimumSize(2*extent, extent)
                self.setMaximumSize(self.UNBOUNDED, extent)
            else:
                self.setMinimumSize(extent, 2*extent)
                self.setMaximumSize(extent, self.UNBOUNDED)
        else:
            self.setMinimumSize(110, 84)
            self.setMaximumSize(self.UNBOUNDED, self.UNBOUNDED)
        self._fit_collapsed_identity()
        self.updateGeometry()

    def _fit_collapsed_identity(self):
        """Counts yield before command targets or the title; never grow chrome."""
        available = self.header.width() - (self.btn_sort.width() + self.btn_collapse.width()
                    + self.title_label.sizeHint().width() + 5*visual.COMPACT_CONTROLS.spacing)
        self.count_label.setVisible(available >= self.count_label.sizeHint().width())
        self.title_label.setToolTip(t('标签'))
        self.title_label.setAccessibleName(t('标签'))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._collapsed_ready:
            self._fit_collapsed_identity()

    def eventFilter(self, watched, event):
        scroll_area = self.__dict__.get('scroll')
        if scroll_area is not None and watched is scroll_area.viewport() and event.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop, QEvent.DragLeave):
            # Events already on TagFlow are handled there; this adapter handles
            # the remaining viewport area without inventing another drop rule.
            if event.type() == QEvent.DragLeave:
                self.flow.end_drag_session()
            elif event.type() == QEvent.DragEnter:
                self.flow.dragEnterEvent(event)
            else:
                from fluent_ui.components.drop_contract import MappedDropEvent
                mapped = MappedDropEvent(event, self.flow.mapFrom(watched, event.position().toPoint()))
                (self.flow.dropEvent if event.type() == QEvent.Drop else self.flow.dragMoveEvent)(mapped)
            return True

        if watched is self.header and event.type() == QEvent.Resize and self._collapsed_ready:
            self._fit_collapsed_identity()
        return super().eventFilter(watched, event)

    def set_panel_placement(self, placement):
        self._placement = TagPanelPlacement(placement)
        if hasattr(self,'btn_collapse'):self.btn_collapse.update()

    # -- content -------------------------------------------------------
    def set_items(self, items, selected=None):
        self._source_items = list(items)
        projection = SectionedProjection(items, self.sort_mode)
        self.flow.manual_order = self.sort_mode == SortProjection.MANUAL
        self.flow.sections_enabled = self.sort_mode != SortProjection.MANUAL
        self.flow.projection = projection
        self.flow.set_items(projection.items, selected)
        self.index_view.set_model(SectionIndexModel(projection))
        self.index_view.setVisible(self.sort_mode != SortProjection.MANUAL)
        self._refresh_header()

    def apply_placement_axis(self, horizontal):
        """Both presentation axes, from the one placement value.

        The section content and the alphabet index are different concerns --
        one is a flow of section groups, the other a strip of letters -- but
        they read the same fact: where the panel is. Setting only one of them
        is what let a horizontal placement keep a vertically stacked section
        list.
        """
        key=(bool(horizontal),self._placement)
        if getattr(self,'_axis_key',None)==key:return
        self._axis_key=key
        self.flow.set_section_axis(horizontal)
        self.index_layout.setDirection(
            (QBoxLayout.BottomToTop if self._placement.leading else QBoxLayout.TopToBottom)
            if horizontal else (QBoxLayout.RightToLeft if self._placement.leading else QBoxLayout.LeftToRight))
        self.index_view.set_orientation(Qt.Horizontal if horizontal else Qt.Vertical)
        self.axis_layout.removeWidget(self.index_view);self.axis_layout.removeWidget(self.btn_new)
        self.axis_layout.setDirection(QBoxLayout.LeftToRight if horizontal else QBoxLayout.TopToBottom)
        extent=visual.SECTION_INDEX_COMPACT_EXTENT
        self.axis_strip.setMinimumSize(0,0);self.axis_strip.setMaximumSize(self.UNBOUNDED,self.UNBOUNDED)
        self.btn_new.setFixedSize(extent,extent)
        if horizontal:
            self.axis_strip.setFixedHeight(extent)
            self.axis_layout.insertWidget(0,self.index_view);self.axis_layout.addWidget(self.btn_new)
        else:
            self.axis_strip.setFixedWidth(extent)
            self.axis_layout.insertWidget(0,self.btn_new);self.axis_layout.insertWidget(1,self.index_view)
        self.axis_layout.setAlignment(self.index_view,Qt.AlignLeft|Qt.AlignVCenter if horizontal else Qt.AlignTop|Qt.AlignHCenter)
        self.axis_layout.setAlignment(self.btn_new,Qt.AlignVCenter if horizontal else Qt.AlignTop|Qt.AlignHCenter)

    def _show_position_menu(self,pos):
        menu=SafeRoundMenu(parent=self)
        for value,label in [('top','顶部'),('bottom','底部'),('left','左侧'),('right','右侧')]:
            action=Action(t(label),menu);action.setCheckable(True);action.setChecked(self._placement.value==value)
            action.triggered.connect(lambda checked=False,v=value:self._request_position(v))
            menu.addAction(action)
        menu.exec(self.header.mapToGlobal(pos))

    def _request_position(self,value):
        host=self.parentWidget()
        while host is not None and not hasattr(host,'set_placement'):host=host.parentWidget()
        if host is not None:
            host.set_placement(value)
            center=getattr(self.window(),'setting_interface',None)
            if center is not None:center.sync_external_preference('tag_panel_placement',value)

    def _jump_section(self, section):
        index = self.index_view.model.positions.get(section)
        if index is not None and index < len(self.flow._rects):
            header = next((rect for key, rect in self.flow._section_headers if key == section), self.flow._rects[index])
            self.scroll.verticalScrollBar().setValue(header.top())

    def _on_sort_cycled(self, mode):
        self.set_sort(mode)

    def set_sort(self, mode):
        self.sort_mode = SortProjection(mode)
        self.btn_sort.set_mode(self.sort_mode)
        if self.config:
            self.config.set('tag_sort', self.sort_mode.value)
        self.set_items(self._source_items, self.selected())

    def selected(self):
        return self.flow.selected()

    def _refresh_header(self, *args):
        self.count_label.setText(str(self.flow.count()))
        self.count_label.setToolTip(t('{value_0} 个标签').format(value_0=self.flow.count()))
        self._fit_collapsed_identity()

    def refresh_theme(self):
        self.flow.refresh_theme()
        self.chrome.update();self.btn_collapse.update()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = visual.colors()
        painter.setPen(Qt.NoPen)
        material=QColor(palette['surface_overlay'])
        if self.collapsed:
            material.setAlpha(210);painter.fillRect(self.rect(),material);return
        title_y=self.header.mapTo(self,QPoint()).y()+self.header.height()
        material.setAlpha(175);painter.fillRect(QRect(0,title_y,self.width(),self.height()-title_y),material)
        material.setAlpha(210);painter.fillRect(QRect(0,0,self.width(),title_y),material)
        painter.setPen(QPen(QColor(palette['border_soft']),1))
        painter.drawLine(8,title_y,self.width()-8,title_y)
        painter.end()

    # -- tag operations ------------------------------------------------
    def create_tag(self):
        name, ok = dialogs.prompt_text(self.window(), t('新建标签'), t('标签名'), '',
                                       hint=t('标签属于整个表情库，不是当前分类的子项。'),
                                       code='TAG/NEW')
        if not ok:
            return
        reason = self.model.create(name)
        if reason:
            self._report(reason)
            return
        self.tags_changed.emit()
        self.message_requested.emit(t('标签已创建'), name.strip(), False)

    def _rename(self, name):
        value, ok = dialogs.prompt_text(self.window(), t('重命名标签'), t('标签名'), name,
                                        code='TAG/RENAME')
        if not ok:
            return
        reason = self.model.rename(name, value)
        if reason:
            self._report(reason)
            return
        self.tags_changed.emit()
        self.message_requested.emit(t('标签已重命名'), value.strip(), False)

    def _delete(self, names):
        names = list(names)
        if not names:
            return
        if len(names) == 1:
            question = t('删除标签 {value_0}？').format(value_0=names[0])
        else:
            question = t('删除选中的 {value_0} 个标签？').format(value_0=len(names))
        if not dialogs.confirm(self.window(), t('删除标签'), question, ok_text=t('删除'),
                               danger=True, code='TAG/DELETE',
                               hint=t('只删除标签本身以及它与表情的关联，不会删除任何表情文件。')):
            return
        self.model.delete(names)
        self.tags_changed.emit()
        self.message_requested.emit(t('标签已删除'), ' / '.join(names), False)

    def _report(self, reason):
        text = {EMPTY: '标签名不能为空', SPACE: '标签名不能包含空格',
                EXISTS: '已有同名标签'}.get(reason, '操作未完成')
        self.message_requested.emit(t('无法完成'), t(text), True)

    def _reorder(self, moving, target, placement):
        if self.model.reorder(moving, target, placement):
            self.tags_changed.emit()

    def _apply_to_resources(self, paths, tag):
        self.apply_requested.emit(paths, tag)

    # -- menus ---------------------------------------------------------
    def _show_context_menu(self, name, global_pos):
        menu = SafeRoundMenu(parent=self)
        selection = self.flow.selected()
        if name is None:
            action = translated(Action, '新建标签', parent=menu)
            action.triggered.connect(lambda: self.create_tag())
            menu.addAction(action)
            menu.exec(global_pos)
            return
        if len(selection) <= 1:
            rename = translated(Action, '重命名标签…', parent=menu)
            rename.triggered.connect(lambda: self._rename(name))
            menu.addAction(rename)
            menu.addSeparator()
            delete = translated(Action, '删除标签', parent=menu)
            delete.triggered.connect(lambda: self._delete([name]))
            menu.addAction(delete)
        else:
            delete = Action(t('删除选中的 {value_0} 个标签').format(value_0=len(selection)), parent=menu)
            delete.triggered.connect(lambda: self._delete(selection))
            menu.addAction(delete)
        menu.exec(global_pos)

    def set_active_filters(self, names):
        self.flow.active_filters = set(names)
        self.flow.update()
        self.chrome.update()
        self.chrome.setToolTip(t('展开标签') + (f" · {len(names)} " + t('标签筛选') if names else ''))

    def _on_selection(self, _names):
        self._refresh_header()
