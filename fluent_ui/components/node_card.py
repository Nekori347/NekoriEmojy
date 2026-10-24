"""Full-width category break, kept in the resource/node mixed manual order."""
from services.i18n import t, bind_text, translated
import json
import os
from pathlib import Path
from services.exchange_icons import IMAGE_SUFFIXES, resolve_icon_path

from PySide6.QtCore import Qt, Signal, QMimeData, QPoint, QPointF, QRect, QRectF, QSize, QVariantAnimation
from PySide6.QtGui import (
    QColor, QDrag, QFont, QFontMetrics, QPainter, QPen, QPixmap, QCursor,
)
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy

from fluent_ui.components.drop_contract import NODE_MIME, RESOURCE_MIME
from fluent_ui.visual import DATA_FONT, accent, colors
from fluent_ui import visual
from fluent_ui.icons import Icon

__all__ = ['NodeCard', 'render_node_icon', 'NODE_MIME', 'RESOURCE_MIME']


def node_row_height(icon_size):
    """Compact at the default icon size; larger user icons keep their extent."""
    return max(30, max(14, min(48, int(icon_size))) + 8)


def render_node_icon(storage, record, size):
    """Return a QPixmap for a node icon; falls back to a neutral folder glyph."""
    size = max(14, int(size))
    value = (record.get("icon") or "").strip()
    path = (resolve_icon_path(storage.data_dir, value) if storage and
            Path(value).suffix.lower() in IMAGE_SUFFIXES else None)
    if path and os.path.isfile(path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if value:
        font = QFont("Segoe UI Emoji")
        font.setPixelSize(max(8, int(size * 0.78)))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, value)
    else:
        Icon.FOLDER.render(painter,QRectF(0,0,size,size),fill=colors()['text_secondary'])
    painter.end()
    return pixmap


