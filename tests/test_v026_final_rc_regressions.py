"""Final RC regressions against live Qt objects and an isolated catalogue."""
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QFileDialog

from test_v026_library_switch import case, save_to


def wait_for(app, predicate):
    end = monotonic() + 8
    while not predicate() and monotonic() < end:
        app.processEvents()
        sleep(.01)
    assert predicate()


def image(path, animated=False):
    first = Image.new('RGB', (32, 32), 'red')
    if animated:
        first.save(path, save_all=True, append_images=[Image.new('RGB', (32, 32), 'blue')], duration=100)
    else:
        first.save(path)


def test_recent_changes_preserve_other_projections_and_position(case, monkeypatch):
    app, window, storage, _, config = case
    gallery, quick = window.gallery_interface, window.quick_panel
    paths = []
    for number in range(4):
        path = Path(storage.library_root) / f'recent-{number}.png'
        image(path)
        identity = storage.index.register(path)
        paths.append(storage.index.absolute_path(storage.index.resource_by_id(identity)))
    gallery.refresh_content(invalidate=True)

    def send(path, _clipboard, owner, _callback, limit):
        owner.add_recent_image(path, limit)
    monkeypatch.setattr(window.send_target_service, 'send', send)
    storage.add_recent_image(paths[0])
    gallery.toggle_recent_view(True)
    recent = gallery._view_signature()
    gallery.toggle_recent_view(False)
    normal = gallery._view_signature()
    position = gallery.entry_model.snapshots[recent][1]
    gallery._send_to_clipboard(paths[1])
    assert gallery.entry_model.snapshots[recent] == (None, position)
    assert gallery._view_signature() == normal
    gallery.toggle_recent_view(True)
    assert [r['path'] for r in gallery._entries] == paths[1::-1]

    gallery.toggle_recent_view(False)
    quick._on_card_clicked(paths[2])
    gallery.toggle_recent_view(True)
    assert [r['path'] for r in gallery._entries] == paths[2::-1]
    normal_contents = gallery.entry_model.snapshots[normal]
    brief_position = gallery._position()
    storage.add_recent_image(paths[3])
    assert [r['path'] for r in gallery._entries] == paths[::-1]
    assert gallery.entry_model.snapshots[normal] is normal_contents
    assert gallery._position()[1] == brief_position[1]

    gallery.toggle_recent_view(False)
    config.set('recent_limit', 2)
    window.on_settings_changed('recent_limit')
    gallery.toggle_recent_view(True)
    assert [r['path'] for r in gallery._entries] == paths[3:1:-1]


@pytest.mark.parametrize('was_animated', [False, True])
def test_rebind_resets_animated_until_new_file_is_probed(case, monkeypatch, was_animated):
    app, window, storage, _, _ = case
    gallery, quick = window.gallery_interface, window.quick_panel
    gallery.show()
    window.show()
    gallery.renderer.loader.animation_backfill.scan_more = False
    gallery.renderer.loader.animation_backfill.timer.stop()
    parent = next(n['id'] for n in storage.index.nodes() if n['name'] == 'OLD')
    root = Path(storage.library_root)
    old = root / ('old.gif' if was_animated else 'old.png')
    new = root / ('new.png' if was_animated else 'new.gif')
    image(old, was_animated)
    image(new, not was_animated)
    identity = storage.index.register(old, display_name='rebind-sample')
    storage.index.add_membership(identity, parent)
    metadata = {'thumb_crop':[.1,.1,.8,.8], 'thumb_frame':1, 'custom':'keep'}
    storage.index.set_resource_metadata(identity, metadata)
    storage.index.set_search_fields(identity, tags='sample')
    assert storage.index.set_animation_attribute(storage.index.resource_by_id(identity), was_animated)
    prior = storage.index.content(parent)
    quick.search_box.setText('rebind-sample')
    quick._perform_search()
    assert quick._all_card_widgets[0]._animated is was_animated
    old.unlink()
    storage.index.refresh_status()
    gallery.refresh_content(invalidate=True)
    quick.show()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: (str(new), ''))
    gallery.rebind_resource(str(old))

    assert storage.index.resource_metadata(identity) == metadata
    assert storage.index.content(parent) == prior
    assert storage.index.resource_by_id(identity)['tags'] == 'sample'
    current_path = storage.index.absolute_path(storage.index.resource_by_id(identity))
    assert Path(current_path) == new
    def cards():
        return [card for card in gallery.renderer.active.values() if getattr(card, 'image_path', None) == current_path]

    # Assert the pending projection before giving the scheduled worker a turn.
    assert not any(card._animated for card in cards())
    assert quick._all_card_widgets[0].image_path == current_path and not quick._all_card_widgets[0]._animated

    def updated():
        record = storage.index.resource_by_id(identity)
        return (storage.index.animation_attribute(record) is (not was_animated)
                and cards() and all(card._animated is (not was_animated) for card in cards())
                and quick._all_card_widgets[0]._animated is (not was_animated))
    wait_for(app, updated)


def test_retired_settings_evicts_update_dialog_after_worker_drains(case, monkeypatch):
    from fluent_ui.components.update_center import update_center
    app, window, _, new, _ = case
    center = update_center()
    service = SimpleNamespace(root=Path(new.library_root), cancel=Event(), channel_available=False)
    (service.root/'version.json').write_text('{"version": "0.2.6"}')
    monkeypatch.setattr(center, 'service', lambda: service)
    settings = window.settings_window
    settings.show()
    dialog = center.open(settings)
    assert center.dialogs[settings] is dialog and dialog.isVisible()
    started = Event()
    def task(_progress):
        started.set()
        assert service.cancel.wait(8)
    dialog._run(task, lambda _: None)
    try:
        wait_for(app, started.is_set)
        assert window.library_switch_block_reason()
        assert center.cancel_running_workers()
        wait_for(app, lambda: dialog.worker is None)
    finally:
        service.cancel.set()
    dialog.close()
    settings.close()
    assert save_to(window, new)
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    assert settings not in center.dialogs
    active = center.open(window.settings_window)
    assert center.dialogs[window.settings_window] is active and active.isVisible()
    active.close()
