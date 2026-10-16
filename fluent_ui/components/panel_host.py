"""A movable panel and the shared thin-line / wide-hit-target splitter."""
from enum import Enum
from PySide6.QtCore import Qt, QEvent, QRect, QRectF, QPointF, QSize, QVariantAnimation
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QMouseEvent, QRegion
from PySide6.QtWidgets import QAbstractButton, QApplication, QSplitter, QSplitterHandle, QVBoxLayout, QWidget, QSizePolicy
from fluent_ui.icons import Icon as FIF
from fluent_ui import visual
from services.i18n import t, i18n_engine


class TagPanelPlacement(str, Enum):
    TOP = 'top'
    BOTTOM = 'bottom'
    LEFT = 'left'
    RIGHT = 'right'

    @property
    def horizontal(self):
        return self in (self.TOP, self.BOTTOM)

    @property
    def leading(self):
        return self in (self.TOP, self.LEFT)


def dock_chevron_points(rect, placement, expanded):
    """One vector geometry: collapse towards the edge, expand away from it."""
    s = visual.COMPACT_CONTROLS.chevron_size / 2
    direction = (-1 if placement.leading else 1) * (1 if expanded else -1)
    points = [(-s, -direction*s/2), (0, direction*s/2), (s, -direction*s/2)]
    center = rect.center()
    return [QPointF(center.x()+x, center.y()+y) if placement.horizontal
            else QPointF(center.x()+y, center.y()+x) for x, y in points]


def paint_dock_chevron(painter, points, active=False):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(visual.colors()['accent' if active else 'text_secondary']),
                        visual.COMPACT_CONTROLS.chevron_stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    path = QPainterPath(points[0])
    for point in points[1:]:
        path.lineTo(point)
    painter.drawPath(path)


