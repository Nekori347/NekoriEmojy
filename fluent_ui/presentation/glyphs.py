from PySide6.QtCore import QRectF,Qt,QSize
from PySide6.QtGui import QPen,QColor,QPainter,QFontMetrics
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIconBase,Theme
from fluent_ui import visual
from fluent_ui.icons import Icon


class BrandLockup(QWidget):
    """One compact wordmark, with the small suffix tucked under its right edge."""
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(96,43)
        visual.theme.changed.connect(self.update)
    def paintEvent(self,event):
        p=QPainter(self);p.setPen(QColor(visual.colors()['text']))
        font=visual.font('brand');font.setPixelSize(30);p.setFont(font)
        width=QFontMetrics(font).horizontalAdvance('Nekori')
        p.drawText(QRectF(0,0,width+1,31),Qt.AlignLeft|Qt.AlignVCenter,'Nekori')
        font.setPixelSize(14);p.setFont(font)
        p.drawText(QRectF(0,26,width+1,17),Qt.AlignRight|Qt.AlignVCenter,'Emojy')


class ClipboardImportIcon(FluentIconBase):
    def path(self,theme=Theme.AUTO):return ''
    def render(self,p,r,theme=Theme.AUTO,**attrs):
        r=QRectF(r);color=attrs.get('fill',visual.colors()['text'])
        Icon.PASTE.render(p,r.adjusted(0,0,-r.width()*.2,-r.height()*.1),fill=color)
        badge=QRectF(r.left()+r.width()*.46,r.top()+r.height()*.46,r.width()*.65,r.height()*.65)
        p.save();p.setPen(Qt.NoPen);p.setBrush(QColor(visual.colors()['surface']))
        p.drawRoundedRect(badge,2,2);Icon.DOWNLOAD.render(p,badge.adjusted(1,1,-1,-1),fill=color);p.restore()


class ToolboxIcon(FluentIconBase):
    def path(self,theme=Theme.AUTO):return ''
    def render(self,p,r,theme=Theme.AUTO,**attrs):
        r=QRectF(r);p.save();p.translate(r.topLeft());p.scale(r.width()/24,r.height()/24)
        p.setPen(QPen(QColor(attrs.get('fill',visual.colors()['text'])),1.7,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(3,8,18,13),2,2);p.drawRoundedRect(QRectF(8,3,8,5),1,1)
        p.drawLine(3,13,21,13);p.drawLine(9,12,9,15);p.drawLine(15,12,15,15);p.restore()
