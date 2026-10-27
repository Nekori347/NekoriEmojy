"""Existing tree context menu -> prompt -> mixed-order persistence."""
from PySide6.QtCore import Qt,QTimer,QPoint,QEventLoop
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit,QPushButton
from test_management_mode import management


def test_tree_context_creation_appends_and_explicit_position_remains(management):
    from services.storage import StorageService
    from services.library_index import ROOT
    view,storage,parent,dest,paths,sent=management
    first=storage.create_node('First child',parent);second=storage.create_node('Second child',parent)
    original_root=[e['id'] for e in storage.entries_of(ROOT)]
    original_child=[e['id'] for e in storage.entries_of(parent)]
    dialogs_seen=[]
    def create_from_menu(open_menu,name):
        def fill_prompt():
            dialog=QApplication.activeModalWidget();assert dialog
            dialog.findChild(QLineEdit).setText(name)
            button=next(b for b in dialog.findChildren(QPushButton) if b.text()=='确定')
            dialogs_seen.append(name);QTest.mouseClick(button,Qt.LeftButton)
        def click_action():
            menu=next(w for w in QApplication.topLevelWidgets() if w.isVisible() and hasattr(w,'view') and hasattr(w,'actions')
                      and any(a.text() in ('新建根级分类','新建子分类') for a in w.actions()))
            row=next(i for i in range(menu.view.count()) if menu.view.item(i).text() in ('新建根级分类','新建子分类'))
            QTimer.singleShot(40,fill_prompt)
            QTest.mouseClick(menu.view.viewport(),Qt.LeftButton,pos=menu.view.visualItemRect(menu.view.item(row)).center())
        QTimer.singleShot(50,click_action)
        open_menu()
        loop=QEventLoop();QTimer.singleShot(180,loop.quit);loop.exec()
    point=view.sidebar.mapToGlobal(QPoint(50,50))
    create_from_menu(lambda:view.sidebar._show_root_menu(point),'Appended root')
    root=storage.index.child_nodes(ROOT)[-1]['id']
    assert [e['id'] for e in storage.entries_of(ROOT)]==original_root+[root]
    tree=view.sidebar.tree
    root_rows=[tree.topLevelItem(i).data(0,Qt.UserRole) for i in range(tree.topLevelItemCount())]
    assert root_rows[-1]==root
    create_from_menu(lambda:view.sidebar._show_node_menu(parent,point),'Appended child')
    child=storage.index.child_nodes(parent)[-1]['id']
    assert [e['id'] for e in storage.entries_of(parent)]==original_child+[child]
    item=tree._find_item(parent)
    assert [item.child(i).data(0,Qt.UserRole) for i in range(item.childCount())]==[first,second,child]
    # The explicitly positioned sibling API remains distinct from the default menu.
    positioned=storage.create_node('Explicit first',parent,position=0)
    assert [e['id'] for e in storage.entries_of(parent)]==[positioned]+original_child+[child]
    reopened=StorageService(library_path=storage.library_root,config=storage.config)
    assert [e['id'] for e in reopened.entries_of(parent)]==[positioned]+original_child+[child]
    assert [e['id'] for e in reopened.entries_of(ROOT)]==original_root+[root]
    assert dialogs_seen==['Appended root','Appended child']
