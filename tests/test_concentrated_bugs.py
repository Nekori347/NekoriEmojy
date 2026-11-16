"""Responsibility-layer reproductions for the authorized ten-bug batch."""
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from PIL import Image
from PySide6.QtCore import Qt,QPoint,QMimeData,QUrl,QRect
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from services.resource_import import ImportTarget
from services.library_index import ROOT


@pytest.fixture
def long_view(surface):
    s=surface
    for n in range(100):
        p=s.tmp/f'row-{n}.png';Image.new('RGB',(17,19),(n*2,n,170)).save(p)
        s.storage.save_file(str(p),target=ImportTarget(s.parent))
    s.g.refresh_content_incremental(parents={s.parent,ROOT});QTest.qWait(180)
    assert len(s.g._entries)>90 and s.g.scroll_area.verticalScrollBar().maximum()>0
    return s


def test_cancel_zone_never_covers_gallery_sorting(surface):
    g=surface.g;g._show_drag_cancel()
    assert g.drop_cancel_zone.parentWidget() is g.scroll_area.viewport()
    assert 0<g.drop_cancel_zone.height()<60
    assert g.available_gallery_rect().contains(g.drop_cancel_zone.geometry())
    g._hide_drag_cancel()


def test_first_root_before_line_is_visible_and_slot_zero(surface):
    tree=surface.g.sidebar.tree;tree.set_display_sort('manual')
    item=tree.topLevelItem(0);rect=tree.visualItemRect(item)
    mime=QMimeData();mime.setData('application/x-nekori-node',json.dumps([surface.other]).encode())
    # Use the actual project constant, including historical MIME spelling.
    from fluent_ui.components.drop_contract import NODE_MIME,INSERT_BEFORE
    mime=QMimeData();mime.setData(NODE_MIME,json.dumps([surface.other]).encode())
    target,_=tree._resolve_target(QPoint(rect.center().x(),rect.top()+1),mime)
    assert target.valid and target.placement==INSERT_BEFORE and target.index==next(e['position'] for e in surface.storage.entries_of(ROOT) if e['id']==item.data(0,Qt.UserRole))
    tree.feedback.show_target(target.placement,rect)
    assert tree.viewport().rect().intersects(tree.feedback.geometry())
    tree.end_drag_session()


def test_gap_paste_and_drop_name_same_row_boundary(long_view):
    s=long_view;g=s.g;rects=g.renderer.index.rects
    start=next(i for i,r in enumerate(rects) if i and r.top()>rects[i-1].top())
    previous=rects[start-1]
    point=QPoint(rects[0].center().x(),previous.bottom()+1)
    position=g.grid_container.mapTo(g,point)
    placement=g.placement_at(position)
    mime=QMimeData();mime.setUrls([QUrl('http://127.0.0.1/test.png')])
    target,_,_=g._resolve_drop(position,mime)
    assert placement.position==g._entries[start]['position']
    assert target.index==placement.position


def test_second_ctrl_selection_does_not_jump(long_view):
    g=long_view.g;bar=g.scroll_area.verticalScrollBar();bar.setValue(bar.maximum()-40);QTest.qWait(160)
    visible=[c for c in g._all_card_widgets if hasattr(c,'image_path') and g.scroll_area.viewport().rect().intersects(QRect(c.mapTo(g.scroll_area.viewport(),QPoint()),c.size()))]
    QTest.mouseClick(visible[-2],Qt.LeftButton,Qt.ControlModifier);QTest.qWait(70)
    before=bar.value();QTest.mouseClick(visible[-1],Qt.LeftButton,Qt.ControlModifier);QTest.qWait(180)
    assert abs(bar.value()-before)<=2,(before,bar.value())
    assert len(g.selected_keys)==2


