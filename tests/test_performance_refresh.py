"""Real UI/data contracts for the targeted real-library performance fixes."""
from PySide6.QtCore import Qt
from test_management_mode import management
from types import SimpleNamespace


def test_target_menu_uses_one_ordered_node_snapshot(management,monkeypatch):
    from fluent_ui.components.category_menu import CategoryTargetMenu
    view,storage,parent,dest,paths,sent=management
    first=storage.create_node('Same',parent)
    second=storage.create_node('Same',dest)
    before=storage.create_node('Before',parent,position=0)
    original=storage.index.nodes;reads=[];content_reads=[];content=storage.index.content
    def nodes():reads.append(True);return original()
    def current_content(node):content_reads.append(node);return content(node)
    card=next(c for c in view._all_card_widgets if getattr(c,'image_path',None)==paths[0])
    with monkeypatch.context() as patch:
        patch.setattr(storage.index,'nodes',nodes)
        patch.setattr(storage.index,'content',current_content)
        menu=view._build_resource_menu(card)
        branches=[m for m in menu._subMenus if isinstance(m,CategoryTargetMenu)]
        assert len(reads)==1 and len(branches)==2
        assert content_reads==[parent]  # ActionPolicy's direct membership check.
        assert branches[0].snapshot is branches[1].snapshot
        rows=branches[0].snapshot
        assert [r['id'] for r in rows if r['depth']==1 and r['path'].startswith('Source /')]==[before,first]
        assert {r['path'] for r in rows if r['id'] in (first,second)}=={'Source / Same','Target / Same'}
        branches[0].prepare()
        child=next(m for m in branches[0]._subMenus if m.node==parent)
        child.prepare()
        assert len(reads)==1
    menu.close();menu.deleteLater()


def test_import_counts_retain_tree_rows_icons_and_collapsed_selection(management,monkeypatch):
    view,storage,parent,dest,paths,sent=management
    child=storage.create_node('Child',parent)
    view.sidebar.refresh_list(parent);view.set_node(child)
    tree=view.sidebar.tree;row=tree._find_item(parent);selected=tree._find_item(child)
    row.setExpanded(False)
    scroll=tree.verticalScrollBar().value()
    def unexpected(*args,**kwargs):raise AssertionError('count update rebuilt category UI')
    monkeypatch.setattr(tree,'_node_icon',unexpected)
    monkeypatch.setattr(view.sidebar.icons,'refresh',unexpected)
    monkeypatch.setattr(storage,'category_labels',unexpected)
    assert view.sidebar._as_node_id(child)==child
    storage.index.add_membership(storage._resource_id(paths[0]),child)
    view._queued_files_finished(SimpleNamespace(paths=[paths[0]],target=SimpleNamespace(parent_node=child),operation=None))
    assert tree._find_item(parent) is row and tree._find_item(child) is selected
    assert not row.isExpanded() and tree.current_node_id==child and view.current_node==child
    assert tree.verticalScrollBar().value()==scroll and selected.text(1)=='1'
    assert any(e.get('path')==paths[0] for e in view._entries)


def test_import_structure_reuses_icons_and_model_reads_snapshot(management,monkeypatch):
    view,storage,parent,dest,paths,sent=management
    tree=view.sidebar.tree;icons={key:tree._find_item(key).icon(0).cacheKey() for key in (parent,dest)}
    child=storage.create_node('New',parent)
    render=tree._node_icon;rendered=[]
    def icon(record):rendered.append(record['id']);return render(record)
    monkeypatch.setattr(tree,'_node_icon',icon)
    nodes=storage.index.nodes();counts=storage.node_counts()
    view.sidebar.sync_nodes(nodes,counts)
    assert rendered==[child]
    assert all(tree._find_item(key).icon(0).cacheKey()==value for key,value in icons.items())
    view.entry_model.entries_of(parent)
    def unexpected(*args,**kwargs):raise AssertionError('per-node query during sync')
    monkeypatch.setattr(storage,'node',unexpected)
    monkeypatch.setattr(storage.index,'nodes',unexpected)
    view.entry_model.sync(parents={parent},nodes=nodes,counts=counts)
    assert any(e['id']==child for e in view.entry_model.direct[parent])
    # Icon replacement remains a real invalidation, not a permanently cached QIcon.
    storage.index.update_node(child,icon='X')
    view.sidebar.sync_nodes(storage.index.__class__.nodes(storage.index),storage.node_counts())
    assert rendered==[child,child]