class NodeCard(QLabel):
    """An ordered structural row: navigate and drag.

    It is a drag *source* only. What a drop onto a category means -- into it,
    before it, after it -- is resolved once by the surface that owns the drag,
    so this card never decides a placement or paints its own hint.
    """

    clicked = Signal(str, Qt.KeyboardModifiers)
    activated = Signal(str)
    disclosure_toggled = Signal(str)
    selection_changed = Signal(str, bool)
    context_requested = Signal(object, QPoint)

    def __init__(self, entry, storage, size=120, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.node_id = entry["id"]
        self.storage = storage
        self.current_size = size
        self.is_selectable = False
        self.is_selected = False
        self._hovered = False
        self._pressed = False
        self._keyboard_focus = False
        self._drag_start = None
        self._dragging = False
        # Set by the gallery: returns every node id that travels with one drag.
        self.drag_payload_provider = None
        self.expanded = False
        self._angle = 0.0
        self._motion = QVariantAnimation(self)
        self._motion.setDuration(visual.MOTION.expand)
        self._motion.setEasingCurve(visual.MOTION.easing)
        self._motion.valueChanged.connect(self._rotate)
        self.setFocusPolicy(Qt.TabFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        bind_text(self, t('{value_0}\n{value_1} 个子分类 · {value_2} 项内容').format(value_0=entry['name'], value_1=entry.get('children', 0), value_2=entry.get('total', 0)), 'setToolTip')
        self._icon = None
        self.refresh_icon()
        visual.theme.changed.connect(self.refresh_icon)
        visual.theme.accent_changed.connect(self.update)

    def set_expanded(self, expanded):
        if self.expanded == bool(expanded):
            return
        self.expanded = bool(expanded)
        self._motion.stop()
        self._motion.setStartValue(self._angle)
        self._motion.setEndValue(90.0 if expanded else 0.0)
        self._motion.start()
        self.update()

    def _rotate(self,value):
        self._angle=value
        self.update()

    # -- appearance ---------------------------------------------------
    def refresh_icon(self):
        extent = max(14, min(48, int(self.storage.config.get('gallery_node_icon_size', 22))))
        self._icon = render_node_icon(self.storage, self.entry.get("node", {"id": self.node_id}),
                                      extent)
        self._icon_extent = extent
        self.setFixedHeight(node_row_height(extent))
        self.update()

    def update_size(self, new_size, load_image=True):
        self.current_size = new_size
        self.refresh_icon()

    def needs_reload(self, target_size):
        return self._icon is None

    def clear_resources(self):
        self._icon = None
        self.update()

    def set_selectable(self, selectable):
        self.is_selectable = selectable

    def set_selected(self, selected):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()
            self.selection_changed.emit(self.node_id, selected)

    def disclosure_rect(self):
        return QRect(self.width()-32,0,32,self.height())

    def paintEvent(self, event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if self._dragging:p.setOpacity(.45)
        self._paint_row(p,self.width())
        p.end()

    def _paint_row(self,p,width,preview=False):
        c=colors()
        if self.is_selected and not preview:
            surface=QColor(c['surface_alt']);surface.setAlpha(155)
            p.setPen(Qt.NoPen);p.setBrush(surface)
            p.drawRoundedRect(QRectF(.5,.5,width-1,self.height()-1),5,5)
        active=self.is_selected or self._hovered or preview
        signal=QColor(accent() if active else c['border_soft'])
        p.setPen(QPen(signal,2))
        p.drawLine(6,(self.height()-18)//2,6,(self.height()+18)//2)

        if self._icon is not None:p.drawPixmap(16,(self.height()-self._icon.height())//2,self._icon)
        font=visual.font();font.setWeight(QFont.Medium);p.setFont(font)
        name_metrics=QFontMetrics(font)
        summary=f"{self.entry.get('children',0)}/{self.entry.get('total',0)}"
        count_font=QFont(font);count_font.setFamily(DATA_FONT.split(',')[0]);count_font.setPixelSize(11);count_font.setBold(False)
        count_width=QFontMetrics(count_font).horizontalAdvance(summary)+8
        count_x=width-(12 if preview else 40)-count_width
        p.setPen(QColor(c['text']))
        text_left = 16 + self._icon_extent + 8
        text_width = max(0, count_x-text_left-34)
        name=name_metrics.elidedText(self.entry['name'],Qt.ElideRight,text_width)
        p.drawText(QRect(text_left,0,text_width,self.height()),Qt.AlignVCenter,name)
        # One structural rule, with identical geometry in every state. Drop
        # placement stays with the gallery's separate feedback painter.
        line_start=text_left+name_metrics.horizontalAdvance(name)+10
        p.setPen(QPen(signal,2 if self._pressed else 1))
        if line_start<count_x-8:
            y=self.height()//2+.5
            p.drawLine(QPointF(line_start,y),QPointF(count_x-8,y))
        p.setPen(QColor(c['muted']))
        p.setFont(count_font)
        p.drawText(QRect(count_x,0,count_width,self.height()),Qt.AlignRight|Qt.AlignVCenter,summary)
        if not preview:
            x,y=self.disclosure_rect().center().x(),self.height()//2
            p.save();p.translate(x,y);p.rotate(self._angle)
            Icon.CHEVRON_RIGHT.render(p,QRectF(-7,-7,14,14),fill=c['text'] if self._hovered else c['text_secondary'])
            p.restore()
        if not preview and self.hasFocus() and self._keyboard_focus:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(c['text_secondary']),1,Qt.DotLine))
            p.drawRoundedRect(QRectF(1,1,width-2,self.height()-2),3,3)

    def drag_pixmap(self):
        """The same title layout on a compact native Qt drag surface."""
        width=min(self.width(),420)
        dpr=self.devicePixelRatioF()
        pixmap=QPixmap(QSize(round((width+8)*dpr),round((self.height()+8)*dpr)))
        pixmap.setDevicePixelRatio(dpr);pixmap.fill(Qt.transparent)
        p=QPainter(pixmap);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen)
        shadow=QColor(colors()['text']);shadow.setAlpha(25);p.setBrush(shadow)
        p.drawRoundedRect(QRectF(3,5,width+2,self.height()+1),6,6)
        surface=QColor(colors()['surface_alt']);surface.setAlpha(230);p.setBrush(surface)
        p.drawRoundedRect(QRectF(4,4,width,self.height()),5,5)
        p.translate(4,4);self._paint_row(p,width,preview=True)
        p.end()
        return pixmap

    # -- interaction --------------------------------------------------
    def enterEvent(self,event):
        self._hovered=True;self.update();super().enterEvent(event)

    def leaveEvent(self,event):
        self._hovered=False;self._pressed=False;self.update();super().leaveEvent(event)

    def hideEvent(self,event):
        self.reset_interaction();super().hideEvent(event)

    def showEvent(self,event):
        super().showEvent(event);self.sync_pointer_state()

    def moveEvent(self,event):
        super().moveEvent(event);self.sync_pointer_state()

    def reset_interaction(self):
        self._hovered=self._pressed=self._keyboard_focus=False
        self.update()

    def sync_pointer_state(self):
        hovered=self.isVisible() and QApplication.widgetAt(QCursor.pos()) is self
        if hovered!=self._hovered:
            self._hovered=hovered
            if not hovered:self._pressed=False
            self.update()

    def focusInEvent(self,event):
        self._keyboard_focus=event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason)
        super().focusInEvent(event);self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._keyboard_focus=False
            self._pressed=True;self.update()
            self.setFocus(Qt.MouseFocusReason)
            self._drag_start = None if self.disclosure_rect().contains(event.position().toPoint()) else event.position().toPoint()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start is None:
            return super().mouseMoveEvent(event)
        if (event.pos() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)

        self._pressed = False;self.update()
        drag = QDrag(self)
        mime = QMimeData()
        payload = self.drag_payload_provider(self.node_id) if self.drag_payload_provider else None
        mime.setData(NODE_MIME, json.dumps(payload or [self.node_id]).encode("utf-8"))
        drag.setMimeData(mime)
        pixmap=self.drag_pixmap()
        drag.setPixmap(pixmap)
        width=round(pixmap.width()/pixmap.devicePixelRatio())-8
        drag.setHotSpot(QPoint(min(self._drag_start.x(),width-12)+4,self._drag_start.y()+4))
        self._dragging=True;self.update()
        try:
            drag.exec(Qt.MoveAction)
        finally:
            self._drag_start=None;self._dragging=False;self._pressed=False
            self.sync_pointer_state();self.update()

    def mouseReleaseEvent(self, event):
        self._pressed=False;self.update()
        if event.button() == Qt.LeftButton and not self._dragging:
            if self.disclosure_rect().contains(event.position().toPoint()):
                self.disclosure_toggled.emit(self.node_id)
            else:
                self.clicked.emit(self.node_id, QApplication.keyboardModifiers())
        self._drag_start = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and not self.disclosure_rect().contains(event.position().toPoint()):
            self.activated.emit(self.node_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.activated.emit(self.node_id)
        elif event.key() in (Qt.Key_Space, Qt.Key_Right, Qt.Key_Left):
            if event.key() == Qt.Key_Space or (event.key() == Qt.Key_Right) != self.expanded:
                self.disclosure_toggled.emit(self.node_id)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def contextMenuEvent(self, event):
        self.context_requested.emit(self, event.pos())
