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


@pytest.mark.parametrize('placement',['top','bottom','left','right'])
def test_overlay_keeps_gallery_and_scrollbar_geometry(surface,placement):
    from PySide6.QtWidgets import QApplication
    g=surface.g;h=g.tag_panel_host;vp=g.scroll_area.viewport();bar=g.scroll_area.verticalScrollBar()
    original=(vp.size(),g.grid_container.size(),bar.geometry(),g.scroll_area.verticalScrollBar().value())
    created=g.renderer.created;cards=tuple(g._all_card_widgets)
    h.set_placement(placement);h.set_expanded(True,persist=False);settle(surface.app)
    rect=QRect(vp.mapFromGlobal(h.panel.mapToGlobal(QPoint())),h.panel.size())
    assert vp.rect().contains(rect)
    assert h.panel.btn_collapse.parentWidget() is h.panel.header
    assert h.panel.header.height()==30
    available=h.available_rect(vp);assert not available.intersects(rect)
    point=available.center();hit=g.childAt(g.mapFromGlobal(vp.mapToGlobal(point)))
    assert hit is not None and hit is not h.splitter and not h.splitter.isAncestorOf(hit)
    assert g.childAt(g.mapFromGlobal(bar.mapToGlobal(bar.rect().center()))) is bar
    h.panel.btn_collapse.click();settle(surface.app)
    assert not h.expanded and h.panel.chrome.isVisible()
    assert (vp.size(),g.grid_container.size(),bar.geometry(),bar.value())==original
    h.panel.chrome.click();settle(surface.app)
    assert h.expanded and g.renderer.created==created and tuple(g._all_card_widgets)==cards


def test_real_card_pixels_show_through_tag_body(surface):
    from PySide6.QtGui import QPixmap
    from PySide6.QtTest import QTest
    from test_tab_overflow import own_paint
    from fluent_ui.components.emoji_card import EmojiCard
    g=surface.g;h=g.tag_panel_host
    h.set_placement('top');h.set_expanded(True,persist=False);QTest.qWait(250)
    card=next(c for c in g._all_card_widgets if isinstance(c,EmojiCard) and c.image_path==surface.paths[0])
    point=card.mapTo(g,QPoint(card.width()//2,card.height()//2-12))
    local=h.panel.mapFrom(g,point)
    assert 60<local.y()<h.panel.height()-20
    pixels=[]
    for color in ('#ff0000','#0000ff'):
        pix=QPixmap(120,120);pix.fill(QColor(color));card.setPixmap(pix);card.update();settle(surface.app)
        pixels.append(g.grab().toImage().pixelColor(point))
    assert pixels[0].red()>pixels[1].red()+20 and pixels[1].blue()>pixels[0].blue()+20
    layer=own_paint(h.panel)
    assert 0<layer.pixelColor(100,70).alpha()<layer.pixelColor(100,15).alpha()<255


def test_floating_actions_avoid_panel_without_rebuilding_gallery(surface,monkeypatch):
    from PIL import Image
    from PySide6.QtTest import QTest
    from services.resource_import import ImportTarget
    g=surface.g;h=g.tag_panel_host;vp=g.scroll_area.viewport();bar=g.scroll_area.verticalScrollBar()
    for i in range(90):
        source=surface.tmp/f'overlay-{i}.png';Image.new('RGB',(16,16),(i*2%255,90,i)).save(source)
        surface.storage.save_file(str(source),target=ImportTarget(surface.parent))
    g.refresh_content_incremental(reason='overlay sample',parents={surface.parent});QTest.qWait(500);settle(surface.app)
    assert bar.maximum()>vp.height()
    baseline=vp.geometry();bar.setValue(bar.maximum());QTest.qWait(250);settle(surface.app)
    for placement in ('top','bottom','left','right'):
        h.set_placement(placement);h.set_expanded(True,persist=False);settle(surface.app)
        before=(bar.value(),g.renderer.created,tuple(g._all_card_widgets))
        h.panel.btn_collapse.click();settle(surface.app);h.panel.chrome.click();settle(surface.app)
        assert (bar.value(),g.renderer.created,tuple(g._all_card_widgets))==before
        assert vp.geometry()==baseline
        g._update_back_top();button=g.btn_back_top
        assert button.isVisible() and h.available_rect(vp).contains(button.geometry())
        hit=g.childAt(g.mapFromGlobal(button.mapToGlobal(button.rect().center())))
        assert hit is button
        g.drop_cancel_zone.begin();assert h.available_rect(vp).contains(g.drop_cancel_zone.geometry());g.drop_cancel_zone.end()
        value=bar.value();QTest.mouseClick(bar,Qt.LeftButton,pos=bar.rect().center());settle(surface.app)
        assert bar.value()<value
        bar.setValue(bar.maximum());settle(surface.app)
        QTest.mouseClick(button,Qt.LeftButton);assert bar.value()==0
        bar.setValue(bar.maximum());settle(surface.app)


@pytest.mark.parametrize('placement',['top','bottom','left','right'])
def test_fixed_preview_stays_outside_tag_foreground(surface,placement):
    g=surface.g;h=g.tag_panel_host
    h.set_placement(placement);h.set_expanded(True,persist=False);settle(surface.app)
    surface.config.set('preview_position','fixed');g.apply_preview_position()
    pane=g.preview_popup.parentWidget();bounds=g.preview_container_rect(pane)
    g.preview_popup.show_preview(surface.paths[0],QPoint(0,0),120,info={},container_rect=bounds)
    assert g.preview_popup.isVisible() and bounds.contains(g.preview_popup.geometry())
    h.set_expanded(False,persist=False);settle(surface.app)
    assert not g.preview_popup.isVisible()
