"""OLE payload/ownership checks; live desktop sessions are separate evidence."""
import struct
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows OLE adapter')

from test_management_mode import management


def test_native_payload_preserves_binary_mime_and_deferred_file_lifetime(tmp_path, monkeypatch):
    import win32clipboard
    from PySide6.QtWidgets import QApplication
    from shiboken6 import delete
    from services.external_drag import ResourceDragMimeData
    from services.windows_resource_drag import ResourceDataObject
    from fluent_ui.components.drop_contract import RESOURCE_MIME, RESOURCE_SOURCES_MIME
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    original = tmp_path/'generated.gif'
    original.write_bytes(b'generated fixture')
    mime = ResourceDragMimeData([str(original)])
    mime.setData(RESOURCE_SOURCES_MIME, b'{"source":"category-id"}')
    data = ResourceDataObject(mime)
    for name in (RESOURCE_MIME, RESOURCE_SOURCES_MIME):
        cf = win32clipboard.RegisterClipboardFormat(name)
        assert data.GetData((cf, None, 1, -1, 1)).data == bytes(mime.data(name))
    assert not (tmp_path/'app/cache/external_drag').exists()
    # A receiver retaining IDataObject must not call a destroyed Qt MIME object.
    delete(mime)
    body = data.GetData((15, None, 1, -1, 1)).data
    assert struct.unpack('<I', body[:4]) == (20,)
    path = body[20:].decode('utf-16le').rstrip('\0')
    from pathlib import Path
    exported = Path(path)
    assert exported != original and exported.read_bytes() == original.read_bytes()
    from PySide6.QtCore import QUrl
    url = data.GetData((data.url_wide, None, 1, -1, 1)).data.decode('utf-16le').rstrip('\0')
    assert Path(QUrl(url).toLocalFile()) == exported
    assert data.GetData((13, None, 1, -1, 1)).data.decode('utf-16le').rstrip('\0') == str(exported)
    exported.unlink()
    assert original.read_bytes() == b'generated fixture'


def test_recycle_feedback_is_per_session_and_frozen_after_completion():
    import pythoncom
    from services.external_drag import ResourceDragMimeData
    from services.windows_resource_drag import ResourceDataObject, RECYCLE_BIN
    first = ResourceDataObject(ResourceDragMimeData([]))
    second = ResourceDataObject(ResourceDragMimeData([]))
    def send(data, cf, value):
        medium = pythoncom.STGMEDIUM()
        medium.set(1, memoryview(value))
        data.SetData((cf, None, 1, -1, 1), medium, False)
    send(first, first.target_format, RECYCLE_BIN.bytes_le)
    send(first, first.logical_format, struct.pack('<I', 2))
    assert first.target == RECYCLE_BIN and first.logical_effect == 2
    assert second.target is None and second.logical_effect == 0
    second.completed = True
    send(second, second.target_format, RECYCLE_BIN.bytes_le)
    assert second.target is None


def test_drop_source_uses_live_button_state_when_ole_flags_are_stale(monkeypatch):
    import winerror
    from services.windows_resource_drag import ResourceDropSource
    source = ResourceDropSource()
    monkeypatch.setattr(source, 'left_pressed', lambda: False)
    assert source.QueryContinueDrag(False, 1) == winerror.DRAGDROP_S_DROP
    assert source.released


def test_recycle_completion_defers_confirmation_and_uses_stable_batch(management, monkeypatch):
    from pathlib import Path
    from PySide6.QtTest import QTest
    from fluent_ui.components import dialogs
    view, storage, parent, dest, paths, sent = management
    storage.add_image_to_category(paths[0], dest)
    snapshot = view._resource_drag_snapshot(paths[:2])
    view._select_single(paths[4])  # a changed projection/selection is not the drop payload
    selection = set(view.selected_keys)
    before = storage.index.resources(), storage.index.content(parent), storage.index.content(dest)
    contents = {p: Path(p).read_bytes() for p in paths}
    calls = []
    def cancel(*args, **kwargs):
        calls.append(kwargs['hint'])
        return False
    monkeypatch.setattr(dialogs, 'confirm', cancel)
    view._recycle_drag_completed(snapshot)
    assert not calls  # no modal inside the completion callback / OLE stack
    QTest.qWait(30)
    assert len(calls) == 1 and '副本' in calls[0]
    assert set(view.selected_keys) == selection and not sent
    assert before == (storage.index.resources(), storage.index.content(parent), storage.index.content(dest))
    assert all(Path(p).read_bytes() == body for p, body in contents.items())
    monkeypatch.setattr(dialogs, 'confirm', lambda *a, **kw: True)
    view._recycle_drag_completed(snapshot)
    QTest.qWait(50)
    assert all(storage.index.resource_by_id(key) is None for key in snapshot[1])
    assert not any(Path(p).exists() for p in paths[:2])
    assert Path(paths[4]).read_bytes() == contents[paths[4]]
    assert not storage.index.content(dest)


