"""The same gallery controls keep their position when category tabs hide."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from services.library_index import ROOT
from test_phase2_interaction import surface, settle


def test_tools_stay_right_across_root_category_and_narrow_width(surface):
    g = surface.g
    tools = g.size_slider.parentWidget()
    for width in (1180, 900):
        g.resize(width, 760)
        positions = []
        for node in (surface.parent, ROOT, surface.parent, ROOT):
            g.set_node(node)
            settle(surface.app)
            positions.append(tools.geometry().right())
            assert tools.geometry().right() == g.tab_row.width() - 1
            assert tools.width() == tools.sizeHint().width()
            assert not g.btn_recent.geometry().intersects(g.size_slider.geometry())
        assert len(set(positions)) == 1
    value = g.size_slider.value()
    g.size_slider.setFocus()
    QTest.keyClick(g.size_slider, Qt.Key_Right)
    assert g.size_slider.value() > value
    assert g.config.get('thumbnail_size') == g.size_slider.value()
    QTest.mouseClick(g.btn_recent, Qt.LeftButton)
    assert g._recent_view
