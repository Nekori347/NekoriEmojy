"""Integrated acceptance on isolated libraries; never inject desktop input."""
import json
import os
import time
from pathlib import Path
from unittest.mock import Mock
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PySide6.QtTest import QTest
from test_phase2_interaction import surface, settle
from services.library_index import ROOT
from services.i18n import i18n_engine
from fluent_ui.views.settings_center import SettingsCenter
from fluent_ui.components.number_box import CompactNumberBox
from fluent_ui.components.feedback import FeedbackHost
from fluent_ui import visual


def test_shift_large_real_file_ranges_one_commit(surface, monkeypatch):
    s, g = surface, surface.g
    folder = Path(s.paths[0]).parent
    records = []
    pixels = Path(s.paths[0]).read_bytes()
    for i in range(3000):
        path = folder / f'perf-{i:04}.png'
        path.write_bytes(pixels)
        records.append((f'perf-{i}', path.name, path.relative_to(s.storage.index.root).as_posix(), path.stem))
    with s.storage.index.connect() as db:
        db.executemany('INSERT INTO resources(id,filename,relative_path,display_name) VALUES(?,?,?,?)', records)
        db.executemany('INSERT INTO content(parent_id,resource_id,position) VALUES(?,?,?)',
                       [(s.other, r[0], i) for i, r in enumerate(records)])
    s.storage.force_reload()
    g.set_node(s.other)
    settle(s.app)
    keys = [g._entry_key(e) for e in g._entries]
    assert len(keys) == 3000
    assert len(g._all_card_widgets) < 100
    g.on_image_clicked(keys[0])
    sync = Mock(wraps=g._sync_command_bar)
    monkeypatch.setattr(g, '_sync_command_bar', sync)
    for name in ('refresh_content', 'refresh_content_incremental', 'clear_gallery', '_calculate_positions'):
        if hasattr(g, name):
            monkeypatch.setattr(g, name, Mock(side_effect=AssertionError('Selection rebuilt gallery')))
    for card in g._all_card_widgets:
        monkeypatch.setattr(card, 'update_size', Mock(side_effect=AssertionError('Selection reloaded thumbnail')))
    monkeypatch.setattr(s.storage.index, 'connect', Mock(side_effect=AssertionError('Selection queried SQL')))
    measurements = []
    for count in (500, 3000, 600, 2000, 3):
        sync.reset_mock()
        start = time.perf_counter()
        g.on_image_clicked(keys[count-1], Qt.ShiftModifier)
        elapsed = (time.perf_counter()-start)*1000
        assert g.selected_keys == set(keys[:count])
        assert g.selected_count_label.text() == f'已选 {count} 项'
        assert sync.call_count == 1
        assert elapsed < 500, elapsed
        measurements.append({'selected': count, 'milliseconds': round(elapsed, 2), 'command_updates': sync.call_count})
    # A Ctrl selection outside the next Shift range survives expansion/retraction.
    g.on_image_clicked(keys[-1], Qt.ControlModifier)
    g.on_image_clicked(keys[-4], Qt.ShiftModifier)
    g.on_image_clicked(keys[-2], Qt.ShiftModifier)
    assert g.selected_keys == set(keys[:3]) | set(keys[-2:])
    result = {'real_files': 3000, 'active_cards': len(g._all_card_widgets), 'ranges': measurements,
              'selection_sql_calls': 0, 'renderer_rebuilds': 0, 'thumbnail_reloads': 0}
    Path('../DevData/l1-l3-shift-performance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')


