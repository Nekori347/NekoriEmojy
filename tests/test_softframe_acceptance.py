"""Acceptance repair and Softframe: isolated data and actual Qt event routing."""
import json
import time
from pathlib import Path
from unittest.mock import Mock
import pytest
from PIL import Image
from PySide6.QtCore import Qt, QPoint, QPointF, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QImage
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_phase2_interaction import surface, settle, card
from services.library_index import ROOT
from fluent_ui.components.drop_contract import TAG_MIME, RESOURCE_MIME
from services.clipboard import ClipboardService


def mime(kind, values):
    data=QMimeData();data.setData(kind,json.dumps(values).encode());return data


def drop(widget, point, data):
    enter=QDragEnterEvent(point,Qt.CopyAction|Qt.MoveAction,data,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(widget,enter)
    assert enter.isAccepted()
    move=QDragMoveEvent(point,Qt.CopyAction|Qt.MoveAction,data,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(widget,move)
    assert move.isAccepted()
    finish=QDropEvent(QPointF(point),Qt.CopyAction|Qt.MoveAction,data,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(widget,finish)
    assert finish.isAccepted()


def test_tag_first_entry_and_resource_to_tag_idempotent(surface):
    s,g=surface,surface.g
    flow=g.tag_panel.flow
    target=next(i for i,x in enumerate(flow._items) if x.name=='Cat')
    data=mime(RESOURCE_MIME,[s.paths[0],s.paths[1]])
    drop(flow,flow._rects[target].center(),data)
    assert 'Cat' in s.storage.resource_of(s.paths[1])['tags'].split()
    snapshot=s.storage.resource_of(s.paths[1])['tags']
    target=next(i for i,x in enumerate(flow._items) if x.name=='Cat')
    drop(flow,flow._rects[target].center(),data)
    assert s.storage.resource_of(s.paths[1])['tags']==snapshot
    # Accept the receiver on first entry over a gap. No scroll is involved.
    tags=mime(TAG_MIME,['Cat'])
    enter=QDragEnterEvent(QPoint(1,1),Qt.MoveAction,tags,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(g.scroll_area.viewport(),enter)
    assert enter.isAccepted()
    dest=card(s,s.paths[4])
    assert dest.acceptDrops() and dest._renderer.acceptDrops()
    drop(dest,dest.rect().center(),tags)
    assert 'Cat' in s.storage.resource_of(s.paths[4])['tags'].split()


def test_tags_click_filter_management_drag_and_collapsed_marker(surface,monkeypatch):
    s,g=surface,surface.g
    s.storage.apply_tags([s.paths[1]],['Dog'],'add');g.refresh_content_incremental(reason='test')
    flow=g.tag_panel.flow
    def center(name):return flow._rects[next(i for i,x in enumerate(flow._items) if x.name==name)].center()
    QTest.mouseClick(flow,Qt.LeftButton,pos=center('Cat'))
    assert g.active_tags=={'Cat'} and flow.active_filters=={'Cat'}
    assert not g.context_strip.isVisible() and not flow.selected()
    assert {e['path'] for e in g._entries if e['kind']=='resource'}=={s.paths[0]}
    QTest.mouseClick(flow,Qt.LeftButton,pos=center('Cat'))
    assert not g.active_tags
    QTest.mouseClick(flow,Qt.LeftButton,Qt.ControlModifier,pos=center('Cat'))
    QTest.mouseClick(flow,Qt.LeftButton,Qt.ControlModifier,pos=center('Dog'))
    assert set(flow.selected())=={'Cat','Dog'} and not g.active_tags
    captured=[]
    monkeypatch.setattr('fluent_ui.components.tag_panel.execute_drag',lambda source,data,*a:captured.append(bytes(data.data(TAG_MIME))))
    QTest.mousePress(flow,Qt.LeftButton,pos=center('Cat'))
    from PySide6.QtGui import QMouseEvent
    start=center('Cat');move=QMouseEvent(QMouseEvent.MouseMove,QPointF(start+QPoint(24,0)),QPointF(flow.mapToGlobal(start+QPoint(24,0))),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(flow,move)
    QTest.mouseRelease(flow,Qt.LeftButton,pos=start)
    assert json.loads(captured[0])==['Cat','Dog'] and not g.active_tags
    g._toggle_tag('Cat');g.tag_panel_host.set_expanded(False);settle(s.app)
    assert g.tag_panel.flow.active_filters=={'Cat'}
    g.tag_panel_host.set_expanded(True);assert g.tag_panel.flow.active_filters=={'Cat'}


def test_quick_external_file_image_and_browser_payloads_root(surface):
    from fluent_ui.components.quick_panel import QuickPanel
    s=surface;q=QuickPanel(s.storage,s.clipboard,s.config)
    q._activation_guard=True;q.show();settle(s.app)
    source=s.tmp/'quick-import.png';Image.new('RGB',(20,20),'orange').save(source)
    files=QMimeData();files.setUrls([QUrl.fromLocalFile(str(source))])
    for _ in range(2):
        drop(q.scroll_area.viewport(),QPoint(12,12),files)
        deadline=time.monotonic()+5
        while q.feedback_host.task_active and time.monotonic()<deadline:QTest.qWait(10)
        assert not q.feedback_host.task_active
    records=[e for e in s.storage.entries_of(ROOT) if e['kind']=='resource' and 'quick-import' in e['name']]
    assert len(records)==1
    assert not any(e['id']==records[0]['id'] for e in s.storage.index.content(s.parent))
    q.search_box.setText('quick-import');q._perform_search(force=True)
    assert any(c.image_path==records[0]['path'] for c in q._all_card_widgets)
    image=QMimeData();image.setImageData(QImage(str(source)));assert ClipboardService.decode_mime_data(image)[0]=='image'
    for data in (QMimeData(),QMimeData()):
        if not data.hasHtml():data.setHtml('<img src="https://example.test/pic.png?a=1&amp;b=2">')
        assert ClipboardService.decode_mime_data(data)==('network_url','https://example.test/pic.png?a=1&b=2')
    url=QMimeData();url.setUrls([QUrl('https://example.test/direct.webp')])
    assert ClipboardService.decode_mime_data(url)[0]=='network_url'
    q.shutdown();q.hide();q.deleteLater();settle(s.app)


def test_fixed_hierarchy_and_trailing_disclosure_navigation(surface):
    s,g=surface,surface.g
    root_y=None
    deep=s.storage.create_node('Deep',s.child);g.sidebar.refresh_list()
    frames=[]
    for node in (ROOT,s.parent,s.child,deep,s.parent):
        g.set_node(node);settle(s.app)
        frames.append((g.location_rail.height(),g.location_rail.current_rect().top(),g.category_tabs.mapTo(g,QPoint()).y(),g.search_box.mapTo(g,QPoint()).y()))
    assert len(set(frames))==1
    g.set_node(s.parent);settle(s.app)
    tree=g.sidebar.tree;item=tree._find_item(s.parent)
    tree.scrollToItem(item);settle(s.app)
    before=g.current_node
    was=item.isExpanded()
    QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.chevron_rect(item).center())
    assert item.isExpanded()!=was and g.current_node==before
    child=tree._find_item(s.other)
    QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.visualItemRect(child).center())
    assert g.current_node==s.other


@pytest.mark.parametrize('theme_name',['light','dark'])
def test_softframe_owned_surfaces_render_and_edit(surface,monkeypatch,theme_name):
    from qfluentwidgets import setTheme,Theme
    from fluent_ui.main_window import MainWindow
    from fluent_ui import visual
    from fluent_ui.components.softframe import SoftframeSlider,SoftframeProgress
    from fluent_ui.components.accent_picker import AccentColorPicker
    from PySide6.QtGui import QFont,QFontDatabase
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    surface.app.setFont(QFont('Microsoft YaHei',9))
    monkeypatch.setattr(MainWindow,'_init_global_hotkey',lambda _:None)
    monkeypatch.setattr(MainWindow,'apply_window_flags',lambda _:None)
    setTheme(Theme.DARK if theme_name=='dark' else Theme.LIGHT)
    window=MainWindow(surface.storage,surface.clipboard,surface.config)
    gallery=window.gallery_interface;gallery.focus_timer.stop()
    window.resize(1080,790);window.show();gallery.set_node(surface.parent)
    out=Path('../DevData/softframe-1015');out.mkdir(exist_ok=True)
    for name in ('Cat','Dog','表情包','日常'):
        gallery.tag_model.create(name)
    gallery.refresh_content_incremental(reason='capture')
    gallery._toggle_tag('Cat');settle(surface.app)
    assert window.accent_line.y()==3 and window.accent_line.height()==3
    assert window.accent_line.geometry().bottom()<window.titleBar.iconLabel.geometry().top()
    assert window.grab().save(str(out/f'main-{theme_name}.png'))
    c=window.setting_interface;c._select_page(1);c._show_tab(1)
    sw=window.settings_window;sw.resize(940,730);sw.show();settle(surface.app)
    assert isinstance(c._rows['thumbnail_size'][0].slider,SoftframeSlider)
    assert sw.grab().save(str(out/f'settings-{theme_name}.png'))
    row=c._rows['thumbnail_size'][0]
    row.spin.setValue(140);assert row.slider.value()==140
    c.discard()
    sw.hide()
    q=window.quick_panel;q._activation_guard=True;q.resize(390,460);q.show()
    q.search_box.setText('a');q._perform_search(force=True)
    q.feedback_host.task('Import',total=10);q.feedback_host.update_task(4,10,'4 / 10')
    settle(surface.app)
    assert isinstance(q.feedback_host.progress,SoftframeProgress)
    assert q.grab().save(str(out/f'quick-{theme_name}.png'))
    q.feedback_host.finish();q.hide()
    picker=AccentColorPicker('#6b8f5a',sw);picker.resize(520,440);picker.show();settle(surface.app)
    assert picker.grab().save(str(out/f'picker-{theme_name}.png'))
    picker.reject();picker.deleteLater()
    gallery.focus_timer.stop();gallery.preview_controller.cancel();q.shutdown()
    q.deleteLater();window.close();window.deleteLater();settle(surface.app)
    setTheme(Theme.LIGHT)


def test_quick_browser_download_and_bitmap_import_use_same_root_pipeline(surface):
    import io
    import threading
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from fluent_ui.components.quick_panel import QuickPanel
    s=surface;q=QuickPanel(s.storage,s.clipboard,s.config)
    q._activation_guard=True;q.show();settle(s.app)
    data=io.BytesIO();Image.new('RGB',(23,21),'purple').save(data,format='PNG')
    class Images(BaseHTTPRequestHandler):
        def do_GET(self):
            body=data.getvalue();self.send_response(200);self.send_header('Content-Type','image/png');self.end_headers();self.wfile.write(body)
        def log_message(self,*a):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Images)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    before=len(s.storage.index.content(ROOT))
    try:
        browser=QMimeData();browser.setHtml(f'<img src="http://127.0.0.1:{server.server_port}/image.png">')
        drop(q.scroll_area.viewport(),QPoint(12,12),browser)
        deadline=time.monotonic()+5
        while q.feedback_host.task_active and time.monotonic()<deadline:QTest.qWait(10)
        assert not q.feedback_host.task_active and len(s.storage.index.content(ROOT))==before+1
        image=QImage(25,22,QImage.Format_RGB32);image.fill(Qt.cyan)
        bitmap=QMimeData();bitmap.setImageData(image)
        drop(q.scroll_area.viewport(),QPoint(12,12),bitmap)
        assert len(s.storage.index.content(ROOT))==before+2
        bad=QMimeData();bad.setText('plain unsupported text')
        event=QDragEnterEvent(QPoint(12,12),Qt.CopyAction,bad,Qt.LeftButton,Qt.NoModifier)
        QApplication.sendEvent(q.scroll_area.viewport(),event)
        assert not event.isAccepted() and q.feedback_host.hint_label.text()=='无法导入此内容'
    finally:
        q.shutdown();q.hide();q.deleteLater();server.shutdown();server.server_close();worker.join();settle(s.app)
