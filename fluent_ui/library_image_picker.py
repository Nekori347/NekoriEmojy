"""Choose an existing library image, lazily showing scaled first-frame previews."""
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtGui import QIcon,QImageReader,QPixmap
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem
from qfluentwidgets import PushButton,PrimaryPushButton


class LibraryImagePicker(QDialog):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.setWindowTitle('选择图库图片作为运行时图标')
        self.resize(680,520)
        layout=QVBoxLayout(self)
        self.list=QListWidget(self)
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setIconSize(QSize(72,72))
        self.list.setGridSize(QSize(100,112))
        self.list.setSpacing(6)
        metadata = storage.get_all_metadata()
        for path in storage.get_all_images():
            keywords = metadata.get(path, '')
            item=QListWidgetItem(keywords[:18] or '图片')
            item.setData(Qt.UserRole,path)
            item.setSizeHint(QSize(100,112))
            self.list.addItem(item)
        layout.addWidget(self.list)
        row=QHBoxLayout();row.addStretch()
        cancel=PushButton('取消');cancel.clicked.connect(self.reject);row.addWidget(cancel)
        choose=PrimaryPushButton('使用所选图片');choose.clicked.connect(self.choose);row.addWidget(choose)
        layout.addLayout(row)
        self.list.itemDoubleClicked.connect(lambda item:self.choose())
        self.list.verticalScrollBar().valueChanged.connect(self.schedule)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.previews)
        self.selected_path=None
        self.schedule()

    def schedule(self,*args):self.timer.start(30)

    def showEvent(self,event):
        super().showEvent(event);self.schedule()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'timer'):self.schedule()

    def previews(self):
        visible=self.list.viewport().rect().adjusted(0,-100,0,100)
        for i in range(self.list.count()):
            item=self.list.item(i)
            if item.data(Qt.UserRole+1) or not self.list.visualItemRect(item).intersects(visible):continue
            reader=QImageReader(item.data(Qt.UserRole));reader.setScaledSize(QSize(72,72))
            image=reader.read()
            if not image.isNull():item.setIcon(QIcon(QPixmap.fromImage(image)))
            item.setData(Qt.UserRole+1,True)

    def choose(self):
        item=self.list.currentItem()
        if item:
            self.selected_path=item.data(Qt.UserRole);self.accept()
