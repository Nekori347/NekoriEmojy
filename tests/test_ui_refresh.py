"""Approved UI changes: actual paint, control geometry and unchanged actions."""
import pytest
from PySide6.QtCore import Qt, QPoint, QRectF
from PySide6.QtGui import QPainter, QPixmap, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from fluent_ui import visual
from fluent_ui.icons import Icon
from fluent_ui.components.emoji_card import EmojiCard
from test_phase2_interaction import surface, settle
from test_l1_l3_interaction import settings


def test_icons_render_actual_sizes_and_bindings_survive_refresh(surface):
    from services.resource_sort import ResourceSort
    from fluent_ui.components.section_index import SortProjection
    g=surface.g
    for icon in (Icon.IMPORT_MENU,Icon.NEW_TAG,Icon.NEW_CATEGORY,Icon.TREE_VIEW,
                 Icon.MANUAL_ORDER,Icon.RECENT_ADDED,Icon.OLDEST_ADDED,
                 Icon.CATEGORY_ICON,Icon.APPLICATION_ICON):
        assert QSvgRenderer(icon.path()).isValid()
        for size in (14,16,18,20):
            pix=QPixmap(size,size);pix.fill(Qt.transparent)
            painter=QPainter(pix);icon.render(painter,QRectF(0,0,size,size),fill='#778899');painter.end()
            image=pix.toImage()
            assert any(image.pixelColor(x,y).alpha() for x in range(size) for y in range(size))
    assert g.btn_paste.dropButton._icon==Icon.IMPORT_MENU
    assert type(g.btn_paste.button._icon).__name__=='ClipboardImportIcon'
    assert g.sidebar.btn_new._icon==Icon.NEW_CATEGORY
    g.sidebar.apply_presentation()
    assert g.sidebar.btn_view_mode._icon==Icon.TREE_VIEW
    for placement in ('top','bottom','left','right'):
        g.tag_panel_host.set_placement(placement);settle(surface.app)
        assert g.tag_panel.btn_new._icon==Icon.NEW_TAG
    for sort in ResourceSort:
        g.set_content_sort(sort)
        assert g.btn_content_sort._icon=={ResourceSort.MANUAL:Icon.MANUAL_ORDER,
            ResourceSort.RECENT_ADDED:Icon.RECENT_ADDED,ResourceSort.OLDEST_ADDED:Icon.OLDEST_ADDED}[sort]
    for mode in SortProjection:
        g.sidebar.btn_sort.set_mode(mode);g.sidebar.btn_sort.refresh()
        assert not g.sidebar.btn_sort.icon().isNull()


def test_preview_and_tools_share_row_and_quiet_checked_surface(settings):
    c=settings;settle(QApplication.instance())
    for width in (900,1180):
        c.resize(width,760);settle(QApplication.instance())
        a,b=c.preview_switch,c.btn_tools
        assert a.height()==b.height()==32
        assert a.mapTo(c,QPoint(0,0)).y()==b.mapTo(c,QPoint(0,0)).y()
    button=c.preview_switch;button._hover_animation.stop();button._hover=0
    colors=[]
    for checked in (False,True):
        button.setChecked(checked);button.setDown(False)
        image=button.grab().toImage();colors.append(image.pixelColor(4,button.height()//2))
        assert button.isChecked()==checked
    # Checked changes the ink/outline, not a selected fill behind the label.
    assert colors[0]==colors[1]
    c.discard()


def test_card_hover_dominates_selected_and_short_top_mark(surface):
    card=EmojiCard(surface.paths[0],size=120,parent=surface.g,load_image=False)
    card.show();card._hovered=False
    accent=QColor(visual.colors()['accent'])
    def count(image,y):
        return sum(image.pixelColor(x,y)==accent for x in range(image.width()))
    try:
        card.is_selected=True;selected=card.grab().toImage()
        card._hovered=True;both=card.grab().toImage()
        card.is_selected=False;hover=card.grab().toImage()
        # Selected+hover uses hover's sole contour, not selected's weaker frame.
        for y in (20,30,40):
            assert [both.pixelColor(x,y) for x in range(6)]==[hover.pixelColor(x,y) for x in range(6)]
        assert 25<count(selected,5)<100
        card._hovered=False;card.is_selected=True
        assert card.grab().toImage()==selected
    finally:card.close();card.deleteLater()


def test_open_sheet_gaps_follow_tabs_clip_and_static_tools(surface):
    from test_tab_overflow import own_paint
    from PySide6.QtWidgets import QToolButton
    from PySide6.QtTest import QTest
    from PySide6.QtGui import QRegion
    g=surface.g;row=g.tab_row;tabs=g.category_tabs;tools=g.size_slider.parentWidget()
    for width in (1180,760):
        g.resize(width,760);settle(surface.app)
        tabs.set_tabs(['Scope']+['Category '+str(i) for i in range(12)])
        for index in (0,6,11):
            tabs.setCurrentIndex(index);settle(surface.app)
            image=own_paint(g.sheet_surface.outline)
            shape,_,_=g.sheet_surface.structure_paths()
            body=tabs.content_tab_rect(index)
            visible=tabs._tab_viewport().intersected(QRegion(body.adjusted(-7,0,7,0))).boundingRect()
            if not visible.isEmpty():
                x=tabs.x()+visible.center().x()
                assert shape.contains(QPoint(x,row.height()-2))
                assert image.pixelColor(x,row.height()-1).alpha()>0  # retained inner divider
            assert shape.contains(tools.geometry().center())
            assert image.pixelColor(tools.x()+tools.width()//2,row.height()-1).alpha()>0
            assert g.btn_recent.geometry().left()>=5
            assert g.btn_recent.geometry().top()>=4
            assert g.size_slider.geometry().right()<=tools.width()-6
        before=tools.geometry();QTest.mouseClick(g.btn_recent,Qt.LeftButton);settle(surface.app)
        assert tools.geometry()==before
    tabs.hide();settle(surface.app)
    shape,_,rules=g.sheet_surface.structure_paths()
    assert len(rules)==1 and shape.contains(tools.geometry().center())


def test_title_double_rule_and_dock_overlay(surface):
    from PySide6.QtCore import QRect
    g=surface.g
    for width in (1180,760):
        g.resize(width,760);settle(surface.app)
        band=g.top_bar;rail=g.location_rail;image=band.grab().toImage()
        y=rail.y()+rail.height()+2
        spans=[]
        for color in ('#DF52AC','#FFF500','#00E5FF'):
            xs=[x for x in range(image.width()) if image.pixelColor(x,y).name()==color.lower()]
            assert xs
            spans.append((min(xs),max(xs)))
        assert max(b-a for a,b in spans)-min(b-a for a,b in spans)<=1
        assert abs((spans[-1][1]+1-spans[0][0])/(rail.width()-rail.axis_left)-.618)<.02
        assert spans[0][0]==rail.x()+rail.axis_left
        expected_gap=(rail.width()-rail.axis_left)*.618*.04
        assert all(abs((spans[i+1][0]-spans[i][1]-1)-expected_gap)<=2 for i in (0,1))
        assert rail.axis_left==2 and y==rail.y()+rail.height()+2
    host=g.tag_panel_host
    # Establish UI-C feasibility using the actual four-way split allocation.
    for placement in ('top','bottom','left','right'):
        host.set_placement(placement);host.set_expanded(True,persist=False);settle(surface.app)
        panel=QRect(host.panel.mapTo(host,QPoint()),host.panel.size())
        content=QRect(host.content.mapTo(host,QPoint()),host.content.size())
        assert panel.intersects(content)
        host.set_expanded(False,persist=False);settle(surface.app)
        assert not host.expanded
