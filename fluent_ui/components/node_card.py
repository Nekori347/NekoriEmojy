"""Full-width category break, kept in the resource/node mixed manual order."""
from services.i18n import t, bind_text, translated
import json
import os
from pathlib import Path
from services.exchange_icons import IMAGE_SUFFIXES, resolve_icon_path

from PySide6.QtCore import Qt, Signal, QMimeData, QPoint, QRect, QRectF, QVariantAnimation
from PySide6.QtGui import (
    QColor, QDrag, QFont, QFontMetrics, QPainter, QPen, QPixmap,
)
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy

from fluent_ui.components.drop_contract import NODE_MIME, RESOURCE_MIME
from fluent_ui.visual import DATA_FONT, accent, colors
from fluent_ui import visual
from fluent_ui.icons import Icon

__all__ = ['NodeCard', 'render_node_icon', 'NODE_MIME', 'RESOURCE_MIME']


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
        self.setFixedHeight(40)
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
        self.setFixedHeight(max(40, extent + 12))
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
        c=colors();p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        if self.is_selected or self._hovered:
            p.setBrush(QColor(c['selected'] if self.is_selected else c['hover']))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0,2,0,-2),8,8)
        p.setPen(QPen(QColor(accent()),2))
        p.drawLine(8,12,8,self.height()-12)

        if self._icon is not None:p.drawPixmap(24,(self.height()-self._icon.height())//2,self._icon)
        font=visual.font();font.setWeight(QFont.Medium);p.setFont(font)
        summary=f"{self.entry.get('children',0)}/{self.entry.get('total',0)}"
        count_width=p.fontMetrics().horizontalAdvance(summary)+12
        count_x=self.width()-count_width-40
        p.setPen(QColor(c['text']))
        text_left = 24 + self._icon_extent + 10
        text_width = max(0, count_x-text_left-10)
        p.drawText(QRect(text_left,0,text_width,self.height()),Qt.AlignVCenter,p.fontMetrics().elidedText(self.entry['name'],Qt.ElideRight,text_width))
        line_start=min(count_x-12,text_left+p.fontMetrics().horizontalAdvance(self.entry['name'])+12)
        p.setPen(QPen(QColor(c['border_soft']),1));p.drawLine(line_start,self.height()//2,count_x-8,self.height()//2)
        p.setPen(QColor(c['muted']))
        font.setFamily(DATA_FONT.split(',')[0]);font.setPixelSize(11);font.setBold(False);p.setFont(font)
        p.drawText(QRect(count_x,0,count_width,self.height()),Qt.AlignRight|Qt.AlignVCenter,summary)
        x,y=self.disclosure_rect().center().x(),self.height()//2
        p.save();p.translate(x,y);p.rotate(self._angle)
        Icon.CHEVRON_RIGHT.render(p,QRectF(-7,-7,14,14),fill=c['text_secondary'])
        p.restore()
        if self.hasFocus() and getattr(self,'_keyboard_focus',False):
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(c['border']),1,Qt.DotLine))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2,5,-2,-5),6,6)
        p.end()

    # -- interaction --------------------------------------------------
    def enterEvent(self,event):
        self._hovered=True;self.update();super().enterEvent(event)

    def leaveEvent(self,event):
        self._hovered=False;self.update();super().leaveEvent(event)

    def hideEvent(self,event):
        self._hovered=False;super().hideEvent(event)

    def focusInEvent(self,event):
        self._keyboard_focus=event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason)
        super().focusInEvent(event);self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
            self._drag_start = event.pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start is None:
            return super().mouseMoveEvent(event)
        if (event.pos() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)

        self._dragging = True
        drag = QDrag(self)
        mime = QMimeData()
        payload = self.drag_payload_provider(self.node_id) if self.drag_payload_provider else None
        mime.setData(NODE_MIME, json.dumps(payload or [self.node_id]).encode("utf-8"))
        drag.setMimeData(mime)
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.setHotSpot(QPoint(36, 36))
        drag.exec(Qt.MoveAction)
        self._drag_start = None

    def mouseReleaseEvent(self, event):
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
