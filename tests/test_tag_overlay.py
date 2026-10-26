"""Real shared surface, foreground tag composition and stable gallery geometry."""
import pytest
from PySide6.QtCore import Qt,QPoint,QRect
from PySide6.QtGui import QColor
from qfluentwidgets import Theme,setTheme
from fluent_ui import visual
from test_phase2_interaction import surface,settle


def test_tool_group_shares_real_gallery_surface(surface):
    g=surface.g;tools=g.size_slider.parentWidget()
    try:
        for theme in (Theme.LIGHT,Theme.DARK):
            setTheme(theme);visual.theme.refresh();settle(surface.app)
            image=g.grab().toImage()
            inside=tools.mapTo(g,QPoint(4,tools.height()//2))
            viewport=g.scroll_area.viewport();outside=viewport.mapTo(g,QPoint(2,viewport.height()//2))
            assert image.pixelColor(inside)==image.pixelColor(outside)
    finally:setTheme(Theme.LIGHT);visual.theme.refresh()