def test_ctrl_selection_on_clipped_bottom_row_preserves_anchor(long_view):
    g=long_view.g;bar=g.scroll_area.verticalScrollBar();bar.setValue(round(bar.maximum()*.55));QTest.qWait(150)
    viewport=g.scroll_area.viewport()
    visible=[]
    for c in g._all_card_widgets:
        if not hasattr(c,'image_path'):continue
        rect=QRect(c.mapTo(viewport,QPoint()),c.size());intersection=rect.intersected(viewport.rect())
        if intersection.height()>12:visible.append((c,c.mapFrom(viewport,intersection.center())))
    QTest.mouseClick(visible[-2][0],Qt.LeftButton,Qt.ControlModifier,visible[-2][1]);QTest.qWait(80)
    anchor=g.renderer.anchor();before=bar.value()
    QTest.mouseClick(visible[-1][0],Qt.LeftButton,Qt.ControlModifier,visible[-1][1]);QTest.qWait(180)
    assert abs(bar.value()-before)<=2,(before,bar.value(),anchor,g.renderer.anchor())


def test_recent_database_failure_does_not_poison_async_send_queue(surface):
    import sqlite3
    from test_phase1_logic import sender
    from services.send_target import SendResult
    service,api,pending,injector=sender();service.remember(101);api.current=201
    class Clipboard:
        def prepare_image_async(self,path,callback):self.callback=callback
        def publish_prepared(self,data):return True
        def delivery_revision(self):return (0,'controlled')
        def delivery_matches(self,ticket):return True
    clipboard=Clipboard();storage=Mock();storage.config=None
    storage.add_recent_image.side_effect=sqlite3.OperationalError('synthetic database locked')
    results=[];service.send('controlled.png',clipboard,storage,results.append)
    clipboard.callback(object(),'')
    while pending:pending.pop(0)()
    assert results==[SendResult.SENT] and service._active is None
    storage.add_recent_image.side_effect=None
    service.send('controlled.png',clipboard,storage,results.append);clipboard.callback(object(),'')
    while pending:pending.pop(0)()
    assert results==[SendResult.SENT,SendResult.SENT]
    service.cancel_requests()


def test_focused_drag_source_does_not_reverse_autoscroll(long_view):
    g=long_view.g;bar=g.scroll_area.verticalScrollBar();bar.setValue(0);QTest.qWait(100)
    source=next(c for c in g._all_card_widgets if hasattr(c,'image_path'));source.setFocus();source._is_dragging=True
    values=[];bar.valueChanged.connect(values.append)
    try:
        g.drop_scroller.direction=1
        for _ in range(100):g.drop_scroller._tick();QTest.qWait(2)
    finally:source._is_dragging=False;g.drop_scroller.stop()
    assert all(b>=a for a,b in zip(values,values[1:])),values


def test_sidebar_sort_retains_live_icons(surface,monkeypatch):
    tree=surface.g.sidebar.tree
    render=Mock(wraps=tree._node_icon);monkeypatch.setattr(tree,'_node_icon',render)
    tree.set_display_sort('name_asc');tree.set_display_sort('name_desc');tree.set_display_sort('manual')
    assert render.call_count==0
    assert tree.topLevelItem(0).data(0,Qt.UserRole)==surface.parent


def test_unsupported_local_browser_candidate_falls_back_to_valid_image(surface):
    from services.clipboard import ClipboardService
    from PySide6.QtGui import QImage
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(surface.tmp/'expired.tmp'))])
    image=QImage(15,15,QImage.Format_RGB32);image.fill(Qt.red);mime.setImageData(image)
    kind,data=ClipboardService.importable_payload(mime,surface.storage.SUPPORTED_FORMATS)
    assert kind=='image' and not data.isNull()


def test_drag_hover_only_checks_advertisements(surface):
    from PySide6.QtWidgets import QWidget
    from PySide6.QtGui import QDragEnterEvent
    from fluent_ui.components.window_import import install_window_import
    class LazyMime(QMimeData):
        def hasImage(self):raise AssertionError('OLE rendering requested before drop')
        def imageData(self):raise AssertionError('OLE bitmap requested before drop')
    mime=LazyMime();mime.setData('image/png',b'advertisement')
    window=QWidget();window.resize(300,200);receiver=install_window_import(window,surface.g)
    event=QDragEnterEvent(QPoint(250,150),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    receiver.eventFilter(window,event)
    assert event.isAccepted()
    window.deleteLater()


def test_collected_receiver_wrapper_does_not_reenter_ui(surface):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.window_import import install_window_import
    window=QWidget();receiver=install_window_import(window,surface.g)
    del receiver.window
    assert receiver.eventFilter(window,QEvent(QEvent.Hide)) is False
    window.deleteLater()

