"""Framework contracts, with desktop feel deliberately left to human QA."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFontMetrics, QMouseEvent
from PySide6.QtTest import QTest
import pytest

from test_relative_navigation import hierarchy, surface, tab
from test_session_components import settle
from test_tag_panel_collapse import scene


def test_branch_return_is_exact_one_shot_and_not_a_relative_view(hierarchy):
    app, g, storage, config, (a, b, c, d, b1, b2, leaf), paths = hierarchy
    assert g.return_child_hint is None
    g.set_node(leaf)
    g.set_node(a)
    settle(app)
    assert g.return_child_hint == leaf
    assert g.location_rail.return_item == (leaf, 'Leaf')
    tab(g, 1)
    assert g.current_node == a and g.return_child_hint == leaf
    counts = g.content_count.text()
    tab(g, 2)
    assert g.return_child_hint == leaf and g.content_count.text() == counts
    QTest.mouseClick(g.location_rail, Qt.LeftButton, pos=g.location_rail.return_rect().center().toPoint())
    settle(app)
    assert g.current_node == leaf and g.active_view_node == leaf
    assert g.return_child_hint is None and g.location_rail.return_item is None
    g.set_node(b1)
    assert g.return_child_hint == leaf
    g.set_node(b2)  # unrelated formal navigation discards it
    assert g.return_child_hint is None
    g.set_node(b)
    assert g.return_child_hint == b2
    g.set_node(b1)  # ordinary parent -> child must not leave a return row
    assert g.return_child_hint is None
    g.set_node(a)
    storage.delete_node(b1)
    g.on_images_changed()
    assert g.return_child_hint is None
    g.save_session_state()
    state = config.get('library_view_states')[g._view_state_key]
    assert 'return_child_hint' not in state


def test_counts_follow_title_and_long_titles_yield_counts_first(hierarchy, monkeypatch):
    from fluent_ui import visual
    from services.i18n import i18n_engine
    app, g, storage, config, (a, b, c, d, b1, b2, leaf), paths = hierarchy
    rail = g.location_rail
    for width, lang in ((1060, 'zh'), (800, 'en')):
        g.resize(width, 740)
        i18n_engine.load_language(lang)
        g.set_node(leaf)
        settle(app)
        assert rail.height() == visual.HIERARCHY_HEADER_HEIGHT
        assert g.content_count.parent() is rail
        font = visual.font('page_title')
        expected_x = rail.current_rect().left() + QFontMetrics(font).horizontalAdvance('Leaf') + 2*visual.COMPACT_CONTROLS.spacing
        assert g.content_count.x() == expected_x
        assert abs(g.content_count.geometry().center().y()-rail.current_rect().center().y()) <= 1
        assert rail.rect().contains(g.content_count.geometry())
        # All four toolbar actions remain disjoint and inside the same header.
        from PySide6.QtCore import QRect
        buttons = [g.btn_filter, g.btn_manage, g.btn_paste, g.btn_content_sort]
        rects = [QRect(w.mapTo(g.top_bar,QPoint()),w.size()) for w in buttons]
        assert all(g.top_bar.rect().contains(r) for r in rects)
        assert all(not left.intersects(right) for i,left in enumerate(rects) for right in rects[i+1:])
    g.set_node(a)
    settle(app)
    assert rail.height() == visual.HIERARCHY_HEADER_HEIGHT
    # Presentation-only refresh: title resilience and animation cannot fetch gallery data.
    monkeypatch.setattr(g, 'refresh_content', lambda *a, **k: pytest.fail('header rebuilt Gallery'))
    outer = g.geometry()
    rail.set_path([{'id': a, 'name': 'An extremely long English category title '*6}])
    rail.set_counts('123 resources\n12 subcategories')
    settle(app)
    assert not g.content_count.isVisible()
    assert 'An extremely long' in rail.toolTip() and '123 resources' in rail.toolTip()
    assert g.geometry() == outer
    i18n_engine.load_language('zh')


def test_sidebar_and_tag_use_the_same_outer_index(surface):
    from fluent_ui import visual
    from fluent_ui.components.section_index import SortProjection
    app, g, storage, config, nodes, paths = surface
    for mode in ('tree', 'categorized_icons'):
        config.set('sidebar_mode', mode)
        g.sidebar.apply_presentation()
        for sort in ('manual', 'name_asc'):
            g.sidebar.set_display_sort(sort)
            settle(app)
            index = g.sidebar.index_view
            assert index.isVisible() == (sort != 'manual')
            if sort != 'manual':
                assert index.geometry().right() == index.parentWidget().width()-1
                assert index.width() == visual.SECTION_INDEX_COMPACT_EXTENT
                assert index.model.projection is g.sidebar.tree.section_projection
    g.tag_panel.set_sort(SortProjection.A_Z)
    for edge in ('left', 'right'):
        g.tag_panel_host.set_placement(edge)
        settle(app)
        assert g.tag_panel.index_view.width() == g.sidebar.index_view.width()
        assert g.tag_panel.index_view.model.projection is g.tag_panel.flow.projection


@pytest.mark.parametrize('placement', ['top', 'left'])
def test_drag_from_ear_transfers_to_splitter_without_collapse(scene, placement):
    app, window, host, panel, content, config, model = scene
    host.set_placement(placement)
    settle(app)
    handle = host.splitter.handle(1)
    start = handle.ear_rect(True).center()
    QTest.mousePress(handle, Qt.LeftButton, pos=start)
    delta = QPoint(0, 30) if host.horizontal else QPoint(30, 0)
    point = start + delta
    # Qt events in an isolated offscreen widget, never the physical desktop.
    event = QMouseEvent(QMouseEvent.MouseMove, point, handle.mapToGlobal(point),
                        Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    handle.mouseMoveEvent(event)
    assert handle._dragging and handle._ear_press is None
    QTest.mouseRelease(handle, Qt.LeftButton, pos=point)
    settle(app)
    assert host.expanded


def test_full_alphabet_does_not_force_narrow_panel_to_grow(scene):
    from fluent_ui.components.section_index import SortProjection
    app, window, host, panel, content, config, model = scene
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        model.create(letter+' name')
    panel.set_sort(SortProjection.A_Z)
    panel.set_items(model.project())
    window.resize(380, 500)
    for placement in ('top', 'left'):
        host.set_placement(placement)
        settle(app)
        assert panel.index_body.rect().contains(panel.index_view.geometry())
        assert window.width() == 380
        index = panel.index_view
        requested = []
        index.section_requested.connect(requested.append)
        QTest.mouseClick(index, Qt.LeftButton, pos=index.rect().bottomRight()-QPoint(1, 1))
        assert requested[-1] == index.model.sections[-1]


@pytest.mark.parametrize('placement', ['top', 'left'])
def test_long_tag_name_keeps_its_full_hit_rect_inside_content(scene, placement):
    from fluent_ui.components.section_index import SortProjection
    app, window, host, panel, content, config, model = scene
    name = 'AVeryLongEnglishTagNameWith中文标签_' * 3
    model.create(name)
    host.set_placement(placement)
    for mode in (SortProjection.MANUAL, SortProjection.A_Z):
        panel.set_sort(mode)
        panel.set_items(model.project())
        settle(app)
        for rect in panel.flow._rects:
            assert panel.flow.rect().contains(rect)
        index = next(i for i, item in enumerate(panel.flow._items) if item.name == name)
        point = panel.flow._rects[index].center()
        app.sendEvent(panel.flow,QMouseEvent(QMouseEvent.MouseMove,point,panel.flow.mapToGlobal(point),Qt.NoButton,Qt.NoButton,Qt.NoModifier))
        assert panel.flow.toolTip() == name


def test_index_and_content_share_one_panel_surface(scene):
    app, window, host, panel, content, config, model = scene
    host.set_placement('bottom')
    panel.set_sort('a_z')
    settle(app)
    assert not panel.flow.autoFillBackground()
    assert not panel.scroll.viewport().autoFillBackground()
    shot = panel.grab().toImage()
    index_blank = panel.index_view.mapTo(panel, QPoint(panel.index_view.width()-1, panel.index_view.height()-1))
    flow_blank = panel.flow.mapTo(panel, QPoint(panel.flow.width()-1, panel.scroll.viewport().height()-2))
    assert shot.pixelColor(index_blank) == shot.pixelColor(flow_blank)


@pytest.mark.parametrize('placement', ['top', 'bottom', 'left', 'right'])
def test_dock_arrows_are_permanent_and_collapsed_separator_never_highlights(scene, monkeypatch, placement):
    from fluent_ui.components import panel_host
    app, window, host, panel, content, config, model = scene
    host.set_placement(placement)
    settle(app)
    handle = host.splitter.handle(1)
    draws = []
    original = panel_host.paint_dock_chevron
    def record(painter, points, active=False):
        draws.append((points, active))
        original(painter, points, active)
    monkeypatch.setattr(panel_host, 'paint_dock_chevron', record)
    handle.clearFocus()
    handle.setAttribute(Qt.WA_UnderMouse, False)
    draws.clear()
    handle.grab()
    assert len(draws) == 1 and not draws[0][1]  # collapse arrow at rest
    collapse = handle.chevron_points()
    host.set_expanded(False)
    settle(app)
    assert not handle.isEnabled()
    assert handle.cursor().shape() == Qt.ArrowCursor
    assert not handle.toolTip()
    handle.setAttribute(Qt.WA_UnderMouse, False)
    before = handle.grab().toImage()
    handle.setAttribute(Qt.WA_UnderMouse, True)
    after = handle.grab().toImage()
    assert before == after  # no resize hover color, even with stale underMouse
    panel.chrome.clearFocus()
    panel.chrome.setAttribute(Qt.WA_UnderMouse, False)
    draws.clear()
    panel.chrome.grab()
    assert len(draws) == 1 and not draws[0][1]  # expand arrow at rest
    expand = panel.chrome.chevron_points()
    axis = (lambda p: p.y()) if host.horizontal else (lambda p: p.x())
    assert (axis(collapse[1])-axis(collapse[0])) * (axis(expand[1])-axis(expand[0])) < 0
    QTest.mouseClick(panel.chrome, Qt.LeftButton, pos=panel.chrome.rect().bottomRight()-QPoint(1, 1))
    settle(app)
    assert host.expanded and handle.isEnabled()
    assert handle.cursor().shape() == (Qt.SplitVCursor if host.horizontal else Qt.SplitHCursor)
