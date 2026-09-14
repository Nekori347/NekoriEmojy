"""Flat, collapsible group header integrated into the existing gallery layout."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QHBoxLayout,QInputDialog
from qfluentwidgets import TransparentToolButton,FluentIcon as FIF,BodyLabel,RoundMenu,Action
from fluent_ui.drag_payload import paths_from_mime


class GroupHeader(QWidget):
    def __init__(self, gallery, section):
        super().__init__(gallery.grid_container)
        self.gallery,self.section=gallery,section
        self.setAcceptDrops(bool(section['id']))
        self.setObjectName('CategoryGroupHeader')
        self.setFixedHeight(40)
        row=QHBoxLayout(self);row.setContentsMargins(4,2,6,2)
        self.toggle=TransparentToolButton(FIF.CHEVRON_RIGHT if section['collapsed'] else FIF.CHEVRON_DOWN_MED,self)
        self.toggle.setFixedSize(30,30)
        self.toggle.setEnabled(bool(section['id']) and not section.get('search_expanded'))
        if section.get('search_expanded'):
            self.toggle.setToolTip('搜索时临时展开，清空搜索后恢复折叠状态')
        self.toggle.clicked.connect(self.collapse)
        row.addWidget(self.toggle)
        row.addWidget(BodyLabel(section['name'],self))
        row.addWidget(BodyLabel(str(section['count']),self))
        row.addStretch()
        if section['id']:
            more=TransparentToolButton(FIF.MORE,self);more.clicked.connect(self.menu);row.addWidget(more)
        self.highlight(False)

    def highlight(self,enabled):
        color='rgba(63,157,219,0.24)' if enabled else 'rgba(128,128,128,0.07)'
        self.setStyleSheet(f'QWidget#CategoryGroupHeader {{ background: {color}; border-radius: 6px; }}')

    def collapse(self):
        self.gallery.groups.set_collapsed(self.section['id'],not self.section['collapsed'])
        self.gallery.on_images_changed()

    def menu(self):
        menu=RoundMenu(parent=self)
        items=[('添加当前选中图片',self.add_selected),('重命名',self.rename),('向上移',lambda:self.move(-1)),
               ('向下移',lambda:self.move(1)),('删除小分类',self.delete)]
        for title,callback in items:
            action=Action(title,parent=menu);action.triggered.connect(callback);menu.addAction(action)
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def add_selected(self):
        paths=list(self.gallery.selected_paths)
        if not paths:
            self.gallery.show_error('尚未选择图片','请先在图库中多选，或直接拖动图片到这个小分类。');return
        self.gallery.change_group_members(self.section['id'], paths, True)

    def rename(self):
        name,ok=QInputDialog.getText(self,'重命名小分类','名称',text=self.section['name'])
        if ok:
            try:self.gallery.groups.rename(self.section['id'],name);self.gallery.on_images_changed()
            except Exception as exc:self.gallery.show_error('未重命名',str(exc))

    def move(self,direction):
        ids=[g['id'] for g in self.gallery.groups.list(self.gallery.current_category)]
        index=ids.index(self.section['id']);target=index+direction
        if 0<=target<len(ids):
            ids[index],ids[target]=ids[target],ids[index]
            self.gallery.groups.reorder(self.gallery.current_category,ids)
            self.gallery.on_images_changed()

    def delete(self):
        # Only group membership is removed; assets stay in their parent category.
        self.gallery.groups.delete(self.section['id'])
        self.gallery.on_images_changed()
        self.gallery.show_success('已删除小分类','图片仍保留在当前大分类中。')

    def dragEnterEvent(self,event):
        try:valid=bool(paths_from_mime(event.mimeData(),self.gallery.storage.context))
        except Exception:valid=False
        self.highlight(valid)
        if valid:event.acceptProposedAction()
        else:event.ignore()

    def dragMoveEvent(self,event):self.dragEnterEvent(event)

    def dragLeaveEvent(self,event):
        self.highlight(False);event.accept()

    def dropEvent(self,event):
        self.highlight(False)
        try:
            paths=paths_from_mime(event.mimeData(),self.gallery.storage.context)
            if not paths:event.ignore();return
            count=self.gallery.groups.add(self.section['id'],paths)
            self.gallery.storage.force_reload()
            self.gallery.on_images_changed()
            self.gallery.show_success('添加到小分类',f'已添加 {count} 个表情')
            event.setDropAction(Qt.CopyAction);event.accept()
        except Exception as exc:
            self.gallery.show_error('小分类未更改',str(exc));event.ignore()
