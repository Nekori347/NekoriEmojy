"""Relative views are content scopes, never category navigation/disclosure."""
import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from test_session_components import surface, settle


@pytest.fixture
def hierarchy(surface):
    app, g, storage, config, _, paths = surface
    a = storage.create_node('A')
    b, c, d = [storage.create_node(n, a) for n in ('B', 'C', 'D')]
    b1, b2 = [storage.create_node(n, b) for n in ('B1', 'B2')]
    leaf = storage.create_node('Leaf', b1)
    storage.move_resources_to(paths[:60], a)
    storage.move_resources_to(paths[:60], b)
    storage.move_resources_to(paths[60:], c)
    storage.move_resources_to(paths[:3], b1)
    storage.move_resources_to(paths[3:6], b2)
    g.sidebar.refresh_list(a)
    g.on_images_changed()
    g.set_node(a)
    settle(app)
    return app, g, storage, config, (a, b, c, d, b1, b2, leaf), paths


def tab(g, index):
    # Exercise the real tab signal wiring (no direct set_relative_view call).
    g.category_tabs.setCurrentIndex(index)


def test_tabs_scope_disclosure_scroll_and_snapshots(hierarchy, monkeypatch):
    app, g, storage, config, (a, b, c, d, b1, b2, leaf), paths = hierarchy
    assert g._tab_nodes == [a, b, c, d]
    g.scroll_area.verticalScrollBar().setValue(500)
    settle(app)
    a_anchor = g.renderer.anchor()
    a_expanded = set(g._expanded_nodes)
    a_count = g.content_count.text()
    assert b not in a_expanded
    tab(g, 1)
    settle(app)
    assert (g.current_node, g.active_view_node) == (a, b)
    assert g._tab_nodes == [a, b, c, d]
    assert g.sidebar.tree.current_node_id == a
    assert g.location_rail.path == [(a, 'A')]
    assert g.content_count.text() == a_count
    assert {e['_parent'] for e in g._entries} == {b}
    assert {e['id'] for e in g._entries if e['kind'] == 'node'} == {b1, b2}
    assert g._expanded_by_scope[a] == a_expanded
    # B's disclosure state is independent, including when B1 is also viewed
    # inside A's inline projection.
    g.toggle_node_expansion(b1)
    settle(app)
    assert b1 in g._expanded_nodes
    g.scroll_area.verticalScrollBar().setValue(550)
    settle(app)
    b_anchor = g.renderer.anchor()
    tab(g, 2)
    settle(app)
    assert g.current_node == a and g.content_scope_node() == c
    assert {e['path'] for e in g._entries} == set(paths[60:])
    tab(g, 0)
    settle(app)
    assert g._expanded_nodes == a_expanded
    assert g.renderer.anchor() == a_anchor
    g.toggle_node_expansion(b)
    assert b1 not in g._expanded_nodes
    tab(g, 1)
    settle(app)
    assert b1 in g._expanded_nodes and b not in g._expanded_nodes
    assert g.renderer.anchor() == b_anchor
    # Warm both actual disjoint image scopes before measuring reuse.
    for i in (1, 2, 1):
        tab(g, i)
        QTest.qWait(350)
        deadline = time.monotonic()+5
        while g.renderer.loader.running and time.monotonic() < deadline:
            QTest.qWait(20)
    decodes = g.renderer.loader.decodes
    hits = g.renderer.loader.memory_hits
    monkeypatch.setattr(g, '_collect_entries', lambda: pytest.fail('warm tab rebuilt projection'))
    timings = []
    for i in (2, 1, 2, 1):
        start = time.perf_counter()
        tab(g, i)
        settle(app)
        timings.append(round((time.perf_counter()-start)*1000, 2))
    assert g.renderer.loader.decodes == decodes
    assert g.renderer.loader.memory_hits > hits
    assert len(g._all_card_widgets) < len(paths)
    print('RELATIVE_PERF', json.dumps(dict(switch_ms=timings, new_decodes=0,
          memory_hits=g.renderer.loader.memory_hits-hits, active_cards=len(g._all_card_widgets))))
    monkeypatch.undo()
    # Formal navigation really changes the rail and tabs, resets the relative view.
    g.set_node(b)
    settle(app)
    assert (g.current_node, g.active_view_node) == (b, b)
    assert g._tab_nodes == [b, b1, b2]
    assert g.location_rail.path == [(a, 'A'), (b, 'B')]


