"""Shared Recent projection and stop-notice regression on disposable data."""
from PySide6.QtCore import Qt
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings


def test_recent_shared_updates_and_returns_to_category_context(surface):
    s=surface;g=s.g
    original=list(g._entries);node=g.current_node
    g.toggle_recent_view(True);settle(s.app)
    assert not g._entries and g.placeholder.text()=='暂无最近使用的表情'
    s.storage.add_recent_image(s.paths[0]);s.storage.add_recent_image(s.paths[1]);settle(s.app)
    assert [e['path'] for e in g._entries]==s.storage.get_recent_images()==[s.paths[1],s.paths[0]]
    from fluent_ui.components.quick_panel import QuickPanel
    q=QuickPanel(s.storage,s.clipboard,s.config)
    q.show();q._perform_search(force=True);settle(s.app)
    assert list(q._cached_results)==s.storage.get_recent_images()
    s.storage.add_recent_image(s.paths[0]);settle(s.app)
    assert list(q._cached_results)==[e['path'] for e in g._entries]==[s.paths[0],s.paths[1]]
    q.search_box.setText('beta');q._perform_search(force=True);settle(s.app)
    assert q.search_box.text()=='beta'
    q.search_box.clear();q._perform_search(force=True);settle(s.app)
    assert list(q._cached_results)==s.storage.get_recent_images()
    from PySide6.QtTest import QTest
    QTest.mouseClick(g.category_tabs,Qt.LeftButton,pos=g.category_tabs.tabRect(g.category_tabs.currentIndex()).center());settle(s.app)
    assert g.current_node==node and [e['id'] for e in g._entries]==[e['id'] for e in original]
    assert g.size_slider.minimum()==60 and g.size_slider.maximum()==300
    assert g.size_slider.width()==88
    q.shutdown();q.close()


def test_recent_limit_entry_moved_without_mutating_value_or_retention(settings):
    c=settings;c.config.set('recent_limit',47)
    c._select_page(3);c._show_tab(0)
    row=c._rows['recent_limit'][0]
    assert '主面板与快速面板共用此设置。' in row.hint_label.text()
    c._select_page(1);c._show_tab(2)
    assert 'recent_limit' not in c._rows
    assert c.config.get('recent_limit')==47


def test_stopped_notice_uses_caption_space_and_clears_task_material(surface):
    g=surface.g;h=g.feedback_host;h.dock_to_caption(g);u=h._caption_ui
    h.upsert_task('ocr','补充识别',kind='ocr',current=1,total=50,cancel=lambda:None)
    h.upsert_task('ocr','文字识别已停止',kind='ocr',state='cancelled',content='完成 12 张，失败 0 张，跳过 38 张')
    settle(surface.app)
    assert u.cover.isVisible() and not u.material.isVisible() and not h.strip.isVisible()
    label=u.cover.label
    assert label.fontMetrics().horizontalAdvance(label.toolTip())<=label.width()
    assert u.bounds()[0]<=u.cover.x() and u.cover.geometry().right()<=u.bounds()[1]
    u.expire_overlay();settle(surface.app)
    assert u.cover.isHidden() and u.material.isHidden() and h.strip.isHidden()
    h.toast('表情已复制',content='未找到可发送的聊天窗口，可手动粘贴。')
    settle(surface.app)
    assert u.bounds()[0]<=u.cover.x() and u.cover.geometry().right()<=u.bounds()[1]
