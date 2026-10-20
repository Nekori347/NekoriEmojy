import os
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QMimeData, QUrl
from PIL import Image

from fluent_ui.views.gallery_view import GalleryInterface, ImportThread
from test_storage_single_frame_gif import _make_storage
from test_phase2_interaction import surface


def make_view(current_node="__library__"):
    view = SimpleNamespace(
        auto_scroll_timer=Mock(), import_thread=None,
        current_node=current_node, current_category="全部资源",
        storage=Mock(images_dir="unused"), sidebar=Mock(),
        show_error=Mock(), show_success=Mock(), refresh_content=Mock(),
        import_paths_to=Mock(), _entries=[], _all_card_widgets=[],
        _display_mode="mixed", download_threads=[],
        _start_background_import=Mock(),
    )
    view._drop_index = lambda pos: 0
    view._import_at = lambda sources, index: GalleryInterface._import_at(view, sources, index)
    view._import_dropped_folders = lambda folders, files: GalleryInterface._import_dropped_folders(
        view, folders, files)
    return view


def drop_event(mime):
    event = Mock()
    event.mimeData.return_value = mime
    event.position.return_value = Mock(toPoint=Mock(return_value=Mock()))
    return event


def test_drop_multiple_folders_and_file_as_one_batch(surface, tmp_path, monkeypatch):
    folders = [tmp_path / 'First', tmp_path / 'Second']
    for folder in folders:
        folder.mkdir()
    loose = tmp_path / 'loose.png'
    loose.touch()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in [*folders, loose]])
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
    from PySide6.QtWidgets import QApplication
    from services.library_index import ROOT
    view=surface.g
    view.set_node(ROOT)
    surface.app.processEvents()
    monkeypatch.setattr(view,'import_paths_to',Mock())
    viewport=view.scroll_area.viewport()
    point=QPoint(viewport.width()//2,viewport.height()-5)
    enter=QDragEnterEvent(point,Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(viewport,enter)
    assert enter.isAccepted()
    event=QDropEvent(QPointF(point),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(viewport,event)
    assert event.isAccepted()
    view.import_paths_to.assert_called_once()
    args, kwargs = view.import_paths_to.call_args
    assert [os.path.normpath(p) for p in args[0]] == [*map(str, folders), str(loose)]
    assert args[1] == '__library__'


def test_busy_import_does_not_create_categories(tmp_path):
    view = make_view()
    view.import_thread = Mock()
    view.import_thread.isRunning.return_value = True
    view._import_dropped_folders([str(tmp_path)], [])
    view.storage.add_category.assert_not_called()
    view._start_background_import.assert_not_called()
    view.show_error.assert_called_once()


def test_import_thread_routes_duplicate_to_each_target(tmp_path):
    storage = _make_storage(tmp_path)
    first = storage.create_node('First')
    second = storage.create_node('Second')
    sources = [tmp_path / 'a.png', tmp_path / 'b.png']
    for source in sources:
        Image.new('RGBA', (16, 16), 'red').save(source)

    worker = ImportThread([str(sources[0])], storage, first)
    finished = Mock()
    worker.finished.connect(finished)
    worker.run()
    finished.assert_called_once_with(1, 0, 0)

    # The second file is pixel-identical, so it merges instead of duplicating,
    # while still receiving its own category relation.
    worker = ImportThread([str(sources[1])], storage, second)
    finished = Mock()
    worker.finished.connect(finished)
    worker.run()
    finished.assert_called_once_with(0, 1, 0)

    assert len(storage.get_all_images()) == 1
    assert storage.get_images_by_category(
        storage.node(first)['name']) == storage.get_images_by_category(storage.node(second)['name'])
