"""Isolated real-widget/data regressions for WP-B drop contracts."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def gallery(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from services.resource_import import ImportTarget
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui import visual
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    config = ConfigService(); visual.theme.configure(config); i18n_engine.init(config)
    storage = StorageService(config=config)
    parent = storage.create_node('Mixed')
    children = [storage.create_node(f'Child {i}', parent) for i in range(3)]
    paths = []
    for i in range(90):
        source = tmp_path/f'{i}.png'
        image = QImage(24,24,QImage.Format_RGB32); image.fill(QColor(i,100,90)); image.save(str(source))
        paths.append(storage.save_file(str(source), target=ImportTarget(parent))[0])
    view = GalleryInterface(storage, ClipboardService(config), config)
    view.resize(1000,740); view.show(); view.set_node(parent); QTest.qWait(120)
    yield view, storage, parent, children, paths
    view.focus_timer.stop(); view.preview_controller.cancel(); view.hide()
    view.deleteLater(); app.processEvents()


def resource_mime(paths):
    from fluent_ui.components.drop_contract import RESOURCE_MIME
    mime = QMimeData(); mime.setData(RESOURCE_MIME, json.dumps(paths).encode())
    return mime


def test_gallery_drop_forwards_actual_global_position(gallery, monkeypatch):
    view, storage, parent, children, paths = gallery
    # Dropping in the category centre requests a membership menu at the drop.
    i = next(i for i,e in enumerate(view._entries) if e['id']==children[0])
    point = view.grid_container.mapTo(view, view.renderer.index.rects[i].center())
    mime = resource_mime(paths[:1]); calls=[]
    monkeypatch.setattr(view, 'request_resource_drop', lambda *a,**kw:calls.append((a,kw)))
    enter=QDragEnterEvent(point,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    view._begin_drop(enter,point)
    drop=QDropEvent(QPointF(point),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    view._complete_drop(drop,point)
    assert drop.isAccepted()
    assert calls[0][0][1] == children[0]
    assert calls[0][1]['global_pos'] == view.mapToGlobal(point)


def test_resource_between_nodes_persists_without_membership_change(gallery):
    from fluent_ui.components.drop_contract import INSERT_AFTER, INTO, APPEND
    from services.storage import StorageService
    view, storage, parent, children, paths = gallery
    entries=storage.entries_of(parent)
    nodes=[e for e in entries if e['kind']=='node']
    resources=[e for e in entries if e['kind']=='resource']
    storage.set_content_order(parent,nodes+resources)
    view.refresh_content_incremental(reason='fixture',parents={parent}); QTest.qWait(30)
    i=next(i for i,e in enumerate(view._entries) if e['id']==children[0])
    rect=view.renderer.index.rects[i]
    point=view.grid_container.mapTo(view,QPoint(rect.center().x(),rect.bottom()-1))
    target,_,vertical=view._resolve_drop(point,resource_mime(paths[:1]))
    assert target.placement==INSERT_AFTER and target.container_id==parent and not vertical
    view._reorder_by_drop(paths[:1],target)
    order=storage.entries_of(parent)
    assert [e['id'] for e in order[:3]]==[children[0],storage._resource_id(paths[0]),children[1]]
    assert not storage.entries_of(children[0])
    reopened=StorageService(config=view.config)
    assert [e['id'] for e in reopened.entries_of(parent)]==[e['id'] for e in order]
    view.set_node(parent); QTest.qWait(30)
    i=next(i for i,e in enumerate(view._entries) if e['id']==children[1])
    centre=view.grid_container.mapTo(view,view.renderer.index.rects[i].center())
    assert view._resolve_drop(centre,resource_mime(paths[:1]))[0].placement==INTO
    bottom=view.grid_container.mapTo(view,QPoint(5,view.renderer.index.height+20))
    assert view._resolve_drop(bottom,resource_mime(paths[:1]))[0].placement==APPEND


def test_membership_refresh_preserves_tree_and_surviving_gallery_anchor(gallery):
    from fluent_ui.components.gallery_model import occurrence_id
    view,storage,parent,children,paths=gallery
    for i in range(40):storage.create_node(f'Neighbour {i}')
    tree=view.sidebar.tree
    view.sidebar.refresh_list(parent); QTest.qWait(40)
    tree.verticalScrollBar().setValue(260); QTest.qWait(20)
    old_tree=tree.verticalScrollBar().value()
    bar=view.scroll_area.verticalScrollBar();bar.setValue(400);QTest.qWait(20)
    visible=list(view.renderer.index.between(bar.value(),bar.value()+view.scroll_area.viewport().height()))
    first_y=view.renderer.index.rects[visible[0]].top()
    moving=[view._entries[i]['path'] for i in visible if view.renderer.index.rects[i].top()==first_y]
    survivor=next(i for i in visible if view.renderer.index.rects[i].top()>first_y)
    key=occurrence_id(view._entries[survivor])
    old_y=view.renderer.index.rects[survivor].top()-bar.value()
    view.assign_resources(moving,children[0],copy=False,source_node=parent);QTest.qWait(100)
    assert tree.verticalScrollBar().value()==old_tree
    new_i=next(i for i,e in enumerate(view._entries) if occurrence_id(e)==key)
    assert view.renderer.index.rects[new_i].top()-bar.value()==old_y
    assert all(storage._resource_id(p) in {e['id'] for e in storage.entries_of(children[0])} for p in moving)
    # Metadata refresh preserves expansion; explicit navigation still reveals.
    item=tree._find_item(parent);item.setExpanded(True)
    view.sidebar.refresh_list(parent);QTest.qWait(30)
    assert tree._find_item(parent).isExpanded()
    last=storage.create_node('Last visible target')
    view.sidebar.refresh_list(parent)
    tree.select_node(last,reveal=True);QTest.qWait(30)
    assert tree.visualItemRect(tree._find_item(last)).intersects(tree.viewport().rect())
    # Nearby top/bottom edits retain the existing scroll rules and data.
    for scroll in (0,bar.maximum()):
        bar.setValue(scroll);QTest.qWait(20)
        anchor=view.renderer.anchor()
        candidates=[e for e in view._entries if e['kind']=='resource']
        view.assign_resources([candidates[-1]['path']],children[1],copy=True,source_node=parent)
        QTest.qWait(20)
        assert view.renderer.anchor()==anchor
    before=bar.value()
    view.drop_scroller.track(QPoint(50,1));QTest.qWait(40);view.drop_scroller.stop()
    assert bar.value()<before
