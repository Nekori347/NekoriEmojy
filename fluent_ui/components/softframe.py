"""Softframe painters shared by settings, tasks and parameter controls.

The shell uses an opaque paper/ink fallback. It does not simulate native Mica.
The fixed contour master is sampled from a continuous virtual height field.
"""
import time
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QTimer, QSize, QVariantAnimation, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider, QProgressBar, QToolButton, QWidget, QLabel
from fluent_ui import visual

_contours = {}


def paint_setting_surface(painter, rect):
    c=visual.colors()
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(rect.adjusted(.5,.5,-.5,-.5), 12, 12)
    painter.setClipPath(clip)
    gradient=QLinearGradient(rect.topLeft(),rect.topRight())
    gradient.setColorAt(0,QColor(c['surface']))
    gradient.setColorAt(.55,QColor(c['surface']))
    end=QColor(c['surface']);low=QColor(c['surface_alt'])
    end.setRgb(*(round(a*.62+b*.38) for a,b in zip(end.getRgb()[:3],low.getRgb()[:3])))
    gradient.setColorAt(1,end)
    painter.fillRect(rect,gradient)
    # The same start-side crop and scale are used for every row; never fit the
    # entire terrain into a narrow strip or centre it separately under a title.
    key = c['text_secondary']
    if key not in _contours:
        master=QPixmap(1020,440);master.setDevicePixelRatio(2);master.fill(Qt.transparent)
        p=QPainter(master)
        source=(Path(__file__).resolve().parents[1]/'assets/softframe-contours.svg').read_bytes()
        QSvgRenderer(source.replace(b'#78816e',key.encode())).render(p,QRectF(0,0,510,220))
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        fade=QLinearGradient(0,0,300,0)
        fade.setColorAt(0,QColor(0,0,0,30));fade.setColorAt(.3,QColor(0,0,0,100))
        fade.setColorAt(.65,QColor(0,0,0,60));fade.setColorAt(1,QColor(0,0,0,0))
        p.fillRect(QRectF(0,0,510,220),fade)
        p.end()
        _contours[key]=master
    painter.setOpacity(.58)
    painter.drawPixmap(int(rect.left()+16),int(rect.center().y()-110),_contours[key])
    painter.setOpacity(.19)
    painter.setPen(QPen(QColor(c['muted']),.7))
    for y in range(int(rect.top())-8,int(rect.bottom()),7):
        painter.drawLine(int(rect.left()+2),y+12,int(rect.left()+14),y)
    for x in range(max(0,int(rect.width())-170),int(rect.width())-4,7):
        painter.setOpacity(.025+.07*(x-max(0,rect.width()-170))/170)
        for y in range(int(rect.top())+5,int(rect.bottom())-3,7):
            painter.drawPoint(x,y)
    painter.setOpacity(1)
    painter.setClipping(False)
    painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor(c['border_soft']),1))
    painter.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5),12,12)
    painter.restore()


