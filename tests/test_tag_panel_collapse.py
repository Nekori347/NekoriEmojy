"""Tag panel collapse/expand and its unified three-state sort.

Collapsing is presentation and nothing else: the foreground extent changes,
while gallery and outer window geometry stay fixed. Tag data, sort, search and selection survive it.
"""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QMimeData, QPoint, QRect, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
import pytest
from fluent_ui import visual


def settle(app, rounds=6):
    for _ in range(rounds):
        app.processEvents()


@pytest.fixture
def scene(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.i18n import i18n_engine
    from fluent_ui import visual
    from fluent_ui.components.tag_model import TagModel
    from fluent_ui.components.tag_panel import TagPanel
    from fluent_ui.components.panel_host import TagPanelHost
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    config = ConfigService()
    # Distinct values per axis, so a mixed-up axis cannot pass by coincidence.
    config.set('tag_panel_horizontal_extent', 154)
    config.set('tag_panel_vertical_extent', 240)
    visual.theme.configure(config)
    i18n_engine.init(config)
    model = TagModel(StorageService(config=config))
    for name in ('Alpha', 'Beta', '中文', '香蕉', '99', '🙂'):
        model.create(name)
    panel = TagPanel(model, config)
    content = QWidget()
    host = TagPanelHost(content, panel, config)
    window = QWidget()
    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(host)
    window.resize(900, 700)
    window.show()
    panel.set_items(model.project())
    settle(app)
    yield app, window, host, panel, content, config, model
    panel.flow.scroller.stop()
    window.close()
    settle(app)


def extent_of(host, panel):
    return panel.height() if host.horizontal else panel.width()


def content_extent(host):
    """The content pane's extent, whichever end of the splitter it sits on."""
    return host.content.height() if host.horizontal else host.content.width()


def test_collapse_changes_only_overlay_extent_and_restores_it(scene):
    app, window, host, panel, content, config, model = scene
    assert host.expanded and host.horizontal
    outer = window.geometry()
    content_before = content_extent(host)
    expanded = extent_of(host, panel)
    assert expanded == 154

    host.set_expanded(False)
    settle(app)
    assert not host.expanded and panel.collapsed
    assert not panel.index_body.isVisible()
    assert extent_of(host, panel) == panel.collapsed_extent()
    assert content_extent(host) == content_before
    # The user's extent is remembered, not replaced by the collapsed one.
    assert config.get('tag_panel_horizontal_extent') == 154
    assert config.get('tag_panel_expanded') is False
    assert window.geometry() == outer

    panel.chrome.click()
    settle(app)
    assert host.expanded and not panel.collapsed and panel.index_body.isVisible()
    assert extent_of(host, panel) == 154
    assert content_extent(host) == content_before
    assert window.geometry() == outer


def test_bottom_expansion_does_not_jump_to_target_before_animation(scene, monkeypatch):
    from PySide6.QtTest import QTest

    app, window, host, panel, content, config, model = scene
    host.set_placement('bottom')
    host.set_expanded(False)
    settle(app)
    start = extent_of(host, panel)
    observed = []
    set_sizes = host.splitter.setSizes

    def trace(sizes):
        set_sizes(sizes)
        observed.append(extent_of(host, panel))

    monkeypatch.setattr(host.splitter, 'setSizes', trace)
    monkeypatch.setattr(QApplication, 'platformName', staticmethod(lambda: 'windows'))
    host.set_expanded(True)
    QTest.qWait(visual.MOTION.expand + 70)
    assert observed and observed[0] <= start + 1
    assert observed == sorted(observed)
    assert extent_of(host, panel) == config.get('tag_panel_horizontal_extent')


@pytest.mark.parametrize('placement,horizontal', [
    ('top', True), ('bottom', True), ('left', False), ('right', False)])
def test_each_placement_collapses_on_its_own_axis(scene, placement, horizontal):
    app, window, host, panel, content, config, model = scene
    host.set_placement(placement)
    settle(app)
    assert host.horizontal == horizontal
    assert extent_of(host, panel) == (154 if horizontal else 240)
    expanded, content_before = extent_of(host, panel), content_extent(host)

    host.set_expanded(False)
    settle(app)
    assert extent_of(host, panel) == panel.collapsed_extent()
    assert content_extent(host) == content_before
    # The other axis keeps its own value untouched.
    assert config.get('tag_panel_horizontal_extent') == 154
    assert config.get('tag_panel_vertical_extent') == 240

    host.set_expanded(True)
    settle(app)
    assert extent_of(host, panel) == (154 if horizontal else 240)


@pytest.mark.parametrize('placement', ['top', 'bottom', 'left', 'right'])
def test_header_chevron_and_whole_collapsed_rail_action(scene, placement):
    from PySide6.QtTest import QTest
    app, window, host, panel, content, config, model = scene
    host.set_placement(placement)
    settle(app)
    handle = host.splitter.handle(1)
    points = panel.btn_collapse.chevron_points()
    axis = (lambda p: p.y()) if host.horizontal else (lambda p: p.x())
    assert (axis(points[1]) < axis(points[0])) == (placement in ('top', 'left'))
    QTest.mouseClick(panel.btn_collapse,Qt.LeftButton)
    settle(app)
    assert not host.expanded and panel.chrome.isVisible()
    assert not panel.header.isVisible() and not panel.index_body.isVisible()
    assert panel.chrome.geometry() == panel.rect()
    assert panel.chrome.toolTip() == panel.chrome.accessibleName() == '展开标签'
    # Far end of the rail, nowhere near the painted icon.
    QTest.mouseClick(panel.chrome, Qt.LeftButton, pos=panel.chrome.rect().bottomRight()-QPoint(1, 1))
    settle(app)
    assert host.expanded
    assert panel.btn_collapse.parentWidget() is panel.header


def test_collapsed_thickness_uses_theme_chrome_metrics_not_expanded_header(scene, monkeypatch):
    """The strip must not inherit thickness from its own header content."""
    from PySide6.QtCore import QSize
    from fluent_ui import visual
    app, window, host, panel, content, config, model = scene
    token = visual.TAG_COLLAPSED_METRICS.extent
    assert panel.height() == 154 > token

    # A header that would be enormous if it were measured changes nothing.
    monkeypatch.setattr(panel.header, 'sizeHint', lambda: QSize(900, 900))
    host.set_expanded(False)
    settle(app)
    assert panel.collapsed_extent() == token
    assert panel.height() == token
    assert host.splitter.sizes()[host.splitter.indexOf(panel)] == token
    assert panel.maximumHeight() == token        # nothing downstream can thicken it

    # Neither can a remembered extent, or a smaller window.
    config.set('tag_panel_horizontal_extent', 400)
    host.apply_extent()
    settle(app)
    assert panel.height() == token
    window.resize(900, 360)
    settle(app)
    assert panel.height() == token
    window.resize(900, 700)
    settle(app)
    assert panel.height() == token

    host.set_expanded(True)
    settle(app)
    assert panel.height() == 400                 # the remembered extent comes back
    assert panel.maximumHeight() > token


@pytest.mark.parametrize('placement', ['top', 'bottom', 'left', 'right'])
def test_compact_chrome_fits_and_index_stays_on_outer_edge(scene, placement):
    from fluent_ui import visual
    from fluent_ui.components.section_index import SortProjection
    app, window, host, panel, content, config, model = scene
    window.setStyleSheet(visual.window_style())
    host.set_placement(placement)
    panel.set_sort(SortProjection.A_Z)
    settle(app)
    margins=panel.header_row.contentsMargins()
    assert panel.header.height() <= 30
    index = QRect(panel.axis_strip.mapTo(panel,QPoint()),panel.axis_strip.size())
    body = QRect(panel.scroll.mapTo(panel,QPoint()),panel.scroll.size())
    if placement == 'top':
        assert index.bottom() < body.top()
    elif placement == 'bottom':
        assert index.top() > body.bottom()
    elif placement == 'left':
        assert index.right() < body.left()
    else:
        assert index.left() > body.right()
    assert (panel.index_view.height() if host.horizontal else panel.index_view.width()) == visual.SECTION_INDEX_COMPACT_EXTENT
    host.set_expanded(False)
    settle(app)
    assert panel.chrome.geometry() == panel.rect()
    assert not panel.title_label.isVisible() and not panel.count_label.isVisible()
    assert not panel.btn_sort.isVisible() and not panel.btn_new.isVisible()
    assert not host.splitter.handle(1).isEnabled()
    assert extent_of(host, panel) == panel.collapsed_extent()
    host.set_expanded(True)
    settle(app)
    assert panel.title_label.isVisible() and panel.btn_sort.isVisible() and panel.btn_new.isVisible()


def test_extents_are_remembered_per_axis_across_placement_switches(scene):
    app, window, host, panel, content, config, model = scene
    host.set_placement('bottom')
    settle(app)
    assert panel.height() == 154
    host.set_placement('left')
    settle(app)
    assert panel.width() == 240
    host.set_expanded(False)
    settle(app)
    host.set_placement('bottom')
    settle(app)
    assert not host.expanded and panel.height() == panel.collapsed_extent()
    host.set_expanded(True)
    settle(app)
    assert panel.height() == 154      # horizontal extent again, not the vertical one
    host.set_placement('left')
    settle(app)
    assert panel.width() == 240


def test_a_small_window_clamps_without_overwriting_the_remembered_extent(scene):
    app, window, host, panel, content, config, model = scene
    assert panel.height() == 154
    config.set('tag_panel_horizontal_extent', 300)
    window.resize(900, 720)
    settle(app)
    assert panel.height() == 300

    window.resize(900, 420)
    settle(app)
    clamped = panel.height()
    assert clamped < 300
    assert content_extent(host) >= 220          # the content keeps a usable extent
    assert config.get('tag_panel_horizontal_extent') == 300

    window.resize(900, 720)
    settle(app)
    assert panel.height() == 300


@pytest.mark.parametrize('placement', ['left', 'right'])
def test_narrow_window_clamps_width_then_expand_restores_requested_width(scene, placement):
    app, window, host, panel, content, config, model = scene
    config.set('tag_panel_vertical_extent', 400)
    host.set_placement(placement)
    settle(app)
    assert panel.width() == 400
    window.resize(500, 700)
    settle(app)
    assert panel.width() < 400
    assert config.get('tag_panel_vertical_extent') == 400
    host.set_expanded(False)
    settle(app)
    host.set_expanded(True)
    settle(app)
    assert panel.width() < 400
    assert config.get('tag_panel_vertical_extent') == 400
    window.resize(900, 700)
    settle(app)
    assert panel.width() == 400


def test_collapsed_state_survives_a_cold_start(scene):
    app, window, host, panel, content, config, model = scene
    host.set_expanded(False)
    settle(app)
    collapsed_extent = panel.collapsed_extent()

    from fluent_ui.components.tag_panel import TagPanel
    from fluent_ui.components.panel_host import TagPanelHost
    fresh_panel = TagPanel(model, config)
    fresh_content = QWidget()
    fresh_host = TagPanelHost(fresh_content, fresh_panel, config)
    fresh_window = QWidget()
    layout = QVBoxLayout(fresh_window)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(fresh_host)
    fresh_window.resize(900, 700)
    fresh_window.show()
    fresh_panel.set_items(model.project())
    settle(app)
    try:
        assert not fresh_host.expanded and fresh_panel.collapsed
        assert not fresh_panel.index_body.isVisible()
        assert extent_of(fresh_host, fresh_panel) == collapsed_extent
        fresh_host.set_expanded(True)
        settle(app)
        assert fresh_panel.height() == 154      # the remembered extent, not the collapsed one
    finally:
        fresh_panel.flow.scroller.stop()
        fresh_window.close()
        settle(app)


def test_collapse_keeps_tags_sort_filter_and_selection(scene, monkeypatch):
    app, window, host, panel, content, config, model = scene
    from fluent_ui.components.section_index import SortProjection
    panel.set_sort(SortProjection.A_Z)
    panel.set_items(model.project())
    settle(app)
    panel.flow._set_selection(['Alpha'])
    visible = [item.name for item in panel.flow._items]
    queries = []
    original = model.project
    monkeypatch.setattr(model, 'project', lambda *a, **kw: (queries.append(1), original(*a, **kw))[1])

    host.set_expanded(False)
    settle(app)
    assert panel.sort_mode == SortProjection.A_Z
    assert panel.btn_sort.mode == SortProjection.A_Z
    assert config.get('tag_sort') == 'a_z'
    assert [item.name for item in panel.flow._items] == visible
    assert panel.flow.selected() == ['Alpha']
    assert queries == []                        # collapsing re-queries nothing
    host.set_expanded(True)
    settle(app)
    assert queries == []


def test_sort_button_cycles_three_states_without_touching_manual_order(scene):
    app, window, host, panel, content, config, model = scene
    from fluent_ui.components.section_index import SortProjection
    manual = model.order()
    seen = []
    for _ in range(3):
        panel.btn_sort.click()
        settle(app)
        seen.append(panel.sort_mode)
    assert seen == [SortProjection.A_Z, SortProjection.Z_A, SortProjection.MANUAL]
    assert model.order() == manual
    assert config.get('tag_sort') == 'manual'
    # Same control, same state expression as the sidebar and the gallery.
    panel.btn_sort.click()
    settle(app)
    assert panel.sort_mode == SortProjection.A_Z
    assert panel.flow.sections_enabled and panel.flow.manual_order is False
    assert config.get('tag_sort') == 'a_z'


def test_reorder_is_refused_outside_manual_order_and_says_so_once(scene):
    app, window, host, panel, content, config, model = scene
    from fluent_ui.components.section_index import SortProjection
    from fluent_ui.components.drop_contract import TAG_MIME, MOVE
    host.set_expanded(False); settle(app)
    panel.chrome.click(); settle(app)     # expanded again, tags visible
    mime = QMimeData()
    mime.setData(TAG_MIME, json.dumps(['Alpha']).encode())

    panel.set_sort(SortProjection.A_Z)
    panel.set_items(model.project())
    settle(app)
    assert panel.flow.manual_order is False
    target, _rect = panel.flow._resolve(panel.flow._rects[1].center(), mime)
    assert not target.valid

    hints = []
    panel.flow.manual_required.connect(lambda: hints.append(1))
    panel.flow.dragEnterEvent(QDragEnterEvent(
        QPoint(5, 5), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier))
    move = QDragMoveEvent(QPoint(*panel.flow._rects[1].center().toTuple()), Qt.MoveAction,
                          mime, Qt.LeftButton, Qt.NoModifier)
    panel.flow.dragMoveEvent(move)
    panel.flow.dragMoveEvent(move)
    panel.flow.scroller.stop()
    assert hints == [1]                         # once per drag, never silently
    assert panel.sort_mode == SortProjection.A_Z    # and never auto-switched

    panel.set_sort(SortProjection.MANUAL)
    panel.set_items(model.project())
    settle(app)
    assert panel.flow.manual_order is True
    target, _rect = panel.flow._resolve(panel.flow._rects[1].center(), mime)
    assert target.valid and target.effect == MOVE


def test_placement_switch_keeps_the_sort_state(scene):
    app, window, host, panel, content, config, model = scene
    from fluent_ui.components.section_index import SortProjection
    panel.set_sort(SortProjection.Z_A)
    panel.set_items(model.project())
    settle(app)
    expected = [item.name for item in panel.flow._items]
    for placement in ('top', 'left', 'right', 'bottom'):
        host.set_placement(placement)
        settle(app)
        assert panel.sort_mode == SortProjection.Z_A
        assert panel.btn_sort.mode == SortProjection.Z_A
        assert config.get('tag_sort') == 'z_a'
        assert [item.name for item in panel.flow._items] == expected


def test_collapse_rebuilds_no_gallery_card_and_no_window_rect(tmp_path, monkeypatch):
    """The whole point: presentation moves, the gallery and the window do not."""
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from fluent_ui import visual
    from fluent_ui.views.gallery_view import GalleryInterface
    from PySide6.QtGui import QImage, QColor
    from fluent_ui.components.panel_host import TagPanelHost
    import inspect
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    config = ConfigService()
    visual.theme.configure(config)
    i18n_engine.init(config)
    storage = StorageService(config=config)
    node = storage.create_node('Zeta')
    paths = []
    for index in range(12):
        image = QImage(16, 16, QImage.Format_RGB32)
        image.fill(QColor(index*10, 110, 70))
        path = tmp_path/f'{index}.png'
        image.save(str(path))
        paths.append(storage.save_file(str(path))[0])
    storage.move_resources_to(paths, node, copy=True)
    gallery = GalleryInterface(storage, ClipboardService(config), config)
    gallery.resize(1060, 800)
    gallery.show()
    settle(app)
    try:
        gallery.set_node(node)
        settle(app)
        host = gallery.tag_panel_host
        refreshes, collects = [], []
        monkeypatch.setattr(gallery, 'refresh_content',
                            lambda *a, **kw: refreshes.append(1))
        monkeypatch.setattr(gallery, '_collect_entries',
                            lambda *a, **kw: (collects.append(1), None)[1])
        created = gallery.renderer.created
        cards = list(gallery._all_card_widgets)
        outer = gallery.geometry()
        content_before = content_extent(host)

        # Search shares the location band above the tabs. The dock host must
        # never swallow it or move it when its placement changes.
        search = gallery.search_box
        for placement in ('top', 'bottom', 'left', 'right'):
            host.set_placement(placement)
            settle(app)
            assert search.parent() is gallery.search_surface
            assert not host.isAncestorOf(search)
            assert host.content is gallery.workspace
            host_top = host.mapTo(gallery.content_pane, QPoint(0, 0)).y()
            search_bottom = gallery.content_pane.mapFromGlobal(
                search.mapToGlobal(QPoint(0, search.height()))).y()
            assert host_top >= search_bottom-1, (placement, host_top, search_bottom)
        host.set_placement('bottom')
        settle(app)

        host.set_expanded(False)
        settle(app)
        assert content_extent(host) == content_before
        assert refreshes == [] and collects == []
        assert gallery.renderer.created == created
        assert list(gallery._all_card_widgets) == cards
        assert gallery.geometry() == outer

        host.set_expanded(True)
        settle(app)
        assert content_extent(host) == content_before
        assert refreshes == [] and collects == []
        assert gallery.renderer.created == created
        assert gallery.geometry() == outer
    finally:
        gallery.focus_timer.stop()
        gallery.close()
        settle(app)

    # Content geometry stays full-size; only the local foreground splitter
    # changes its allocation. There is no native outer-window move here.
    for cls in (TagPanelHost,):
        source = inspect.getsource(cls)
        assert host.content.geometry()==host.rect()  # foreground geometry is allowed; the gallery stays full-size
        assert 'SetWindowPos' not in source