def test_root_header_and_owner_feedback_layout(surface):
    s, g = surface, surface.g
    sidebar = g.sidebar
    assert sidebar.root_count.text() == '5'
    assert sidebar.tree.topLevelItemCount() == 2
    assert all(sidebar.tree.topLevelItem(i).data(0, Qt.UserRole) != ROOT for i in range(sidebar.tree.topLevelItemCount()))
    sidebar.btn_root.click()
    assert g.current_node == ROOT and sidebar.btn_root.isChecked()
    assert not sidebar.tree.selectedItems()
    positions = [w.geometry() for w in (sidebar.btn_view_mode, sidebar.btn_sort, sidebar.btn_new)]
    assert all(abs(r.center().y()-positions[0].center().y()) <= 2 for r in positions)
    assert all(not a.intersects(b) for i,a in enumerate(positions) for b in positions[i+1:])
    settle(s.app)
    before = [w.mapTo(g, QPoint()) for w in (g.search_box, g.command_bar, g.tag_panel_host)]
    g.feedback_host.notice('Needs attention', 'Persistent detail', action=lambda: None)
    settle(s.app)
    assert before == [w.mapTo(g, QPoint()) for w in (g.search_box, g.command_bar, g.tag_panel_host)]
    assert g.workspace_layout.indexOf(g.feedback_host.strip) < g.workspace_layout.indexOf(g.scroll_area)
    g.feedback_host.toast('Copied')
    g.feedback_host.toast('Copied')
    for i in range(5):g.feedback_host.toast(str(i))
    settle(s.app)
    assert len(g.feedback_host.toasts) == 3
    assert g.scroll_area.viewport().rect().contains(g.feedback_host.toast_layer.geometry())
    g.feedback_host.set_overlays_suppressed(True)
    assert not g.feedback_host.toast_layer.isVisible()
    g.feedback_host.set_overlays_suppressed(False)
    g.feedback_host.task('Import', total=None)
    assert g.feedback_host.progress.maximum() == 0
    assert not g.feedback_host.action_button.isVisible()
    g.feedback_host.update_task(4, 10)
    assert g.feedback_host.progress.value() == 4 and g.feedback_host.progress.maximum() == 10
    g.feedback_host.finish('Partial', 'One failed', outcome='partial')
    assert g.feedback_host.strip.isVisible() and not g.feedback_host.task_active
    g.feedback_host.finish('Failed', 'Read denied', outcome='error')
    assert g.feedback_host.notices[-1][2]
    g.feedback_host.dismiss()


@pytest.fixture
def settings(surface, monkeypatch):
    monkeypatch.setattr('fluent_ui.views.settings_center.AutostartService.is_enabled', lambda _: False)
    c = SettingsCenter(surface.config, surface.storage)
    c.resize(880, 680)
    c.show()
    yield c
    c.discard()
    c.close()
    c.deleteLater()
    settle(surface.app)


def test_settings_ia_pending_dependency_sync_and_dirty_actions(surface, settings):
    c = settings
    assert [x[0] for x in c._icon_pages()] == ['常规','外观','交互','数据与资源库','关于']
    for i, (_,tabs) in enumerate(c._icon_pages()):
        c._select_page(i)
        for j in range(len(tabs)):c._show_tab(j)
    assert len(c._page_widgets) == 15
    assert 'gallery_click_action' in c._all_rows and 'quick_panel_thumbnail_size' in c._all_rows
    assert isinstance(c._all_rows['quick_panel_thumbnail_size'][0].spin, CompactNumberBox)
    c._select_page(1);c._show_tab(1)
    row = c._rows['sidebar_mode'][0]
    row.set_value('categorized_icons');row.changed.emit()
    assert c.pending['sidebar_mode'] == 'categorized_icons' and c.icon_options.isEnabled()
    assert all(not b.isEnabled() for b in c._dirty_blocked_actions)
    assert not c.btn_defaults.isEnabled()
    assert '未保存修改' in c.export_hint.hint_label.text()
    surface.config.set('sidebar_mode', 'tree')
    c.sync_external_preference('sidebar_mode', 'tree')
    assert row.value() == 'tree' and 'sidebar_mode' not in c.pending
    c._select_page(2);c._show_tab(1)
    row = c._rows['gallery_click_action'][0]
    row.set_value('send');row.changed.emit()
    assert surface.config.config['gallery_click_action'] == 'select'
    c.discard()
    assert row.value() == 'select'
    row.set_value('send');row.changed.emit();c.save()
    assert surface.config.config['gallery_click_action'] == 'send' and not c.pending
    # An immediate app icon action is independent of preference discard.
    from services.app_icon import ApplicationIconService
    icons = ApplicationIconService(surface.config)
    icons.set_from_image(surface.paths[0])
    chosen = icons.current_path()
    c._stage('quick_panel_thumbnail_size', 100);c.discard()
    assert icons.current_path() == chosen


