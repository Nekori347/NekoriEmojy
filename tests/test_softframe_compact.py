"""User regressions: editor state, tight geometry, transparent icons and identity."""
import pytest
from PySide6.QtCore import Qt,QPoint,QRectF
from PySide6.QtGui import QPainter,QImage,QRegion
from PySide6.QtWidgets import QWidget
from PySide6.QtTest import QTest
from qfluentwidgets import Theme,setTheme
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings
from test_demo_local_fixes import main
from fluent_ui import visual


def painted(widget):
    result=QImage(widget.size(),QImage.Format_ARGB32);result.fill(Qt.transparent)
    p=QPainter(result);widget.render(p,QPoint(),QRegion(),QWidget.DrawChildren);p.end()
    return result


def test_live_preview_is_an_immediate_editor_preference(surface,settings):
    c=settings;old=c.preview_enabled
    c.preview_switch.click();settle(surface.app)
    assert not c.pending and not c.has_pending_changes()
    assert not c.btn_save.isEnabled() and not c.btn_discard.isEnabled()
    assert surface.config.config['settings_preview']==(not old)
    c._stage('thumbnail_size',180)
    staged=dict(c.pending)
    c.preview_switch.click();settle(surface.app)
    assert c.pending==staged
    c.discard()
    assert c.preview_enabled==old and not c.pending
    from services.config import ConfigService
    assert ConfigService(surface.tmp/'app').get('settings_preview')==old


