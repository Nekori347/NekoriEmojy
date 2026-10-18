"""Own the scroll thumb paint without replacing its value/drag controller."""
from PySide6.QtCore import QObject,QEvent,Qt,QRectF
from PySide6.QtGui import QPainter,QColor
from PySide6.QtWidgets import QScrollBar,QStyle,QStyleOptionSlider
from fluent_ui import visual


class ScrollPaint(QObject):
    def eventFilter(self,bar,event):
        if event.type()==QEvent.ContextMenu:return True
        if event.type()!=QEvent.Paint:return False
        if bar.maximum()<=bar.minimum():return True
        option=QStyleOptionSlider();bar.initStyleOption(option)
        rect=bar.style().subControlRect(QStyle.CC_ScrollBar,option,QStyle.SC_ScrollBarSlider,bar)
        p=QPainter(bar);p.setRenderHint(QPainter.Antialiasing)
        c=visual.colors();color=QColor(c['text_secondary'] if bar.isSliderDown() else c['border'])
        color.setAlpha(210 if bar.underMouse() or bar.isSliderDown() else 130)
        r=QRectF(rect)
        if bar.orientation()==Qt.Vertical:
            sidebar=bool(bar.property('sidebarThumb'))
            r.setLeft(bar.width()-7 if sidebar else r.center().x()-2);r.setWidth(6 if sidebar else 4)
        else:
            r.setTop(r.center().y()-2);r.setHeight(4)
        p.setPen(Qt.NoPen);p.setBrush(color);p.drawRoundedRect(r,2,2)
        return True


def install_scrollbars(root):
    for bar in root.findChildren(QScrollBar):
        if getattr(bar,'_softframe_paint',None):continue
        bar._softframe_paint=ScrollPaint(bar);bar.installEventFilter(bar._softframe_paint)
