"""Shared projection selection, operation boundaries, and local tab motion."""
import pytest
from unittest.mock import Mock
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_phase2_interaction import surface,settle


def card(s,key):
    return next(c for c in s.g._all_card_widgets if getattr(c,'image_path',None)==key or getattr(c,'node_id',None)==key)

def click(s,key,mods=Qt.NoModifier):
    w=card(s,key);QTest.mouseClick(w,Qt.LeftButton,mods,pos=QPoint(30,w.height()//2));settle(s.app)


def test_mixed_gestures_projection_all_and_true_blank(surface,monkeypatch):
    s=surface;g=s.g;s.config.set('gallery_click_action','select')
    click(s,s.child);click(s,s.paths[0],Qt.ControlModifier)
    assert g.selected_keys=={s.child,s.paths[0]}
    click(s,s.paths[-1],Qt.ShiftModifier)
    keys=[g._entry_key(e) for e in g._entries]
    assert set(keys[keys.index(s.paths[0]):keys.index(s.paths[-1])+1])<=g.selected_keys
    click(s,s.child,Qt.ShiftModifier);assert s.child in g.selected_keys
    g.set_mode('manage');assert s.child in g.selected_keys
    g.select_all_cards();assert g.selected_keys==set(keys)
    # Clearing selection must not rebuild, decode, or query the library.
    connection=g.storage.index.connect;refresh=g.refresh_content
    monkeypatch.setattr(g.storage.index,'connect',Mock(side_effect=AssertionError('selection SQL')))
    monkeypatch.setattr(g,'refresh_content',Mock(side_effect=AssertionError('selection rebuild')))
    vp=g.scroll_area.viewport();p=QPoint(vp.width()-12,vp.height()-12)
    assert vp.childAt(p) is None
    QTest.mouseClick(vp,Qt.LeftButton,pos=p);settle(s.app)
    assert not g.selected_keys and g.mode=='manage'
    click(s,s.child);click(s,s.paths[0]);assert g.selected_keys=={s.child,s.paths[0]}
    assert '2' in g.selected_count_label.text() and '1 个节点' in g.selected_count_label.text()
    g.set_mode('normal');assert not g.selected_keys
    monkeypatch.setattr(g.storage.index,'connect',connection)
    monkeypatch.setattr(g,'refresh_content',refresh)


def test_send_and_mixed_operation_boundaries(surface,monkeypatch):
    s=surface;g=s.g;sent=[];s.config.set('gallery_click_action','send')
    monkeypatch.setattr(g,'_send_to_clipboard',sent.append)
    click(s,s.paths[0]);assert sent==[s.paths[0]]
    click(s,s.child);click(s,s.paths[1],Qt.ControlModifier)
    assert len(g.selected_keys)==2
    click(s,s.paths[0]);assert sent==[s.paths[0]] and g.selected_keys=={s.paths[0]}
    click(s,s.paths[0]);assert len(sent)==2
    g.set_mode('manage');click(s,s.child);click(s,s.paths[0])
    assert not g.btn_tags.isEnabled() and not g.btn_delete.isEnabled() and not g.btn_move_to.isEnabled()
    assert not g._build_selection_more_menu().actions()[0].isEnabled()
    before=list(g.selected_keys)
    assert g._drag_payload(s.paths[0]) is None and g._drag_node_payload(s.child) is None
    assert set(before)==g.selected_keys and len(sent)==2
    monkeypatch.setattr(g,'choose_target_node',Mock(side_effect=AssertionError('mixed partial operation')))
    g._batch_assign(False);g._batch_tags();g._batch_delete()
    assert g._drag_payload(s.paths[1])==[s.paths[1]],'unselected drag source is independent'
    menu=Mock();monkeypatch.setattr(g,'_build_resource_menu',lambda widget:menu)
    g.show_context_menu(card(s,s.paths[0]),QPoint(20,20))
    assert g.selected_keys=={s.paths[0]} and menu.exec.call_count==1


def test_ancestor_normalization_and_move_preserve_subtree(surface,monkeypatch):
    s=surface;g=s.g
    nested=s.storage.create_node('Nested',s.child)
    g._expanded_nodes.add(s.child);g.refresh_content_incremental(reason='fixture',parents={s.child});settle(s.app)
    for _ in range(10):QApplication.processEvents()
    g.set_mode('manage');g.selected_keys={s.child,nested,s.paths[3]};g._commit_selection_visuals()
    assert g._drag_node_payload(s.child)==[s.child]
    internal=list(s.storage.index.content(s.child));resource=s.storage.resource_of(s.paths[3])
    s.storage.index.add_membership(resource['id'],s.other)
    with s.storage.index.connect() as db:
        memberships=set(db.execute('SELECT parent_id FROM content WHERE resource_id=?',(resource['id'],)).fetchall())
    monkeypatch.setattr(g,'choose_target_node',lambda *a,**k:s.other)
    g.selected_keys={s.child,nested};g._commit_selection_visuals();g._batch_assign(False)
    assert s.storage.node(s.child)['parent_id']==s.other
    assert s.storage.node(nested)['parent_id']==s.child
    assert s.storage.index.content(s.child)==internal
    assert s.storage.resource_of(s.paths[3])['id']==resource['id']
    with s.storage.index.connect() as db:
        assert memberships==set(db.execute('SELECT parent_id FROM content WHERE resource_id=?',(resource['id'],)).fetchall())
    assert not g.selected_keys



def test_command_bar_height_changes_do_not_relayout_flow(surface,monkeypatch):
    s=surface;g=s.g;QTest.qWait(280)
    layout=Mock(wraps=g.renderer.relayout);monkeypatch.setattr(g.renderer,'relayout',layout)
    g._select_key(s.child,Qt.NoModifier);g._select_key(s.paths[0],Qt.ControlModifier)
    QTest.qWait(80);assert g.command_bar.isVisible() and not layout.called
    g._drop_selection_only();QTest.qWait(80)
    assert not g.command_bar.isVisible() and not layout.called
    g.resize(g.width()-100,g.height());QTest.qWait(80)
    assert layout.called,'real width changes still relayout'
