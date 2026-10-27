"""Real tree navigation and viewport geometry; business selection never moves."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_phase2_interaction import surface, settle


def test_chevron_maps_hidden_child_and_restores_selection(surface):
    s=surface;g=s.g;tree=g.sidebar.tree
    g.set_node(s.child);tree.select_node(s.child)
    child=tree.currentItem();parent=child.parent();parent.setExpanded(True)
    settle(s.app);QTest.qWait(220)
    delegate=tree.itemDelegate()
    assert not delegate._indicator_target().isEmpty()
    assert delegate._collapsed_selection_rect().isEmpty()
    entries=list(g._entries);scroll=g.scroll_area.verticalScrollBar().value()
    QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.chevron_rect(parent).center())
    settle(s.app)
    assert not parent.isExpanded()
    assert tree.current_node_id==s.child
    assert list(g._entries)==entries and g.scroll_area.verticalScrollBar().value()==scroll
    assert delegate._indicator_target().isEmpty()
    assert delegate._indicator.isEmpty()
    hint=delegate._collapsed_selection_rect()
    assert hint.contains(tree.visualItemRect(parent).center())
    # Actual rendering must exercise the dashed drawing branch.
    assert not tree.viewport().grab().isNull()
    QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.chevron_rect(parent).center())
    settle(s.app)
    assert parent.isExpanded() and tree.current_node_id==s.child
    assert delegate._collapsed_selection_rect().isEmpty()
    assert not delegate._indicator_target().isEmpty()
    # Clicking the parent navigates normally and removes all indirect hints.
    QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.visualItemRect(parent).center())
    settle(s.app)
    assert tree.current_node_id==s.parent
    assert not delegate._indicator_target().isEmpty()
    assert delegate._collapsed_selection_rect().isEmpty()


def test_nested_mapping_and_scroll_then_real_selection_change(surface):
    s=surface;g=s.g;tree=g.sidebar.tree
    nested=s.storage.create_node('Grandchild',s.child)
    for i in range(25):s.storage.create_node(f'Before {i}',position=0)
    tree.refresh(select=nested);g.set_node(nested)
    tree.select_node(nested)
    item=tree.currentItem();parent=item.parent();grand=parent.parent()
    grand.setExpanded(True);parent.setExpanded(True)
    tree.scrollToItem(item);settle(s.app);QTest.qWait(220)
    assert tree.verticalScrollBar().value()>0
    delegate=tree.itemDelegate()
    for node,expanded,expected in ((parent,False,parent),(grand,False,grand),
                                  (grand,True,parent),(parent,True,None)):
        node.setExpanded(expanded);settle(s.app)
        assert tree.current_node_id==nested and g.current_node==nested
        hint=delegate._collapsed_selection_rect()
        if expected is None:
            assert hint.isEmpty() and not delegate._indicator_target().isEmpty()
        else:
            row=tree.visualItemRect(expected)
            assert not row.isEmpty() and hint.contains(row.center())
            assert delegate._indicator_target().isEmpty()
    parent.setExpanded(False);settle(s.app)
    assert not delegate._collapsed_selection_rect().isEmpty()
    g.set_node(s.other);tree.select_node(s.other);settle(s.app)
    assert tree.current_node_id==s.other
    assert delegate._collapsed_selection_rect().isEmpty()


