"""Round4 regression: independent hover layers and hidden-selection ancestry."""
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from test_development_round4 import canvas_for
from fluent_ui import visual


def test_unselected_parent_and_child_have_independent_hover_surfaces(surface):
    s=surface;c=canvas_for(s);s.g.set_node(s.other)
    child=next(i for i,item in enumerate(c.items) if item[0]==s.child)
    parent=next(i for i,item in enumerate(c.items) if item[0]==s.parent)
    QTest.mouseMove(c,c.rects[child].center())
    assert c._hovered==child and c._hovered_group==parent
    image=c.grab().toImage();r=c.rects[child];outer=c.group_by_index[parent]
    assert image.pixelColor(r.left()+12,r.top()+6)!=image.pixelColor(outer.right()-7,r.top()+6)
    assert s.g.current_node==s.other


def test_hidden_selection_uses_outermost_collapsed_ancestor_without_identity_change(surface):
    s=surface;grandchild=s.storage.create_node('Grandchild',s.child)
    s.g.sidebar.refresh_list(s.parent);c=canvas_for(s)
    def index(node):return next(i for i,item in enumerate(c.items) if item[0]==node)
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.child)).center())
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.parent)).center())
    tree_state=s.g.sidebar.tree._expanded_ids();s.g.set_node(grandchild)
    assert c._collapsed_selection_index()==index(s.parent)
    assert c._collapsed_selection_rect()==c.group_by_index[index(s.parent)]
    assert s.g.current_node==grandchild and s.g.sidebar.tree._expanded_ids()==tree_state
    assert s.parent in c.collapsed and s.child in c.collapsed
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.parent)).center())
    assert c._collapsed_selection_index()==index(s.child)
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.child)).center())
    assert c._collapsed_selection_index()==-1
    assert not c.rects[index(grandchild)].isEmpty()
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.parent)).center())
    assert c._collapsed_selection_index()==index(s.parent)
    s.g.set_node(s.other);assert c._collapsed_selection_index()==-1
    s.g.set_node(s.parent);assert c._collapsed_selection_index()==-1
    assert s.parent in c.collapsed


def test_hover_cleanup_and_multi_selection_match_tree_semantics(surface):
    from PySide6.QtCore import QEvent
    s=surface;c=canvas_for(s)
    index=next(i for i,item in enumerate(c.items) if item[0]==s.parent)
    child=next(i for i,item in enumerate(c.items) if item[0]==s.child)
    QTest.mouseMove(c,c.rects[child].center());assert c._hovered==child
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index).center())
    assert c._hovered!=child and c.rects[child].isEmpty()
    s.g.set_node(s.child);assert c._collapsed_selection_index()==index
    s.g.sidebar.tree._find_item(s.other).setSelected(True)
    assert c._collapsed_selection_index()==-1  # Same single-selection rule as tree.
    s.app.sendEvent(c,QEvent(QEvent.Leave));assert c._hovered==-1 and c._hovered_group==-1
