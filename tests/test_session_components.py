"""Lifecycle/placement/drop contracts. Physical desktop feel stays human QA."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QPoint, QMimeData
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
import pytest


@pytest.fixture
def surface(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from fluent_ui import visual
    from fluent_ui.views.gallery_view import GalleryInterface
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    config = ConfigService()
    config.set('tag_panel_horizontal_extent', 154)
    visual.theme.configure(config)
    i18n_engine.init(config)
    storage = StorageService(config=config)
    nodes = [storage.create_node(name) for name in ('Zeta', 'Alpha', 'Beta')]
    paths = []
    for index in range(100):
        image = QImage(16, 16, QImage.Format_RGB32)
        image.fill(QColor(index, 110, 70))
        path = tmp_path/f'{index}.png'
        image.save(str(path))
        paths.append(storage.save_file(str(path))[0])
    for node in nodes:
        storage.move_resources_to(paths, node, copy=True)
    gallery = GalleryInterface(storage, ClipboardService(config), config)
    gallery.resize(1060, 800)
    gallery.show()
    QTest.qWait(80)
    yield app, gallery, storage, config, nodes, paths
    gallery.focus_timer.stop()
    gallery.close()
    gallery.renderer.loader.pool.waitForDone() if hasattr(gallery.renderer.loader, 'pool') else None
    app.processEvents()


def settle(app):
    for _ in range(5):
        app.processEvents()


def test_session_visible_layout_cold_start_and_hide(surface):
    app, gallery, storage, config, nodes, paths = surface
    from fluent_ui.views.gallery_view import GalleryInterface
    from services.clipboard import ClipboardService
    from services.config import ConfigService
    expected = {}
    for index, node in enumerate(nodes):
        gallery.set_node(node)
        settle(app)
        gallery.scroll_area.verticalScrollBar().setValue(900+index*200)
        settle(app)
        expected[node] = gallery.renderer.anchor()
        assert expected[node][1] >= 0
        gallery.save_session_state()
        gallery.hide()
        settle(app)
        gallery.show()
        settle(app)
        assert gallery.renderer.anchor() == expected[node]
    gallery.save_session_state()
    # Reconstruct from the file, with a different construction placeholder.
    loaded = ConfigService()
    other = GalleryInterface(storage, ClipboardService(loaded), loaded)
    assert other._initial_anchor is not None
    other.resize(1060, 800)
    other.show()
    settle(app)
    try:
        assert other.current_node == nodes[-1]
        assert other.renderer.anchor() == expected[nodes[-1]]
        for node in nodes:
            other.set_node(node)
            settle(app)
            assert other.renderer.anchor() == expected[node]
        # Transient state is not persisted.
        assert other.search_keyword == '' and not other.active_tags
        assert other.mode == 'normal' and not other.selected_keys
    finally:
        other.focus_timer.stop()
        other.close()
        settle(app)


def test_panel_four_positions_sort_and_shared_sections(surface):
    app, gallery, storage, config, nodes, paths = surface
    from PySide6.QtWidgets import QBoxLayout
    from fluent_ui.components.section_index import SortProjection, SectionIndexModel, SectionKeyProvider
    from fluent_ui.components.tag_model import TagItem
    host, panel = gallery.tag_panel_host, gallery.tag_panel
    assert abs(panel.height()-154) <= 2  # Without requiring a manual resize.
    identity = id(panel)
    # The index and the section groups only have a shape once there is a sort
    # projection to show, so the panel gets tags in several sections first.
    for name in ('Alpha', 'Beta', '中文', '香蕉', '99'):
        panel.model.create(name)
    panel.set_sort(SortProjection.A_Z)
    panel.set_items(panel.model.project())
    for projection_mode in (SortProjection.A_Z, SortProjection.Z_A):
        panel.set_sort(projection_mode)
        panel.set_items(panel.model.project())
        for position in ('top', 'bottom', 'left', 'right', 'bottom'):
            host.set_placement(position)
            settle(app)
            assert id(host.panel) == identity
            assert panel.height() >= 84 and panel.width() >= 110
            extent = panel.height() if host.horizontal else panel.width()
            assert abs(extent-(154 if host.horizontal else 220)) <= 2
            assert panel.index_view.orientation == (Qt.Horizontal if host.horizontal else Qt.Vertical)
            # The axis is a placement property, not a size property: below the
            # tags when the panel is horizontal, beside them when it is
            # vertical. The flag alone is what let a stale vertical index pass a
            # horizontal placement, so the rendered relationship is asserted.
            assert panel.index_layout.direction() == (
                (QBoxLayout.BottomToTop if position == 'top' else QBoxLayout.TopToBottom) if host.horizontal else (QBoxLayout.RightToLeft if position == 'left' else QBoxLayout.LeftToRight))
            assert (panel.index_view.width() > panel.index_view.height()) == host.horizontal
            index_at = panel.index_view.mapTo(panel, QPoint(0, 0))
            scroll_at = panel.scroll.mapTo(panel, QPoint(0, 0))
            if position == 'top':
                assert index_at.y()+panel.index_view.height() <= scroll_at.y()
            elif position == 'bottom':
                assert index_at.y() >= scroll_at.y()+panel.scroll.height()-2
            elif position == 'left':
                assert index_at.x()+panel.index_view.width() <= scroll_at.x()
            else:
                assert index_at.x() >= scroll_at.x()+panel.scroll.width()-2

            # Section *content* axis, measured on the real section geometry --
            # not on a direction flag. The index strip and the section groups
            # are two presentation concerns, and a horizontal placement that
            # only turned the index left the groups stacked vertically.
            headers = [rect for _key, rect in panel.flow._section_headers]
            assert len(headers) >= 3, (position, headers)
            if host.horizontal:
                assert headers[0].y() == headers[1].y() == headers[2].y(), (position, headers)
                assert headers[2].x() > headers[1].x() > headers[0].x(), (position, headers)
            else:
                assert headers[0].x() == headers[1].x() == headers[2].x(), (position, headers)
                assert headers[2].y() > headers[1].y() > headers[0].y(), (position, headers)
            # Items of one section continue along the other axis inside it: a
            # column runs downward under a horizontal placement.
            first_section = panel.flow.projection.itemsBySection[
                panel.flow.projection.sections[0]]
            if len(first_section) > 1:
                rects = panel.flow._rects[:len(first_section)]
                if host.horizontal:
                    assert rects[0].x() == rects[1].x() and rects[1].y() > rects[0].y(), rects
                else:
                    assert rects[0].y() == rects[1].y() and rects[1].x() > rects[0].x(), rects
    # Neither a window resize nor a switch away from a vertical placement may
    # leave the axis behind.
    host.set_placement('right')
    gallery.resize(900, 700)
    settle(app)
    assert panel.index_view.orientation == Qt.Vertical
    host.set_placement('top')
    gallery.resize(1040, 820)
    settle(app)
    assert panel.index_view.orientation == Qt.Horizontal
    assert panel.index_layout.direction() == QBoxLayout.BottomToTop
    assert panel.index_view.width() > panel.index_view.height()
    host.set_placement('bottom')
    names = ['中文', 'Alpha', '香蕉', '99', '🙂']
    for name in names:
        panel.model.create(name)
    items = [TagItem(name) for name in names]
    panel.set_items(items)
    manual = panel.model.order()
    panel.set_sort(SortProjection.A_Z)
    assert panel.model.order() == manual
    assert SectionKeyProvider.section('中文') == 'Z'
    assert SectionKeyProvider.section('香蕉') == 'X'
    assert SectionKeyProvider.section('99') == '#'
    assert SectionKeyProvider.section('🙂') == '#'
    panel.index_view.resize(350, 24)
    calls = []
    panel.index_view.section_requested.connect(calls.append)
    for x in range(0, 350, 10):
        panel.index_view._choose(QPoint(x, 5))
    assert len(set(calls)) > 1
    panel.set_sort(SortProjection.MANUAL)
    assert [item.name for item in panel.flow._items] == names
    # Manual order has no section group to arrange, so it keeps the plain
    # wrapping chip flow that was already accepted, in either placement.
    assert not panel.flow._section_headers
    if len(panel.flow._rects) > 1:
        assert panel.flow._rects[0].y() == panel.flow._rects[1].y()
    host.set_placement('left')
    settle(app)
    assert panel.flow._rects[0].y() == panel.flow._rects[1].y()
    host.set_placement('bottom')


def test_tag_drop_subtree_and_sidebar_drag_cache(surface, monkeypatch):
    app, gallery, storage, config, nodes, paths = surface
    from fluent_ui.components import dialogs
    from fluent_ui.components.drop_contract import TAG_MIME, NODE_MIME, APPLY_TAG, APPLY_TAG_TO_SUBTREE
    import json
    child_z = storage.create_node('Z-child', nodes[0])
    child_a = storage.create_node('A-child', nodes[0])
    storage.move_resources_to(paths[:8], child_z, copy=True)
    gallery.sidebar.refresh_list()
    gallery.tag_model.create('DropTag')
    tags = QMimeData()
    tags.setData(TAG_MIME, b'["DropTag"]')
    tree = gallery.sidebar.tree
    target = tree.resolve_category_target(nodes[0], .1, tags)
    assert target.effect == APPLY_TAG_TO_SUBTREE
    # Dragging must not query the subtree. Only a committed drop counts it.
    calls = []
    original = storage.resources_in_subtree
    monkeypatch.setattr(storage, 'resources_in_subtree', lambda node: (calls.append(node), original(node))[1])
    for ratio in (.1, .5, .9):
        tree.resolve_category_target(nodes[0], ratio, tags)
    assert calls == []
    confirmations = []
    monkeypatch.setattr(dialogs, 'confirm', lambda *a, **kw: (confirmations.append(a[2]), True)[1])
    gallery.apply_tags_to_category(nodes[0], ['DropTag'])
    assert len(calls) == 1 and '100' in confirmations[0]
    assert all('DropTag' in storage.resource_of(path)['tags'] for path in paths)
    gallery.set_node(nodes[1]); settle(app)
    entry = gallery._entries[0]
    gallery.selected_keys = {paths[0], paths[1]}
    from fluent_ui.components.drop_contract import tag_drop_target
    gallery.tag_model.create('SelectionTag')
    gallery._commit_tag_drop(tag_drop_target(entry['id']), ['SelectionTag'])
    assert all('SelectionTag' in storage.resource_of(path)['tags'] for path in paths[:2])
    # An entire drag resolves parents/stream once, never SQLite per move. The
    # session caches node parents and the canonical stream per container, so
    # the stream query -- not `entries_of` -- is the one that must happen once.
    node_mime = QMimeData()
    node_mime.setData(NODE_MIME, json.dumps([nodes[2]]).encode())
    stream_calls = []
    original_content = storage.index.content
    monkeypatch.setattr(storage.index, 'content',
                        lambda node: (stream_calls.append(node), original_content(node))[1])
    monkeypatch.setattr(storage, 'node', lambda *_: (_ for _ in ()).throw(AssertionError('node query in drag hot path')))
    for _ in range(40):
        assert tree.resolve_category_target(nodes[0], .1, node_mime).valid
        assert tree.resolve_category_target(nodes[0], .5, node_mime).valid
    assert len(stream_calls) == 1, stream_calls
    monkeypatch.undo()
    tree.set_display_sort('name_asc')
    root_parent = tree._find_item(nodes[0])
    assert [root_parent.child(i).data(0, Qt.UserRole) for i in range(root_parent.childCount())] == [child_z, child_a]
    gallery.sidebar.toggle_presentation()
    settle(app)
    assert config.get('sidebar_mode') == 'categorized_icons'
    icons = gallery.sidebar.icons
    assert {item[0] for item in icons.canvas.items} >= set(nodes+[child_z, child_a])
    position = next(rect.center() for item, rect in zip(icons.canvas.items, icons.canvas.rects) if item[0] == nodes[0])
    assert icons.canvas.resolve(position, tags)[0].effect == APPLY_TAG_TO_SUBTREE


def test_window_geometry_persistence_contract():
    """The two ways the user's saved window position was destroyed.

    A headless run wrote its synthetic screen rectangle as if it were the
    user's position, and Qt's opaque saveGeometry() blob was stored beside the
    plain rectangle and won whenever the two disagreed.
    """
    import inspect
    import sys
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QWidget
    from services import dev_placement
    from fluent_ui.main_window import MainWindow

    minimum = QSize(780, 480)
    assert MainWindow._usable_geometry([0, 0, 960, 700], minimum)
    assert not MainWindow._usable_geometry(None, minimum)
    assert not MainWindow._usable_geometry([0, 0, 0, 0], minimum)
    assert not MainWindow._usable_geometry([0, 0, 779, 700], minimum)
    assert not MainWindow._usable_geometry([0, 0, '960', 700], minimum)

    # A window that is not on a real screen has no position worth remembering.
    stray = QWidget()
    stray.setGeometry(-40000, -40000, 400, 300)
    assert not dev_placement.on_real_screen(stray)
    assert not dev_placement.geometry_writable(stray)
    stray.deleteLater()

    # A development placement and a smoke run must never write it either.
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(dev_placement, 'active', lambda: True)
        assert not dev_placement.geometry_writable()
        monkey.undo()
        monkey.setattr(dev_placement, 'headless', lambda: True)
        assert not dev_placement.geometry_writable()
        monkey.undo()
        monkey.setattr(sys, 'argv', [*sys.argv, '--smoke-test'])
        assert not dev_placement.geometry_writable()
    finally:
        monkey.undo()

    # One fact, one place: the opaque Qt blob is not a geometry source any more.
    source = inspect.getsource(MainWindow)
    assert 'self.restoreGeometry' not in source
    assert 'self.saveGeometry' not in source
