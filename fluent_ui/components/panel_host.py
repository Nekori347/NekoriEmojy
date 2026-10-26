"""A movable panel and the shared thin-line / wide-hit-target splitter."""
from enum import Enum
from PySide6.QtCore import Qt, QEvent, QRect, QRectF, QPoint, QPointF, QSize, Signal, QSignalBlocker, QVariantAnimation, QAbstractAnimation
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QRegion
from PySide6.QtWidgets import QAbstractButton, QApplication, QSplitter, QSplitterHandle, QVBoxLayout, QWidget, QSizePolicy
from fluent_ui.icons import Icon as FIF
from fluent_ui import visual
from fluent_ui.components.controls import ButtonPaint, pointer_hits, focus_input
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


class EdgeDockPanelChrome(ButtonPaint, QAbstractButton):
    """One transparent linear action, with identity on the collapsed rail."""
    def __init__(self, panel, *, expanded=False):
        super().__init__(panel)
        self.expanded = expanded
        self._init_surface()
        self.panel = panel
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.TabFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(panel.toggle_collapse_requested)
        i18n_engine.language_changed.connect(self.refresh_text)
        visual.theme.changed.connect(self.update)
        self.refresh_text()

    def refresh_text(self, *_):
        self.setToolTip(t('收起标签' if self.expanded else '展开标签'))
        self.setAccessibleName(self.toolTip())

    def sizeHint(self):
        extent = self.panel.collapsed_extent()
        return QSize(extent, extent)

    def chevron_points(self):
        return dock_chevron_points(self.rect(), self.panel._placement, expanded=self.expanded)

    def paintEvent(self, event):
        p = QPainter(self)
        c = visual.colors()
        active = pointer_hits(self) or self.isDown() or self.keyboard_focus_visible()
        p.setRenderHint(QPainter.Antialiasing)
        points=self.chevron_points();center=self.rect().center()
        path=QPainterPath(points[0])
        for point in points[1:]:path.lineTo(point)
        rules=QPainterPath()
        # The original short rules rotate together with the directional mark.
        for start,end in ((-28,-9),(9,28)):
            if self.panel._placement.horizontal:
                rules.moveTo(center.x()+start,center.y());rules.lineTo(center.x()+end,center.y())
            else:
                rules.moveTo(center.x(),center.y()+start);rules.lineTo(center.x(),center.y()+end)
        color=QColor(c['accent' if active else 'text_secondary'])
        if active:
            glow=QColor(color);glow.setAlpha(52 if self.isDown() else 28)
            p.setPen(QPen(glow,5 if self.isDown() else 4,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawPath(path);p.drawPath(rules)
        p.setPen(QPen(color,visual.COMPACT_CONTROLS.chevron_stroke,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawPath(rules)
        paint_dock_chevron(p,points,active)
        if not self.expanded:
            side=self.panel.collapsed_metrics.icon_size
            r=QRect(0,0,side,side)
            inset=self.panel.collapsed_metrics.edge_padding
            r.moveTo(inset if self.panel._collapsed_horizontal else (self.width()-side)//2,
                     (self.height()-side)//2 if self.panel._collapsed_horizontal else (30-side)//2)
            FIF.TAG.render(p,r,fill=c['text_primary'])
            flow=getattr(self.panel,'flow',None)
            if flow is not None and flow.active_filters:
                p.setPen(QPen(QColor(c['accent']),2,Qt.SolidLine,Qt.RoundCap))
                p.drawLine(r.bottomLeft()+QPoint(0,2),r.bottomRight()+QPoint(0,2))

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class ResizeHandle(QSplitterHandle):
    """Only resize here; the panel header owns its collapse command."""
    def __init__(self,orientation,parent):
        super().__init__(orientation,parent)
        self.setAttribute(Qt.WA_Hover);self.setMouseTracking(True)
        self._dragging=False;self._keyboard_focus=False;self._focus_input=focus_input()
        self.setCursor(Qt.SplitHCursor if orientation==Qt.Horizontal else Qt.SplitVCursor)

    @property
    def dock_host(self):return getattr(self.splitter(),'dock_host',None)

    def ear_rect(self,hit=False):
        length=max(60,visual.COMPACT_CONTROLS.ear_hit_length) if hit else visual.COMPACT_CONTROLS.ear_length
        r=QRect(0,0,self.width(),length) if self.orientation()==Qt.Horizontal else QRect(0,0,length,self.height())
        r.moveCenter(self.rect().center());return r.intersected(self.rect())

    def mousePressEvent(self,event):
        self._keyboard_focus=False;self._dragging=event.button()==Qt.LeftButton
        super().mousePressEvent(event);self.update()

    def mouseMoveEvent(self,event):
        super().mouseMoveEvent(event);self.update()

    def mouseReleaseEvent(self,event):
        self._dragging=False;super().mouseReleaseEvent(event);self.update()

    def focusInEvent(self,event):
        self._keyboard_focus=event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason)
        super().focusInEvent(event);self.update()

    def focusOutEvent(self,event):
        self._keyboard_focus=False;super().focusOutEvent(event);self.update()

    def keyPressEvent(self,event):
        self._keyboard_focus=True;super().keyPressEvent(event);self.update()

    def event(self,event):
        result=super().event(event)
        if event.type() in (QEvent.UngrabMouse,QEvent.Hide,QEvent.WindowDeactivate) or (event.type()==QEvent.EnabledChange and not self.isEnabled()):
            self._dragging=False;self.update()
        if event.type() in (QEvent.HoverEnter,QEvent.HoverMove,QEvent.HoverLeave):
            self.setCursor(Qt.SplitHCursor if self.orientation()==Qt.Horizontal else Qt.SplitVCursor);self.update()
        return result

    def paintEvent(self,event):
        if self.dock_host and not self.dock_host.expanded:return
        p=QPainter(self);active=pointer_hits(self) or self._dragging
        p.setPen(QPen(QColor(visual.accent() if active else visual.colors()['border_soft']),1))
        if self.orientation()==Qt.Horizontal:p.drawLine(self.width()//2,0,self.width()//2,self.height())
        else:p.drawLine(0,self.height()//2,self.width(),self.height()//2)
        if self.hasFocus() and self._keyboard_focus and self._focus_input.keyboard:
            p.setPen(QPen(QColor(visual.accent()),1,Qt.DotLine));p.setBrush(Qt.NoBrush)
            p.drawRect(self.ear_rect().adjusted(0,0,-1,-1))


class PanelSplitter(QSplitter):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(visual.COMPACT_CONTROLS.splitter_extent)
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return ResizeHandle(self.orientation(), self)


class TagPanelHost(QWidget):
    """One full-size gallery, one masked local foreground splitter.

    The splitter retains Qt's resize mechanics and two remembered extents; its
    transparent spare pane is not a second gallery. Only panel/handle rectangles
    participate in painting and input. Neither expansion nor resizing lays out
    the content again.
    """
    occlusion_changed=Signal()

    def __init__(self,content,panel,config,parent=None,*,viewport=None):
        super().__init__(parent)
        self.content,self.panel,self.config=content,panel,config
        self.viewport=viewport if viewport is not None else content
        self.placement=None;self.expanded=bool(config.get('tag_panel_expanded',True));self._applying=False
        self._covered=QRect()
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0);layout.addWidget(content)
        self.splitter=PanelSplitter(Qt.Vertical,self);self.splitter.dock_host=self
        self.splitter.setStyleSheet('QSplitter, QSplitterHandle {background:transparent;}')
        self._spare=QWidget(self.splitter);self._spare.setAutoFillBackground(False)
        self._motion=QVariantAnimation(self);self._motion.setDuration(visual.MOTION.expand);self._motion.setEasingCurve(visual.MOTION.easing)
        self._motion.valueChanged.connect(self._animate_extent);self._motion.finished.connect(self._finish_motion)
        self.splitter.splitterMoved.connect(self._extent_changed)
        panel.toggle_collapse_requested.connect(self.toggle_expanded)
        panel.installEventFilter(self);self.viewport.installEventFilter(self)
        self.set_placement(config.get('tag_panel_placement','bottom'))

    @property
    def horizontal(self):return self.placement.horizontal

    @property
    def extent_key(self):return 'tag_panel_horizontal_extent' if self.horizontal else 'tag_panel_vertical_extent'

    def set_placement(self,placement):
        placement=TagPanelPlacement(placement)
        if placement==self.placement:return
        self._motion.stop();self.placement=placement
        self.splitter.setOrientation(Qt.Vertical if self.horizontal else Qt.Horizontal)
        for index,widget in enumerate((self.panel,self._spare) if placement.leading else (self._spare,self.panel)):
            self.splitter.insertWidget(index,widget);self.splitter.setStretchFactor(index,0 if widget is self.panel else 1)
        self.apply_panel_axis();self.panel.set_collapsed(not self.expanded,self.horizontal);self.apply_extent()

    def apply_panel_axis(self):
        self.panel.set_panel_placement(self.placement);self.panel.apply_placement_axis(self.horizontal)
        return self.horizontal

    def set_expanded(self,expanded,persist=True):
        expanded=bool(expanded)
        if expanded==self.expanded:return
        self._motion.stop();start=self.panel.height() if self.horizontal else self.panel.width()
        animate=self.isVisible() and QApplication.platformName() not in ('offscreen','minimal') and visual.animations_enabled()
        self.expanded=expanded;self.panel.set_collapsed(not expanded,self.horizontal,transitioning=animate)
        if persist:self.config.set('tag_panel_expanded',expanded)
        target=self.apply_extent(resize=not animate)
        if animate and target is not None:
            # Reconfiguring a finished QVariantAnimation evaluates its old
            # progress. Only a running transition may change drawer geometry.
            with QSignalBlocker(self._motion):
                self._motion.setStartValue(start);self._motion.setEndValue(target);self._motion.setCurrentTime(0)
            visual.start_animation(self._motion,visual.MOTION.expand)

    def toggle_expanded(self):self.set_expanded(not self.expanded)

    def _animate_extent(self,value):self._set_extent(int(value))

    def _finish_motion(self):
        self.panel.set_collapsed(not self.expanded,self.horizontal);self.apply_extent()

    def apply_extent(self,*,resize=True):
        if not self.isVisible():return
        self.apply_panel_axis()
        bounds=QRect(self.viewport.mapTo(self,QPoint()),self.viewport.size()).intersected(self.rect())
        self._applying=True
        try:
            self.splitter.setGeometry(bounds)
            handle_width=visual.COMPACT_CONTROLS.splitter_extent if self.expanded or self._motion.state()==QAbstractAnimation.Running or not resize else 1
            self.splitter.setHandleWidth(handle_width)
            handle=self.splitter.handle(1);handle.setEnabled(self.expanded);handle.setFocusPolicy(Qt.StrongFocus if self.expanded else Qt.NoFocus)
            handle.setToolTip('');handle.setAccessibleName('')
            length=bounds.height() if self.horizontal else bounds.width()
            reserve=min(220 if self.horizontal else 300,max(40,length//2))
            self._spare.setMinimumSize(0,reserve) if self.horizontal else self._spare.setMinimumSize(reserve,0)
            if self.expanded:
                minimum=min(84 if self.horizontal else 110,max(1,length-reserve-handle_width))
                axis_minimum=min(minimum,self.panel.collapsed_extent()) if not resize or self._motion.state()==QAbstractAnimation.Running else minimum
                if self.horizontal:self.panel.setMinimumHeight(axis_minimum)
                else:self.panel.setMinimumWidth(axis_minimum)
                default=self.config.get('tag_panel_height',116) if self.horizontal else 220
                requested=int(self.config.get(self.extent_key,default))
                extent=max(minimum,min(requested,length-reserve-handle_width))
            else:extent=self.panel.collapsed_extent()
            if resize and self._motion.state()!=QAbstractAnimation.Running:self._set_extent(extent)
            self.splitter.raise_();self._sync_mask()
        finally:self._applying=False
        return extent

    def _set_extent(self,extent):
        length=self.splitter.height() if self.horizontal else self.splitter.width()
        rest=max(0,length-int(extent)-self.splitter.handleWidth())
        previous=self._applying;self._applying=True
        try:self.splitter.setSizes([int(extent),rest] if self.placement.leading else [rest,int(extent)])
        finally:self._applying=previous
        self._sync_mask()

    def _sync_mask(self):
        if self.splitter.count()!=2:return
        region=QRegion(self.panel.geometry());handle=self.splitter.handle(1)
        if self.expanded or self._motion.state()==QAbstractAnimation.Running:region=region.united(QRegion(handle.geometry()))
        self.splitter.setMask(region)
        covered=region.boundingRect().translated(self.splitter.pos())
        if covered!=self._covered:
            self._covered=covered;self.occlusion_changed.emit()

    def available_rect(self,widget):
        rect=QRect(widget.mapFromGlobal(self.viewport.mapToGlobal(QPoint())),self.viewport.size())
        if self._covered.isEmpty():return rect
        covered=self._covered.translated(widget.mapFromGlobal(self.mapToGlobal(QPoint())))
        if self.placement==TagPanelPlacement.TOP:rect.setTop(min(rect.bottom()+1,covered.bottom()+1))
        elif self.placement==TagPanelPlacement.BOTTOM:rect.setBottom(max(rect.top()-1,covered.top()-1))
        elif self.placement==TagPanelPlacement.LEFT:rect.setLeft(min(rect.right()+1,covered.right()+1))
        else:rect.setRight(max(rect.left()-1,covered.left()-1))
        return rect

    def _extent_changed(self,pos,index):
        if self._applying or not self.isVisible():return
        if not self.expanded:self.apply_extent();return
        self.config.set(self.extent_key,self.splitter.sizes()[self.splitter.indexOf(self.panel)])
        self._sync_mask()

    def eventFilter(self,obj,event):
        if obj is self.viewport and event.type() in (QEvent.Move,QEvent.Resize):self.apply_extent()
        elif obj is self.panel and event.type() in (QEvent.Move,QEvent.Resize):self._sync_mask()
        return super().eventFilter(obj,event)

    def showEvent(self,event):
        super().showEvent(event);self.layout().activate();self.apply_extent()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self._motion.state()==QAbstractAnimation.Running:
            self._motion.stop();self.panel.set_collapsed(not self.expanded,self.horizontal)
        self.layout().activate();self.apply_extent()
        r=QRectF(self.rect());radius=12
        path=QPainterPath();path.moveTo(0,0);path.lineTo(r.width(),0);path.lineTo(r.width(),r.height()-radius)
        path.quadTo(r.width(),r.height(),r.width()-radius,r.height());path.lineTo(radius,r.height())
        path.quadTo(0,r.height(),0,r.height()-radius);path.closeSubpath()
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