def test_numberbox_keyboard_hit_regions_bounds_and_wheel(surface):
    box = CompactNumberBox()
    box.setRange(10, 100);box.setSingleStep(5);box.setValue(50);box.show()
    settle(surface.app)
    assert not box.up_button.geometry().intersects(box.down_button.geometry())
    assert box.up_button.focusPolicy() == box.down_button.focusPolicy() == Qt.NoFocus
    QTest.mouseClick(box.up_button, Qt.LeftButton);assert box.value() == 55
    QTest.keyClick(box.editor, Qt.Key_Down);assert box.value() == 50
    box.editor.selectAll();QTest.keyClicks(box.editor,'73');QTest.keyClick(box.editor,Qt.Key_Return)
    assert box.value() == 73
    event = QWheelEvent(QPointF(5,5),QPointF(5,5),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
    QApplication.sendEvent(box.editor,event);assert box.value() == 73
    box.setValue(100);assert not box.up_button.isEnabled()
    box.setValue(10);assert not box.down_button.isEnabled()
    box.close();box.deleteLater()


def test_accent_preview_cancel_accept_save_discard(surface, settings):
    c=settings;c._select_page(1);c._show_tab(0)
    row=c._rows['accent_color'][0]
    saved=row.value()
    c._stage('accent_color','#2468ac');row.set_value('#2468ac')
    row.choose_color();picker=row.picker
    picker.set_color(QColor('#ab1234'))
    deadline=time.monotonic()+1
    while c.pending.get('accent_color')!='#ab1234' and time.monotonic()<deadline:
        QTest.qWait(10)
    assert c.pending['accent_color']=='#ab1234'
    assert surface.config.config['accent_color'].lower()==saved
    picker.reject()
    assert row.value()=='#2468ac' and c.pending['accent_color']=='#2468ac'
    row.choose_color();picker=row.picker
    picker.hsv_numbers[0].setValue(120)
    picker.hsv_numbers[1].setValue(100)
    picker.hsv_numbers[2].setValue(100)
    assert picker.color.name()=='#00ff00'
    picker.accept();assert c.pending['accent_color']=='#00ff00'
    c.save();assert surface.config.config['accent_color']=='#00ff00'
    row.choose_color();row.picker.set_color(QColor('#ff0000'));row.picker.accept();c.discard()
    assert row.value()=='#00ff00' and surface.config.get('accent_color')=='#00ff00'


@pytest.mark.parametrize('language',['en','zh_TW','ja'])
def test_narrow_settings_tabs_and_controls_languages(surface, settings, language):
    c=settings;i18n_engine.set_language(language)
    c.resize(820,680)
    for i,(_,tabs) in enumerate(c._icon_pages()):
        c._select_page(i)
        for j in range(len(tabs)):
            c._show_tab(j);settle(surface.app)
            assert c.body_widget.width() <= c.scroll.viewport().width(), (i,j,[(r.title_label.text(),r.minimumSizeHint().width()) for r in c.body_widget.findChildren(__import__('fluent_ui.components.setting_rows',fromlist=['SettingRow']).SettingRow)])
            for row, _ in c._rows.values():
                if not row.isVisible():continue
                assert '[MISSING' not in row.title_label.text()
                if hasattr(row,'spin'):
                    assert row.rect().contains(row.spin.geometry())
    i18n_engine.set_language('zh')


def test_titlebar_icon_service_geometry_and_hit_area(surface, monkeypatch):
    from fluent_ui.main_window import MainWindow
    from fluent_ui.window_shell import NekoriWindow, NekoriTitleBar, add_shell_accent
    from fluent_ui.components.interaction_controls import IconDropDownButton
    from services.app_icon import ApplicationIconService
    from qfluentwidgets import TransparentToolButton, FluentIcon as FIF
    w=NekoriWindow();w.setTitleBar(NekoriTitleBar(w));w.config=surface.config
    w.app_icon=ApplicationIconService(surface.config);w.tray_icon=Mock()
    add_shell_accent(w)
    w.titleBar.titleLabel.setText('NEKORI');w.titleBar.iconLabel.show()
    gear=TransparentToolButton(FIF.SETTING,w.titleBar);gear.setFixedSize(28,28)
    w.titleBar.settingsButton=gear;w.titleBar.hBoxLayout.insertWidget(3,gear)
    MainWindow.reload_application_icon(w)
    w.show()
    for width in (1080,780,420):
        w.resize(width,480);settle(surface.app);w.accent_line.reposition()
        assert not w.titleBar.canDrag(gear.geometry().center())
        assert w.accent_line.testAttribute(Qt.WA_TransparentForMouseEvents)
        if w.accent_line.isVisible():
            assert w.accent_line.geometry().bottom()<gear.geometry().top()
            assert w.accent_line.geometry().left()==10
            assert w.accent_line.geometry().right()<w.width()-8
    w.app_icon.set_from_image(surface.paths[0]);MainWindow.reload_application_icon(w)
    assert w.windowIcon().cacheKey()==QApplication.instance().windowIcon().cacheKey()
    assert w.tray_icon.setIcon.call_count==2
    assert ApplicationIconService(surface.config).current_path()==w.app_icon.current_path()
    w.app_icon.reset();MainWindow.reload_application_icon(w)
    assert w.tray_icon.setIcon.call_count==3
    w.close();w.deleteLater()


def test_hotkey_conflict_inline_and_export_saved_only(surface, settings, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    c=settings;c._select_page(2);c._show_tab(0)
    main=c._rows['global_hotkey'][0]
    quick=c._rows['quick_panel_hotkey'][0]
    main.set_value('ctrl+shift+k');main.changed.emit()
    quick.set_value('shift+ctrl+k');quick.changed.emit()
    assert not c.btn_save.isEnabled() and not c.save()
    assert main.hint_label.text()==quick.hint_label.text()
    assert not c.feedback_host.notices and not c.feedback_host.toasts
    quick.set_value('alt+2');quick.changed.emit();assert c.btn_save.isEnabled()
    c._stage('accent_color','#123456')
    path=surface.tmp/'export.json'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),'JSON'))
    c._export_settings()
    exported=json.loads(path.read_text(encoding='utf-8'))
    assert exported['accent_color']==surface.config.config['accent_color']
    assert exported['global_hotkey']==surface.config.config['global_hotkey']


