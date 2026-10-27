"""Formal location changes preserve the independent sidebar disclosure."""
from unittest.mock import Mock
import pytest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from test_phase2_interaction import surface,settle


@pytest.mark.parametrize('entry',['double_click','enter','menu'])
def test_formal_gallery_navigation_preserves_sidebar(surface,monkeypatch,entry):
    s=surface;g=s.g;tree=g.sidebar.tree
    deep=s.storage.create_node('Deep',s.child)
    for i in range(22):s.storage.create_node(f'Previous {i}',position=0)
    tree.refresh();g.set_node(s.parent);g.toggle_node_expansion(s.child);settle(s.app)
    parent=tree._find_item(s.parent);child=tree._find_item(s.child)
    parent.setExpanded(False);child.setExpanded(False)
    tree.scrollToItem(parent);settle(s.app)
    scroll=tree.verticalScrollBar().value();expanded=tree._expanded_ids()
    widget=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==deep)
    # Navigation rebuilds its new content scope once, never the sidebar tree.
    monkeypatch.setattr(tree,'refresh',Mock(side_effect=AssertionError('tree reload')))
    refresh=Mock(wraps=g.refresh_content);monkeypatch.setattr(g,'refresh_content',refresh)
    if entry=='double_click':QTest.mouseDClick(widget,Qt.LeftButton,pos=QPoint(35,15))
    elif entry=='enter':QTest.keyClick(widget,Qt.Key_Return)
    else:
        menu=g._build_node_context_menu(widget);menu.actions()[0].trigger()
    settle(s.app)
    assert g.current_node==deep and g.content_scope_node()==deep and tree.current_node_id==deep
    assert tree._expanded_ids()==expanded and tree.verticalScrollBar().value()==scroll
    assert refresh.call_count==1
    delegate=tree.itemDelegate()
    assert delegate._collapsed_selection_rect().contains(tree.visualItemRect(parent).center())
    parent.setExpanded(True);settle(s.app)
    assert delegate._collapsed_selection_rect().contains(tree.visualItemRect(child).center())
    child.setExpanded(True);settle(s.app)
    assert delegate._collapsed_selection_rect().isEmpty()
    assert not delegate._indicator_target().isEmpty()
    parent.setExpanded(False);settle(s.app)
    g.set_node(s.other);settle(s.app)
    assert not parent.isExpanded() and delegate._collapsed_selection_rect().isEmpty()


def test_refresh_restore_breadcrumb_back_and_explicit_reveal(surface):
    from fluent_ui.views.gallery_view import GalleryInterface
    s=surface;g=s.g;tree=g.sidebar.tree
    deep=s.storage.create_node('Deep',s.child)
    tree.refresh();g.set_node(s.parent)
    tree._find_item(s.parent).setExpanded(False)
    g.set_node(deep);settle(s.app)
    expected=tree._expanded_ids()
    g._save_view_state();tree.refresh(select=deep);settle(s.app)
    assert tree._expanded_ids()==expected and tree.current_node_id==deep
    # Both the location rail and parent navigation use formal set_node.
    g.set_category(s.child);settle(s.app)
    assert tree._expanded_ids()==expected and g.current_node==s.child
    g.navigate_up();settle(s.app)
    assert g.current_node==s.parent and tree._expanded_ids()==expected
    g.set_node(deep);g._save_view_state()
    restored=GalleryInterface(s.storage,s.clipboard,s.config)
    try:
        restored.resize(1100,700);restored.show();settle(s.app)
        assert restored.current_node==deep
        assert restored.sidebar.tree._expanded_ids()==expected
        assert not restored.sidebar.tree.itemDelegate()._collapsed_selection_rect().isEmpty()
        restored.sidebar.tree.select_node(deep,reveal=True);settle(s.app)
        assert restored.sidebar.tree._find_item(s.parent).isExpanded()
        assert restored.sidebar.tree._find_item(s.child).isExpanded()
        assert not restored.sidebar.tree.visualItemRect(restored.sidebar.tree.currentItem()).isEmpty()
    finally:
        restored.focus_timer.stop();restored.filter_flyout.hide();restored.close();restored.deleteLater();settle(s.app)
