"""One shared contract for every drag & drop surface.

The category tree, the content gallery and the tag panel all answer the same two
questions -- *where* would this land, and *what* would happen -- and they answer
them with the same vocabulary and the same indicator. A host still owns its own
geometry; what it must not own is a private placement name or a private way of
drawing the answer, because three surfaces inventing three dialects is exactly
how "the same" drag ends up meaning three different things.

Placement is the position relative to the target:

    INSERT_BEFORE / INSERT_AFTER   next to a sibling edge
    INTO                           inside a container (a category, a tag)
    APPEND                         at the end of the container
    INVALID                        this combination is not allowed

Effect is what the drop does:

    MOVE / COPY / IMPORT / APPLY_TAG

The indicator is drawn by `DropFeedback`: one small widget owned by the host,
never inserted into a layout and never created per drag, so pointing at
something can never move it.
"""
import json
import uuid
import weakref
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, QEvent, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from fluent_ui import visual

# -- drag payloads ----------------------------------------------------------
NODE_MIME = "application/x-emojy-node"
RESOURCE_MIME = "application/x-emojy-resources"
RESOURCE_SOURCES_MIME = "application/x-emojy-resource-sources"
TAG_MIME = "application/x-emojy-tags"
DRAG_SESSION_MIME = 'application/x-nekori-drag-session'
_operations = weakref.WeakValueDictionary()
_committing = ContextVar('nekori_drop_operation', default=None)

# -- placement --------------------------------------------------------------
INSERT_BEFORE = 'insert_before'
INSERT_AFTER = 'insert_after'
INTO = 'into'
APPEND = 'append'
INVALID = 'invalid'
CANCEL = 'cancel'

# -- effect -----------------------------------------------------------------
MOVE = 'move'
COPY = 'copy'
IMPORT = 'import'
APPLY_TAG = 'apply_tag'
APPLY_TAG_TO_SUBTREE = 'apply_tag_to_subtree'


def tag_drop_target(target_id, *, category=False):
    """Same category semantics in a tree, full-width node or icon tile."""
    return DropTarget(INTO, APPLY_TAG_TO_SUBTREE if category else APPLY_TAG,
                      target_id, target_id)


class DropTarget:
    """What one pointer position means for one surface.

    `container_id` is the thing the drop lands *in* (a category node, a
    gallery location), `target_id` the thing it lands *next to* or *onto*, and
    `index` the canonical insertion index inside the container when the
    surface can resolve one.
    """

    __slots__ = ('placement', 'effect', 'target_id', 'container_id', 'index', 'feedback_rect')

    def __init__(self, placement=INVALID, effect=None, target_id=None,
                 container_id=None, index=None):
        self.placement = placement
        self.effect = effect
        self.target_id = target_id
        self.container_id = container_id
        self.index = index
        self.feedback_rect = None

    @property
    def valid(self):
        return self.placement != INVALID

    def __repr__(self):
        return (f"DropTarget({self.placement}, {self.effect}, target={self.target_id!r}, "
                f"container={self.container_id!r}, index={self.index!r})")

    def freeze(self):
        return FrozenDropTarget(self.placement,self.effect,self.target_id,self.container_id,self.index)


@dataclass(frozen=True)
class FrozenDropTarget:
    placement: str
    effect: str | None
    target_id: str | None
    container_id: str | None
    index: int | None

    @property
    def valid(self):return self.placement != INVALID

    def freeze(self):return self


class DragOperation:
    """Identity/claim shared by receiver entries; source lifetime is separate."""
    def __init__(self, identity):
        self.id=identity;self.state='dragging';self.target=None;self.error=''
        self.deferred=False;self.source=None;self.destroyed_slot=None
        self.cleanup=None
        self.result_sound=None
        self.kind=None
        self._receivers=[]
        self.started=time.perf_counter()

    def record(self,event,**extra):
        from services import crash_evidence as evidence
        fields={'session':self.id,'state':self.state,'elapsed_ms':round((time.perf_counter()-self.started)*1000,2)}
        fields.update(extra)
        if self.target is not None:fields.update(container=self.target.container_id,anchor=self.target.target_id,placement=self.target.placement)
        evidence.breadcrumb(event,**fields)
        logging.getLogger('nekori.crash_evidence').info('%s %s',event,fields)

    def cancel(self, reason='cancelled'):
        if self.state in ('dragging','committing','awaiting_choice'):
            self.state='cancelled'
            self.result_sound=None
            self.record('drag_cancelled',reason=reason)
            logging.getLogger('nekori.drag').info('session=%s cancelled=%s',self.id,reason)
            self._release_receivers()

    def watch_receiver(self,receiver):
        slot=lambda *_:self.cancel('receiver_destroyed')
        receiver.destroyed.connect(slot)
        self._receivers.append((weakref.ref(receiver),slot))

    def _release_receivers(self):
        from shiboken6 import isValid
        receivers,self._receivers=self._receivers,[]
        for reference,slot in receivers:
            receiver=reference()
            if receiver is not None and isValid(receiver):
                receiver.destroyed.disconnect(slot)

    def defer(self):
        if self.state=='committing':self.deferred=True

    def complete(self, callback):
        if self.state not in ('dragging','awaiting_choice'):return False
        self.state='committing'
        self.deferred=False
        token=_committing.set(self)
        try:
            result=callback()
            if self.state!='committing':return False
            self.state='rejected' if result is False else ('awaiting_choice' if self.deferred else 'committed')
            self.record('drop_'+self.state)
            if self.state=='committed':
                from services.send_sound import flush_operation_sound
                flush_operation_sound(self)
            return result is not False
        except Exception as error:
            self.state='failed';self.error=str(error)
            self.record('drop_failed')
            logging.getLogger('nekori.drag').exception('session=%s target=%r',self.id,self.target)
            return False
        finally:
            _committing.reset(token)
            if self.state not in ('dragging','committing','awaiting_choice'):
                self.result_sound=None
                self._release_receivers()


