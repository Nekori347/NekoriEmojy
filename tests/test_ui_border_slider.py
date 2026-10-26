"""Local sheet contours and shared slider focus lifecycle."""
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QCursor,QHoverEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QStyle,QStyleOptionSlider
from test_phase2_interaction import surface,settle
from test_tab_overflow import own_paint
from fluent_ui.components.softframe import SoftframeSlider


def test_mouse_focus_slider_has_no_latched_ring_but_keyboard_still_works(surface,monkeypatch):
    s=SoftframeSlider(Qt.Horizontal,surface.g);s.setGeometry(40,40,180,28);s.setRange(0,100);s.setValue(50);s.show()
    monkeypatch.setattr(QCursor,'pos',lambda:surface.g.mapToGlobal(QPoint(500,600)))
    s._handle_hover=False;s.clearFocus();baseline=s.grab().toImage()
    s.setFocus(Qt.MouseFocusReason);settle(surface.app)
    assert s.hasFocus()
    assert s.grab().toImage()==baseline
    QTest.keyClick(s,Qt.Key_Right);assert s.value()==51
    assert s.grab().toImage()!=baseline
    s.close();s.deleteLater();settle(surface.app)


def test_one_row_painter_owns_tools_flare_and_active_tab_contour(surface):
    g=surface.g;row=g.tab_row;tabs=g.category_tabs;tools=g.size_slider.parentWidget();settle(surface.app)
    image=own_paint(row)
    assert image.pixelColor(tools.x(),row.height()-4).alpha()>0,'missing left lower ear curve'
    body=tabs.content_tab_rect(tabs.currentIndex())
    assert own_paint(tabs).pixelColor(body.left(),24).alpha()==0,'tab still draws a second sheet contour'


def test_content_antialias_is_not_cut_by_its_integer_mask(surface):
    pane=surface.g.content_pane;settle(surface.app)
    clipped=own_paint(pane);mask=pane.mask();pane.clearMask();unclipped=own_paint(pane);pane.setMask(mask)
    for x in range(14):
        for y in range(pane.height()-14,pane.height()):
            assert clipped.pixelColor(x,y)==unclipped.pixelColor(x,y)
            xx=pane.width()-1-x
            assert clipped.pixelColor(xx,y)==unclipped.pixelColor(xx,y)


@pytest.mark.parametrize('orientation',[Qt.Horizontal,Qt.Vertical])
def test_slider_release_hover_capture_and_values(surface,monkeypatch,orientation):
    s=SoftframeSlider(orientation,surface.g);s.setGeometry(40,40,180,180);s.setRange(0,100);s.setValue(50);s.setSingleStep(2);s.show();s.raise_()
    position=[s.mapToGlobal(QPoint(-10,-10))]
    monkeypatch.setattr(QCursor,'pos',lambda:position[0])
    option=QStyleOptionSlider();s.initStyleOption(option)
    handle=s.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,s)
    center=handle.center();position[0]=s.mapToGlobal(center)
    surface.app.sendEvent(s,QHoverEvent(QEvent.HoverMove,QPointF(center),QPointF(center)))
    assert s._handle_hover
    QTest.mousePress(s,Qt.LeftButton,pos=center)
    assert s.isSliderDown() and s._handle_drag
    QTest.mouseRelease(s,Qt.LeftButton,pos=center)
    assert not s.isSliderDown() and not s._handle_drag and s._handle_hover
    surface.app.sendEvent(s,QEvent(QEvent.UngrabMouse))
    assert s._handle_hover and not s._handle_drag
    position[0]=s.mapToGlobal(QPoint(-10,-10));surface.app.sendEvent(s,QHoverEvent(QEvent.HoverLeave,QPointF(-10,-10),QPointF(center)))
    assert not s._handle_hover
    value=s.value();QTest.keyClick(s,Qt.Key_Right if orientation==Qt.Horizontal else Qt.Key_Up)
    assert s.value()==value+2
    # Track clicks retain the existing QSlider action instead of becoming a toggle.
    before=s.value();QTest.mouseClick(s,Qt.LeftButton,pos=QPoint(s.width()-10,s.height()//2) if orientation==Qt.Horizontal else QPoint(s.width()//2,10))
    assert s.value()!=before
    s.setEnabled(False);assert not s.isSliderDown() and not s._handle_hover
    s.setEnabled(True);s.hide();assert not s._handle_drag and not s._handle_hover
    s.deleteLater();settle(surface.app)
