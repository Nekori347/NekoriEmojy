"""Common sheet ownership and immediate tag-header interaction contracts."""
import pytest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from test_phase2_interaction import surface,settle
from test_tag_panel_collapse import scene
from test_tab_overflow import own_paint


def test_sheet_surface_does_not_fill_unselected_tab_area(surface):
    g=surface.g;tabs=g.category_tabs
    tabs.set_tabs(['Selected','Other','Third']);settle(surface.app)
    rect=tabs.content_tab_rect(1)
    point=tabs.mapTo(g.sheet_surface,rect.center())
    assert own_paint(g.sheet_surface).pixelColor(point).alpha()==0


def test_expanded_header_title_click_collapses_without_touching_commands(scene):
    app,window,host,panel,*_=scene
    host.set_placement('top');settle(app)
    QTest.mouseClick(panel.title_label,Qt.LeftButton);settle(app)
    assert not host.expanded


def test_first_axis_change_has_final_control_geometry_without_a_paint(scene):
    app,window,host,panel,*_=scene
    for placement in ('right','top','left','bottom','right','left'):
        host.set_placement(placement)
        control=panel.btn_collapse
        if host.horizontal:
            assert abs(control.mapTo(panel.header,control.rect().center()).x()-panel.header.rect().center().x())<=2
        else:
            assert abs(control.geometry().center().y()-panel.rect().center().y())<=1


def test_first_expansion_after_collapsed_resize_is_centered_before_animation(scene,monkeypatch):
    from PySide6.QtWidgets import QApplication
    app,window,host,panel,*_=scene
    host.set_placement('top');host.set_expanded(False);settle(app)
    window.resize(650,500);settle(app)
    monkeypatch.setattr(QApplication,'platformName',staticmethod(lambda:'windows'))
    host.set_expanded(True)
    assert abs(panel.btn_collapse.mapTo(panel.header,panel.btn_collapse.rect().center()).x()-panel.header.rect().center().x())<=2
    host._motion.stop();host._finish_motion()


@pytest.mark.parametrize('placement',['top','bottom','left','right'])
def test_header_command_priority_reserved_edges_and_one_toggle(scene,monkeypatch,placement):
    from fluent_ui.components import dialogs
    app,window,host,panel,*_=scene
    host.set_placement(placement);settle(app)
    prompts=[];monkeypatch.setattr(dialogs,'prompt_text',lambda *a,**kw:(prompts.append(1) or '',False))
    for button in (panel.btn_new,panel.btn_sort):
        QTest.mouseClick(button,Qt.LeftButton,pos=QPoint(1,button.height()//2));settle(app)
        assert host.expanded
        point=button.mapTo(panel.header,QPoint(-1,button.height()//2))
        QTest.mouseClick(panel.header,Qt.LeftButton,pos=point);settle(app)
        assert host.expanded
        button.setEnabled(False)
        point=button.mapTo(panel.header,button.rect().center())
        QTest.mouseClick(panel.header,Qt.LeftButton,pos=point);settle(app)
        assert host.expanded
        button.setEnabled(True)
    assert prompts==[1]
    QTest.mouseClick(panel.title_label,Qt.LeftButton);settle(app)
    assert not host.expanded
    QTest.mouseClick(panel.chrome,Qt.LeftButton);settle(app)
    assert host.expanded


def test_header_hover_excludes_commands_and_drops_after_axis_change(scene,monkeypatch):
    from PySide6.QtGui import QCursor
    app,window,host,panel,*_=scene
    host.set_placement('top');settle(app)
    position=[panel.title_label.mapToGlobal(panel.title_label.rect().center())]
    monkeypatch.setattr(QCursor,'pos',lambda:position[0])
    assert panel.btn_collapse._action_hovered()
    position[0]=panel.btn_new.mapToGlobal(panel.btn_new.rect().center())
    assert not panel.btn_collapse._action_hovered()
    panel.btn_new.setEnabled(False)
    assert not panel.btn_collapse._action_hovered()
    position[0]=window.mapToGlobal(QPoint(-10,-10))
    panel.btn_collapse.setDown(True);host.set_placement('left');settle(app)
    assert not panel.btn_collapse.isDown() and not panel.btn_collapse._action_hovered()


def test_header_context_menu_cancel_does_not_toggle_the_panel(scene):
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    app,window,host,panel,*_=scene
    panel._show_position_menu(QPoint(8,10));settle(app)
    menus=[menu for menu in window.findChildren(SafeRoundMenu) if menu.isVisible()]
    assert menus and host.expanded
    for menu in menus:menu.close()
    settle(app)
    assert host.expanded and not panel.btn_collapse.isDown()


def test_shared_fill_and_outline_follow_scroll_selection_and_theme(surface):
    from qfluentwidgets import Theme,setTheme
    from fluent_ui import visual
    g=surface.g;sheet=g.sheet_surface;tabs=g.category_tabs
    try:
        for theme in (Theme.LIGHT,Theme.DARK):
            setTheme(theme);visual.theme.refresh()
            for width in (1180,760):
                g.resize(width,760);settle(surface.app)
                tabs.set_tabs(['Scope']+['Category '+str(i) for i in range(12)])
                for index in (0,5,11,0):
                    tabs.setCurrentIndex(index);settle(surface.app)
                    fill=own_paint(sheet);stroke=own_paint(sheet.outline)
                    for i in range(tabs.count()):
                        r=tabs.content_tab_rect(i);p=r.center()
                        if not tabs._tab_viewport().contains(p):continue
                        p=tabs.mapTo(sheet,p)
                        assert (fill.pixelColor(p).alpha()>0)==(i==index)
                    # The final structure crosses both former widget clip ends.
                    y=g.content_pane.y()
                    assert all(stroke.pixelColor(0,yy).alpha()>0 for yy in (y-1,y,y+1))
                    assert own_paint(g.content_pane).pixelColor(0,20).alpha()==0
                    assert g.childAt(g.mapFromGlobal(sheet.outline.mapToGlobal(QPoint(30,y+70)))) is not sheet.outline
                buttons=[b for b in tabs._scroll_buttons if b.isVisible() and b.isEnabled()]
                if buttons:buttons[-1].click();settle(surface.app)
                point=tabs.mapTo(sheet,tabs.content_tab_rect(tabs.currentIndex()).center())
                if tabs._tab_viewport().contains(tabs.content_tab_rect(tabs.currentIndex()).center()):
                    assert own_paint(sheet).pixelColor(point).alpha()>0
    finally:setTheme(Theme.LIGHT);visual.theme.refresh()
