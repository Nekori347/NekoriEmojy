"""Main interaction acceptance using isolated data and offscreen Qt events."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import Qt, QMimeData, QUrl, QPoint, QRect
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel
from PySide6.QtTest import QTest

from services.library_index import ROOT
from services.action_policy import ActionPolicy
from services.resource_import import ImportTarget
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from fluent_ui import visual
from fluent_ui.views.gallery_view import GalleryInterface


def settle(app):
    for _ in range(5):
        app.processEvents()


@pytest.fixture
def surface(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path / 'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path / 'library'))
    config = ConfigService()
    visual.theme.configure(config)
    i18n_engine.init(config)
    storage = StorageService(config=config)
    parent = storage.create_node('Parent')
    child = storage.create_node('Child', parent)
    other = storage.create_node('Other')
    paths = []
    for name, color in [('alpha', 'red'), ('beta', 'blue'), ('missing', 'green'), ('child', 'yellow')]:
        source = tmp_path / (name + '.png')
        Image.new('RGB', (16, 16), color).save(source)
        target = child if name == 'child' else parent
        paths.append(storage.save_file(str(source), target=ImportTarget(target))[0])
    animation = tmp_path / 'animated.gif'
    Image.new('RGB', (16, 16), 'cyan').save(animation, save_all=True,
        append_images=[Image.new('RGB', (16, 16), 'magenta')], duration=100, loop=0)
    paths.append(storage.save_file(str(animation), target=ImportTarget(parent))[0])
    storage.apply_tags([paths[0]], ['Cat'], 'add')
    Path(paths[2]).unlink()
    storage.availability.refresh()
    clipboard = ClipboardService(config)
    clipboard.clipboard.clear()
    g = GalleryInterface(storage, clipboard, config)
    g.focus_timer.stop()
    g.resize(1180, 760)
    g.show()
    g.set_node(parent)
    settle(app)
    yield SimpleNamespace(app=app, g=g, storage=storage, config=config, paths=paths,
                          parent=parent, child=child, other=other, clipboard=clipboard, tmp=tmp_path)
    # A real application quits these shared services via aboutToQuit. Tests
    # reuse QApplication, so shut them down before deleting their widgets.
    g.imports.shutdown()
    g.ocr.close()
    g.filter_flyout.hide()
    g.close()
    from fluent_ui.components.emoji_card import _thumbnail_pool
    _thumbnail_pool.waitForDone()
    settle(app)
    g.deleteLater()
    settle(app)


def actions(menu):
    return {a.text(): a for a in menu.actions() if not a.isSeparator()}


def card(s, path):
    return next(c for c in s.g._all_card_widgets if getattr(c, 'image_path', None) == path)


def test_sidebar_visible_segment_persistence_sort_and_formal_new(surface, monkeypatch):
    s, g = surface, surface.g
    toggle = g.sidebar.btn_view_mode
    assert toggle.isVisible() and s.config.get('sidebar_mode', 'tree') == 'tree'
    assert not any(label.text() == '我的资源库' for label in g.sidebar.findChildren(QLabel))
    QTest.mouseClick(toggle, Qt.LeftButton)
    assert s.config.get('sidebar_mode') == 'categorized_icons'
    assert g.sidebar.icons.isVisible() and not g.sidebar.tree.isVisible()
    assert toggle.toolTip() == '分类图标'
    assert ConfigService(s.tmp / 'app').get('sidebar_mode') == 'categorized_icons'
    QTest.mouseClick(toggle, Qt.LeftButton)
    assert g.sidebar.tree.isVisible() and not g.sidebar.icons.isVisible()
    widths = []
    for mode in ('name_asc', 'name_desc', 'manual'):
        g.sidebar.btn_sort.click()
        widths.append(g.sidebar.btn_sort.width())
        assert g.sidebar.tree.display_sort == mode
    assert len(set(widths)) == 1
    assert s.config.get('sidebar_sort') == 'manual'
    g.set_relative_view(s.child)
    create = Mock()
    monkeypatch.setattr(g.sidebar, 'create_node', create)
    g.sidebar.btn_new.click()
    create.assert_called_once_with(s.parent)


def test_split_regions_and_clipboard_availability(surface, monkeypatch):
    s, g = surface, surface.g
    split = g.btn_paste
    assert not split.button.isEnabled() and split.dropButton.isEnabled()
    assert not split.button.geometry().intersects(split.dropButton.geometry())
    paste = Mock()
    monkeypatch.setattr(g, 'paste_into', paste)
    QTest.mouseClick(split.dropButton, Qt.LeftButton)
    assert g.import_menu.isVisible()
    paste.assert_not_called()
    assert set(actions(g.import_menu)) == {'导入文件…', '导入文件夹为分类…'}
    g.import_menu.hide()
    for text in ('plain text', 'http://'):
        s.clipboard.clipboard.setText(text)
        assert not split.button.isEnabled()
    s.clipboard.clipboard.setText('https://example.test/image.png')
    assert split.button.isEnabled()
    QTest.mouseClick(split.button, Qt.LeftButton)
    paste.assert_called_once()
    assert not g.import_menu.isVisible()
    assert split.text() == ''
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(s.tmp / 'alpha.png'))])
    s.clipboard.clipboard.setMimeData(data)
    assert split.button.isEnabled()
    bad = s.tmp / 'note.txt'
    bad.write_text('unsupported')
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(bad))])
    s.clipboard.clipboard.setMimeData(data)
    assert not split.button.isEnabled() and split.dropButton.isEnabled()
    image = QImage(str(s.tmp / 'alpha.png'))
    s.clipboard.clipboard.setImage(image)
    assert split.button.isEnabled()


def test_folder_import_secondary_preserves_structure(surface, monkeypatch):
    s, g = surface, surface.g
    folder = s.tmp / 'Imported'
    nested = folder / 'Nested'
    nested.mkdir(parents=True)
    Image.new('RGB', (16, 16), 'black').save(nested / 'nested.png')
    g.set_relative_view(s.child)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(folder))
    actions(g.import_menu)['导入文件夹为分类…'].trigger()
    thread = g.import_thread
    assert thread and thread.wait(5000)
    settle(s.app)
    imported = next(n for n in s.storage.child_nodes(s.child) if n['name'] == 'Imported')
    nested_node = next(n for n in s.storage.child_nodes(imported['id']) if n['name'] == 'Nested')
    assert len(s.storage.index.content(nested_node['id'])) == 1
    assert g.btn_paste.text() == ''


def test_filter_continuous_checkbox_clear_and_context_sync(surface):
    s, g = surface, surface.g
    QTest.mouseClick(g.btn_filter, Qt.LeftButton)
    popup = g.filter_flyout
    assert popup.isVisible()
    for key in ('no_tag', 'is_static'):
        QTest.mouseClick(popup.checkboxes[key], Qt.LeftButton, pos=QPoint(10, 12))
        assert popup.isVisible() and getattr(g.filter_state, key)
    assert g.context_strip.isVisible()
    chips = [g.chip_layout.itemAt(i).widget().text() for i in range(g.chip_layout.count())
             if g.chip_layout.itemAt(i).widget() is not None]
    assert '无标签' in chips and '静态表情' in chips
    g._update_filter('no_tag', False)
    assert not popup.checkboxes['no_tag'].isChecked()
    QTest.mouseClick(popup.clear_button, Qt.LeftButton)
    assert popup.isVisible() and not g.filter_state.is_active()
    assert not g.context_strip.isVisible()
    assert not any(c.isChecked() for c in popup.checkboxes.values())
    QTest.mouseClick(g.btn_filter, Qt.LeftButton)
    assert not popup.isVisible()
    QTest.mouseClick(g.btn_filter, Qt.LeftButton)
    QTest.keyClick(popup.checkboxes['no_tag'], Qt.Key_Escape)
    assert not popup.isVisible()
    QTest.mouseClick(g.btn_filter, Qt.LeftButton)
    QTest.mouseClick(g.search_box, Qt.LeftButton, pos=QPoint(10, 10))
    assert not popup.isVisible()
    # Place the actual trigger at the screen's lower-right corner in offscreen Qt.
    area = g.screen().availableGeometry()
    anchor = g.btn_filter.mapTo(g, QPoint())
    g.move(area.right() - anchor.x() - 8, area.bottom() - anchor.y() - 8)
    g._show_filter_menu()
    assert area.contains(popup.geometry())
    assert popup.geometry().bottom() < g.btn_filter.mapToGlobal(QPoint()).y()


def test_selection_bar_layout_shared_mode_and_mixed_count(surface):
    s, g = surface, surface.g
    g._select_single(s.child)
    g._toggle_selection(s.paths[0])
    assert g.command_bar.isVisible()  # Node and resource are both selected entries.
    g._toggle_selection(s.paths[1])
    settle(s.app)
    shared = g.command_bar
    assert shared.isVisible() and g.top_bar.isVisible()
    assert g.selected_count_label.text() == '已选 3 项（2 张表情，1 个节点）'
    layout = g.content_pane.content_layout
    assert [layout.itemAt(i).widget() for i in range(layout.count())] == [
        g.context_strip, shared, g.tag_panel_host]
    assert g.tag_panel_host.y() >= shared.y() + shared.height()
    g.set_mode('manage')
    assert g.command_bar is shared and g.btn_manage.isChecked()
    assert g.get_selected_paths() == [e['path'] for e in g._selected_entries() if e['kind'] == 'resource']
    g._drop_selection_only()
    assert shared.isVisible() and g.selected_count_label.text() == '已选 0 项'
    assert g.top_bar.isVisible()
    g.select_all_cards()
    assert g.selected_keys == set(g.entry_model.projected) and s.child in g.selected_keys
    assert g.btn_select_all.toolTip() == '取消全选'
    g.select_all_cards()
    assert not g.selected_keys and not g._selection_parents
    g.btn_exit_mode.click()
    assert g.mode == 'normal' and not shared.isVisible() and not g.btn_manage.isChecked()


def test_navigation_clears_selection_and_manage_but_relative_is_not_formal(surface):
    s, g = surface, surface.g
    g._entry_clicked(card(s, s.paths[0]).content_entry, Qt.NoModifier)
    g.set_mode('manage')
    g.category_tabs.setCurrentIndex(1)
    assert g.current_node == s.parent and g.content_scope_node() == s.child
    assert g.mode == 'normal' and not g.selected_keys and not g._selection_parents
    g._select_single(s.paths[3])
    g.set_mode('manage')
    g.set_node(s.other)
    assert g.mode == 'normal' and not g.selected_keys and not g._selection_parents
    g.set_mode('manage')
    g.set_node(s.other)  # Repeat formal navigation also ends Manage at zero selection.
    assert g.mode == 'normal'


def test_projection_intersection_sort_preservation_and_manual_guard(surface):
    s, g = surface, surface.g
    g.select_all_cards()
    original = set(g.selected_keys)
    canonical = s.storage.index.content(s.parent)
    for mode in ('recent_added', 'oldest_added', 'manual'):
        g.btn_content_sort.click()
        assert g.selected_keys == original
        assert s.config.get('resource_sort') == mode
        assert g.content_sort == mode
        assert g.btn_arrange.isEnabled() == (mode == 'manual')
        g.set_content_sort(mode)  # Re-selecting retains the active projection.
        assert g.content_sort == mode
    assert s.storage.index.content(s.parent) == canonical
    g._update_filter('no_tag', True)
    assert s.paths[0] not in g.selected_keys
    assert set(g._selection_parents) == g.selected_keys
    g._clear_filter()
    g.select_all_cards()
    g.search_box.setText('alpha')
    g._search_timer.stop()
    g._execute_search()
    assert g.selected_keys == {s.paths[0]}
    assert not g.btn_arrange.isEnabled() and g.content_sort == 'manual'
    g.search_box.clear()
    g._search_timer.stop()
    g._execute_search()
    g.select_all_cards()
    g._toggle_tag('Cat')
    assert g.selected_keys == {s.paths[0]} and set(g._selection_parents) == {s.paths[0]}
    assert not g.context_strip.isVisible()
    assert g.tag_panel.flow.active_filters == {'Cat'}


def test_manage_click_enter_hover_and_finish_lifecycle(surface, monkeypatch):
    s, g = surface, surface.g
    s.config.set('gallery_click_action', 'send')
    send = Mock()
    monkeypatch.setattr(g, '_send_to_clipboard', send)
    g._select_single(s.paths[0])
    g.set_mode('manage')
    assert g.selected_keys == {s.paths[0]}
    c = card(s, s.paths[1])
    QTest.mouseClick(c, Qt.LeftButton)
    QTest.keyClick(c, Qt.Key_Return)
    QTest.mouseDClick(c, Qt.LeftButton)
    send.assert_not_called()
    g.on_hover_started(c, c.image_path)
    assert not g.preview_popup.isVisible()
    QTest.keyClick(c, Qt.Key_Escape)
    assert g.mode == 'normal' and not g.selected_keys and not g._selection_parents
    g._entry_clicked(card(s, s.paths[0]).content_entry, Qt.ControlModifier)
    g._entry_clicked(card(s, s.paths[1]).content_entry, Qt.ControlModifier)
    assert g.command_bar.isVisible()
    g.btn_exit_mode.click()
    assert g.mode == 'normal' and not g.selected_keys and not g._selection_parents


def test_context_groups_phase1_guards_and_node_cleanup(surface):
    s, g = surface, surface.g
    g._select_single(s.paths[4])
    menu = g._build_resource_menu(card(s, s.paths[4]))
    groups, group = [], []
    for index in range(menu.view.count()):
        item = menu.view.item(index)
        if item.data(Qt.DecorationRole) == 'seperator':
            groups.append(group)
            group = []
        else:
            group.append(item.data(Qt.UserRole).text())
    groups.append(group)
    assert groups == [
        ['使用 / 发送'], ['加入分类…', '移动到…', '移出当前分类', '标签…',
                      '识别文字', '重新识别文字', '查看与编辑文字…'],
        ['在资源管理器中显示', '复制文件路径', '导出选中项到文件夹…'],
        ['选择缩略图帧…'], ['设为当前分类图标', '设为软件图标'], ['删除表情（回收站）']]
    g._select_single(s.paths[2])
    missing = actions(g._build_resource_menu(card(s, s.paths[2])))
    assert '使用 / 发送' not in missing and '选择缩略图帧…' not in missing
    assert missing['重新绑定文件…'].isEnabled() and missing['移除失效记录'].isEnabled()
    context = g._action_context()
    for label, key in [('在资源管理器中显示', 'show_in_explorer'), ('复制文件路径', 'copy_path'),
                       ('导出选中项到文件夹…', 'export'), ('标签…', 'tag_edit'), ('设为软件图标', 'set_icon')]:
        assert missing[label].isEnabled() == ActionPolicy.enabled(key, context)
    more = actions(g._build_selection_more_menu())
    assert '选择缩略图帧…' not in more and '重新绑定文件…' not in more
    assert '在资源管理器中显示' not in more
    assert not more['导出选中项到文件夹…'].isEnabled()
    assert {'移出当前分类', '复制文件路径'} <= set(more)
    node = actions(g._build_node_context_menu(SimpleNamespace(node_id=s.child)))
    assert '打开' in node and '在分类树中显示' not in node


def test_narrow_bar_overflow_and_dropdown_elision(surface):
    s, g = surface, surface.g
    g.set_mode('manage')
    g.select_all_cards()
    g.resize(760, 760)
    g.splitter.setSizes([260, 460])
    settle(s.app)
    assert g._selection_overflow
    direct = [g.selected_count_label, g.btn_more, g.btn_delete, g.btn_exit_mode]
    assert all(w.isVisible() for w in direct)
    assert all(not w.isVisible() for w in g._organization_buttons)
    assert {'加入分类…', '移动到…', '标签…'} <= set(actions(g._build_selection_more_menu()))
    rects = [QRect(w.mapTo(g.command_bar, QPoint()), w.size()) for w in direct]
    assert all(g.command_bar.rect().contains(r) for r in rects)
    assert all(not a.intersects(b) for i, a in enumerate(rects) for b in rects[i+1:])
    g.resize(1250, 760)
    settle(s.app)
    assert not g._selection_overflow and all(w.isVisible() for w in g._organization_buttons)
    button = g.btn_content_sort
    assert button.width() == button.height() == visual.COMPACT_CONTROLS.action_extent
    assert button.toolTip().startswith('表情显示排序')
    old=g.content_sort;button.click();assert g.content_sort!=old
