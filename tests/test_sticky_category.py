"""Mixed-flow ownership, real disclosure input and no scroll-time database work."""
import pytest
from unittest.mock import Mock
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from fluent_ui.components.gallery_model import occurrence_id
from test_phase2_interaction import surface, settle
from services.resource_import import ImportTarget


@pytest.fixture
def grouped(surface):
    s=surface;g=s.g
    scope=s.storage.create_node('Sticky scope')
    a=s.storage.create_node('A',scope);b=s.storage.create_node('B',scope)
    nested=s.storage.create_node('Nested',a)
    for j,target in enumerate((a,nested,b)):
        for i in range(24):
            p=s.tmp/f'sticky-{j}-{i}.png'
            Image.new('RGB',(12,12),(i+10,j+30,180)).save(p)
            s.storage.save_file(str(p),target=ImportTarget(target))
    g.config.set('thumbnail_size',180)
    g.entry_model.invalidate();g.set_node(scope)
    # Put direct A resources before its nested section to cover both owners.
    order=s.storage.index.content(a)
    s.storage.set_content_order(a,[e for e in order if e['kind']=='resource']+[e for e in order if e['kind']=='node'])
    g.entry_model.invalidate();g._expanded_nodes.update((a,b,nested));g.refresh_content()
    settle(s.app);QTest.qWait(250)
    s.groups=(scope,a,b,nested)
    return s


def header(g,node):
    i=next(i for i,e in enumerate(g._entries) if e['kind']=='node' and e['id']==node)
    return g.renderer.index.rects[i]


def test_scroll_push_off_deepest_and_real_collapse(grouped,monkeypatch):
    s=grouped;g=s.g;scope,a,b,nested=s.groups
    sticky=g.renderer.sticky;bar=g.scroll_area.verticalScrollBar()
    bar.setValue(0);settle(s.app);assert sticky.isHidden()
    # A real bound header supplies its tooltip only on section change.
    bar.setValue(header(g,a).top()+80);settle(s.app)
    assert sticky.isVisible() and sticky.node_id==a
    assert 'Sticky scope' in sticky.toolTip()
    g._select_single(a);assert sticky.is_selected
    g._select_single(nested);assert not sticky.is_selected
    g._select_single(a);assert sticky.is_selected
    monkeypatch.setattr(s.storage,'node_path',Mock(side_effect=AssertionError('same-section query')))
    with monkeypatch.context() as block:
        block.setattr(s.storage.index,'connect',Mock(side_effect=AssertionError('scroll-time SQL')))
        block.setattr(g,'_collect_entries',Mock(side_effect=AssertionError('scroll rebuilt gallery')))
        for offset in (100,130,180,120):
            bar.setValue(header(g,a).top()+offset);settle(s.app)
            assert sticky.node_id==a
    monkeypatch.undo()
    boundary=header(g,nested).top()
    bar.setValue(boundary-sticky.height()//2);settle(s.app)
    assert sticky.node_id==a and sticky.y()<0
    bar.setValue(boundary);settle(s.app)
    assert sticky.isHidden(),'original nested header is visible'
    bar.setValue(boundary+90);settle(s.app)
    assert sticky.isVisible() and sticky.node_id==nested
    assert 'A / Nested' in sticky.toolTip()
    before=[(e['id'],e['position']) for e in s.storage.index.content(a)]
    # The fixed row forwards disclosure to the actual node and anchors it.
    QTest.mouseClick(sticky,Qt.LeftButton,pos=sticky.disclosure_rect().center());settle(s.app)
    assert nested not in g._expanded_nodes and sticky.isHidden()
    assert abs(header(g,nested).top()-bar.value())<=1
    assert all(e.get('_parent')!=nested for e in g._entries)
    i=next(i for i,e in enumerate(g._entries) if e['kind']=='node' and e['id']==nested)
    card=g.renderer.active[occurrence_id(g._entries[i])]
    QTest.mouseClick(card,Qt.LeftButton,pos=card.disclosure_rect().center());settle(s.app)
    assert nested in g._expanded_nodes
    assert len([e for e in g._entries if e['kind']=='node' and e['id']==nested])==1
    assert before==[(e['id'],e['position']) for e in s.storage.index.content(a)]
    target=header(g,b).top()+90
    bar.setValue(target);settle(s.app)
    assert bar.value()==target, 'recycling a focused node moved the viewport'
    assert sticky.isVisible() and sticky.node_id==b
    bar.setValue(0);settle(s.app);assert sticky.isHidden()


def test_filter_search_order_and_drag_do_not_leave_stale_owner(grouped):
    s=grouped;g=s.g;scope,a,b,nested=s.groups;bar=g.scroll_area.verticalScrollBar()
    bar.setValue(header(g,nested).top()+100);settle(s.app)
    assert g.renderer.sticky.node_id==nested
    g._show_drag_cancel();assert g.renderer.sticky.isHidden()
    g._hide_drag_cancel();assert g.renderer.sticky.isVisible()
    g.search_keyword='sticky';g.refresh_content();settle(s.app)
    assert g.renderer.sticky.isHidden(),'flat search projection has no category breaks'
    g.search_keyword='';g.filter_state.no_tag=True;g.refresh_content();settle(s.app)
    bar.setValue(header(g,b).top()+90);settle(s.app)
    assert g.renderer.sticky.node_id==b
    order=s.storage.index.content(scope)
    s.storage.set_content_order(scope,list(reversed(order)))
    g.entry_model.invalidate();g.refresh_content();settle(s.app)
    bar.setValue(header(g,b).top()+90);settle(s.app)
    assert g.renderer.sticky.node_id==b


def test_foreground_tag_panel_leaves_sticky_visible_and_real_collapse_anchored(grouped):
    s=grouped;g=s.g;scope,a,b,nested=s.groups
    host=g.tag_panel_host;bar=g.scroll_area.verticalScrollBar();sticky=g.renderer.sticky
    for placement in ('top','bottom','left','right'):
        host.set_placement(placement);host.set_expanded(True,persist=False);settle(s.app)
        visible=g.available_gallery_rect()
        bar.setValue(header(g,a).top()+200);settle(s.app)
        assert sticky.isVisible() and sticky.node_id==a
        assert visible.contains(sticky.geometry())
    host.set_placement('top');settle(s.app)
    visible=g.available_gallery_rect();bar.setValue(header(g,nested).top()+90);settle(s.app)
    assert sticky.node_id==nested
    QTest.mouseClick(sticky,Qt.LeftButton,pos=sticky.disclosure_rect().center());settle(s.app)
    assert nested not in g._expanded_nodes
    assert abs(header(g,nested).top()-bar.value()-visible.top())<=1
