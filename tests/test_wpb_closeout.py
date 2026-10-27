"""Concrete mixed-flow gaps and category projection drop regressions."""
import json
import pytest
from PySide6.QtCore import QMimeData,QPoint,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_wpb_drop import resource_mime

@pytest.fixture
def gallery(tmp_path,monkeypatch):
    from PIL import Image
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.resource_import import ImportTarget
    from services.i18n import i18n_engine
    from fluent_ui import visual
    from fluent_ui.views.gallery_view import GalleryInterface
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'library'))
    config=ConfigService();visual.theme.configure(config);i18n_engine.init(config)
    storage=StorageService(config=config);parent=storage.create_node('Mixed')
    children=[storage.create_node(f'Child {i}',parent) for i in range(3)]
    paths=[]
    for i in range(8):
        source=tmp_path/f'{i}.png';Image.new('RGB',(24,24),(i*20,90,100)).save(source)
        paths.append(storage.save_file(str(source),target=ImportTarget(parent))[0])
    view=GalleryInterface(storage,ClipboardService(config),config)
    view.resize(1000,740);view.show();view.set_node(parent);QTest.qWait(150)
    yield view,storage,parent,children,paths
    view.focus_timer.stop();view.preview_controller.cancel();view.imports.shutdown();view.ocr.close()
    view.close();view.deleteLater();app.processEvents()

def node_mime(ids):
    from fluent_ui.components.drop_contract import NODE_MIME
    mime=QMimeData();mime.setData(NODE_MIME,json.dumps(ids).encode());return mime

def point(view,entry_id,dy=0):
    i=next(i for i,e in enumerate(view._entries) if e['id']==entry_id)
    rect=view.renderer.index.rects[i]
    return view.grid_container.mapTo(view,QPoint(rect.center().x(),rect.top()+dy)),rect

def mixed(gallery,expanded=False):
    view,storage,parent,children,paths=gallery
    records=storage.entries_of(parent);by_id={e['id']:e for e in records}
    a,d=map(storage._resource_id,paths[:2]);b,c=children[:2]
    lead=[by_id[k] for k in (a,b,c,d)]
    storage.set_content_order(parent,lead+[e for e in records if e['id'] not in (a,b,c,d)])
    if expanded:
        storage.move_resources_to(paths[2:4],b,copy=True,source_node=parent)
        view._expanded_nodes.add(b)
    view.refresh_content_incremental(reason='fixture',parents={parent,b});QTest.qWait(40)
    return view,storage,parent,children,paths

def test_gap_after_expanded_section_has_one_parent_slot(gallery):
    view,storage,parent,children,paths=mixed(gallery,expanded=True)
    p,rect=point(view,children[1]);mime=resource_mime(paths[5:6])
    i=next(i for i,e in enumerate(view._entries) if e['id']==children[1])
    previous=view.renderer.index.rects[i-1]
    p=view.grid_container.mapTo(view,QPoint(previous.center().x(),rect.top()))
    # Both halves of the same visible four-pixel gap before C mean the
    # parent's B|C boundary, not the last resource row inside expanded B.
    for dy in range(-4,0):
        target,_,_=view._resolve_drop(p+QPoint(0,dy),mime)
        assert target.container_id==parent,(dy,target)
        assert target.index==2,(dy,target)

