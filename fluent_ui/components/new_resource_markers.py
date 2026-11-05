"""One viewport decoration and one cancellable hover confirmation per gallery."""
from PySide6.QtCore import Qt, QTimer, QEvent, QRectF
from PySide6.QtGui import QPainter, QCursor, QColor
from PySide6.QtWidgets import QWidget, QApplication
from fluent_ui import visual
from fluent_ui.icons import Icon


class NewResourceMarkers(QWidget):
    def __init__(self, gallery):
        super().__init__(gallery.grid_container)
        self.gallery = gallery
        self.ids = set()
        self.pending = None
        self.last_pointer = QCursor.pos()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.confirm)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        gallery.storage.unseen_changed.connect(self.refresh)
        gallery.scroll_area.verticalScrollBar().valueChanged.connect(self.cancel)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)
        self.refresh()

    def refresh(self):
        self.ids = self.gallery.storage.unseen_resource_ids()
        self.setVisible(bool(self.ids) and self.gallery.config.get('show_new_resource_markers',True))
        self.update()

    def layout_changed(self):
        self.cancel()
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.setVisible(bool(self.ids) and self.gallery.config.get('show_new_resource_markers',True))
        self.update()

    def cancel(self, *_):
        self.timer.stop()
        self.pending = None
        # Layout/show/scroll may synthesize a move at the stationary pointer.
        # Only a subsequent change in screen position is a viewing gesture.
        self.last_pointer = QCursor.pos()

    def eventFilter(self, card, event):
        if event.type() in (QEvent.Leave, QEvent.Hide, QEvent.MouseButtonPress):
            if self.pending and self.pending[0] is card:self.cancel()
        elif event.type() == QEvent.MouseMove:
            position = QCursor.pos()
            if position != self.last_pointer:
                self.last_pointer = position
                if (not event.buttons() and not card._is_dragging
                        and not getattr(self.gallery, '_gallery_drag_session', None)
                        and self.gallery.config.get('show_new_resource_markers', True)
                        and card.entry_id in self.ids):
                    if not self.pending or self.pending[:2] != (card, card.entry_id):
                        self.pending = (card, card.entry_id, card.mapToGlobal(card.rect().topLeft()))
                        self.timer.start()
                else:self.cancel()
        return False

    def confirm(self):
        pending = self.pending
        self.pending = None
        if not pending:return
        card, identity, origin = pending
        if (not card.isVisible() or card.entry_id != identity or card._is_dragging
                or QApplication.mouseButtons() or getattr(self.gallery,'_gallery_drag_session',None)
                or not self.gallery.config.get('show_new_resource_markers',True)
                or origin != card.mapToGlobal(card.rect().topLeft())):return
        hit = QApplication.widgetAt(QCursor.pos())
        if hit is None or (hit is not card and not card.isAncestorOf(hit)):return
        self.gallery.storage.mark_resource_seen(identity)

    def paintEvent(self, event):
        if not self.gallery.config.get('show_new_resource_markers', True):return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for card in self.gallery._all_card_widgets:
            if (getattr(card,'entry_id',None) not in self.ids or not card.isVisible()):continue
            # The overlay is a sibling of the pooled card wrappers. mapTo()
            # needs their shared ancestor, not this sibling decoration.
            point = card.mapTo(self.parentWidget(), card.rect().topLeft()) - self.pos()
            rect = QRectF(point.x()-4, point.y()-4, 16, 16)
            # A restrained outline separates the accent from complex images.
            Icon.NEW_RESOURCE.render(painter, rect.adjusted(-1,-1,1,1), fill=visual.colors()['window_base'])
            Icon.NEW_RESOURCE.render(painter, rect, fill=visual.accent())
