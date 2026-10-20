"""Only the three approved RC layout areas; disposable library and Qt input."""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout
from test_phase2_interaction import surface, settle
from test_l1_l3_interaction import settings
from fluent_ui.components.setting_rows import SuzuExportRow
from fluent_ui.presentation.settings import DecisionBar


@pytest.mark.parametrize('width', [700, 950, 1280])
def test_settings_footer_never_wraps_and_preview_is_in_navigation(settings, width):
    c = settings
    c.resize(width, 740)
    for primary, tab in [(0, 0), (3, 2), (4, 0)]:
        c._select_page(primary); c._show_tab(tab); settle(QApplication.instance())
        footer = c.findChild(DecisionBar)
        buttons = [c.btn_defaults, c.btn_discard, c.btn_save]
        assert footer.height() == 64
        assert len({b.mapTo(c, QPoint()).y() for b in buttons}) == 1
        assert buttons[0].mapTo(footer, QPoint()).x() >= 10
        assert footer.width()-buttons[-1].mapTo(footer, QPoint(buttons[-1].width(), 0)).x() == 10
        assert c.preview_switch.mapTo(c, QPoint()).x() < c.nav.mapTo(c, QPoint(c.nav.width(), 0)).x()
        assert c.preview_switch.mapTo(c, QPoint()).y() > c.nav.mapTo(c, QPoint(0, c.nav.height())).y()
        assert all(b.height() == 44 and b.content_geometry()[2].width() == 26 for b in buttons)
        assert all(b.content_geometry()[1].width() >= b.fontMetrics().horizontalAdvance(b.text()) for b in buttons)
        before = [b.geometry() for b in buttons]
        for b in buttons: b.setEnabled(not b.isEnabled())
        settle(QApplication.instance())
        assert [b.geometry() for b in buttons] == before


@pytest.mark.parametrize('width,stacked', [(650, True), (1000, False)])
def test_suzu_export_copy_group_and_original_routes(settings, monkeypatch, width, stacked):
    c = settings
    c.resize(width, 760); c._select_page(3); c._show_tab(2); settle(QApplication.instance())
    row = c.findChild(SuzuExportRow)
    c.scroll.ensureWidgetVisible(row); settle(QApplication.instance())
    assert row.hint_label.text() == '将表情导出为 Suzu 兼容的分享格式。\n不包含 Nekori 的完整分类和排序信息。'
    buttons = [row.controls.itemAt(i).widget() for i in range(2)]
    assert (row.layout().direction() == QBoxLayout.TopToBottom) == stacked, (c.width(),row.width(),row.parentWidget().width(),c.scroll.width(),row.controls.minimumSize().width(),row.hint_label.fontMetrics().horizontalAdvance(row.hint_label.text().splitlines()[1]))
    assert buttons[0].y() == buttons[1].y() and buttons[0].height() == buttons[1].height()
    assert buttons[0].geometry().right() < buttons[1].x()
    assert buttons[1].geometry().right() <= row.width()-20
    assert row.hint_label.height() >= row.hint_label.heightForWidth(row.hint_label.width())
    if stacked: assert buttons[0].y() > row.hint_label.geometry().bottom()
    else: assert row.hint_label.geometry().right() < buttons[0].x()
    calls = []
    monkeypatch.setattr(c, '_legacy_share', calls.append)
    for b in buttons: QTest.mouseClick(b, Qt.LeftButton)
    assert calls == ['all', 'categories']