def test_tool_local_tasks_real_cancel_and_suzu_preview(surface, monkeypatch):
    from fluent_ui.views.qq_scan_view import QQScanInterface
    from fluent_ui.views.tg_sticker_view import TGStickerInterface
    from fluent_ui.components.feedback import feedback_for
    from fluent_ui.components.exchange_task_dialog import run_exchange_task
    from services.suzu_migration import SuzuMigrationService
    from services.exchange_export import ExchangeExportService
    monkeypatch.setattr(QQScanInterface,'populateUserComboBox',lambda _:None)
    qq=QQScanInterface(config_service=surface.config);tg=TGStickerInterface()
    for view in (qq,tg):
        assert view.tooltip.host is feedback_for(view)
        assert view.tooltip.host is not surface.g.feedback_host
        view.tooltip.show('Task');assert view.feedback_host.task_active
        view.tooltip.update('3 / 7',current=3,total=7)
        assert view.feedback_host.progress.value()==3 and view.feedback_host.progress.maximum()==7
        view.tooltip.fail('Error','Cannot read')
        assert view.feedback_host.notices[-1][2]
    from types import SimpleNamespace
    assert feedback_for(SimpleNamespace(view=tg,gallery_interface=surface.g)) is tg.feedback_host
    worker=Mock();worker.isRunning.return_value=True;qq._current_worker=worker
    qq.tooltip.show('Task');qq.feedback_host.action_button.click();worker.cancel.assert_called_once()
    qq._current_worker=None
    qq.tooltip.show('Scan', cancellable=False)
    assert qq.feedback_host.action_button.isHidden()
    result=run_exchange_task(tg,'Task',lambda progress: (progress(2,2,'Done'),42)[1])
    assert result==42 and not tg.feedback_host.task_active
    assert not surface.g.feedback_host.task_active
    # Parsing for preview must not mutate the destination library.
    package=surface.tmp/'preview.zip'
    ExchangeExportService(storage=surface.storage).export_zip(str(package))
    before=surface.storage.index.content(ROOT)
    preview=SuzuMigrationService(surface.storage).preview_package(package)
    assert preview['resources']>0 and preview['nodes']>0
    assert surface.storage.index.content(ROOT)==before
    qq.shutdown();tg.shutdown()
    qq.close();tg.close();qq.deleteLater();tg.deleteLater();settle(surface.app)
