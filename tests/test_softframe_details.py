"""User-reported controls, imports and dock regressions; offscreen only."""
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt,QPoint,QMimeData
from PySide6.QtTest import QTest
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings
from fluent_ui.components.controls import MetaButton
from fluent_ui import visual
from services.resource_sort import ResourceSort


def test_clipboard_advertisement_never_decodes_image(surface,monkeypatch):
    class DelayedImage:
        def hasUrls(self):return False
        def hasImage(self):return True
        def imageData(self):raise AssertionError('Availability must not render OLE image')
    monkeypatch.setattr(surface.clipboard,'clipboard',SimpleNamespace(mimeData=lambda:DelayedImage()))
    assert surface.clipboard.has_importable_data(surface.storage.SUPPORTED_FORMATS)


def test_empty_and_unsupported_clipboard_return_without_import(surface,monkeypatch):
    g=surface.g;calls=[]
    monkeypatch.setattr(g,'import_paths_to',lambda *a,**k:calls.append(a))
    monkeypatch.setattr(surface.clipboard,'get_data_from_clipboard',lambda:(None,None))
    g.handle_global_paste()
    text=surface.tmp/'text.txt';text.write_text('plain')
    monkeypatch.setattr(surface.clipboard,'get_data_from_clipboard',lambda:('file',[str(text)]))
    g.handle_global_paste();settle(surface.app)
    assert not calls
    assert g.feedback_host.named_tasks


def test_view_tools_cycle_sort_and_snap_size(surface):
    g=surface.g
    assert g.sidebar.tree.topLevelItemCount()>0
    assert int(g.sidebar.root_count.text())==len(surface.storage.get_all_images())
    assert not hasattr(g,'btn_view_more')
    assert g.btn_filter.parentWidget() is g.search_surface
    initial=ResourceSort(g.content_sort);seen=[]
    for _ in range(3):g.btn_content_sort.click();seen.append(ResourceSort(g.content_sort))
    assert set(seen)==set(ResourceSort) and seen[-1]==initial
    g.size_slider.setValue(127)
    assert g.size_slider.value()==130 and surface.config.get('thumbnail_size')==130
    assert g.btn_paste.dropButton.icon() is not None
    assert g.sidebar.tree.isColumnHidden(1)
    g.sidebar.set_presentation('categorized_icons');settle(surface.app)
    assert g.sidebar.icons.canvas.group_rects
    g.sidebar.set_presentation('tree')
    rail=g.location_rail
    search_y=g.search_box.mapTo(g.top_bar,g.search_box.rect().center()).y()
    current_y=rail.mapTo(g.top_bar,rail.current_rect().center().toPoint()).y()
    assert abs(search_y-current_y)<=1
    assert abs(g.view_commands.mapTo(g.top_bar,g.view_commands.rect().center()).y()-rail.mapTo(g.top_bar,QPoint(0,rail.height()-1)).y())<=1


@pytest.mark.parametrize('placement',['top','bottom','left','right'])
def test_dock_header_stays_anchored_and_index_commands_fit(surface,placement):
    g=surface.g;host=g.tag_panel_host;p=g.tag_panel
    from fluent_ui.components.section_index import SortProjection
    p.set_sort(SortProjection.A_Z)
    host.set_placement(placement);host.set_expanded(True);settle(surface.app)
    before=p.header.mapTo(p,QPoint()).y()
    if host.horizontal:
        sizes=host.splitter.sizes();i=0 if host.splitter.widget(0) is p else 1
        sizes[i]+=35;host.splitter.setSizes(sizes);settle(surface.app)
        assert p.header.mapTo(p,QPoint()).y()==before
    assert p.header.height()==30
    new=p.btn_new.mapTo(p,QPoint());index=p.index_view.mapTo(p,QPoint())
    if host.horizontal:assert new.x()>=index.x()+p.index_view.width()
    else:assert new.y()+p.btn_new.height()<=index.y()
    p._request_position('right');assert host.placement.value=='right'


def test_settings_decisions_colour_and_window_edge_picker(surface,settings):
    c=settings
    assert all(isinstance(b,MetaButton) for b in (c.btn_defaults,c.btn_discard,c.btn_save))
    c._select_page(1);c._show_tab(0);settle(surface.app)
    color=c._rows['accent_color'][0];assert color.rgb.text()==color.color.name().upper()
    assert c.preview_switch.isCheckable() and not hasattr(c.preview_switch,'checkedChanged')
    c._show_tab(1);settle(surface.app)
    row=c._rows['tag_panel_placement'][0];row.buttons['left'].click()
    assert row.value()=='left' and c.pending['tag_panel_placement']=='left'
    assert row.buttons['left'].parentWidget().__class__.__name__=='DockPositionPicker'
    c._select_page(3);c._show_tab(0);settle(surface.app)
    assert c.library_info.value_label.text()==c._library_path()
    assert c.library_info.value_label.width()>c.library_info.width()*.8


def test_settings_decisions_share_one_row_when_they_fit(surface,settings):
    c=settings;c.resize(930,770);settle(surface.app)
    buttons=(c.btn_defaults,c.btn_discard,c.btn_save)
    assert len({b.y() for b in buttons})==1
    assert all(b.width()>=b.sizeHint().width() for b in buttons)


def test_theme_does_not_requery_sidebar_or_tag_projection(surface,monkeypatch):
    g=surface.g
    monkeypatch.setattr(g.sidebar.tree,'refresh',lambda *a,**k:pytest.fail('Theme rebuilt category tree'))
    monkeypatch.setattr(g,'_rebuild_tag_panel',lambda *a,**k:pytest.fail('Theme queried tag projection'))
    g.refresh_theme();settle(surface.app)
    from qfluentwidgets import setTheme,Theme
    for mode in (Theme.DARK,Theme.LIGHT):
        setTheme(mode,lazy=True);visual.theme.refresh();settle(surface.app)
        g.search_box.grab();g.import_menu.view.grab();settle(surface.app)
        assert g.search_box.styleSheet()==visual.control_style()
        assert g.import_menu.view.styleSheet()==visual.menu_style()


def test_fixed_preview_does_not_cancel_its_own_layout(surface):
    g=surface.g;popup=g.preview_popup;pane=g.scroll_area.viewport()
    popup.apply_presentation(pane)
    popup.show_preview(surface.paths[0],pane.mapToGlobal(pane.rect().center()),180,container_rect=pane.rect())
    settle(surface.app)
    assert popup.isVisible()
    assert pane.rect().contains(popup.geometry())
    assert abs(pane.rect().bottom()-popup.geometry().bottom()-4)<=1
    popup.hide_preview()
