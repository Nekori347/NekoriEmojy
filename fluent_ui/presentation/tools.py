"""Input bench and results sheet for the import tools, sharing the native shell."""
from PySide6.QtCore import Qt,QRect,QSize,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QBoxLayout,QLayout,QLayoutItem,QLineEdit,QSizePolicy
from fluent_ui import visual
from .surfaces import Surface,RuleHeading
from services.i18n import bind_text


class WrapCommands(QLayout):
    """Commands preserve label width and wrap as complete hit targets."""
    def __init__(self,parent=None):
        super().__init__(parent);self._items=[];self.setContentsMargins(8,8,8,8);self.setSpacing(6)
    def addItem(self,item):self._items.append(item)
    def count(self):return len(self._items)
    def itemAt(self,i):return self._items[i] if 0<=i<len(self._items) else None
    def takeAt(self,i):return self._items.pop(i) if 0<=i<len(self._items) else None
    def addStretch(self,*_):pass
    def expandingDirections(self):return Qt.Horizontal
    def hasHeightForWidth(self):return True
    def heightForWidth(self,width):return self._arrange(QRect(0,0,width,0),False)
    def minimumSize(self):
        w=max((i.minimumSize().width() for i in self._items),default=0)
        return QSize(w+16,48)
    def sizeHint(self):return self.minimumSize()
    def setGeometry(self,r):super().setGeometry(r);self._arrange(r,True)
    def _arrange(self,r,apply):
        m=self.contentsMargins();x=r.x()+m.left();y=r.y()+m.top();start=x;h=0
        for item in self._items:
            if item.widget() and item.widget().isHidden():continue
            size=item.sizeHint();size.setHeight(max(30,size.height()))
            if x>start and x+size.width()>r.x()+r.width()-m.right():x=start;y+=h+self.spacing();h=0
            if apply:item.setGeometry(QRect(x,y,size.width(),size.height()))
            x+=size.width()+self.spacing();h=max(h,size.height())
        return y-r.y()+h+m.bottom()


class ImportBench(QWidget):
    def __init__(self,view):
        super().__init__(view);self.view=view
        self.row=QHBoxLayout(self);self.row.setContentsMargins(0,0,0,0);self.row.setSpacing(12)
        self.inputs=Surface('raised',self,radius=12)
        left=QVBoxLayout(self.inputs);left.setContentsMargins(0,0,0,0);left.setSpacing(6)
        left.addWidget(view.summaryRow);left.addWidget(view.configCard,1)
        self.results=Surface('base',self,radius=14)
        right=QVBoxLayout(self.results);right.setContentsMargins(12,10,12,10);right.setSpacing(8)
        heading=RuleHeading('',self.results);bind_text(heading.label,'预览');right.addWidget(heading)
        if hasattr(view,'previewTitleLabel'):right.addWidget(view.previewTitleLabel)
        right.addLayout(view.contentLayout,1)
        right.addWidget(view.actionBar)
        self.row.addWidget(self.inputs,2);self.row.addWidget(self.results,3)
        self._form_timer=QTimer(self);self._form_timer.setSingleShot(True)
        self._form_timer.timeout.connect(self.fit_form)

    def fit_form(self):
        cap=max(100,self.view.configScrollArea.viewport().width()-12)
        for layout in self.view.configFormWidget.findChildren(QHBoxLayout):
            items=[layout.itemAt(i) for i in range(layout.count()) if not layout.itemAt(i).isEmpty()]
            width=sum(i.minimumSize().width() for i in items)+max(0,len(items)-1)*layout.spacing()
            layout.setDirection(QBoxLayout.TopToBottom if width>cap else QBoxLayout.LeftToRight)
            for i in range(layout.count()):layout.setStretch(i,0)
            layout.setAlignment(Qt.AlignTop)
        self.view.configFormWidget.layout().invalidate()
        self.view.configFormWidget.layout().activate()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        narrow=self.width()<840
        self.row.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        self.inputs.setMaximumHeight(300 if narrow else 16777215)
        self.inputs.setMinimumHeight(min(260,max(160,self.height()//2)) if narrow else 0)
        self.inputs.setMinimumWidth(0 if narrow else 350)
        self.inputs.setMaximumWidth(16777215 if narrow else 390)
        for layout in self.view.configFormWidget.findChildren(QHBoxLayout):
            for i in range(layout.count()):layout.setStretch(i,0)
            layout.setDirection(QBoxLayout.TopToBottom if not narrow else QBoxLayout.LeftToRight)
            layout.setAlignment(Qt.AlignTop)
        self._form_timer.start(0)


def build_import_tool(view):
    view.mainLayout.setContentsMargins(4,2,4,4);view.mainLayout.setSpacing(12)
    view.topBarLayout.setContentsMargins(8,0,8,0)
    view.btnBack.hide()  # Window close retains its existing owner lifecycle.
    view.titleLabel.setProperty('role','title')
    view.mainLayout.addWidget(view.topBar)
    # Controls are kept, but form geometry is a labelled input column on the
    # bench; scrolling remains inside configuration, not the results sheet.
    view.configFormWidget.layout().setAlignment(Qt.AlignTop)
    view.configCardLayout.setContentsMargins(16,12,16,12)
    view.configCard.setProperty('industrial',True)
    view.contentLayout.setSpacing(8)
    # Detail is a bottom inspection shelf in this tool. The result list owns
    # the width; a small owner window no longer loses it to a fixed side card.
    view.contentLayout.setDirection(QBoxLayout.TopToBottom)
    view.detailWidget.setMinimumWidth(0);view.detailWidget.setMaximumWidth(16777215)
    view.detailWidget.setMaximumHeight(144)
    view.presentation=ImportBench(view);view.mainLayout.addWidget(view.presentation,1)
    visual.apply_typography(view)
