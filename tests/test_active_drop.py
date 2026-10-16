"""Real receiving widgets and one-commit block moves, using disposable DevData."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, QPointF, Qt, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QColor, QImage
from PySide6.QtWidgets import QApplication


def _drop(widget, point, mime_type, values):
    mime = QMimeData()
    mime.setData(mime_type, json.dumps(values).encode())
    actions = Qt.CopyAction | Qt.MoveAction
    enter = QDragEnterEvent(point, actions, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, enter)
    assert enter.isAccepted(), (widget.objectName(), mime_type)
    move = QDragMoveEvent(point, actions, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, move)
    assert move.isAccepted(), (widget.objectName(), mime_type)
    drop = QDropEvent(QPointF(point), actions, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, drop)
    assert drop.isAccepted(), (widget.objectName(), mime_type)


def test_bidirectional_tag_drop_reaches_real_surfaces(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from fluent_ui import visual
    from fluent_ui.components.drop_contract import RESOURCE_MIME, TAG_MIME
    from fluent_ui.views.gallery_view import GalleryInterface

    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    config = ConfigService()
    visual.theme.configure(config)
    i18n_engine.init(config)
    storage = StorageService(config=config)
    paths = []
    for index in range(3):
        image = QImage(16, 16, QImage.Format_RGB32)
        image.fill(QColor(index*25, 100, 140))
        source = tmp_path/f'{index}.png'
        image.save(str(source))
        paths.append(storage.save_file(str(source))[0])
    gallery = GalleryInterface(storage, ClipboardService(config), config)
    gallery.resize(1000, 750)
    gallery.show()
    app.processEvents()
    try:
        for name in ('First', 'Second', 'Third', 'Fourth'):
            assert gallery.tag_model.create(name) is None
        gallery._rebuild_tag_panel()
        app.processEvents()
        flow = gallery.tag_panel.flow
        chip = flow._rects[0].center()

        # A resource and a selected resource block land on the actual chip.
        _drop(flow, chip, RESOURCE_MIME, [paths[0]])
        _drop(flow, chip, RESOURCE_MIME, paths[1:])
        assert all('First' in storage.get_image_keywords(path) for path in paths)

        # A tag and a selected tag block land on a virtual Gallery card via
        # the grid and viewport, the actual QWidget drop receivers.
        first_entry_path = gallery._entries[0]['path']
        card = gallery.renderer.index.rects[0].center()
        _drop(gallery.grid_container, card, TAG_MIME, ['Second'])
        gallery.selected_keys = set(paths[1:])
        viewport_point = gallery.grid_container.mapTo(gallery.scroll_area.viewport(),
                                                      gallery.renderer.index.rects[1].center())
        _drop(gallery.scroll_area.viewport(), viewport_point, TAG_MIME, ['Third', 'Fourth'])
        assert 'Second' in storage.get_image_keywords(first_entry_path)
        assert all({'Third', 'Fourth'} <= set(storage.get_image_keywords(path).split())
                   for path in paths[1:])
    finally:
        gallery.focus_timer.stop()
        gallery.close()
        app.processEvents()


def test_category_block_commit_preserves_root_and_child_order(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.library_index import ROOT
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    storage = StorageService(config=ConfigService())
    a, b, c = [storage.create_node(name) for name in ('A', 'B', 'C')]
    storage.move_nodes([c, a], ROOT, 0)
    assert [e['id'] for e in storage.index.content(ROOT) if e['kind'] == 'node'] == [c, a, b]
    x, y = [storage.create_node(name, b) for name in ('X', 'Y')]
    storage.move_nodes([y], b, 0)
    assert [node['id'] for node in storage.child_nodes(b)] == [y, x]
    storage.move_nodes([c, a], b, 1)
    assert [node['id'] for node in storage.child_nodes(b)] == [y, c, a, x]


def test_tree_icon_tag_reorder_and_compact_presentation(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from services.library_index import ROOT
    from fluent_ui import visual
    from fluent_ui.components.drop_contract import NODE_MIME, TAG_MIME
    from fluent_ui.components.section_index import SortProjection
    from fluent_ui.views.gallery_view import GalleryInterface

    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    config = ConfigService()
    visual.theme.configure(config)
    i18n_engine.init(config)
    storage = StorageService(config=config)
    a, b, c = [storage.create_node(name) for name in ('Alpha', 'Beta', 'Gamma')]
    x, y = [storage.create_node(name, a) for name in ('ChildX', 'ChildY')]
    image = QImage(16, 16, QImage.Format_RGB32)
    image.fill(QColor(60, 80, 110))
    source = tmp_path/'preview.png'
    image.save(str(source))
    path = storage.save_file(str(source))[0]
    gallery = GalleryInterface(storage, ClipboardService(config), config)
    gallery.resize(1000, 750)
    gallery.show()
    app.processEvents()
    try:
        tree = gallery.sidebar.tree
        target = tree._find_item(b)
        rect = tree.visualItemRect(target)
        mime = QMimeData()
        mime.setData(NODE_MIME, json.dumps([c]).encode())
        original_content = storage.index.content
        calls = []
        def content_once(parent):
            calls.append(parent)
            return original_content(parent)
        storage.index.content = content_once
        tree._drag_session = None
        for _ in range(30):
            assert tree._resolve_target(QPoint(rect.left()+15, rect.top()+2), mime)[0].valid
        assert calls == [ROOT]  # no SQLite query on each mouseMove
        storage.index.content = original_content
        original_refresh = tree.refresh
        rebuilt = []
        def track_refresh(*args, **kwargs):
            rebuilt.append(True)
            return original_refresh(*args, **kwargs)
        tree.refresh = track_refresh
        _drop(tree.viewport(), QPoint(rect.left()+15, rect.top()+2), NODE_MIME, [c])
        assert not rebuilt  # drop patches the existing tree instead
        tree.refresh = original_refresh
        assert [node['id'] for node in storage.child_nodes(ROOT)] == [a, c, b]

        tree._find_item(a).setExpanded(True)
        app.processEvents()
        rect = tree.visualItemRect(tree._find_item(x))
        _drop(tree.viewport(), QPoint(rect.left()+15, rect.top()+2), NODE_MIME, [y])
        assert [node['id'] for node in storage.child_nodes(a)] == [y, x]

        config.set('sidebar_mode', 'categorized_icons')
        gallery.sidebar.apply_presentation()
        app.processEvents()
        canvas = gallery.sidebar.icons.canvas
        target_index = next(i for i, item in enumerate(canvas.items) if item[0] == c)
        rect = canvas.rects[target_index]
        _drop(canvas, QPoint(rect.left()+2, rect.center().y()), NODE_MIME, [b])
        assert [node['id'] for node in storage.child_nodes(ROOT)] == [a, b, c]
        assert len(canvas._label_lines('A very long category name that must be readable', 90)) == 2
        assert canvas._label_lines('A very long category name that must be readable', 90)[-1].endswith('…')

        gallery.sidebar.set_display_sort('name_asc')
        assert gallery.sidebar.index_view.isVisible()
        assert gallery.sidebar.index_view.width() == visual.SECTION_INDEX_COMPACT_EXTENT
        assert [node['id'] for node in storage.child_nodes(a)] == [y, x]

        for name in ('One', 'Two', 'Three'):
            assert gallery.tag_model.create(name) is None
        gallery._rebuild_tag_panel()
        flow = gallery.tag_panel.flow
        _drop(flow, flow._rects[0].topLeft()+QPoint(3, 3), TAG_MIME, ['Three', 'Two'])
        assert gallery.tag_model.order()[:3] == ['Two', 'Three', 'One']
        gallery.tag_panel.set_sort(SortProjection.A_Z)
        assert gallery.tag_panel.index_view.width() < 150
        assert gallery.tag_panel.flow._section_headers

        preview = gallery.preview_popup
        preview.apply_presentation(gallery.content_pane)
        from PySide6.QtCore import QRect
        preview.show_preview(path, QPoint(100, 100), 150, 'Alpha', 'One',
                             info={'name': 'preview.png', 'path': path},
                             container_rect=QRect(0, 0, 450, 450))
        app.processEvents()
        assert preview.image_label.geometry().bottom() < preview.metadata_footer.geometry().top()
        assert visual.surface_style('popover') in preview.styleSheet()
    finally:
        gallery.focus_timer.stop()
        gallery.close()
        app.processEvents()