@pytest.mark.parametrize('placement',['left','right','top','bottom'])
def test_index_and_add_share_a_compact_axis_and_collapse_is_clear(surface,placement):
    from fluent_ui.components.section_index import SortProjection
    g=surface.g;host=g.tag_panel_host;panel=g.tag_panel
    panel.set_sort(SortProjection.A_Z);host.set_placement(placement);host.set_expanded(True);settle(surface.app)
    axis=panel.axis_strip;index=panel.index_view;button=panel.btn_new
    axis_size=visual.SECTION_INDEX_COMPACT_EXTENT
    a=index.mapTo(axis,index.rect().center());b=button.mapTo(axis,button.rect().center())
    if host.horizontal:
        assert axis.height()==axis_size and a.y()==b.y()
    else:
        assert axis.width()==axis_size and a.x()==b.x()
    assert button.width()==button.height()==axis_size
    handle=host.splitter.handle(1)
    assert any(painted(handle).pixelColor(handle.width()//2,y).alpha() for y in range(handle.height()))
    host.set_expanded(False);settle(surface.app)
    image=painted(handle)
    assert not any(image.pixelColor(x,y).alpha() for y in range(image.height()) for x in range(image.width()))


def test_main_width_divider_is_continuous_and_root_title_is_tight(surface):
    g=surface.g;handle=g.splitter.handle(1);image=painted(handle)
    for fraction in (.1,.5,.9):
        assert image.pixelColor(handle.width()//2,int(handle.height()*fraction)).alpha()>0
    sidebar=g.sidebar
    assert sidebar.root_count.y()==sidebar.root_label.geometry().bottom()+1
    assert sidebar.btn_root.height()==36
    footer=g.btn_settings.parentWidget()
    from fluent_ui.presentation.glyphs import BrandLockup
    brand=footer.findChild(BrandLockup)
    assert brand.height()<=34 and brand.geometry().bottom()==g.btn_settings.geometry().bottom()


def test_image_gap_stays_four_pixels_without_destroying_size():
    from fluent_ui.components.virtual_gallery import FlowIndex
    entries=[dict(kind='resource',id=str(i),_parent='root') for i in range(20)]
    index=FlowIndex();index.layout(entries,754,112)
    rows={}
    for rect in index.rects:
        assert rect.width()==112
        rows.setdefault(rect.top(),[]).append(rect)
    for rects in rows.values():
        for left,right in zip(rects,rects[1:]):assert right.left()-left.right()-1==4
    tops=sorted(rows)
    assert tops[1]-tops[0]-112==4


def test_size_slider_thumb_has_clear_edges_at_both_limits(surface):
    slider=surface.g.size_slider
    for value in (slider.minimum(),slider.maximum()):
        slider.setValue(value);slider.setFocus();settle(surface.app)
        image=painted(slider)
        white=[(x,y) for y in range(image.height()) for x in range(image.width())
               if (c:=image.pixelColor(x,y)).alpha()>200 and min(c.red(),c.green(),c.blue())>230]
        assert white
        left=min(x for x,y in white);right=max(x for x,y in white)
        assert left>=1 and right<image.width()-1
        assert 24<=right-left+1<=28


@pytest.mark.parametrize('dark',[False,True])
def test_meta_actions_are_white_or_transparent(surface,settings,dark):
    setTheme(Theme.DARK if dark else Theme.LIGHT);visual.theme.refresh();settle(surface.app)
    for button in (settings.btn_defaults,settings.btn_discard,settings.btn_save):
        button.setEnabled(False);image=painted(button)
        assert image.pixelColor(button.width()//2,7).alpha()==0
        button.setEnabled(True);image=painted(button);c=image.pixelColor(button.width()//2,7)
        assert c.alpha()==255 and min(c.red(),c.green(),c.blue())>=245
    setTheme(Theme.LIGHT);visual.theme.refresh()


def test_caption_commands_have_shared_geometry_and_window_state(surface,monkeypatch):
    from fluent_ui.window_shell import CaptionButton
    from fluent_ui.main_window import MainWindow
    from qframelesswindow.titlebar.title_bar_buttons import TitleBarButtonState
    # Offscreen has no HWND; exercise the same command through Qt state changes.
    monkeypatch.setattr('qframelesswindow.utils.toggleMaxState',lambda w:w.showNormal() if w.isMaximized() else w.showMaximized())
    monkeypatch.setattr('fluent_ui.views.settings_center.AutostartService.is_enabled',lambda _:False)
    w=MainWindow(surface.storage,surface.clipboard,surface.config);w.gallery_interface.focus_timer.stop();w.show()
    bar=w.titleBar;settle(surface.app)
    for button in (bar.minBtn,bar.maxBtn,bar.closeBtn):
        assert isinstance(button,CaptionButton) and button.size().width()==28 and button.height()==24
        assert button.icon_rect().center()==button.highlight_rect().center()
        button.setState(TitleBarButtonState.HOVER);assert not button.grab().isNull()
    QTest.mouseClick(bar.maxBtn,Qt.LeftButton);settle(surface.app)
    assert w.isMaximized() and bar.maxBtn._maximized
    QTest.mouseClick(bar.maxBtn,Qt.LeftButton);settle(surface.app)
    assert not w.isMaximized() and not bar.maxBtn._maximized
    assert bar.iconLabel.height()==22
    assert bar.iconLabel.geometry().bottom()==bar.minBtn.geometry().bottom()
    w.close();w.deleteLater();settle(surface.app)


def test_clipboard_import_glyph_has_no_background(surface):
    from fluent_ui.presentation.glyphs import ClipboardImportIcon
    image=QImage(64,64,QImage.Format_ARGB32);image.fill(Qt.transparent)
    p=QPainter(image);ClipboardImportIcon().render(p,QRectF(4,4,50,50),fill='#ffffff');p.end()
    visible=[image.pixelColor(x,y) for y in range(64) for x in range(64) if image.pixelColor(x,y).alpha()>0]
    assert visible and all(c.red()==c.green()==c.blue()==255 for c in visible)


def test_search_prompt_and_actual_fields(surface):
    s=surface;g=s.g;path=s.paths[0]
    record=s.storage.index.resource(path)
    s.storage.index.set_search_fields(record['id'],ocr_text='SavedImageWord')
    for term in ('alpha','cat','parent','SavedImageWord'):
        assert path in s.storage.search_images(term,'全部表情')
    assert g.search_box.placeholderText()=='搜索名称、标签或关键词…'
    g.set_search_keyword('SavedImageWord');g._execute_search();settle(s.app)
    assert path in [entry.get('path') for entry in g._entries]


def test_settings_and_brand_use_the_same_version(surface,settings):
    from services.update_service import current_version
    from services.version_info import version_info
    from fluent_ui.components.setting_rows import InfoRow
    from fluent_ui.presentation.glyphs import BrandLockup
    c=settings;c._select_page(4);settle(surface.app)
    assert 'v'+current_version() in [r.value_label.text() for r in c.body_widget.findChildren(InfoRow)]
    assert version_info()['version']==current_version()=='0.1.1'
    assert surface.g.sidebar.findChild(BrandLockup).version=='v0.1.1'
