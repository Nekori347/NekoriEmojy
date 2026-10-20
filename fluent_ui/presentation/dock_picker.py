from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QPen,QColor
from PySide6.QtWidgets import QWidget,QAbstractButton
from fluent_ui import visual


class EdgeTarget(QAbstractButton):
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        c=visual.colors();p.setPen(Qt.NoPen)
        p.setBrush(QColor(c['accent'] if self.isChecked() else c['hover'] if self.underMouse() else c['border_soft']))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2),2,2)


class DockPositionPicker(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(124,76);self.buttons={}
        for name,rect in [('top',(27,22,70,12)),('bottom',(27,56,70,12)),('left',(12,22,14,46)),('right',(98,22,14,46))]:
            button=EdgeTarget(self);button.setGeometry(*rect);button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor);button.setFocusPolicy(Qt.StrongFocus);self.buttons[name]=button
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        p.setPen(QPen(QColor(c['text_secondary']),1));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(8.5,7.5,107,63),6,6);p.drawLine(9,19,115,19)
        p.drawLine(16,13,30,13);p.drawLine(95,13,99,13);p.drawLine(104,13,108,13)
