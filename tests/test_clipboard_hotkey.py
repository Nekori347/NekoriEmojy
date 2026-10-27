import ctypes
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QMimeData, QUrl, QEvent, QCoreApplication
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
from services.import_hotkey import WindowsHotkey, hotkey_parts
from services.clipboard import ClipboardService
from services.library_index import ROOT
from test_phase2_interaction import surface


def test_native_keys_visible_minimized_hidden_and_no_repeat():
    if sys.platform!='win32' or os.environ.get('QT_QPA_PLATFORM')=='offscreen':
        pytest.skip('Run with QT_QPA_PLATFORM=windows')
    app=QApplication.instance() or QApplication([])
    owner=QWidget();hotkey=WindowsHotkey(app);hits=[]
    hotkey.activated.connect(lambda:hits.append(True))
    try:
        assert hotkey.configure(True,'ctrl+alt+F9')
        api=ctypes.windll.user32
        for index,action in enumerate((owner.show,owner.showMinimized,owner.hide)):
            action();QTest.qWait(60)
            # Real Windows keyboard input; no pointer motion or chat target.
            for key in (0x11,0x12,0x78):api.keybd_event(key,0,0,0)
            QTest.qWait(60)
            api.keybd_event(0x78,0,0,0);QTest.qWait(20)
            for key in (0x78,0x12,0x11):api.keybd_event(key,0,2,0)
            QTest.qWait(50)
            assert len(hits)==index+1
        hotkey.configure(False,'')
        assert hotkey.registration is None
    finally:hotkey.close();owner.close()


def test_settings_save_reset_conflict_and_root_import(surface):
    from unittest.mock import Mock
    from fluent_ui.views.settings_center import SettingsCenter
    from fluent_ui.components.clipboard_import_command import ClipboardImportCommand
    from services.config import ConfigService
    s=surface
    s.config.config['clipboard_import_hotkey']='ctrl+alt+F10'
    center=SettingsCenter(s.config,s.storage)
    window=QWidget();window.gallery_interface=s.g
    window.settings_window=SimpleNamespace(center=center)
    tray=Mock();command=ClipboardImportCommand(window,s.config,tray)
    center._select_page(2)
    try:
        assert command.hotkey.binding==hotkey_parts('ctrl+alt+F10')
        center._stage('clipboard_import_hotkey','alt+2')
        assert not center.save() and s.config.get('clipboard_import_hotkey')=='ctrl+alt+F10'
        center._stage('clipboard_import_hotkey','ctrl+alt+F9');assert center.save()
        assert command.hotkey.binding==hotkey_parts('ctrl+alt+F9')
        center._stage('clipboard_import_enabled',False);assert center.save()
        assert command.hotkey.binding is None
        assert ConfigService(s.config.base_dir).get('clipboard_import_enabled') is False
        assert center._all_rows['clipboard_import_hotkey'][1]=='ctrl+alt+v'
        # The shared command imports while the gallery remains in a child scope.
        node=s.g.current_node;before=s.storage.index.content(s.parent)
        image=QImage(30,22,QImage.Format_RGB32);image.fill(0xff995533)
        s.clipboard.clipboard.setImage(image)
        command.trigger();rid=command.request_id
        for _ in range(500):
            QTest.qWait(10)
            if s.g.imports.requests[rid].state=='completed':break
        request=s.g.imports.requests[rid]
        assert request.state=='completed' and request.saved==1
        resource=s.storage._resource_id(request.paths[0])
        assert any(e['id']==resource for e in s.storage.index.content(ROOT))
        assert s.storage.index.content(s.parent)==before and s.g.current_node==node
    finally:command.hotkey.close();center.discard();center.close();window.close()


