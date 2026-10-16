from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QColor,QPen,QIcon,QAction
from PySide6.QtWidgets import QStyledItemDelegate,QStyle
from fluent_ui import visual
from fluent_ui.icons import Icon


class MenuDelegate(QStyledItemDelegate):
    def paint(self,p,option,index):
        p.save();p.setRenderHint(QPainter.Antialiasing);c=visual.colors();r=QRectF(option.rect).adjusted(5,1,-5,-1)
        icon=index.data(Qt.DecorationRole)
        if icon=='seperator':
            p.setPen(QPen(QColor(c['border_soft']),1));p.drawLine(r.left()+10,r.center().y(),r.right()-10,r.center().y());p.restore();return
        enabled=bool(option.state&QStyle.State_Enabled)
        p.setOpacity(1 if enabled else .4)
        if option.state&(QStyle.State_Selected|QStyle.State_MouseOver):
            p.setPen(Qt.NoPen);p.setBrush(QColor(c['hover']));p.drawRoundedRect(r,6,6)
            p.setPen(QPen(QColor(c['accent']),2));p.drawLine(r.left()+4,r.top()+7,r.left()+4,r.bottom()-7)
        p.setFont(visual.font());p.setPen(QColor(c['text']))
        action=index.data(Qt.UserRole)
        text=action.text() if isinstance(action,QAction) else action.title() if hasattr(action,'title') else str(index.data(Qt.DisplayRole) or '').lstrip()
        shortcut=action.shortcut().toString() if isinstance(action,QAction) else ''
        reserve=p.fontMetrics().horizontalAdvance(shortcut)+36 if shortcut else 0
        rect=r.adjusted(30,0,-14-reserve,0)
        if isinstance(action,QAction) and action.isChecked():
            Icon.ACCEPT.render(p,QRectF(r.left()+10,r.center().y()-7,14,14),fill=c['text'])
        elif isinstance(icon,QIcon):icon.paint(p,int(r.left()+10),int(r.center().y()-7),14,14)
        p.drawText(rect,Qt.AlignVCenter|Qt.AlignLeft,p.fontMetrics().elidedText(text,Qt.ElideRight,int(rect.width())))
        if isinstance(action,QAction) and not action.shortcut().isEmpty():
            from PySide6.QtGui import QFontMetrics
            from fluent_ui.components.keycap_label import paint_keycap
            font=visual.font('data');width=QFontMetrics(font).horizontalAdvance(shortcut)+12
            paint_keycap(p,QRectF(r.right()-14-width,r.center().y()-11,width,22),shortcut,font)
        p.restore()
