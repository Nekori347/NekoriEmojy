"""Categorized icon navigation projected from the existing LibraryTree."""
from enum import Enum
from PySide6.QtCore import Qt, QPoint, QRect, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QCursor
from PySide6.QtWidgets import QScrollArea, QWidget, QApplication, QLabel
from fluent_ui import visual
from fluent_ui.icons import Icon
from services.i18n import t
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
        self.verticalScrollBar().valueChanged.connect(self.canvas.refresh_hover)

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
        self.canvas.collapsed.intersection_update(record[0] for record in records)
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
        self.setFont(visual.font('secondary'))
        self.host = host
        self.items, self.rects = [], []
        self.group_rects, self.group_by_index = [], {}
        self._press = None
        self._hovered = -1
        self._hover_pos = None
        self._hovered_group = -1
        self._disclosure_press = None
        state = host.tree.sidebar.gallery_view._saved_view_state
        self.collapsed = set(state.get('sidebar_icons_collapsed', []))
        self.visible_indices = []
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
        tile_width = max(32,size+8, self.fontMetrics().height()*3 if labels else 0)
        tile_height = max(32,size+14+(label_height+2 if labels else 0))
        rects, y, column, active_depth = [QRect() for _ in self.items], 4, 0, None
        self.visible_indices = []; hidden_depth = None
        starts = {self.projection.itemsBySection[key][0]['id']: key for key in self.projection.sections}
        self.section_headers = {}
        for item_index, (_node, _name, _icon, depth, group) in enumerate(self.items):
            if hidden_depth is not None and depth > hidden_depth:
                continue
            hidden_depth = depth if group and _node in self.collapsed else None
            self.visible_indices.append(item_index)
            if depth==0 and item_index and (group or self.items[item_index-1][3]>0 or self.items[item_index-1][4]):
                if column:y+=tile_height+spacing;column=0
                y+=10
            if _node in starts:
                if column:
                    y += tile_height+spacing
                column = 0
                self.section_headers[starts[_node]] = QRect(8, y, max(1, self.width()-16), SectionHeader.HEIGHT)
                y += SectionHeader.HEIGHT
            indent = min(depth, 3)*4
            available = max(1, self.width()-16-indent)
            capacity = max(1, (available+spacing)//(tile_width+spacing))
            if group or depth != active_depth:
                if column:
                    y += tile_height+spacing
                column = 0
            if group:
                height = max(38, size+18)
                rects[item_index] = QRect(8+indent, y, available, height)
                y += height+spacing
            else:
                width = tile_width+spacing
                grid_left=8+indent+(available-(capacity*width-spacing))//2
                rects[item_index] = QRect(grid_left+column*width, y, tile_width, tile_height)
                column += 1
                if column == capacity:
                    column = 0
                    y += tile_height+spacing
            active_depth = depth
        if column:
            y += tile_height+spacing
        self.rects = rects
        self.group_rects=[];self.group_by_index={}
        for i,(_,_,_,depth,group) in enumerate(self.items):
            if not group or depth!=0 or rects[i].isEmpty():continue
            end=i
            while end+1<len(self.items) and self.items[end+1][3]>depth:end+=1
            bottom=max(rect.bottom() for rect in rects[i:end+1] if not rect.isEmpty())
            card=QRect(4,rects[i].top()-2,max(1,self.width()-8),bottom-rects[i].top()+6)
            self.group_rects.append(card);self.group_by_index[i]=card
        self.setMinimumHeight(y+8)
        self.refresh_hover()
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

    def group_at(self, pos):
        if pos is None:return -1
        return next((i for i, rect in self.group_by_index.items() if rect.contains(pos)), -1)

    def disclosure_rect(self, index):
        if index < 0 or not self.items[index][4] or self.rects[index].isEmpty():return QRect()
        rect=self.rects[index]
        return QRect(rect.right()-29,rect.center().y()-14,28,28)

    def _update_hover(self, pos):
        self._hover_pos=pos
        self._hovered=self.index_at(pos) if pos is not None else -1
        self._hovered_group=self.group_at(pos)

    def refresh_hover(self, *_):
        # Layout/scroll changes invalidate old canvas coordinates. Resolve the
        # local target from the cursor, never retain a now-hidden item index.
        point=QCursor.pos()
        self._update_hover(self.mapFromGlobal(point) if QApplication.widgetAt(point) is self else None)
        self.update()

    def _collapsed_selection_index(self):
        """Same single-hidden-selection ancestry rule as NavigationItem."""
        selected=self.host.tree.selectedItems()
        if len(selected)!=1:return -1
        selected_id=selected[0].data(0,Qt.UserRole)
        index=next((i for i,item in enumerate(self.items) if item[0]==selected_id),-1)
        if index<0 or not self.rects[index].isEmpty():return -1
        ancestor=selected[0].parent();target=None
        while ancestor is not None:
            key=ancestor.data(0,Qt.UserRole)
            if key in self.collapsed:target=key
            ancestor=ancestor.parent()
        return next((i for i,item in enumerate(self.items) if item[0]==target and not self.rects[i].isEmpty()),-1)

    def _collapsed_selection_rect(self, index=None):
        index=self._collapsed_selection_index() if index is None else index
        if index<0:return QRect()
        # Root cards use their complete existing perimeter. A nested collapsed
        # drawer retains its own full-width header and surrounding inset.
        return self.group_by_index.get(index,self.rects[index].adjusted(-2,-2,2,3))

    def _toggle_drawer(self, index):
        node_id=self.items[index][0]
        self.collapsed.symmetric_difference_update({node_id})
        self.end_drag_session()
        self.relayout()
        # Keep this independent projection in the existing per-Library view
        # record, including when the gallery is in the transient Recent view.
        gallery=self.host.tree.sidebar.gallery_view
        states=dict(self.host.config.get('library_view_states',{}))
        state=dict(states.get(gallery._view_state_key,{}))
        state['sidebar_icons_collapsed']=sorted(self.collapsed)
        states[gallery._view_state_key]=state
        self.host.config.set('library_view_states',states)

    @staticmethod
    def _group_path(rect):
        path=QPainterPath();path.addRoundedRect(QRectF(rect).adjusted(.5,.5,-.5,-.5),10,10)
        return path

    def paintEvent(self, event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing);painter.setFont(self.font())
        palette=visual.colors()
        selected={item.data(0,Qt.UserRole) for item in self.host.tree.selectedItems()}
        # Card surfaces first; decorations last so item/header hover cannot
        # paint over the parent's selected line or complete hover perimeter.
        for index,group in self.group_by_index.items():
            chosen=self.items[index][0] in selected
            color=QColor(palette['selected'] if chosen else palette['surface_alt'])
            if index==self._hovered_group:
                hover=QColor(palette['hover'])
                if chosen:
                    color=QColor(*[round(color.getRgb()[i]*.45+hover.getRgb()[i]*.55) for i in range(3)])
                else:color=hover
            elif not chosen:color.setAlpha(85)
            painter.fillPath(self._group_path(group),color)
        size=int(self.host.config.get('sidebar_icon_size',20))
        labels=bool(self.host.config.get('sidebar_show_labels',True))
        for key,rect in self.section_headers.items():SectionHeader.paint(painter,rect,key)
        for index in self.visible_indices:
            node_id,name,icon,depth,group=self.items[index];rect=self.rects[index]
            if not event.rect().intersects(rect):continue
            chosen=node_id in selected
            if index not in self.group_by_index and (chosen or index==self._hovered):
                self._selection(painter,rect,palette,chosen,top_line=group,hovered=index==self._hovered)
            elif index==self._hovered:
                painter.setPen(Qt.NoPen);painter.setBrush(QColor(palette['hover']))
                painter.drawRoundedRect(rect,8,8)
            painter.setPen(QColor(palette['text']))
            if group:
                button=self.disclosure_rect(index)
                icon.paint(painter,QRect(rect.left()+8,rect.center().y()-size//2+3,size,size))
                if labels:
                    painter.drawText(rect.adjusted(size+14,6,-34,0),Qt.AlignVCenter,
                        self.fontMetrics().elidedText(name,Qt.ElideRight,max(1,rect.width()-size-48)))
                if self._hover_pos is not None and button.contains(self._hover_pos):
                    painter.setPen(Qt.NoPen);painter.setBrush(QColor(palette['selected']))
                    painter.drawRoundedRect(button,6,6)
                chevron=Icon.CHEVRON_RIGHT if node_id in self.collapsed else Icon.CHEVRON_DOWN_MED
                chevron.render(painter,QRect(button.center().x()-7,button.center().y()-7,14,14),fill=palette['text_secondary'])
            else:
                lines=self._label_lines(name,max(1,rect.width()-6)) if labels else ()
                line_height=self.fontMetrics().height()
                content_height=size+(2+len(lines)*line_height if lines else 0)
                top=rect.top()+(rect.height()-content_height)//2-3
                icon.paint(painter,QRect(rect.center().x()-size//2,top,size,size))
                for n,line in enumerate(lines):
                    painter.drawText(QRect(rect.left()+3,top+size+2+n*line_height,rect.width()-6,line_height),Qt.AlignCenter,line)
        hint=self._collapsed_selection_index()
        for index,group in self.group_by_index.items():
            path=self._group_path(group);hovered=index==self._hovered_group
            edge=QColor(palette['accent'] if hovered or index==hint else palette['border_soft'])
            edge.setAlpha(140 if index==hint else 170 if hovered else 90)
            pen=QPen(edge,1 if index==hint else 1.25 if hovered else 1)
            if index==hint:pen.setStyle(Qt.DashLine)
            painter.setBrush(Qt.NoBrush);painter.setPen(pen);painter.drawPath(path)
            if self.items[index][0] in selected:
                painter.save();painter.setClipPath(path)
                painter.fillRect(QRectF(group.left()+5,group.top()+4,max(1,group.width()-10),2),QColor(palette['accent']))
                painter.restore()
        if hint>=0 and hint not in self.group_by_index:
            color=QColor(palette['accent']);color.setAlpha(140)
            painter.setBrush(Qt.NoBrush);painter.setPen(QPen(color,1,Qt.DashLine))
            painter.drawPath(self._group_path(self._collapsed_selection_rect(hint)))

    def _selection(self,painter,rect,palette,selected,*,top_line=True,hovered=False):
        path=QPainterPath();path.addRoundedRect(QRectF(rect).adjusted(.5,.5,-.5,-.5),8,8)
        # Parent hover already fills with palette['hover']; using it again
        # made an unselected child's hover disappear into the same surface.
        painter.fillPath(path,QColor(palette['selected'] if selected else palette['surface_raised']))
        if hovered:
            painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor(palette['border']),1))
            painter.drawPath(path)
        if selected:
            painter.save();painter.setClipPath(path)
            y=rect.top()+4 if top_line else rect.bottom()-5
            painter.fillRect(QRectF(rect.left()+5,y,max(1,rect.width()-10),2),QColor(palette['accent']));painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press = event.position().toPoint()
            self._disclosure_press = None
            button_index=self.index_at(self._press)
            if button_index >= 0 and self.disclosure_rect(button_index).contains(self._press):
                self._disclosure_press=self.items[button_index][0]
                self._press=None
                event.accept()
                return
            self._dragged = False
            self._pending_collapse = None
            index = self.index_at(self._press)
            if index < 0:
                return
            node_id = self.items[index][0]
            selected = {item.data(0, Qt.UserRole) for item in self.host.tree.selectedItems()}
            keys = [self.items[i][0] for i in self.visible_indices]
            if event.modifiers() & Qt.ControlModifier:
                selected.symmetric_difference_update({node_id})
            elif event.modifiers() & Qt.ShiftModifier and self._anchor in keys:
                low, high = sorted((keys.index(self._anchor), keys.index(node_id)))
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
        pos=event.position().toPoint()
        was_button=self._hovered>=0 and self._hover_pos is not None and self.disclosure_rect(self._hovered).contains(self._hover_pos)
        previous=(self._hovered,self._hovered_group,was_button)
        self._update_hover(pos);index=self._hovered
        button=index>=0 and self.disclosure_rect(index).contains(pos)
        if previous!=(index,self._hovered_group,button):self.update()
        self.setToolTip(t('展开 / 折叠内容') if button else self.items[index][1] if index>=0 else '')
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

    def enterEvent(self,event):
        self._update_hover(event.position().toPoint());self.update()
        super().enterEvent(event)

    def leaveEvent(self,event):
        self._update_hover(None);self.update()
        super().leaveEvent(event)

    def hideEvent(self,event):
        self._update_hover(None)
        super().hideEvent(event)

    def mouseReleaseEvent(self, event):
        pos=event.position().toPoint();index=self.index_at(pos)
        if self._disclosure_press is not None:
            node=self._disclosure_press;self._disclosure_press=None
            if event.button()==Qt.LeftButton and index>=0 and self.items[index][0]==node and self.disclosure_rect(index).contains(pos):
                self._toggle_drawer(index)
            event.accept()
            return
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
            last=self.rects[self.visible_indices[-1]] if self.visible_indices else QRect()
            if kind and kind != TAG_MIME and (kind != NODE_MIME or self.host.tree.display_sort == 'manual') and not last.isEmpty() and pos.y() > last.bottom():
                return DropTarget(APPEND, effect, None, ROOT),last
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
