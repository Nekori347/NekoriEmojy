"""Categorized icon navigation projected from the existing LibraryTree."""
from enum import Enum
from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QScrollArea, QWidget, QApplication, QLabel
from fluent_ui import visual
from fluent_ui.components.navigation import CompactTitleLabel
from fluent_ui.components.drop_contract import (DropFeedback, EdgeAutoScroller, NODE_MIME,
    execute_drag, INVALID_TARGET, APPEND, DropTarget, TAG_MIME)
from fluent_ui.components.section_index import SectionHeader
from services.library_index import ROOT


class SidebarPresentationMode(str, Enum):
    TREE = 'tree'
    CATEGORIZED_ICONS = 'categorized_icons'


class LibraryTitle(CompactTitleLabel):
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent().parent().gallery_view.set_node(ROOT)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent().parent().toggle_presentation()
            event.accept()


class SidebarIcons(QScrollArea):
    def __init__(self, tree, config, parent=None):
        super().__init__(parent)
        self.tree, self.config = tree, config
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet('QScrollArea {background:transparent;border:none;}')
        self.viewport().setAutoFillBackground(False)
        self.viewport().setStyleSheet('background:transparent;')
        self.canvas = IconCanvas(self)
        self.setWidget(self.canvas)

    def refresh(self):
        records = []
        def walk(item, depth):
            if item.data(0, SectionHeader.ROLE):
                return
            node_id = item.data(0, Qt.UserRole)
            records.append((node_id, item.text(0), item.icon(0), depth, bool(item.childCount()) or node_id == ROOT))
            for index in range(item.childCount()):
                walk(item.child(index), depth+1)
        for index in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(index), 0)
        self.canvas.items = records
        self.canvas.projection = self.tree.section_projection
        self.canvas.relayout()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                size = max(14, min(48, int(self.config.get('sidebar_icon_size', 20)) + (2 if delta > 0 else -2)))
                self.config.set('sidebar_icon_size', size)
                self.tree.sidebar.apply_presentation()
            event.accept()
            return
        super().wheelEvent(event)


