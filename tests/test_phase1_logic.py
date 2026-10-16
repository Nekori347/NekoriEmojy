"""Phase 1 acceptance: catalog order, shared guards and safe send outcomes."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor

from services.action_policy import ActionContext, ActionPolicy
from services.config import ConfigService
from services.library_index import LibraryIndex, ROOT
from services.nekori_package import NekoriPackageService
from services.resource_import import ImportTarget
from services.resource_sort import ResourceSort
from services.send_target import SendResult, SendTargetService, PasteInjector, INPUT
from services.storage import StorageService


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def storage(tmp_path, app):
    return StorageService(tmp_path / 'library', ConfigService(tmp_path / 'app'))


def save(storage, tmp_path, name, color, target=None):
    source = tmp_path / name
    Image.new('RGBA', (16, 16), color).save(source)
    return storage.save_file(str(source), target=target)[0]


class TargetAPI:
    def __init__(self):
        self.windows = {101: (os.getpid() + 1, 'Chat'), 102: (os.getpid() + 2, 'Chat'),
                        201: (os.getpid(), 'Main'), 202: (os.getpid(), 'Quick'),
                        203: (os.getpid(), 'Settings'), 204: (os.getpid(), 'About'),
                        205: (os.getpid(), 'Similarity'), 206: (os.getpid(), 'QQ'),
                        207: (os.getpid(), 'Telegram'), 208: (os.getpid(), '#32770'),
                        301: (os.getpid() + 3, 'Shell_TrayWnd')}
        self.current = 201
        self.acquire = True

    def is_window(self, hwnd):
        return hwnd in self.windows

    def process_id(self, hwnd):
        return self.windows[hwnd][0]

    def class_name(self, hwnd):
        return self.windows[hwnd][1]

    def foreground(self):
        return self.current

    def acquire_foreground(self, hwnd):
        if self.acquire:
            self.current = hwnd


def sender():
    api, pending, injector = TargetAPI(), [], Mock()
    injector.paste.return_value = True
    service = SendTargetService(api=api, injector=injector, schedule=pending.append)
    return service, api, pending, injector


def test_schema_backfill_once_and_sequence_never_reused(tmp_path):
    root = tmp_path / 'old'
    root.mkdir()
    with sqlite3.connect(root / 'index.sqlite3') as db:
        db.executescript('''PRAGMA user_version=1;
            CREATE TABLE resources (id TEXT PRIMARY KEY, filename TEXT UNIQUE,
            relative_path TEXT UNIQUE, display_name TEXT, tags TEXT DEFAULT '',
            ocr_text TEXT DEFAULT '', metadata_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'normal', created_at TEXT);''')
        for identifier, stamp in [('c', '2020-01-01'), ('b', '2019-01-01'), ('a', '2020-01-01')]:
            db.execute('INSERT INTO resources(id,filename,relative_path,display_name,created_at) VALUES (?,?,?,?,?)',
                       (identifier, identifier+'.png', identifier+'.png', identifier, stamp))
    index = LibraryIndex(root)
    assert [index.resource_by_id(i)['library_added_seq'] for i in ('b', 'a', 'c')] == [1, 2, 3]
    index.forget_resource('c')
    reopened = LibraryIndex(root)
    new_id = reopened.register(root / 'new.png')
    assert reopened.resource_by_id(new_id)['library_added_seq'] == 4
    assert reopened.resource_by_id('a')['library_added_seq'] == 2


def test_duplicate_file_and_clipboard_preserve_records_membership_and_order(storage, tmp_path):
    node, other = storage.create_node('Target'), storage.create_node('Other')
    a = save(storage, tmp_path, 'a.png', 'red', ImportTarget(node, 0))
    save(storage, tmp_path, 'b.png', 'blue', ImportTarget(node, 0))
    before, record = storage.index.content(node), storage.resource_of(a)
    root_before = storage.index.content(ROOT)
    assert storage.save_file(str(tmp_path / 'a.png'), target=ImportTarget(node, 0)) == (a, True)
    assert storage.index.content(node) == before
    assert storage.index.content(ROOT) == root_before
    assert storage.resource_of(a) == record
    storage.save_file(str(tmp_path / 'a.png'), target=ImportTarget(other, 0))
    assert storage.index.content(other)[0]['id'] == record['id']
    assert storage.resource_of(a) == record
    image = QImage(16, 16, QImage.Format_RGBA8888)
    image.fill(QColor('green'))
    pasted, _ = storage.save_image(image, ImportTarget(node, 0))
    storage.save_file(str(tmp_path / 'b.png'), target=ImportTarget(node, 0))
    before = storage.index.content(node)
    seq = storage.resource_of(pasted)['library_added_seq']
    assert storage.save_image(image, ImportTarget(node, 0)) == (pasted, True)
    assert storage.index.content(node) == before
    assert storage.resource_of(pasted)['library_added_seq'] == seq


def test_native_full_restore_preserves_seq_and_merge_allocates_local_seq(storage, tmp_path):
    first = save(storage, tmp_path, 'a.png', 'red')
    second = save(storage, tmp_path, 'b.png', 'blue')
    storage.index.reorder_resources(ROOT, [storage._resource_id(second), storage._resource_id(first)])
    package = tmp_path / 'native.zip'
    NekoriPackageService(storage).export(package)
    recipient = StorageService(tmp_path / 'restored', storage.config)
    NekoriPackageService(recipient).import_package(package)
    assert {r['display_name']: r['library_added_seq'] for r in recipient.index.resources()} == {'a.png': 1, 'b.png': 2}
    third = save(recipient, tmp_path, 'c.png', 'green')
    assert recipient.resource_of(third)['library_added_seq'] == 3
    merged = StorageService(tmp_path / 'merged', storage.config)
    existing = save(merged, tmp_path, 'local.png', 'yellow')
    before_seq = merged.resource_of(existing)['library_added_seq']
    service = NekoriPackageService(merged)
    service.import_package(package)
    records = {r['display_name']: r['library_added_seq'] for r in merged.index.resources()}
    assert records == {'local.png': before_seq, 'b.png': 2, 'a.png': 3}
    merged.index.set_order(ROOT, list(reversed(merged.index.content(ROOT))))
    original_order = merged.index.content(ROOT)
    service.import_package(package)
    assert {r['display_name']: r['library_added_seq'] for r in merged.index.resources()} == records
    assert merged.index.content(ROOT) == original_order


def test_suzu_traversal_assigns_stable_seq(storage, tmp_path):
    from services.suzu_migration import SuzuMigrationService
    source = tmp_path / 'suzu'
    (source / 'images').mkdir(parents=True)
    for name, color in [('a.png', 'red'), ('b.png', 'blue')]:
        Image.new('RGBA', (16, 16), color).save(source / 'images' / name)
    (source / 'order.json').write_text(json.dumps(['b.png', 'a.png']))
    (source / 'categories.json').write_text(json.dumps({'Memes': ['a.png', 'b.png']}))
    service = SuzuMigrationService(storage)
    service.migrate_from_data_dir(source)
    before = {r['display_name']: r['library_added_seq'] for r in storage.index.resources()}
    assert before == {'b.png': 1, 'a.png': 2}
    service.migrate_from_data_dir(source)
    assert {r['display_name']: r['library_added_seq'] for r in storage.index.resources()} == before


def test_mixed_delete_recycles_existing_and_forgets_missing_only(storage, tmp_path, monkeypatch):
    existing = save(storage, tmp_path, 'a.png', 'red')
    missing = save(storage, tmp_path, 'b.png', 'blue')
    Path(missing).unlink()
    from services import recycle_bin
    recycle = Mock(wraps=recycle_bin.recycle_file)
    monkeypatch.setattr(recycle_bin, 'recycle_file', recycle)
    result = storage.delete_images_batch([existing, missing])
    assert (result['deleted'], result['missing_cleaned'], result['failed']) == (1, 1, 0)
    recycle.assert_called_once_with(existing, storage.library_root)
    assert not Path(existing).exists()
    assert storage.index.resources() == []


@pytest.fixture
def gallery(storage, app):
    from fluent_ui.views.gallery_view import GalleryInterface
    service, api, pending, injector = sender()
    view = GalleryInterface(storage, Mock(copy_image_to_clipboard=Mock(return_value=True)), storage.config,
                            send_target_service=service)
    view.focus_timer.stop()
    view.resize(900, 700)
    view.show()
    app.processEvents()
    yield view
    view.close()
    view.deleteLater()
    app.processEvents()


def test_availability_guards_refresh_cards_and_block_descendant_removal(gallery, storage, tmp_path, app, monkeypatch):
    from fluent_ui.components import dialogs
    node = storage.create_node('Parent')
    child = storage.create_node('Child', node)
    direct = save(storage, tmp_path, 'a.png', 'red', ImportTarget(node))
    descendant = save(storage, tmp_path, 'b.png', 'blue', ImportTarget(child))
    gallery.on_images_changed()
    gallery.set_node(node)
    gallery._select_single(direct)
    app.processEvents()
    card = next(c for c in gallery._all_card_widgets if getattr(c, 'image_path', None) == direct)
    more = lambda: {a.text(): a for a in gallery._build_selection_more_menu().actions()}
    assert card.property('state') == 'normal' and more()['移出当前分类'].isEnabled()
    Path(direct).unlink()
    context = gallery._action_context([direct], revalidate=True)
    assert card.property('state') == 'missing'
    assert not ActionPolicy.enabled('thumbnail_frame', context)
    assert not ActionPolicy.enabled('show_in_explorer', context)
    assert not ActionPolicy.enabled('export', context)
    assert ActionPolicy.enabled('tag_edit', context) and ActionPolicy.enabled('copy_path', context)
    menu = gallery._build_resource_menu(card)
    actions = {a.text(): a for a in menu.actions()}
    assert not actions['在资源管理器中显示'].isEnabled()
    assert not actions['导出选中项到文件夹…'].isEnabled()
    assert actions['移除失效记录'].isEnabled()
    picker, explorer = Mock(), Mock()
    monkeypatch.setattr(dialogs, 'FramePickerDialog', picker)
    monkeypatch.setattr('subprocess.Popen', explorer)
    monkeypatch.setattr(gallery, 'show_error', Mock())
    gallery._choose_thumbnail_frame(direct)
    gallery.reveal_in_explorer(direct)
    picker.assert_not_called()
    explorer.assert_not_called()
    # A restored file is revalidated too; every visible occurrence is patched.
    Image.new('RGBA', (16, 16), 'red').save(direct)
    assert storage.availability.exists(direct, revalidate=True)
    assert card.property('state') == 'normal'
    gallery.search_keyword = '.png'
    gallery.refresh_content()
    gallery.selected_keys = {direct, descendant}
    gallery._sync_command_bar()
    assert not more()['移出当前分类'].isEnabled()
    before = storage.index.memberships()
    confirm = Mock(return_value=True)
    monkeypatch.setattr(dialogs, 'confirm', confirm)
    gallery._batch_remove_membership()
    confirm.assert_not_called()
    assert storage.index.memberships() == before


def test_thumbnail_guard_requires_real_animation(storage, tmp_path):
    still = tmp_path / 'still.gif'
    animated = tmp_path / 'animated.gif'
    Image.new('RGB', (16, 16), 'red').save(still)
    Image.new('RGB', (16, 16), 'red').save(animated, save_all=True,
        append_images=[Image.new('RGB', (16, 16), 'blue')], duration=100, loop=0)
    a = storage.save_file(str(still))[0]
    b = storage.save_file(str(animated))[0]
    assert not ActionPolicy.enabled('thumbnail_frame', ActionContext.build(storage, [a]))
    assert ActionPolicy.enabled('thumbnail_frame', ActionContext.build(storage, [b]))
    assert not ActionPolicy.enabled('thumbnail_frame', ActionContext.build(storage, [a, b]))


def test_time_projection_preserves_node_runs_manual_order_and_reorder_guard(gallery, storage, tmp_path, monkeypatch):
    parent = storage.create_node('Parent')
    child = storage.create_node('Child', parent)
    paths = [save(storage, tmp_path, f'{i}.png', color, ImportTarget(parent))
             for i, color in enumerate(('red', 'blue', 'green', 'yellow'))]
    ids = [storage._resource_id(p) for p in paths]
    storage.index.set_order(parent, [('resource', ids[1]), ('resource', ids[0]), ('node', child),
                                     ('resource', ids[3]), ('resource', ids[2])])
    gallery.on_images_changed()
    gallery.set_node(parent)
    canonical = storage.index.content(parent)
    for mode, expected in [('oldest_added', [ids[0], ids[1], child, ids[2], ids[3]]),
                           ('recent_added', [ids[1], ids[0], child, ids[3], ids[2]])]:
        gallery.set_content_sort(mode)
        assert [e['id'] for e in gallery._entries] == expected
        assert storage.index.content(parent) == canonical
        monkeypatch.setattr(gallery, 'show_error', Mock())
        assert not gallery._manual_order_available()
        assert not gallery._exact_placement_available()
        gallery.selected_keys = set(paths)
        gallery._move_selection_extreme(True)
        assert storage.index.content(parent) == canonical
    gallery.set_content_sort('manual')
    assert [e['id'] for e in gallery._entries] == [e['id'] for e in canonical]
    assert gallery._manual_order_available()


def test_global_sort_preferences_reopen(gallery, storage, tmp_path):
    from fluent_ui.views.gallery_view import GalleryInterface
    gallery.sidebar.set_display_sort('name_desc')
    gallery.tag_panel.set_sort('a_z')
    gallery.set_content_sort('oldest_added')
    config = ConfigService(tmp_path / 'app')
    other = GalleryInterface(storage, gallery.clipboard, config, send_target_service=gallery.send_target_service)
    try:
        assert (config.get('sidebar_sort'), config.get('tag_sort'), config.get('resource_sort')) == ('z_a', 'a_z', 'oldest_added')
        assert other.sidebar.tree.display_sort == 'name_desc'
        assert other.tag_panel.sort_mode.value == 'a_z'
        assert other.content_sort == 'oldest_added'
    finally:
        other.focus_timer.stop()
        other.close()
        other.deleteLater()
    defaults = ConfigService(tmp_path / 'old-config')
    assert all(defaults.get(key) == 'manual' for key in ('sidebar_sort', 'tag_sort', 'resource_sort'))


def test_own_process_shell_and_stale_or_reused_handles_never_send(app):
    service, api, pending, injector = sender()
    assert service.remember(101)
    for hwnd in range(201, 209):
        api.current = hwnd
        assert not service.capture_foreground()
        assert service.last_external_hwnd == 101
    for hwnd in (0, 301, 999):
        assert not service.remember(hwnd)
    api.windows[101] = (os.getpid() + 10, 'Chat')  # HWND reused by another process.
    completed, storage, clipboard = Mock(), Mock(), Mock()
    service.send('emoji.gif', clipboard, storage, completed)
    completed.assert_called_once_with(SendResult.COPIED_ONLY)
    injector.paste.assert_not_called()


@pytest.mark.parametrize('failure', ['no_target', 'focus_timeout', 'destroyed', 'changed_foreground', 'copy_failed'])
def test_failed_send_never_injects_and_updates_recent_only_after_copy(app, failure):
    service, api, pending, injector = sender()
    storage = Mock()
    clipboard = Mock(copy_image_to_clipboard=Mock(return_value=failure != 'copy_failed'))
    results = []
    if failure != 'no_target':
        service.remember(101)
    if failure in ('focus_timeout', 'destroyed', 'changed_foreground'):
        api.acquire = False
    service.send('emoji.gif', clipboard, storage, results.append)
    if failure == 'destroyed':
        del api.windows[101]
    if failure == 'changed_foreground':
        # Foreground changes between the two checks immediately before input.
        calls = iter([101, 102])
        api.foreground = lambda: next(calls)
    while pending:
        pending.pop(0)()
    assert results == [SendResult.COPY_FAILED if failure == 'copy_failed' else SendResult.COPIED_ONLY]
    injector.paste.assert_not_called()
    if failure == 'copy_failed':
        storage.add_recent_image.assert_not_called()
    else:
        storage.add_recent_image.assert_called_once()


@pytest.mark.parametrize('outcome', [SendResult.SENT, SendResult.COPIED_ONLY, SendResult.COPY_FAILED])
def test_main_and_quick_share_send_and_only_sent_hides(gallery, storage, tmp_path, app, outcome, monkeypatch):
    from fluent_ui.components.quick_panel import QuickPanel
    service = gallery.send_target_service
    api = service.api
    service.remember(101)
    if outcome == SendResult.COPIED_ONLY:
        api.acquire = False
        api.windows.pop(101)
    path = save(storage, tmp_path, 'send.png', 'purple')
    gallery.config.set('hide_main_after_paste', True)
    gallery.clipboard.copy_image_to_clipboard.return_value = outcome != SendResult.COPY_FAILED
    recent = Mock(wraps=storage.add_recent_image)
    monkeypatch.setattr(storage, 'add_recent_image', recent)
    hide = Mock()
    gallery.hide_after_paste_requested.connect(hide)
    monkeypatch.setattr(gallery, 'show_success', Mock())
    monkeypatch.setattr(gallery, 'show_error', Mock())
    gallery.use_resource(path)
    quick = QuickPanel(storage, gallery.clipboard, gallery.config, send_target_service=service)
    hide_quick = Mock()
    monkeypatch.setattr(quick, 'hide_panel', hide_quick)
    quick._on_card_clicked(path)
    assert quick.send_target_service is gallery.send_target_service
    assert gallery.last_send_result == quick.last_send_result == outcome
    assert hide.call_count == hide_quick.call_count == (1 if outcome == SendResult.SENT else 0)
    assert recent.call_count == (0 if outcome == SendResult.COPY_FAILED else 2)
    assert quick.feedback_host is not gallery.feedback_host
    if outcome == SendResult.COPIED_ONLY:
        assert quick.feedback_host.title_label.text() == '已复制，但未找到可发送窗口'
    elif outcome == SendResult.COPY_FAILED:
        assert quick.feedback_host.notices[-1][2]

    quick.deleteLater()
    app.processEvents()


def test_paste_injector_uses_sendinput_ctrl_v_without_desktop_input():
    import ctypes
    native = Mock()
    native.SendInput.return_value = 4
    assert PasteInjector(SimpleNamespace(native=native)).paste()
    count, inputs, size = native.SendInput.call_args.args
    assert count == 4 and size == ctypes.sizeof(INPUT)
    assert [(i.type, i.data.ki.wVk, i.data.ki.dwFlags) for i in inputs] == [(1, 0x11, 0), (1, 0x56, 0), (1, 0x56, 2), (1, 0x11, 2)]