class DisclosureButton(QToolButton):
    """One chevron rotates without changing its hit area or layout."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.TabFocus)
        self._angle = 90.0
        self.setFixedSize(28,28)
        self.setCursor(Qt.PointingHandCursor)
        self._motion=QVariantAnimation(self)
        self._motion.setDuration(visual.MOTION.expand)
        self._motion.setEasingCurve(visual.MOTION.easing)
        self._motion.valueChanged.connect(self._step)
        visual.theme.changed.connect(self.update)

    def _step(self,value):
        self._angle=value
        self.update()

    def set_expanded(self,expanded):
        self._motion.stop()
        self._motion.setStartValue(self._angle)
        self._motion.setEndValue(90.0 if expanded else 0.0)
        visual.start_animation(self._motion, visual.MOTION.expand)

    def paintEvent(self,event):
        from fluent_ui.icons import Icon
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        c=visual.colors()
        if self.underMouse() or self.hasFocus():
            p.setPen(Qt.NoPen);p.setBrush(QColor(c['hover']))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),6,6)
        p.translate(self.width()/2,self.height()/2);p.rotate(self._angle)
        Icon.CHEVRON_RIGHT.render(p,QRectF(-7,-7,14,14),fill=c['text_secondary'])


class SectionHeading(QWidget):
    def paintEvent(self,event):
        c=visual.colors();p=QPainter(self)
        y=self.height()//2
        p.setPen(QPen(QColor(c['accent']),3));p.drawLine(2,y-7,2,y+7)
        label=self.findChild(QLabel)
        start=label.geometry().right()+12 if label else 100
        p.setPen(QPen(QColor(c['border_soft']),1))
        p.drawLine(start,y,self.width()-38,y)
        p.drawLine(self.width()-39,y-3,self.width()-39,y+3)


class SoftframeSlider(QSlider):
    """Style-based handle input, fine track and short capsule drawing."""
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation,parent)
        self._handle_hover=False
        self._handle_drag=False
        self.setAttribute(Qt.WA_Hover)
        self.setFocusPolicy(Qt.TabFocus)
        self.setMinimumSize(60,28)
        self.setStyleSheet('QSlider {background:transparent;} QSlider::groove:horizontal {background:transparent; height:2px; margin:0 4px;} QSlider::handle:horizontal {background:transparent; border:none; width:28px; margin:-8px 0;} QSlider::groove:vertical {background:transparent; width:2px; margin:4px 0;} QSlider::handle:vertical {background:transparent; border:none; height:24px; margin:0 -8px;}')
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        c=visual.colors();opt=QStyleOptionSlider();self.initStyleOption(opt)
        handle=self.style().subControlRect(QStyle.CC_Slider,opt,QStyle.SC_SliderHandle,self)
        horizontal=self.orientation()==Qt.Horizontal
        center=QRectF(handle).center()
        p.setOpacity(1 if self.isEnabled() else .4)
        p.setPen(QPen(QColor(c['track']),2,Qt.SolidLine,Qt.RoundCap))
        if horizontal:
            p.drawLine(7,self.height()//2,self.width()-7,self.height()//2)
            pill=QRectF(center.x()-14,self.height()/2-5,28,10)
        else:
            p.drawLine(self.width()//2,7,self.width()//2,self.height()-7)
            pill=QRectF(self.width()/2-4,center.y()-12,8,24)
        active=self._handle_hover or self.isSliderDown()
        p.setBrush(QColor(c['thumb']));p.setPen(QPen(QColor(c['accent'] if active else c['border']),1 if active else .8))
        p.drawRoundedRect(pill,5,5)
        if active:
            tint=QColor(c['accent']);tint.setAlpha(24)
            p.setBrush(tint);p.setPen(Qt.NoPen);p.drawRoundedRect(pill,5,5)
        if self.hasFocus():
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(c['accent']),1))
            p.drawRoundedRect(pill.adjusted(-2,-2,2,2),5,5)

    def event(self,event):
        if event.type() in (QEvent.HoverEnter,QEvent.HoverMove,QEvent.HoverLeave):
            option=QStyleOptionSlider();self.initStyleOption(option)
            handle=self.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,self)
            hovered=event.type()!=QEvent.HoverLeave and handle.contains(event.position().toPoint())
            if hovered!=self._handle_hover:self._handle_hover=hovered;self.update()
        return super().event(event)

    def mousePressEvent(self,event):
        option=QStyleOptionSlider();self.initStyleOption(option)
        handle=self.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,self)
        if event.button()==Qt.LeftButton and handle.contains(event.position().toPoint()):
            horizontal=self.orientation()==Qt.Horizontal
            self._drag_offset=(event.position().x()-handle.left() if horizontal else event.position().y()-handle.top())
            self._handle_drag=True;self.setFocus(Qt.MouseFocusReason);self.setSliderDown(True)
            event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if not self._handle_drag:return super().mouseMoveEvent(event)
        option=QStyleOptionSlider();self.initStyleOption(option)
        horizontal=self.orientation()==Qt.Horizontal
        # QSS groove margins are not included consistently in its reported
        # rectangle. Use the handle's actual two endpoint positions instead.
        option.sliderPosition=self.minimum()
        low=self.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,self)
        option.sliderPosition=self.maximum()
        high=self.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,self)
        ends=(low.left(),high.left()) if horizontal else (low.top(),high.top())
        start=min(ends);span=abs(ends[1]-ends[0])
        position=(event.position().x() if horizontal else event.position().y())-self._drag_offset-start
        self.setSliderPosition(QStyle.sliderValueFromPosition(self.minimum(),self.maximum(),round(position),max(1,span),option.upsideDown))
        event.accept()

    def mouseReleaseEvent(self,event):
        if self._handle_drag and event.button()==Qt.LeftButton:
            self._handle_drag=False;self.setSliderDown(False)
            if not self.hasTracking():self.setValue(self.sliderPosition())
            event.accept();return
        super().mouseReleaseEvent(event)

    def wheelEvent(self,event):
        event.ignore()


class SoftframeProgress(QProgressBar):
    """Completed solid / remaining hatch, with a real unknown-progress mode."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self._pulse=QTimer(self);self._pulse.setInterval(60);self._pulse.timeout.connect(self.update)
        visual.theme.motion_changed.connect(self._sync_motion)
        self.setTextVisible(False)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def _sync_motion(self):
        self._pulse.setInterval(60)
        if self.isVisible() and self.maximum()==self.minimum()==0 and visual.animations_enabled():self._pulse.start()
        else:self._pulse.stop()

    def setRange(self,minimum,maximum):
        super().setRange(minimum,maximum)
        if hasattr(self,'_pulse'):self._sync_motion()

    def showEvent(self,event):
        super().showEvent(event);self._sync_motion()

    def hideEvent(self,event):
        self._pulse.stop();super().hideEvent(event)

    def paintEvent(self,event):
        p=QPainter(self);c=visual.colors();r=QRectF(self.rect()).adjusted(3,2,-3,-2)
        p.fillRect(r,QColor(c['surface_alt']))
        p.save();p.setClipRect(r);p.setPen(QPen(QColor(c['border']),1))
        for x in range(-int(r.height()),int(r.width())+12,7):
            p.drawLine(x,int(r.bottom()),x+int(r.height()),int(r.top()))
        p.restore()
        if self.minimum()==self.maximum()==0:
            width=r.width()*.23
            offset=(time.monotonic()%1.8)/1.8*(r.width()+width)-width if visual.animations_enabled() else (r.width()-width)/2
            p.save();p.setClipRect(r);p.fillRect(QRectF(r.left()+offset,r.top(),width,r.height()),QColor(c['accent']));p.restore()
        else:
            fraction=max(0,min(1,(self.value()-self.minimum())/max(1,self.maximum()-self.minimum())))
            p.fillRect(QRectF(r.left(),r.top(),r.width()*fraction,r.height()),QColor(c['accent']))
        p.setPen(QPen(QColor(c['muted']),1))
        for x in (r.left(),r.right()):p.drawLine(int(x),0,int(x),self.height())
