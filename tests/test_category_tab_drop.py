"""Category tabs are relative projections and real category drop targets."""
from PySide6.QtCore import QPoint,QPointF,Qt,QEvent
from PySide6.QtGui import QDragEnterEvent,QDragMoveEvent,QDropEvent,QDragLeaveEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_wpb_closeout import gallery,node_mime
from test_wpb_drop import resource_mime

def enter(view,mime,index):
    tabs=view.category_tabs;p=tabs.content_tab_rect(index).center()
    event=QDragEnterEvent(p,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(tabs,event)
    return p,event

def move(view,mime,index):
    p=view.category_tabs.content_tab_rect(index).center()
    event=QDragMoveEvent(p,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(view.category_tabs,event)
    return p,event

def release(view,mime,index):
    p=view.category_tabs.content_tab_rect(index).center()
    event=QDropEvent(QPointF(p),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(view.category_tabs,event);QTest.qWait(30)
    return event

def test_resource_tab_drop_uses_existing_menu_and_cancel_does_not_write(gallery):
    view,storage,parent,children,paths=gallery;mime=resource_mime(paths[:1])
    before=storage.index.content(parent)
    p,event=enter(view,mime,1);assert event.isAccepted()
    event=release(view,mime,1);assert event.isAccepted()
    menu=view._drop_action_menu
    assert menu.isVisible()
    assert len([a for a in menu.actions() if a.isEnabled()])==3
    assert storage.index.content(parent)==before and not storage.entries_of(children[0])
    menu.actions()[-1].trigger();QTest.qWait(20)
    assert storage.index.content(parent)==before and not storage.entries_of(children[0])

def test_tab_dwell_changes_only_relative_projection_not_tree(gallery):
    view,storage,parent,children,paths=gallery;tree=view.sidebar.tree
    nested=storage.create_node('Moving subtree',children[2])
    storage.move_resources_to(paths[:1],children[2],copy=True,source_node=parent)
    before_subtree=storage.index.content(children[2])
    for i in range(24):storage.create_node(f'Neighbour {i}')
    view.sidebar.refresh_list(parent);QTest.qWait(30)
    item=tree._find_item(parent);item.setExpanded(False)
    tree.verticalScrollBar().setValue(100)
    assert tree.verticalScrollBar().value()>0
    before=(tree.currentItem().data(0,Qt.UserRole),tree._expanded_ids(),tree.verticalScrollBar().value())
    mime=node_mime([children[2]])
    _,event=enter(view,mime,1);assert event.isAccepted()
    QTest.qWait(780)
    assert view.current_node==parent and view.content_scope_node()==children[0]
    assert (tree.currentItem().data(0,Qt.UserRole),tree._expanded_ids(),tree.verticalScrollBar().value())==before
    assert storage.node(children[2])['parent_id']==parent
    assert release(view,mime,1).isAccepted()
    assert storage.node(children[2])['parent_id']==children[0]
    assert storage.node(nested)['parent_id']==children[2]
    assert storage.index.content(children[2])==before_subtree
    assert paths[0] in {e['path'] for e in storage.entries_of(parent) if e['kind']=='resource'}

def test_fast_cross_leave_resize_and_invalid_node_targets_cancel_dwell(gallery):
    from fluent_ui.components.drop_contract import INVALID
    view,storage,parent,children,paths=gallery
    nested=storage.create_node('Grandchild',children[0])
    # The existing left-tree resolver is the actual authority, not a tab rule.
    view.sidebar.refresh_list(parent)
    view._rebuild_category_tabs()
    mime=node_mime([children[2]])
    enter(view,mime,1);QTest.qWait(120);move(view,mime,2);QTest.qWait(120)
    QApplication.sendEvent(view.category_tabs,QDragLeaveEvent());QTest.qWait(760)
    assert view.content_scope_node()==parent and not view._tab_hover_timer.isActive()
    enter(view,mime,1);view.resize(view.width()-40,view.height());QTest.qWait(760)
    assert view.content_scope_node()==parent
    for target in (children[0],nested):
        view.set_node(children[0])
        index=view._tab_nodes.index(target)
        invalid=node_mime([children[0],children[2]])
        _,event=enter(view,invalid,index)
        assert not event.isAccepted() and not view._tab_hover_timer.isActive()
        assert view.sidebar.tree.resolve_category_target(target,.5,invalid).placement==INVALID
        assert not release(view,invalid,index).isAccepted()
    assert storage.node(children[0])['parent_id']==parent
    assert storage.node(children[2])['parent_id']==parent

def test_resources_existing_membership_can_dwell_and_menu_add_is_idempotent(gallery):
    view,storage,parent,children,paths=gallery
    storage.move_resources_to(paths[:1],children[0],copy=True,source_node=parent)
    view.refresh_content_incremental(reason='fixture',parents={children[0]})
    mime=resource_mime(paths[:1]);enter(view,mime,1);QTest.qWait(760)
    assert view.content_scope_node()==children[0]
    assert release(view,mime,1).isAccepted()
    menu=view._drop_action_menu
    add=next(a for a in menu.actions() if '加入分类' in a.text());add.trigger();QTest.qWait(30)
    assert [e['path'] for e in storage.entries_of(children[0])]==paths[:1]
    assert paths[0] in {e['path'] for e in storage.entries_of(parent) if e['kind']=='resource'}

def test_origin_mime_survives_dwell_and_content_or_sidebar_receive(gallery):
    import json
    from fluent_ui.components.drop_contract import RESOURCE_SOURCES_MIME,DropTarget,INTO,MOVE
    view,storage,parent,children,paths=gallery
    storage.move_resources_to(paths[:1],children[1],copy=True,source_node=parent)
    view.refresh_content_incremental(reason='fixture',parents={children[1]})
    mime=resource_mime(paths[:1]);mime.setData(RESOURCE_SOURCES_MIME,json.dumps({paths[0]:parent}).encode())
    enter(view,mime,1);QTest.qWait(760)
    assert view.content_scope_node()==children[0]
    QApplication.sendEvent(view.category_tabs,QDragLeaveEvent())
    # A new receive surface must read the original membership context from
    # the same drag, rather than guessing from the now-empty relative view.
    from fluent_ui.components.drop_contract import DragSession
    target=DropTarget(INTO,MOVE,children[0],children[0])
    session=DragSession(mime);view._commit_drop_payload(target,mime,list(session.payload),
        view.mapToGlobal(QPoint(50,50)),sources=session.sources)
    QTest.qWait(30);menu=view._drop_action_menu
    assert any('移动到' in a.text() for a in menu.actions())
    menu.actions()[0].trigger();QTest.qWait(40)
    assert paths[0] not in {e['path'] for e in storage.entries_of(parent) if e['kind']=='resource'}
    assert paths[0] in {e['path'] for e in storage.entries_of(children[0])}
    assert paths[0] in {e['path'] for e in storage.entries_of(children[1])}

def test_menu_uses_actual_release_after_tab_scroll_and_screen_clamping(gallery):
    from PySide6.QtGui import QGuiApplication
    view,storage,parent,children,paths=gallery
    for i in range(12):storage.create_node(f'Long target category {i}',parent)
    view.sidebar.refresh_list(parent);view.refresh_content_incremental(reason='fixture',parents={parent})
    view.resize(670,600);QTest.qWait(80)
    tabs=view.category_tabs
    right=next(b for b in tabs._scroll_buttons if b.arrowType()==Qt.RightArrow)
    assert right.isVisible()
    right.click();QTest.qWait(20)
    indices=[i for i in range(1,tabs.count()) if tabs._tab_viewport().contains(tabs.content_tab_rect(i).center())]
    assert indices
    index=indices[-1];target=view._tab_nodes[index];mime=resource_mime(paths[:1])
    p,event=enter(view,mime,index);expected=tabs.mapToGlobal(p)
    assert event.isAccepted() and release(view,mime,index).isAccepted()
    menu=view._drop_action_menu;area=(QGuiApplication.screenAt(expected) or menu.screen()).availableGeometry()
    actual=QPoint(max(area.left(),min(expected.x(),area.right()-menu.width()+1)),
                  max(area.top(),min(expected.y(),area.bottom()-menu.height()+1)))
    assert menu.pos()==actual and storage.node(target)['name'] in menu.actions()[0].text()
    menu.actions()[-1].trigger()
    assert not storage.entries_of(target)

def test_actual_resource_source_mime_and_binding_survive_projection_change(gallery,monkeypatch):
    from PySide6.QtGui import QDrag,QMouseEvent
    from fluent_ui.components.drop_contract import DragSession
    view,storage,parent,children,paths=gallery
    source=next(c for c in view._all_card_widgets if getattr(c,'image_path',None)==paths[0])
    observed=[]
    def drag_exec(drag,*a):
        session=DragSession(drag.mimeData())
        assert session.sources=={paths[0]:parent}
        assert view.drop_cancel_zone.isVisible()
        enter(view,drag.mimeData(),1);QTest.qWait(760)
        assert view.content_scope_node()==children[0]
        assert source.image_path==paths[0] and not source._renderer.isVisible()
        observed.append(True)
        QApplication.sendEvent(view.category_tabs,QDragLeaveEvent())
        return Qt.IgnoreAction
    monkeypatch.setattr(QDrag,'exec',drag_exec)
    source._drag_start_pos=QPoint(2,2)
    event=QMouseEvent(QEvent.MouseMove,QPointF(25,25),QPointF(source.mapToGlobal(QPoint(25,25))),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    source.mouseMoveEvent(event)
    assert observed and not view.drop_cancel_zone.isVisible()
    assert source not in view.renderer.active.values()
