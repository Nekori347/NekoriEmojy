"""Follow-up reproductions; isolated data, no desktop input."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from test_concentrated_bugs import long_view
from services.library_index import ROOT
from test_wpa_import_diagnostics import web


def test_cancel_dimensions_and_bottom_tag_occlusion(surface):
    g=surface.g
    for size in (60,120):
        g._commit_thumbnail_size(size)
        for width,height in ((1180,760),(760,480)):
            g.resize(width,height);g.tag_panel_host.set_placement('bottom')
            for expanded in (True,False):
                g.tag_panel_host.set_expanded(expanded,persist=False);QTest.qWait(100)
                g._show_drag_cancel();zone=g.drop_cancel_zone
                assert zone.parentWidget() is g.scroll_area.viewport()
                assert 0<zone.height()<60 and zone.height()<size
                assert zone.width()<=248
                assert g.available_gallery_rect().contains(zone.geometry())
                assert zone.geometry().bottom()<=g.available_gallery_rect().bottom()-2
                g._hide_drag_cancel()


def test_modifiers_and_keyboard_focus_gate_send_and_release_queue(surface):
    from unittest.mock import Mock
    from test_phase1_logic import TargetAPI
    from services.send_target import SendTargetService,SendResult
    class API(TargetAPI):
        held=True;ready=False
        def modifiers_pressed(self):return self.held
        def keyboard_ready(self,hwnd):return self.ready
    api=API();pending=[];injector=Mock();injector.paste.return_value=True
    service=SendTargetService(api=api,injector=injector,schedule=pending.append)
    service.remember(101);clipboard=Mock();storage=Mock();storage.config=None;results=[]
    service.send('controlled.png',clipboard,storage,results.append)
    for _ in range(3):pending.pop(0)()
    injector.paste.assert_not_called();assert api.current==201
    api.held=False;pending.pop(0)();injector.paste.assert_not_called()
    api.ready=True
    while pending:pending.pop(0)()
    assert results==[SendResult.SENT] and service._active is None
    # Held keys time out without being synthetically released, then a new send works.
    api.held=True;service.send('controlled.png',clipboard,storage,results.append)
    while pending:pending.pop(0)()
    assert results[-1]==SendResult.COPIED_ONLY and service.last_outcome.reason=='modifiers_held'
    assert service._active is None and api.held
    api.held=False
    for n in range(20):
        api.current=201;service.remember(101 if n%2 else 102)
        service.send('controlled.png',clipboard,storage,results.append)
        while pending:pending.pop(0)()
    assert results[-20:]==[SendResult.SENT]*20
    service.cancel_requests()


def virtual_mime(data,*,declared=False):
    from PySide6.QtCore import QMimeData,QUrl
    mime=QMimeData();descriptor=bytearray(596);descriptor[:4]=(1).to_bytes(4,'little')
    if declared:
        descriptor[4:8]=(0x40).to_bytes(4,'little');descriptor[72:76]=len(data).to_bytes(4,'little')
    mime.setData('application/x-qt-windows-mime;value="FileGroupDescriptorW"',bytes(descriptor))
    mime.setData('application/x-qt-windows-mime;value="FileContents"',b'')
    mime.setData('application/x-qt-windows-mime;value="FileContents";index=0',data)
    mime.setUrls([QUrl('http://127.0.0.1/protected.png')]);return mime


def test_virtual_file_without_size_flag_owns_bytes_and_preserves_gif(surface):
    import io,time
    from PIL import Image
    from services.clipboard import ClipboardService
    data=io.BytesIO();Image.new('RGB',(47,43),'teal').save(data,format='GIF',save_all=True,
        append_images=[Image.new('RGB',(47,43),'pink')],duration=100,loop=0)
    mime=virtual_mime(data.getvalue());kind,payload=ClipboardService.importable_payload(mime,surface.storage.SUPPORTED_FORMATS)
    assert kind=='image_bytes';mime.clear()  # source object lifetime ends before worker starts
    rid=surface.g._import_clipboard_payload(surface.parent,kind,payload)
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        QTest.qWait(20)
        if surface.g.imports.worker is None:break
    request=surface.g.imports.requests[rid]
    assert request.state=='completed' and request.saved==1 and not request.failed
    with Image.open(request.paths[0]) as image:assert image.n_frames==2
    assert payload.data==b'' and payload.fallback_url==''


def test_invalid_virtual_content_does_not_repeat_native_read(surface,monkeypatch):
    from unittest.mock import Mock
    from services.clipboard import ClipboardService
    from services.resource_import import ImportTarget
    from fluent_ui.components.drop_contract import DropTarget,INTO,IMPORT
    mime=virtual_mime(b'not image content');read=Mock(wraps=mime.data);monkeypatch.setattr(mime,'data',read)
    surface.g._import_urls(mime,DropTarget(INTO,IMPORT,None,surface.parent))
    # It submits the URL using the old path; virtual data was materialized once.
    assert sum('FileContents' in c.args[0] for c in read.call_args_list)==1
    for request in surface.g.imports.requests.values():surface.g.imports.cancel(request.id)
    QTest.qWait(30)


def test_waiting_virtual_cancel_discards_payload(surface):
    from services.resource_import import ImportBytes,ImportTarget
    payload=ImportBytes(b'owned','http://127.0.0.1/never-read')
    rid=surface.g.imports.submit([payload],ImportTarget(surface.parent),surface.g)
    surface.g.imports.cancel(rid);QTest.qWait(30)
    assert payload.data==b'' and payload.fallback_url==''


def test_corrupt_virtual_image_falls_back_once_in_worker(surface,web):
    import time
    from services.resource_import import ImportBytes,ImportTarget
    payload=ImportBytes(b'\x89PNG\r\n\x1a\ninvalid body',web+'/ok.png')
    rid=surface.g.imports.submit([payload],ImportTarget(surface.parent),surface.g)
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        surface.app.processEvents();time.sleep(.01)
        request=surface.g.imports.requests[rid]
        if request.state not in {'waiting','running','finalizing'}:break
    assert request.state=='completed' and request.saved==1 and request.failed==0
    assert payload.data==b'' and payload.fallback_url==''


def test_virtual_declared_oversize_rejected_before_content_read(surface,monkeypatch):
    from unittest.mock import Mock
    from services.clipboard import ClipboardService
    from services.resource_import import MAX_IMPORT_BYTES
    mime=virtual_mime(b'owned',declared=True)
    key='application/x-qt-windows-mime;value="FileGroupDescriptorW"'
    descriptor=bytearray(mime.data(key));descriptor[72:76]=(MAX_IMPORT_BYTES+1).to_bytes(4,'little')
    mime.setData(key,bytes(descriptor));read=Mock(wraps=mime.data);monkeypatch.setattr(mime,'data',read)
    assert ClipboardService.rendered_image(mime) is None
    assert not any('FileContents' in c.args[0] for c in read.call_args_list)


def test_height_only_layout_does_not_restore_stale_scroll(long_view):
    g=long_view.g;bar=g.scroll_area.verticalScrollBar()
    bar.setValue(bar.maximum()//3);QTest.qWait(100)
    g._schedule_responsive_layout()
    expected=min(bar.maximum(),bar.value()+124)
    bar.setValue(expected)
    QTest.qWait(100)
    assert bar.value()==expected


def test_tray_pixel_restore_is_scoped_to_its_view(long_view):
    g=long_view.g;bar=g.scroll_area.verticalScrollBar()
    bar.setValue(bar.maximum()//2);g.save_scroll_position()
    g.set_node(ROOT);QTest.qWait(120);expected=bar.value()
    g.restore_scroll_position();QTest.qWait(80)
    assert bar.value()==expected


def test_hide_resize_show_preserves_visible_anchor(long_view):
    g=long_view.g;bar=g.scroll_area.verticalScrollBar()
    bar.setValue(bar.maximum()*3//4);QTest.qWait(120);anchor=g.renderer.anchor()
    old=g.size();g.hide();g.resize(old.width(),1900);QTest.qWait(50)
    g.resize(old);g.show();QTest.qWait(180)
    assert g.renderer.anchor()==anchor