def test_gap_below_resource_row_is_after_row_not_left_of_image(gallery):
    view,storage,parent,children,paths=mixed(gallery)
    p,rect=point(view,children[0]);mime=resource_mime(paths[5:6])
    for dy in range(-4,0):
        # The full-width header gap remains a boundary even at the left
        # edge, far from the centred resource card in the previous row.
        target,_,_=view._resolve_drop(p+QPoint(-rect.width()//2+2,dy),mime)
        assert target.container_id==parent
        assert target.index==1,(dy,target)

def test_node_before_resource_removes_moving_block_before_counting_slot(gallery):
    view,storage,parent,children,paths=mixed(gallery)
    d=storage._resource_id(paths[1]);p,rect=point(view,d)
    p=view.grid_container.mapTo(view,QPoint(rect.left()+1,rect.center().y()))
    target,_,_=view._resolve_drop(p,node_mime([children[0]]))
    view._apply_node_drop([children[0]],target)
    assert [e['id'] for e in storage.entries_of(parent)[:4]]==[
        storage._resource_id(paths[0]),children[1],children[0],d]

def test_node_into_descendant_is_invalid_before_commit(gallery):
    from fluent_ui.components.drop_contract import INVALID
    view,storage,parent,children,paths=mixed(gallery)
    nested=storage.create_node('Nested',children[0]);view._expanded_nodes.add(children[0])
    view.refresh_content_incremental(reason='fixture',parents={children[0]});QTest.qWait(40)
    p,rect=point(view,nested,15)
    target,_,_=view._resolve_drop(p,node_mime([children[0]]))
    assert target.placement==INVALID

def test_shared_boundary_feedback_and_qt_surface_commit_persist(gallery):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QDragEnterEvent,QDragMoveEvent,QDropEvent
    from fluent_ui.components.drop_contract import indicator_rect,INSERT_AFTER,INSERT_BEFORE
    from services.storage import StorageService
    view,storage,parent,children,paths=mixed(gallery,expanded=True)
    mime=resource_mime(paths[5:7])
    pb,rb=point(view,children[0]);pc,rc=point(view,children[1])
    tb,fb,vb=view._resolve_drop(pb+QPoint(0,rb.height()-2),mime)
    tc,fc,vc=view._resolve_drop(pc+QPoint(0,1),mime)
    assert (tb.placement,tc.placement)==(INSERT_AFTER,INSERT_BEFORE)
    assert (tb.container_id,tb.index)==(tc.container_id,tc.index)==(parent,2)
    assert indicator_rect(tb.placement,fb,vb)==indicator_rect(tc.placement,fc,vc)
    i=next(i for i,e in enumerate(view._entries) if e['id']==children[1])
    card=next(w for w in view._all_card_widgets if getattr(w,'node_id',None)==children[1])
    local=QPoint(card.width()//2,1)
    enter=QDragEnterEvent(local,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(card,enter);assert enter.isAccepted()
    move=QDragMoveEvent(local,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(card,move);assert move.isAccepted()
    drop=QDropEvent(QPointF(local),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(card,drop);assert drop.isAccepted()
    ids=[e['id'] for e in storage.entries_of(parent)]
    assert ids[1:5]==[children[0],storage._resource_id(paths[5]),storage._resource_id(paths[6]),children[1]]
    assert [e['id'] for e in StorageService(config=view.config).entries_of(parent)]==ids
    assert {e['path'] for e in storage.entries_of(children[0])}==set(paths[2:4])

def test_compact_rows_edges_gaps_and_extremes_keep_existing_contract(gallery):
    from fluent_ui.components.drop_contract import INSERT_BEFORE,INSERT_AFTER,INTO,APPEND
    view,storage,parent,children,paths=mixed(gallery)
    pb,rb=point(view,children[0]);pc,rc=point(view,children[1]);pa,ra=point(view,storage._resource_id(paths[0]))
    for mime in (resource_mime(paths[5:6]),node_mime([children[2]])):
        for p,placement,index in [(pb+QPoint(0,1),INSERT_BEFORE,1),(pb+QPoint(0,rb.height()-2),INSERT_AFTER,2),
                (pc+QPoint(0,-4),INSERT_BEFORE,2),(pc+QPoint(0,-1),INSERT_BEFORE,2),
                (pc+QPoint(0,1),INSERT_BEFORE,2),(pc+QPoint(0,rc.height()-2),INSERT_AFTER,3),
                (pa+QPoint(0,-2),INSERT_BEFORE,0)]:
            target,_,_=view._resolve_drop(p,mime)
            assert (target.placement,target.container_id,target.index)==(placement,parent,index)
        target,_,_=view._resolve_drop(pb+QPoint(0,rb.height()//2),mime)
        assert (target.placement,target.container_id)==(INTO,children[0])
        bottom=view.grid_container.mapTo(view,QPoint(20,view.renderer.index.height+10))
        assert view._resolve_drop(bottom,mime)[0].placement==APPEND