def current_drop_operation():return _committing.get()


def prepare_drag(mime, source=None):
    operation=getattr(mime,'_nekori_drag_operation',None)
    if operation is None:
        identity=payload_text(mime.data(DRAG_SESSION_MIME)) if mime.hasFormat(DRAG_SESSION_MIME) else ''
        operation=_operations.get(identity)
        if operation is None:
            operation=DragOperation(identity or uuid.uuid4().hex)
            _operations[operation.id]=operation
        mime._nekori_drag_operation=operation
    if source is not None:
        mime.setData(DRAG_SESSION_MIME,operation.id.encode())
    return operation


def begin_drag(source, mime):
    from services.drag_activity import drag_activity
    operation=prepare_drag(mime,source)
    if operation.state!='dragging' or not drag_activity().begin(operation):
        operation.cancel('source_reentry');return False
    operation.record('drag_started')
    operation.source=weakref.ref(source)
    operation.cleanup=getattr(source,'_drag_cleanup',None)
    operation.destroyed_slot=lambda *_:operation.cancel('source_destroyed')
    source.destroyed.connect(operation.destroyed_slot)
    return True


def finish_drag(mime):
    from services.drag_activity import drag_activity
    operation=prepare_drag(mime)
    if operation.state=='dragging':operation.cancel('no_accepted_drop')
    operation.record('drag_source_finished')
    try:
        if operation.source is not None:
            from shiboken6 import isValid
            source=operation.source()
            if (source is None or not isValid(source)) and operation.cleanup is not None:
                owner=getattr(operation.cleanup,'__self__',None)
                if owner is None or isValid(owner):operation.cleanup()
            if source is not None and isValid(source) and operation.destroyed_slot is not None:
                source.destroyed.disconnect(operation.destroyed_slot)
    finally:
        operation.source=operation.destroyed_slot=None
        operation.cleanup=None
        drag_activity().end(operation)


INVALID_TARGET = DropTarget()


class MappedDropEvent:
    """Coordinate adapter; acceptance always belongs to the original Qt event."""
    def __init__(self, event, point):
        self.event, self.point = event, point

    def position(self):
        from PySide6.QtCore import QPointF
        return QPointF(self.point)

    def __getattr__(self, name):
        return getattr(self.event, name)


class DragSession:
    """One receiver entry, one commit, no cached state shared with the next drag."""

    def __init__(self, mime, parents=None):
        self.operation=prepare_drag(mime)
        self.id=self.operation.id
        self.kind = next((kind for kind in (TAG_MIME, NODE_MIME, RESOURCE_MIME)
                          if mime.hasFormat(kind)), 'urls' if mime.hasUrls() else None)
        self.operation.kind=self.kind
        parser = parse_node_payload if self.kind == NODE_MIME else parse_list_payload
        self.payload = tuple(parser(mime.data(self.kind))) if self.kind not in (None, 'urls') else ()
        self.parents = dict(parents or {})
        # Membership origins travel with the drag, not the current projection:
        # a dwell navigation may clear selection before the eventual release.
        self.sources = {}
        if self.kind == RESOURCE_MIME and mime.hasFormat(RESOURCE_SOURCES_MIME):
            try:
                sources = json.loads(payload_text(mime.data(RESOURCE_SOURCES_MIME)))
                if isinstance(sources, dict):
                    self.sources = {path: parent for path, parent in sources.items()
                                    if path in self.payload and isinstance(parent, str)}
            except ValueError:
                pass
        self.streams = {}
        self.target = INVALID_TARGET

    @property
    def committed(self):return self.operation.state in ('committed','awaiting_choice')

    @property
    def supported(self):
        return self.kind is not None and (self.kind == 'urls' or bool(self.payload))

    def commit(self, target, callback):
        """The shared DropCommit boundary; adapters only perform domain writes."""
        if self.operation.state!='dragging' or not self.supported or not target.valid:
            return False
        self.target=target.freeze()
        self.operation.target=self.target
        if target.placement==CANCEL:
            self.operation.cancel('cancel_zone');return True
        return self.operation.complete(lambda:callback(self.target,list(self.payload)))