class EdgeDockPanelChrome(QAbstractButton):
    """Collapsed identity: the entire available rail is one expand action."""
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(panel.toggle_collapse_requested)
        i18n_engine.language_changed.connect(self.refresh_text)
        visual.theme.changed.connect(self.update)
        self.refresh_text()

    def refresh_text(self, *_):
        self.setToolTip(t('展开标签'))
        self.setAccessibleName(t('展开标签'))

    def sizeHint(self):
        extent = self.panel.collapsed_extent()
        return QSize(extent, extent)

    def chevron_points(self):
        return dock_chevron_points(self.rect(), self.panel._placement, expanded=False)

    def paintEvent(self, event):
        p = QPainter(self)
        c = visual.colors()
        if self.underMouse() or self.isDown() or self.hasFocus():
            p.fillRect(self.rect(), QColor(c['surface_selected'] if self.isDown() else c['surface_hover']))
        side = self.panel.collapsed_metrics.icon_size
        r = QRect(0, 0, side, side)
        # Same identity and leading alignment on both axes.
        inset = self.panel.collapsed_metrics.edge_padding
        r.moveTo(inset if self.panel._collapsed_horizontal else (self.width()-side)//2,
                 (self.height()-side)//2 if self.panel._collapsed_horizontal else inset)
        FIF.TAG.render(p, r, fill=c['text_primary'])
        flow = getattr(self.panel, 'flow', None)
        if flow is not None and flow.active_filters:
            p.setPen(QPen(QColor(c['accent']), 3, Qt.SolidLine, Qt.RoundCap))
            if self.panel._collapsed_horizontal:
                p.drawLine(r.left(),self.height()-4,r.right(),self.height()-4)
            else:
                p.drawLine(4,r.top(),4,r.bottom())
        paint_dock_chevron(p, self.chevron_points(), self.underMouse() or self.hasFocus())
        if self.hasFocus():
            p.setPen(QPen(QColor(c['accent']), visual.LINE_WIDTH))
            p.drawRect(self.rect().adjusted(1, 1, -2, -2))

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class ResizeHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WA_Hover)
        self.setMouseTracking(True)
        self._ear_press = None
        self._dragging = False
        self.setCursor(Qt.SplitHCursor if orientation == Qt.Horizontal else Qt.SplitVCursor)

    @property
    def dock_host(self):
        return getattr(self.splitter(), 'dock_host', None)

    def ear_rect(self, hit=False):
        m = visual.COMPACT_CONTROLS
        length = m.ear_hit_length if hit else m.ear_length
        r = QRect(0, 0, self.width(), length) if self.orientation() == Qt.Horizontal else QRect(0, 0, length, self.height())
        r.moveCenter(self.rect().center())
        return r.intersected(self.rect())

    def chevron_points(self):
        host = self.dock_host
        if not host:
            return []
        return dock_chevron_points(self.ear_rect(), host.placement, expanded=True)

    def mousePressEvent(self, event):
        self._dragging = False
        if self.dock_host and event.button() == Qt.LeftButton and self.ear_rect(True).contains(event.position().toPoint()):
            self._ear_press = QMouseEvent(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.isEnabled():
            return
        if self._ear_press is not None:
            if (event.position()-self._ear_press.position()).manhattanLength() < QApplication.startDragDistance():
                return
            super().mousePressEvent(self._ear_press)
            self._ear_press = None
            self._dragging = True
        self.setCursor(Qt.PointingHandCursor if self.dock_host and not self._dragging and self.ear_rect(True).contains(event.position().toPoint())
                       else Qt.SplitHCursor if self.orientation() == Qt.Horizontal else Qt.SplitVCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._ear_press is not None and event.button() == Qt.LeftButton:
            self._ear_press = None
            if self.ear_rect(True).contains(event.position().toPoint()):
                self.dock_host.set_expanded(False)
            event.accept()
            return
        self._dragging = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.dock_host and event.key() in (Qt.Key_Space, Qt.Key_Return):
            self.dock_host.set_expanded(False)
            self.dock_host.panel.chrome.setFocus()
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, event):
        if event.type() in (QEvent.HoverEnter, QEvent.HoverLeave):
            self.update()
        return super().event(event)

    def paintEvent(self, event):
        if self.dock_host and not self.dock_host.expanded:
            return
        painter = QPainter(self)
        active = self.isEnabled() and self.underMouse()
        if not self.dock_host:
            painter.setPen(QPen(QColor(visual.accent() if active else visual.colors()['border_soft']),1))
            if self.orientation()==Qt.Horizontal:
                painter.drawLine(self.width()//2,0,self.width()//2,self.height())
            else:
                painter.drawLine(0,self.height()//2,self.width(),self.height()//2)
            return
        painter.setPen(QPen(QColor(visual.accent() if active else visual.colors()['border']),
                           2 if self.isEnabled() else visual.LINE_WIDTH))
        middle=self.rect().center()
        if self.orientation() == Qt.Horizontal:
            painter.drawLine(middle.x(),middle.y()-28,middle.x(),middle.y()-9)
            painter.drawLine(middle.x(),middle.y()+9,middle.x(),middle.y()+28)
        else:
            painter.drawLine(middle.x()-28,middle.y(),middle.x()-9,middle.y())
            painter.drawLine(middle.x()+9,middle.y(),middle.x()+28,middle.y())
        if self.dock_host and self.isEnabled():
            c = visual.colors()
            # The command is discoverable at rest. Hover only emphasizes it.
            paint_dock_chevron(painter, self.chevron_points(), active or self.hasFocus())


class PanelSplitter(QSplitter):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(visual.COMPACT_CONTROLS.splitter_extent)
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return ResizeHandle(self.orientation(), self)


class TagPanelHost(QWidget):
    """One panel: placement, extent and collapsed state in a single owner.

    Four placements, one mechanism. `placement` says which edge the panel is
    docked to and therefore which axis its extent is measured on; `expanded`
    says whether the panel shows its content or only its header strip. The two
    extents (horizontal height / vertical width) are remembered separately, so
    BOTTOM -> LEFT -> BOTTOM restores each one's own value and neither is
    overwritten by the smaller size a small window forces.

    Collapsing never touches the window: the splitter hands the released extent
    to the content pane, which is how a docked panel is supposed to behave.
    Growing the outer window instead would fight the saved window geometry and
    would cover the gallery rather than making room for it.
    """
    def __init__(self, content, panel, config, parent=None):
        super().__init__(parent)
        self.content, self.panel, self.config = content, panel, config
        self.placement = None
        self.expanded = bool(config.get('tag_panel_expanded', True))
        self._applying = False
        self._motion=QVariantAnimation(self)
        self._motion.setDuration(visual.MOTION.expand)
        self._motion.setEasingCurve(visual.MOTION.easing)
        self._motion.valueChanged.connect(self._animate_extent)
        self._motion.finished.connect(self.apply_extent)
        self.splitter = PanelSplitter(Qt.Vertical, self)
        self.splitter.dock_host = self
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)
        self.splitter.splitterMoved.connect(self._extent_changed)
        panel.toggle_collapse_requested.connect(self.toggle_expanded)
        self.set_placement(config.get('tag_panel_placement', 'bottom'))

    @property
    def horizontal(self):
        return self.placement.horizontal

    @property
    def extent_key(self):
        return 'tag_panel_horizontal_extent' if self.horizontal else 'tag_panel_vertical_extent'

    def set_placement(self, placement):
        placement = TagPanelPlacement(placement)
        if placement == self.placement:
            return
        self.placement = placement
        self.splitter.setOrientation(Qt.Vertical if self.horizontal else Qt.Horizontal)
        panel_first = placement.leading
        for index, widget in enumerate((self.panel, self.content) if panel_first else (self.content, self.panel)):
            self.splitter.insertWidget(index, widget)
            self.splitter.setStretchFactor(index, 0 if widget is self.panel else 1)
        self.apply_panel_axis()
        self.panel.set_collapsed(not self.expanded, self.horizontal)
        self.apply_extent()

    def apply_panel_axis(self):
        """Both presentation axes are a function of the placement, nothing else.

        Not of the widget's width, height or aspect ratio: the axes are decided
        by where the panel *is*, and they are re-asserted at every geometry
        boundary so a stale axis cannot outlive the placement that produced it.
        """
        horizontal = self.horizontal
        self.panel.set_panel_placement(self.placement)
        self.panel.apply_placement_axis(horizontal)
        return horizontal

    # -- collapsed presentation ----------------------------------------
    def set_expanded(self, expanded, persist=True):
        expanded = bool(expanded)
        if expanded == self.expanded:
            return
        self._motion.stop()
        previous=self.splitter.sizes()
        self.expanded = expanded
        self.panel.set_collapsed(not expanded, self.horizontal)
        if persist:
            self.config.set('tag_panel_expanded', expanded)
        self.apply_extent()
        target=self.splitter.sizes()
        if self.isVisible() and QApplication.platformName() not in ('offscreen','minimal') and len(previous)==2:
            index=0 if self.splitter.widget(0) is self.panel else 1
            self._motion_index=index
            # The new semantic state is immediate; only the allocated extent
            # interpolates. Resizing by hand never goes through this animation.
            if self.horizontal:
                self.panel.setMinimumHeight(min(previous[index],target[index]));self.panel.setMaximumHeight(max(previous[index],target[index]))
            else:
                self.panel.setMinimumWidth(min(previous[index],target[index]));self.panel.setMaximumWidth(max(previous[index],target[index]))
            self._motion.setStartValue(previous[index]);self._motion.setEndValue(target[index]);self._motion.start()

    def _animate_extent(self,value):
        length=self.splitter.height() if self.horizontal else self.splitter.width()
        sizes=[max(0,length-int(value)-self.splitter.handleWidth())]*2
        sizes[self._motion_index]=int(value)
        self._applying=True
        self.splitter.setSizes(sizes)
        self._applying=False

    def toggle_expanded(self):
        self.set_expanded(not self.expanded)

    def apply_extent(self):
        if not self.isVisible():
            return
        # Every real geometry boundary re-derives the axis and the extent from
        # the placement, so neither can lag behind it.
        self.apply_panel_axis()
        handle_extent = visual.COMPACT_CONTROLS.splitter_extent if self.expanded else self.panel.collapsed_metrics.separator_extent
        self.splitter.setHandleWidth(handle_extent)
        handle = self.splitter.handle(1)
        if handle is not None:
            handle.setEnabled(self.expanded)
            handle.setFocusPolicy(Qt.StrongFocus if self.expanded else Qt.NoFocus)
            handle.setCursor((Qt.SplitVCursor if self.horizontal else Qt.SplitHCursor) if self.expanded else Qt.ArrowCursor)
            handle.setToolTip(t('收起标签') if self.expanded else '')
            handle.setAccessibleName(t('收起标签') if self.expanded else '')
            handle.update()
        length = self.splitter.height() if self.horizontal else self.splitter.width()
        if self.expanded:
            reserve, minimum = (220, 84) if self.horizontal else (300, 110)
            if length < reserve+minimum+handle_extent:
                return
            default = self.config.get('tag_panel_height', 116) if self.horizontal else 220
            requested = int(self.config.get(self.extent_key, default))
            # Clamped to what is left after the content keeps its usable
            # extent; the requested value itself stays in the config, so a
            # bigger window later restores the extent the user chose.
            extent = max(minimum, min(requested, length-reserve-handle_extent))
        else:
            # A collapsed panel is exactly its compact strip, so it always fits.
            extent = self.panel.collapsed_extent()
        self._applying = True
        try:
            rest = max(0, length-extent-handle_extent)
            panel_first = self.splitter.widget(0) is self.panel
            self.splitter.setSizes([extent, rest] if panel_first else [rest, extent])
        finally:
            self._applying = False

    def _extent_changed(self, pos, index):
        if self._applying or not self.isVisible():
            return
        if not self.expanded:
            # The collapsed extent is not a user choice: a stray move must not
            # leave the panel larger than the header it is allowed to show.
            self.apply_extent()
            return
        extent = self.splitter.sizes()[self.splitter.indexOf(self.panel)]
        self.config.set(self.extent_key, extent)

    def showEvent(self, event):
        super().showEvent(event)
        self.layout().activate()
        self.apply_extent()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout().activate()
        self.apply_extent()
        r=QRectF(self.rect());radius=12
        path=QPainterPath();path.moveTo(0,0);path.lineTo(r.width(),0);path.lineTo(r.width(),r.height()-radius)
        path.quadTo(r.width(),r.height(),r.width()-radius,r.height());path.lineTo(radius,r.height())
        path.quadTo(0,r.height(),0,r.height()-radius);path.closeSubpath()
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