def test_windows_registration_conflict_rebind_and_thread_message():
    if sys.platform != 'win32':pytest.skip('Windows native mechanism')
    app=QApplication.instance() or QApplication([])
    hotkey=WindowsHotkey(app);hits=[];hotkey.activated.connect(lambda:hits.append(True))
    try:
        assert hotkey.configure(True,'ctrl+alt+F9')
        def occupied(text):
            mods,vk=hotkey_parts(text)
            code=f'import ctypes; u=ctypes.windll.user32; ok=u.RegisterHotKey(None,1,{mods}, {vk}); print(ok); u.UnregisterHotKey(None,1)'
            return subprocess.check_output([sys.executable,'-c',code],text=True).strip()=='0'
        assert occupied('ctrl+alt+F9')
        # Real Windows thread queue -> Qt native filter, independent of HWND.
        ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(),0x312,hotkey.registration,0)
        QTest.qWait(30);assert hits==[True]
        assert hotkey.configure(True,'ctrl+alt+F10')
        assert not occupied('ctrl+alt+F9') and occupied('ctrl+alt+F10')
        holder=subprocess.Popen([sys.executable,'-u','-c',
            'import ctypes,sys; u=ctypes.windll.user32; print(u.RegisterHotKey(None,1,3,0x78),flush=True); sys.stdin.readline(); u.UnregisterHotKey(None,1)'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='1'
            assert not hotkey.configure(True,'ctrl+alt+F9')
            assert hotkey.error and occupied('ctrl+alt+F10')
        finally:holder.communicate('\n',timeout=5)
        assert hotkey.configure(False,'')
        assert not occupied('ctrl+alt+F10')
    finally:hotkey.close()


def test_parser_matches_editor_and_rejects_unmodified():
    assert hotkey_parts('win+shift+v')==hotkey_parts('Meta+Shift+V')
    for text in ('','v','ctrl','ctrl+v','ctrl+v, ctrl+c'):
        with pytest.raises(ValueError):hotkey_parts(text)


def test_shared_clipboard_command_root_precedence_and_admission(tmp_path):
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui.components.clipboard_import_command import ClipboardImportCommand
    app=QApplication.instance() or QApplication([])
    clipboard=ClipboardService();submitted=[];notes=[]
    def submit(sources,target,owner,**kwargs):
        submitted.append((sources,target,kwargs));return 'one'
    queue=SimpleNamespace(submit=submit,requests={})
    gallery=SimpleNamespace(clipboard=clipboard,storage=SimpleNamespace(SUPPORTED_FORMATS=('.gif','.png')),
                            imports=queue,feedback_host=SimpleNamespace(toast=notes.append))
    gallery.paste_clipboard_to=lambda *a,**kw:GalleryInterface.paste_clipboard_to(gallery,*a,**kw)
    command=SimpleNamespace(gallery=gallery,request_id=None,feedback=notes.append)
    def trigger():ClipboardImportCommand.trigger(command)
    image=QImage(20,20,QImage.Format_RGB32);image.fill(0xff778899)
    # URL + image data for the same local GIF yields a single file import.
    path=tmp_path/'animated.gif';path.write_bytes(b'GIF89a')
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(path))]);mime.setImageData(image)
    clipboard.clipboard.setMimeData(mime);trigger()
    assert [os.path.normpath(p) for p in submitted[-1][0]]==[str(path)] and submitted[-1][1].parent_node==ROOT
    assert submitted[-1][2]['background'] and submitted[-1][1].insert_position is None
    queue.requests['one']=SimpleNamespace(state='decision');trigger();assert len(submitted)==1
    queue.requests['one'].state='completed'
    mime=QMimeData();mime.setImageData(image);clipboard.clipboard.setMimeData(mime);trigger()
    assert isinstance(submitted[-1][0][0],QImage)
    mime=QMimeData();mime.setText('https://example.org/emote.gif');clipboard.clipboard.setMimeData(mime);trigger()
    assert submitted[-1][0]==['https://example.org/emote.gif']
    mime=QMimeData();mime.setText('not an image');clipboard.clipboard.setMimeData(mime);trigger()
    assert len(submitted)==3 and notes


def test_background_duplicate_waits_until_activation_and_cancel_keeps_data(tmp_path,monkeypatch):
    from PIL import Image
    from services.config import ConfigService
    from services.storage import StorageService
    from services.resource_import import ImportTarget
    from fluent_ui.components.import_queue import ImportQueue
    from fluent_ui.components.duplicate_dialog import DuplicateBatchDialog
    app=QApplication.instance() or QApplication([])
    config=ConfigService(tmp_path/'app');config.config['ocr_auto']=False
    storage=StorageService(tmp_path/'library',config=config)
    path=tmp_path/'sample.png';Image.new('RGB',(15,12),'red').save(path)
    saved=storage.save_file(str(path))[0];node=storage.create_node('other')
    storage.index.add_membership(storage._resource_id(saved),node)
    before=storage.index.content(ROOT);owner=QWidget();queue=ImportQueue(storage,app)
    shown=[]
    monkeypatch.setattr(DuplicateBatchDialog,'show',lambda dialog:shown.append(dialog))
    try:
        rid=queue.submit([str(path)],ImportTarget(ROOT),owner,background=True)
        for _ in range(500):
            QTest.qWait(10)
            if queue._pending_batches:break
        assert queue.requests[rid].state=='decision' and not shown and not owner.isVisible()
        QCoreApplication.sendEvent(owner,QEvent(QEvent.WindowActivate))
        assert len(shown)==1
        shown[0].select('reuse')
        for _ in range(500):
            QTest.qWait(10)
            if queue.requests[rid].state=='completed':break
        assert queue.requests[rid].state=='completed'
        assert storage.index.content(ROOT)==before and len(storage.index.content(node))==1
        rid=queue.submit([str(path)],ImportTarget(ROOT),owner,background=True)
        for _ in range(500):
            QTest.qWait(10)
            if queue._pending_batches:break
        queue.cancel(rid)
        assert not queue._pending_batches and os.path.isfile(saved)
        assert storage.index.content(ROOT)==before
    finally:queue.shutdown();owner.deleteLater()


def test_direct_gif_url_uses_existing_download_and_preserves_animation(surface):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from PIL import Image
    from io import BytesIO
    s=surface;stream=BytesIO()
    Image.new('RGB',(24,18),'#115533').save(stream,format='GIF',save_all=True,
        append_images=[Image.new('RGB',(24,18),'#9955aa')],duration=100,loop=0)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','image/gif');self.end_headers()
            self.wfile.write(stream.getvalue())
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever);thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}/emote.gif'
        s.clipboard.clipboard.setText(url)
        rid=s.g.paste_clipboard_to(ROOT,background=True)
        for _ in range(500):
            QTest.qWait(10)
            if s.g.imports.requests[rid].state in {'completed','failed'}:break
        request=s.g.imports.requests[rid]
        assert request.state=='completed' and request.saved==1
        with Image.open(request.paths[0]) as image:assert image.n_frames==2 and image.format=='GIF'
    finally:server.shutdown();server.server_close();thread.join()