def test_search_filters_sort_and_content_actions(hierarchy, monkeypatch):
    app, g, storage, config, (a, b, c, d, b1, b2, leaf), paths = hierarchy
    g.set_node(b)
    tab(g, 1)
    storage.apply_tags(paths[:6], ['猫'], 'add')
    g.refresh_content_incremental(paths=paths[:6], parents=set())
    g.search_box.setText('猫')
    g._execute_search()
    g._search_timer.stop()
    g._update_filter('is_static', True)
    g._toggle_tag('猫')
    g.set_content_sort('recent_added')
    assert {e['path'] for e in g._entries} == set(paths[:3])
    tab(g, 2)
    assert g.search_box.text() == '猫' and g.search_keyword == '猫'
    assert g.active_tags == {'猫'} and g.filter_state.is_static
    assert g.content_sort == 'recent_added'
    assert {e['path'] for e in g._entries} == set(paths[3:6])
    assert g.current_node == b and g.content_scope_node() == b2
    assert g.context_strip.isVisible()
    captured = []
    monkeypatch.setattr(g, 'paste_into', captured.append)
    g.handle_global_paste()
    assert captured[-1].parent == b2 and not captured[-1].exact
    created = []
    monkeypatch.setattr(g.sidebar, 'create_node', lambda parent, **kw: created.append((parent, kw)))
    g.create_node_here()
    assert created == [(b2, {'position': None})]
    # Empty-space placement, resource membership defaults and import defaults.
    monkeypatch.setattr(g, '_nearest_entry', lambda p: (None, False))
    assert g.placement_at(QPoint()).parent == b2
    assert g._resource_sources([paths[3]])[paths[3]] == b2
    g.set_node(b1)
    assert not g.search_keyword and not g.active_tags and not g.filter_state.is_active()
    assert not g.context_strip.isVisible()
    assert g.content_sort == 'recent_added'  # Formal navigation preserves presentation sort.
    manual = storage.index.content(b1)
    for expected in ('manual', 'recent_added', 'oldest_added'):
        g.set_content_sort(expected)
        assert g.content_sort == expected
    assert storage.index.content(b1) == manual
    tree_order = storage.index.content('__library__')
    for expected in ('name_asc', 'name_desc', 'manual'):
        g.sidebar.btn_sort.click()
        assert g.sidebar.tree.display_sort == expected
    assert storage.index.content('__library__') == tree_order


@pytest.mark.parametrize('invalid', [None, 'reparent', 'delete'])
def test_session_stable_id_and_fallback(hierarchy, invalid):
    from fluent_ui.views.gallery_view import GalleryInterface
    from services.clipboard import ClipboardService
    from services.config import ConfigService
    app, g, storage, config, (a, b, c, d, b1, b2, leaf), paths = hierarchy
    tab(g, 1)
    g.toggle_node_expansion(b1)
    g.scroll_area.verticalScrollBar().setValue(500)
    settle(app)
    anchor = g.renderer.anchor()
    g.save_session_state()
    # A restart has one GalleryThumbnails owner at a time. Drain the old
    # owner before constructing its replacement, as the real shutdown does.
    g.hide()
    g.focus_timer.stop()
    g.renderer.loader.wanted.clear()
    from fluent_ui.components.emoji_card import _thumbnail_pool
    _thumbnail_pool.waitForDone(10000)
    settle(app)
    state = config.get('library_view_states')[g._view_state_key]
    assert state['active_relative_view_node_id'] == b and 'tab_index' not in state
    storage.move_node(c, a, position=0)  # Reorder siblings after saving the session.
    if invalid == 'reparent':
        storage.move_node(b, c)
    elif invalid == 'delete':
        storage.delete_node(b)
    loaded = ConfigService()
    other = GalleryInterface(storage, ClipboardService(loaded), loaded)
    other.resize(g.size())
    other.show()
    settle(app)
    try:
        assert other.current_node == a
        assert other.active_view_node == (a if invalid else b)
        assert other._tab_nodes[other.category_tabs.currentIndex()] == other.active_view_node
        if not invalid:
            assert other.renderer.anchor() == anchor
            assert b1 in other._expanded_nodes
            tab(other, 0)
            assert b not in other._expanded_nodes and b1 not in other._expanded_nodes
        assert not other.search_keyword and not other.active_tags
    finally:
        other.focus_timer.stop()
        other.close()
        settle(app)