def test_missing_or_other_library_snapshot_cannot_delete_current_selection(management, monkeypatch):
    from PySide6.QtTest import QTest
    from fluent_ui.components import dialogs
    view, storage, parent, dest, paths, sent = management
    snapshot = view._resource_drag_snapshot([paths[0]])
    view._select_single(paths[1])
    storage.forget_resource(snapshot[1][0])
    monkeypatch.setattr(dialogs, 'confirm', lambda *a, **kw: pytest.fail('no surviving drag resource'))
    view._recycle_drag_completed(snapshot)
    view._recycle_drag_completed(('other library', (storage.index.resource(paths[1])['id'],)))
    QTest.qWait(30)
    assert storage.index.resource(paths[1]) is not None


def test_delete_transaction_rejects_a_path_now_owned_by_an_unconfirmed_id(management, monkeypatch):
    from pathlib import Path
    view, storage, parent, dest, paths, sent = management
    confirmed = storage.index.resource(paths[0])['id']
    before = storage.index.resources(), storage.index.content(parent)
    monkeypatch.setattr('services.recycle_bin.recycle_file', lambda *args: pytest.fail('wrong resource must not be recycled'))
    result = storage.delete_images_batch([paths[1]], expected_ids=[confirmed])
    assert result['failed'] == 1 and result['deleted'] == 0
    assert before == (storage.index.resources(), storage.index.content(parent))
    assert Path(paths[1]).is_file()


@pytest.mark.parametrize('accept', [False, True])
def test_existing_real_confirmation_buttons_for_recycled_batch(management, accept):
    from pathlib import Path
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton
    from fluent_ui.components import dialogs
    view, storage, parent, dest, paths, sent = management
    snapshot = view._resource_drag_snapshot(paths[:2])
    before = storage.index.resources(), storage.index.content(parent)
    observed = []
    def press():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, dialogs.NekoriDialog) and dialog.isVisible()
        text = '删除' if accept else '取消'
        button = next(button for button in dialog.findChildren(QPushButton) if button.text() == text)
        observed.append(True)
        QTest.mouseClick(button, Qt.LeftButton)
    QTimer.singleShot(100, press)
    view._recycle_drag_completed(snapshot)
    QTest.qWait(250)
    assert observed and QApplication.activeModalWidget() is None
    if accept:
        assert all(storage.index.resource_by_id(key) is None for key in snapshot[1])
        assert not any(Path(path).exists() for path in paths[:2])
    else:
        assert before == (storage.index.resources(), storage.index.content(parent))
        assert all(Path(path).is_file() for path in paths)


@pytest.mark.parametrize('outcome', ['recycle', 'folder', 'cancel', 'failed', 'copy_error'])
def test_only_completed_recycle_of_delivered_copies_is_delete_intent(tmp_path, monkeypatch, outcome):
    import uuid
    import pythoncom
    from PySide6.QtGui import QDrag
    from PySide6.QtWidgets import QApplication, QLabel
    from services.external_drag import ResourceDragMimeData
    from services import windows_resource_drag as native
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    path = tmp_path/'generated.png'; path.write_bytes(b'fixture')
    widget = QLabel(); drag = QDrag(widget); drag.setMimeData(ResourceDragMimeData([str(path)]))
    if outcome == 'copy_error':
        def fail(*args):raise OSError('test copy failure')
        monkeypatch.setattr('services.external_drag.shutil.copyfile', fail)
    def session(data, source, effects):
        def send(name, body):
            import win32clipboard
            medium = pythoncom.STGMEDIUM(); medium.set(1, memoryview(body))
            data.SetData((win32clipboard.RegisterClipboardFormat(name), None, 1, -1, 1), medium, False)
        data.GetData((15, None, 1, -1, 1))
        target = uuid.UUID('f3364ba0-65b9-11ce-a9ba-00aa004ae837') if outcome == 'folder' else native.RECYCLE_BIN
        send('TargetCLSID', target.bytes_le)
        send('Logical Performed DropEffect', struct.pack('<I', 0 if outcome == 'failed' else 2))
        source.QueryContinueDrag(outcome == 'cancel', 0)
        return 0  # real Shell can return NONE after successful recycling
    monkeypatch.setattr(native.pythoncom, 'DoDragDrop', session)
    monkeypatch.setattr(native.ResourceDropSource, 'left_pressed', staticmethod(lambda: False))
    assert native.execute(drag) == (outcome == 'recycle')
    assert path.read_bytes() == b'fixture'
