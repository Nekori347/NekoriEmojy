from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QStyledItemDelegate,QStyleOptionViewItem


class CategoryDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option,index)
        view=self.parent()
        sidebar=view.parent()
        if getattr(sidebar,'is_grid_mode',False):
            option.decorationPosition=QStyleOptionViewItem.Top
            option.decorationAlignment=Qt.AlignHCenter|Qt.AlignVCenter
            option.displayAlignment=Qt.AlignHCenter|Qt.AlignTop

    def paint(self,painter,option,index):
        super().paint(painter,option,index)
        if index.row()==getattr(self.parent(),'_drop_target',-1):
            painter.save()
            painter.setPen(QPen(QColor('#3f9ddb'),2))
            painter.setBrush(QColor(63,157,219,42))
            painter.drawRoundedRect(option.rect.adjusted(2,2,-2,-2),6,6)
            painter.restore()