def test_header_geometry_rail_scrub_and_render(hierarchy, monkeypatch):
    from fluent_ui import visual
    app, g, storage, config, (a, b, c, d, b1, b2, leaf), paths = hierarchy
    from PySide6.QtGui import QFont, QFontDatabase
    # Offscreen does not discover Windows fonts automatically on this host.
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    app.setFont(QFont('Microsoft YaHei', 9))
    g.set_node(leaf)
    settle(app)
    rail = g.location_rail
    assert list(rail._rows(rail.path)) == [b1, leaf]
    assert rail.height() == visual.HIERARCHY_HEADER_HEIGHT
    assert rail.current_rect().top() == visual.HIERARCHY_CURRENT_TOP
    # Scrub beyond the two visible levels to A without navigating mid-drag.
    start = QPoint(30, rail.height()-15)
    QTest.mousePress(rail, Qt.LeftButton, pos=start)
    QTest.mouseMove(rail, start+QPoint(0, 3*visual.HIERARCHY_SCRUB_STEP))
    assert rail.path[rail._preview][0] == a
    assert g.current_node == leaf  # Scrub preview does not navigate mid-drag.
    QTest.mouseRelease(rail, Qt.LeftButton, pos=start+QPoint(0, 3*visual.HIERARCHY_SCRUB_STEP))
    settle(app)
    assert g.current_node == a
    g.set_node(b)
    settle(app)
    QTest.mouseClick(rail, Qt.LeftButton, pos=QPoint(30, 10))
    assert g.current_node == a
    tab(g, 1)
    settle(app)
    tabs_y = g.tab_row.mapTo(g, QPoint()).y()
    search_y = g.search_box.mapTo(g, QPoint()).y()
    grid_y = g.scroll_area.mapTo(g, QPoint()).y()
    assert search_y < tabs_y < grid_y
    # Commands now share the inset search row inside the connected content sheet.
    assert g.search_box.width() < g.tab_row.width()
    assert g.search_box.parent() is g.search_surface
    assert g.tab_row.isAncestorOf(g.btn_content_sort)
    assert g.top_bar.isAncestorOf(g.search_surface)
    assert not g.context_strip.isVisible()
    from fluent_ui.components.navigation import TabStrip
    generic_tabs = TabStrip(g)
    generic_tabs.set_tabs(['Settings A', 'Settings B'])
    assert generic_tabs.content_tab_rect(0) == generic_tabs.tabRect(0)
    generic_tabs.hide()
    assert (g.category_tabs.tabRect(0).width() - g.category_tabs.content_tab_rect(0).width()
            == visual.TAB_LOCATION_GAP)
    output = Path(__file__).resolve().parents[2]/'DevData'/'relative-navigation.png'
    assert g.grab().save(str(output))
    # Exercise the real property timeline in an offscreen widget, never the
    # user's physical desktop. Navigation/content must update before it ends.
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QAbstractAnimation
    monkeypatch.setattr(QApplication, 'platformName', lambda: 'animation-test')
    g.set_node(b)
    assert rail.animation.state() == QAbstractAnimation.Running
    assert g.current_node == b and g.content_scope_node() == b
    QTest.qWait(visual.HIERARCHY_DURATION_MS+40)
    assert rail.progress == 1.0
    g.set_node(a)
    assert rail._direction == -1
    g.set_node(leaf)  # Rapid input retargets the continuous rail transition.
    assert rail.animation.state() == QAbstractAnimation.Running
    QTest.qWait(visual.HIERARCHY_DURATION_MS+40)
    assert rail.progress == 1.0
    settle(app)
    assert g.grab().save(str(output.with_name('relative-hierarchy.png')))
