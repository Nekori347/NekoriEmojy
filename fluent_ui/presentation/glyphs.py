from PySide6.QtCore import QRectF,Qt,QSize
from PySide6.QtGui import QPen,QColor,QPainter,QFontMetrics,QPainterPath
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIconBase,Theme
from fluent_ui import visual
from fluent_ui.icons import Icon


class BrandLockup(QWidget):
    """One compact wordmark, with the small suffix tucked under its right edge."""
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(74,34)
        from services.update_service import current_version
        self.version='v'+current_version();self.setToolTip('NekoriEmojy '+self.version)
        visual.theme.changed.connect(self.update)
        from fluent_ui.components.update_center import update_center
        update_center().changed.connect(self.update)
    def paintEvent(self,event):
        p=QPainter(self);p.setPen(QColor(visual.colors()['text']))
        font=visual.font('brand');font.setPixelSize(24);p.setFont(font)
        width=QFontMetrics(font).horizontalAdvance('Nekori')
        p.drawText(QRectF(0,0,width+1,25),Qt.AlignLeft|Qt.AlignVCenter,'Nekori')
        font.setPixelSize(12);p.setFont(font)
        p.drawText(QRectF(0,21,width,13),Qt.AlignRight|Qt.AlignVCenter,'Emojy')
        from fluent_ui.components.update_center import update_center
        font=visual.font('data_small');font.setPixelSize(8);p.setFont(font);p.setPen(QColor(visual.colors()['warning'] if update_center().release else visual.colors()['muted']))
        p.drawText(QRectF(0,24,max(1,width-26),10),Qt.AlignLeft|Qt.AlignVCenter,self.version)


class ClipboardImportIcon(FluentIconBase):
    def path(self,theme=Theme.AUTO):return ''
    def render(self,p,r,theme=Theme.AUTO,**attrs):
        Icon.PASTE_ADD.render(p,QRectF(r),theme,**attrs)


class ToolboxIcon(FluentIconBase):
    def path(self,theme=Theme.AUTO):return ''
    def render(self,p,r,theme=Theme.AUTO,**attrs):
        r=QRectF(r);p.save();p.translate(r.topLeft());p.scale(r.width()/24,r.height()/24)
        p.setPen(QPen(QColor(attrs.get('fill',visual.colors()['text'])),1.7,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(3,8,18,13),2,2);p.drawRoundedRect(QRectF(8,3,8,5),1,1)
        p.drawLine(3,13,21,13);p.drawLine(9,12,9,15);p.drawLine(15,12,15,15);p.restore()
