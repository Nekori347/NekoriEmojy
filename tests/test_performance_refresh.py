"""Real UI/data contracts for the targeted real-library performance fixes."""
from PySide6.QtCore import Qt
from test_management_mode import management


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