def execute_drag(source, mime, pixmap, cleanup, hotspot=None):
    """Our commit already moves data/items; never invoke Qt's source-row removal."""
    from PySide6.QtGui import QDrag
    if not begin_drag(source,mime):return Qt.IgnoreAction
    drag = None
    try:
        drag=QDrag(source);drag.setMimeData(mime);drag.setPixmap(pixmap)
        if hotspot is not None:drag.setHotSpot(hotspot)
        return drag.exec(Qt.MoveAction, Qt.MoveAction)
    finally:
        try:cleanup()
        finally:
            finish_drag(mime)
            from shiboken6 import isValid
            if drag is not None and isValid(drag):drag.deleteLater()


# -- resolution helpers -----------------------------------------------------
def edge_placement(ratio, low=0.3, high=0.7):
    """Top / middle / bottom of a target row: sibling before, inside, after.

    Used on the vertical axis (a category row) and, with `low`/`high` at 0.5,
    on the horizontal axis (a tag chip).
    """
    if ratio < low:
        return INSERT_BEFORE
    if ratio > high:
        return INSERT_AFTER
    return INTO


def split_placement(ratio):
    """Which side of a target the pointer is on; there is no middle band."""
    return INSERT_BEFORE if ratio < 0.5 else INSERT_AFTER


def axis_ratio(rect, point, horizontal=True):
    if horizontal:
        return (point.x()-rect.left()) / max(1, rect.width())
    return (point.y()-rect.top()) / max(1, rect.height())


def payload_text(data):
    """Decode a drag payload; `QMimeData.data()` hands back a QByteArray.

    A QByteArray is neither `bytes` nor `bytearray`, so an isinstance check on
    those silently falls through to `str()`, which yields the repr of the buffer
    and makes every payload look corrupt.
    """
    if data is None:
        return ''
    if isinstance(data, str):
        return data
    try:
        return bytes(data).decode('utf-8')
    except (TypeError, ValueError, UnicodeDecodeError):
        return str(data)


def parse_node_payload(data):
    """A category drag carries a JSON list of node ids.

    A bare id is still accepted: older callers and checks set the id directly,
    and a single-node drag is the common case.
    """
    text = payload_text(data)
    try:
        value = json.loads(text)
    except ValueError:
        return [text] if text else []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def parse_list_payload(data):
    """A resource or tag drag carries a JSON list of strings."""
    text = payload_text(data)
    try:
        value = json.loads(text)
    except ValueError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def indicator_rect(placement, rect, vertical):
    """Geometry of the shared indicator for a placement next to `rect`.

    An insertion is drawn in the gap next to the target rather than on top of
    it, so the mark reads as "between these two" at any card size. APPEND is an
    insertion after the last item of a container, so it paints the same way.
    """
    if placement in (INSERT_AFTER, APPEND):
        if vertical:
            return QRect(rect.right()+5, rect.top(), DropFeedback.THICKNESS, rect.height())
        return QRect(rect.left(), rect.bottom()+3, rect.width(), DropFeedback.THICKNESS)
    if vertical:
        return QRect(rect.left()-7, rect.top(), DropFeedback.THICKNESS, rect.height())
    return QRect(rect.left(), rect.top()-5, rect.width(), DropFeedback.THICKNESS)


class DropFeedback(QWidget):
    """The one indicator painter, owned by the surface it draws over.

    Created once per host and only ever moved, shown and hidden. It is a child
    widget of that host but never part of its layout, so an indicator can never
    displace what it is pointing at, and no widget is created per drag.
    """

    THICKNESS = 2

    def __init__(self, host):
        super().__init__(host)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.hide()
        self._mode = None

    def show_target(self, placement, rect, vertical=False, geometry=None):
        """Show the shared feedback for a placement, or nothing when invalid."""
        if placement == INVALID or rect is None or rect.isNull():
            self.clear()
            return
        if geometry is not None:
            geometry, self._mode = QRect(geometry), 'slot'
        elif placement == INTO:
            geometry, self._mode = QRect(rect), 'outline'
        else:
            geometry, self._mode = indicator_rect(placement, rect, vertical), 'line'
        if self.isVisible() and self.geometry() == geometry and getattr(self, '_last_mode', None) == self._mode:
            return
        self._last_mode = self._mode
        self.setGeometry(geometry)
        self.show()
        self.raise_()
        self.update()

    def clear(self):
        """Drag left or the drop happened: the mark goes immediately."""
        self._mode = None
        self.hide()

    def paintEvent(self, event):
        if self._mode is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        signal = QColor(visual.accent())
        if self._mode == 'outline':
            painter.setPen(QPen(signal, self.THICKNESS))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1),
                                    visual.CONTROL_RADIUS, visual.CONTROL_RADIUS)
        elif self._mode == 'slot':
            painter.setPen(Qt.NoPen)
            painter.setBrush(signal)
            painter.drawRoundedRect(QRectF(self.rect()), self.width()/2, self.width()/2)
        else:
            painter.fillRect(self.rect(), signal)
        painter.end()


