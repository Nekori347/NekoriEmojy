"""Lazy category targets inside the existing menu, sharing membership operations."""
from PySide6.QtCore import Qt,QEvent,QTimer
from PySide6.QtGui import QIcon
from fluent_ui.components.node_card import render_node_icon
from qfluentwidgets import Action
from fluent_ui.components.safe_round_menu import SafeRoundMenu
from fluent_ui.components.controls import LineEdit
from fluent_ui.icons import Icon
from services.i18n import t,translated,bind_text
from services.library_index import ROOT


class CategoryTargetMenu(SafeRoundMenu):
    def __init__(self,title,storage,choose,parent=None,*,node=None,snapshot=None,records=None):
        super().__init__(str(title) if node is not None else t(title),parent)
        self.storage=storage;self.choose=choose;self.node=node;self._prepared=False
        self.records = records if records is not None else {r['id']: r for r in storage.index.nodes()}
        self.snapshot=snapshot if snapshot is not None else storage.node_choice_rows(nodes=self.records.values())
        self.setIcon(self._node_icon(node) if node else Icon.FOLDER)
        self.view.installEventFilter(self)
        self.search=None
        if node is None:
            self.search=LineEdit(self);self.search.setFixedSize(290,34)
            bind_text(self.search,'搜索分类名称或完整路径','setPlaceholderText')
            self.addWidget(self.search,selectable=False);self._search_action=self._actions[-1]
            self._filter=QTimer(self);self._filter.setSingleShot(True);self._filter.setInterval(80)
            self._filter.timeout.connect(lambda:self._populate(self.search.text().strip()))
            self.search.textChanged.connect(lambda *_:self._filter.start());self.search.installEventFilter(self)

    def prepare(self):
        if not self._prepared:self._populate('');self._prepared=True

    def _populate(self,query):
        for action in list(self._actions):
            if action is not getattr(self,'_search_action',None):self.removeAction(action)
        for menu in list(self._subMenus):self.removeMenu(menu);menu.deleteLater()
        if query:
            from services.search_text import normalize_search
            import re
            key=lambda value:re.sub(r'\s*/\s*','/',normalize_search(value))
            query=key(query)
            rows=[r for r in self.snapshot if query in key(r['path'])]
        else:
            parent=self.node or ROOT
            # Snapshot preserves the library's existing sibling order.
            nodes=self.records
            rows=[r for r in self.snapshot if nodes.get(r['id'],{}).get('parent_id')==parent]
            if self.node:
                self._target(t('选择此分类'),self.node)
        parents={r['parent_id'] for r in self.records.values()}
        for row in rows:
            if not query and row['id'] in parents:
                menu=CategoryTargetMenu(row['name'],self.storage,self.choose,self,
                                        node=row['id'],snapshot=self.snapshot,records=self.records)
                self.addMenu(menu)
            else:self._target(row['path'] if query else row['name'],row['id'])
        if not rows and not self.node:
            action=translated(Action,'没有匹配的分类',parent=self);action.setEnabled(False);self.addAction(action)
        if self.isVisible():self._show_menu(self.pos())

    def _target(self,label,node_id):
        action=Action(self._node_icon(node_id),str(label),self)
        action.setData(node_id);action.triggered.connect(lambda checked=False,n=node_id:self.choose(n))
        self.addAction(action)

    def _node_icon(self, node_id):
        record = self.records.get(node_id, {})
        if not record.get('icon'):
            return Icon.FOLDER
        return QIcon(render_node_icon(self.storage, record, 16))

    def _show_menu(self,pos,*args,**kwargs):
        self.prepare();super()._show_menu(pos,*args,**kwargs)

    def eventFilter(self,obj,event):
        if event.type()!=QEvent.KeyPress:return super().eventFilter(obj,event)
        key=event.key()
        if obj is self.search and key==Qt.Key_Down:
            self._filter.stop();self._populate(self.search.text().strip())
            self.view.setFocus();self.view.setCurrentRow(1);return True
        if key in (Qt.Key_Return,Qt.Key_Enter,Qt.Key_Right):
            if obj is self.search:
                self._filter.stop();self._populate(self.search.text().strip())
                self.view.setCurrentRow(1)
            item=self.view.currentItem()
            if item is None:
                for i in range(self.view.count()):
                    row=self.view.item(i)
                    if row.flags()&Qt.ItemIsEnabled:self.view.setCurrentItem(row);item=row;break
            if item is not None:
                value=item.data(Qt.UserRole)
                if isinstance(value,CategoryTargetMenu):
                    self.lastHoverItem=self.lastHoverSubMenuItem=item;self._onShowMenuTimeOut()
                    value.view.setFocus();value.view.setCurrentRow(0)
                elif key!=Qt.Key_Right:self._onItemClicked(item)
            return True
        if key in (Qt.Key_Left,Qt.Key_Escape):
            self.hide()
            if self.parentMenu:self.parentMenu.view.setFocus()
            return True
        return super().eventFilter(obj,event)