class IconCanvas(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.setFont(visual.font())
        self.host = host
        self.items, self.rects = [], []
        self._press = None
        self._hovered = -1
        self._dragged = False
        self._anchor = None
        self._pending_collapse = None
        self.section_headers = {}
        self.projection = host.tree.section_projection
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.feedback = DropFeedback(self)
        self.scroller = EdgeAutoScroller(host)

    def relayout(self):
        size = int(self.host.config.get('sidebar_icon_size', 20))
        labels = bool(self.host.config.get('sidebar_show_labels', True))
        spacing = 4
        label_height = 2*self.fontMetrics().height() if labels else 0
        tile_width = max(size+12, self.fontMetrics().height()*3+8 if labels else 0)
        tile_height = size+12+(label_height+4 if labels else 0)
        rects, y, column, active_depth = [], 4, 0, None
        starts = {self.projection.itemsBySection[key][0]['id']: key for key in self.projection.sections}
        self.section_headers = {}
        for _node, _name, _icon, depth, group in self.items:
            if _node in starts:
                if column:
                    y += tile_height+spacing
                column = 0
                self.section_headers[starts[_node]] = QRect(8, y, max(1, self.width()-16), SectionHeader.HEIGHT)
                y += SectionHeader.HEIGHT
            indent = min(depth, 5)*10
            available = max(1, self.width()-16-indent)
            capacity = max(1, (available+spacing)//(tile_width+spacing))
            if group or depth != active_depth:
                if column:
                    y += tile_height+spacing
                column = 0
            if group:
                height = max(28, size+8)
                rects.append(QRect(8+indent, y, available, height))
                y += height+spacing
            else:
                width = available//capacity
                rects.append(QRect(8+indent+column*width, y, width-spacing, tile_height))
                column += 1
                if column == capacity:
                    column = 0
                    y += tile_height+spacing
            active_depth = depth
        if column:
            y += tile_height+spacing
        self.rects = rects
        self.group_rects=[]
        for i,(_,_,_,depth,group) in enumerate(self.items):
            if not group or depth!=0:continue
            end=i
            while end+1<len(self.items) and self.items[end+1][3]>depth:end+=1
            bottom=max(rect.bottom() for rect in rects[i:end+1])
            self.group_rects.append(QRect(3,rects[i].top(),max(1,self.width()-6),bottom-rects[i].top()+4))
        self.setMinimumHeight(y+8)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout()

    def sizeHint(self):
        return QSize(200, self.minimumHeight())

    def index_at(self, pos):
        return next((i for i, rect in enumerate(self.rects) if rect.contains(pos)), -1)

    def _label_lines(self, text, width):
        metrics = self.fontMetrics()
        if metrics.horizontalAdvance(text) <= width:
            return (text,)
        count = 1
        while count < len(text) and metrics.horizontalAdvance(text[:count+1]) <= width:
            count += 1
        prefix = text[:count]
        space = prefix.rfind(' ')
        if space >= count//2:
            count = space+1
        first = text[:count].rstrip()
        second = metrics.elidedText(text[count:].lstrip(), Qt.ElideRight, width)
        return (first, second)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette=visual.colors()
        for group in getattr(self,'group_rects',[]):
            painter.setBrush(QColor(palette['surface_alt']));painter.setPen(QPen(QColor(palette['border_soft']),1))
            painter.drawRoundedRect(group,12,12)
        size = int(self.host.config.get('sidebar_icon_size', 20))
        labels = bool(self.host.config.get('sidebar_show_labels', True))
        palette = visual.colors()
        selected = {item.data(0, Qt.UserRole) for item in self.host.tree.selectedItems()}
        for key, rect in self.section_headers.items():
            SectionHeader.paint(painter, rect, key)
        for index, (node_id, name, icon, depth, group) in enumerate(self.items):
            rect = self.rects[index]
            if not event.rect().intersects(rect):
                continue
            if node_id in selected or index == self._hovered:
                painter.fillRect(rect, QColor(palette['hover'] if index == self._hovered else palette['selected']))
                painter.setPen(QPen(QColor(palette['accent']),2))
                painter.drawLine(rect.left()+3,rect.top()+7,rect.left()+3,rect.bottom()-7)
            painter.setPen(QColor(palette['text']))
            if group:
                icon.paint(painter, QRect(rect.left()+12, rect.center().y()-size//2, size, size))
                if labels:
                    painter.drawText(rect.adjusted(size+18, 0, -4, 0), Qt.AlignVCenter,
                                     self.fontMetrics().elidedText(name, Qt.ElideRight, rect.width()-size-22))
            else:
                icon.paint(painter, QRect(rect.center().x()-size//2, rect.top()+5, size, size))
                if labels:
                    line_height = self.fontMetrics().height()
                    for line_number, line in enumerate(self._label_lines(name, max(1, rect.width()-8))):
                        painter.drawText(QRect(rect.left()+4, rect.top()+size+8+line_number*line_height,
                                               rect.width()-8, line_height), Qt.AlignCenter, line)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press = event.position().toPoint()
            self._dragged = False
            self._pending_collapse = None
            index = self.index_at(self._press)
            if index < 0:
                return
            node_id = self.items[index][0]
            selected = {item.data(0, Qt.UserRole) for item in self.host.tree.selectedItems()}
            keys = [item[0] for item in self.items]
            if event.modifiers() & Qt.ControlModifier:
                selected.symmetric_difference_update({node_id})
            elif event.modifiers() & Qt.ShiftModifier and self._anchor in keys:
                low, high = sorted((keys.index(self._anchor), index))
                selected = set(keys[low:high+1])
            elif node_id in selected:
                self._pending_collapse = node_id
            else:
                selected = {node_id}
            if not event.modifiers() & Qt.ShiftModifier:
                self._anchor = node_id
            self._select(selected)

    def _select(self, ids):
        self.host.tree.clearSelection()
        for node_id in ids:
            item = self.host.tree._find_item(node_id)
            if item is not None:
                item.setSelected(True)
        self.update()

    def mouseMoveEvent(self, event):
        index = self.index_at(event.position().toPoint())
        if index != self._hovered:
            self._hovered=index;self.update()
        self.setToolTip(self.items[index][1] if index >= 0 else '')
        if self._press is None or not event.buttons() & Qt.LeftButton:
            return
        if (event.position().toPoint()-self._press).manhattanLength() < QApplication.startDragDistance():
            return
        source = self.index_at(self._press)
        if source < 0 or self.items[source][0] == ROOT:
            return
        self._dragged = True
        mime = self.host.tree.mimeData(self.host.tree.selectedItems())
        try:
            execute_drag(self, mime, self.items[source][2].pixmap(32, 32), self.end_drag_session)
        finally:
            self._press = None
            self._pending_collapse = None

    def leaveEvent(self,event):
        self._hovered=-1;self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        index = self.index_at(event.position().toPoint())
        if event.button() == Qt.LeftButton and index >= 0 and not self._dragged:
            if not event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
                if self._pending_collapse:
                    self._select({self._pending_collapse})
                self.host.tree.node_selected.emit(self.items[index][0])
        self._press = None
        self._pending_collapse = None

    def contextMenuEvent(self, event):
        index = self.index_at(event.pos())
        if index >= 0 and self.items[index][0] != ROOT:
            self.host.tree.node_menu_requested.emit(self.items[index][0], event.globalPos(), 'into')
        else:
            self.host.tree.blank_menu_requested.emit(event.globalPos())

    def resolve(self, pos, mime):
        index = self.index_at(pos)
        if index < 0:
            kind, effect = self.host.tree._dragged_kind(mime)
            if kind and kind != TAG_MIME and (kind != NODE_MIME or self.host.tree.display_sort == 'manual') and self.rects and pos.y() > self.rects[-1].bottom():
                return DropTarget(APPEND, effect, None, ROOT), self.rects[-1]
            return INVALID_TARGET, None
        rect = self.rects[index]
        # Group rows use vertical edges; tiles use left/right sibling edges.
        group = self.items[index][4]
        ratio = (pos.y()-rect.top())/max(1, rect.height()) if group else (pos.x()-rect.left())/max(1, rect.width())
        return self.host.tree.resolve_category_target(self.items[index][0], ratio, mime), rect

    def dragEnterEvent(self, event):
        self.end_drag_session()
        if self.host.tree.begin_drag_session(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        pos = event.position().toPoint()
        target, rect = self.resolve(pos, event.mimeData())
        if target.valid:
            index = self.index_at(pos)
            self.feedback.show_target(target.placement, rect, vertical=index >= 0 and not self.items[index][4])
            self.scroller.track(self.mapTo(self.host.viewport(), pos))
            event.acceptProposedAction()
        else:
            self.feedback.clear()
            event.ignore()

    def dragLeaveEvent(self, event):
        self.end_drag_session()

    def end_drag_session(self):
        self.feedback.clear()
        self.scroller.stop()
        self.host.tree.end_drag_session()

    def dropEvent(self, event):
        try:
            if self.host.tree._drag_session is None:
                event.ignore()
                return
            pos = event.position().toPoint()
            target, _rect = self.resolve(pos, event.mimeData())
            if self.host.tree._drag_session and self.host.tree.commit_target(target, event.mimeData(), self.mapToGlobal(pos)):
                event.acceptProposedAction()
            else:
                event.ignore()
        finally:
            self.end_drag_session()