class DropCancelZone(QWidget):
    """A temporary receive surface; CANCEL consumes the drag without domain writes."""
    entered = Signal()

    def __init__(self, host, *, bounds_provider=None):
        super().__init__(host)
        self.bounds_provider=bounds_provider
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.NoFocus)
        self._session = None
        self._hovered = False
        host.installEventFilter(self)
        self.hide()

    def begin(self):
        self._session = None
        self._hovered = False
        self._place()
        self.show()
        self.raise_()

    def end(self):
        self._session = None
        self._hovered = False
        self.hide()

    def _place(self):
        host = self.parentWidget()
        bounds=self.bounds_provider() if self.bounds_provider is not None else host.rect()
        width = max(1, min(260, bounds.width()-24))
        self.setGeometry(bounds.left()+(bounds.width()-width)//2,max(bounds.top(),bounds.bottom()-53),width,42)

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() == QEvent.Resize and self.isVisible():
            self._place()
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event):
        session = DragSession(event.mimeData())
        if session.kind != RESOURCE_MIME or not session.supported:
            event.ignore()
            return
        self._session = session
        self._hovered = True
        self.entered.emit()
        self.update()
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self._session is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._session = None
        self._hovered = False
        self.update()
        event.accept()

    def dropEvent(self, event):
        if self._session and self._session.commit(DropTarget(CANCEL, CANCEL), lambda target, block: None):
            # Consume here so the parent cannot interpret the same release as
            # an insertion into a card underneath this overlay.
            event.acceptProposedAction()
        else:
            event.ignore()
        self.end()

    def paintEvent(self, event):
        from fluent_ui.icons import Icon
        from services.i18n import t
        c = visual.colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        background = QColor(c['danger'] if self._hovered else c['surface'])
        background.setAlpha(52 if self._hovered else 235)
        border = QColor(c['danger'] if self._hovered else c['border'])
        border.setAlpha(175 if self._hovered else 140)
        painter.setBrush(background)
        painter.setPen(QPen(border, 1))
        outline = self.rect().adjusted(1,1,-1,-1)
        painter.drawRoundedRect(outline, outline.height()/2, outline.height()/2)
        painter.save()
        painter.setOpacity(.35)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(c['text_secondary']), 1, Qt.DashLine))
        painter.drawEllipse(QRectF(9,7,28,28))
        painter.setOpacity(.42)
        Icon.CANCEL.render(painter, QRect(14,12,18,18), fill=c['text_secondary'])
        painter.restore()
        painter.setFont(visual.font())
        painter.setPen(QColor(c['text_primary']))
        painter.drawText(self.rect().adjusted(38,0,-10,0), Qt.AlignCenter, t('拖到此处取消'))
        painter.end()


class EdgeAutoScroller:
    """Scroll a viewport while a drag rests near its top or bottom edge.

    Shared by every scrollable drop surface so a long drag reaches content the
    pointer cannot: a drop target that cannot be reached is not a drop target.
    """

    STEP = 15
    INTERVAL = 16

    def __init__(self, scroll_area, margin=40):
        self.scroll_area = scroll_area
        self.margin = margin
        self.direction = 0
        self.timer = QTimer(scroll_area)
        self.timer.setInterval(self.INTERVAL)
        self.timer.timeout.connect(self._tick)

    def track(self, position_in_viewport):
        height = self.scroll_area.viewport().height()
        y = position_in_viewport.y()
        if y < self.margin:
            self._start(-1)
        elif y > height-self.margin:
            self._start(1)
        else:
            self.stop()

    def _start(self, direction):
        self.direction = direction
        if not self.timer.isActive():
            self.timer.start()

    def stop(self):
        self.timer.stop()
        self.direction = 0

    def _tick(self):
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.value() + self.STEP*self.direction)


def viewport_rect(widget, host):
    """`widget`'s rectangle in `host` coordinates (both inside one window)."""
    return QRect(widget.mapTo(host, QPoint(0, 0)), widget.size())
