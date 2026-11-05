"""A normal transparent tool button with restrained, motion-aware sound waves."""
import math
from PySide6.QtCore import QRectF, QVariantAnimation, QSize
from PySide6.QtGui import QPainter, QPen, QColor
from fluent_ui import visual
from fluent_ui.icons import Icon
from fluent_ui.components.controls import TransparentToolButton


class SoundPreviewButton(TransparentToolButton):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setIcon(Icon.SPEAKER)
        self.setFixedSize(32,32);self.setIconSize(QSize(20,20))
        self.playing=False;self.phase=0.0
        self.wave=QVariantAnimation(self);self.wave.setStartValue(0.0);self.wave.setEndValue(1.0)
        self.wave.setDuration(950);self.wave.setLoopCount(-1)
        self.wave.valueChanged.connect(self._phase)
        visual.theme.motion_changed.connect(self._sync_motion)

    def _phase(self,value):self.phase=float(value);self.update()

    def set_playing(self,playing):
        self.playing=bool(playing);self._sync_motion()

    def _sync_motion(self):
        animate=self.playing and self.isVisible() and visual.animations_enabled()
        if animate and self.wave.state()!=self.wave.State.Running:self.wave.start()
        elif not animate:self.wave.stop();self.phase=0.0
        self.update()

    def showEvent(self,event):
        super().showEvent(event);self._sync_motion()

    def hideEvent(self,event):
        self.wave.stop();super().hideEvent(event)

    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.playing:return
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        size=self.iconSize().width();painter.translate((self.width()-size)/2,(self.height()-size)/2)
        painter.scale(size/24,size/24)
        painter.setPen(QPen(QColor(visual.colors()['text']),2))
        for i,rect in enumerate((QRectF(9,7,10,10),QRectF(6,3,20,18))):
            alpha=.4+.6*(.5+.5*math.sin(2*math.pi*(self.phase-i*.2))) if visual.animations_enabled() else 1.0
            painter.setOpacity(alpha)
            painter.drawArc(rect,-55*16,110*16)
