from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QColor,QPen
from fluent_ui.components.controls import PushButton
from fluent_ui import visual


class ColorSwatchButton(PushButton):
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        p.setPen(QPen(QColor(c['border']),1));p.setBrush(QColor(c['control']))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),8,8)
        p.setPen(Qt.NoPen);p.setBrush(getattr(self,'color',QColor(c['accent'])))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(4,4,-4,-4),4,4)
