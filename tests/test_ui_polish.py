"""Latest user interactions, with isolated Qt events and no desktop input."""
from unittest.mock import Mock
import json
import pytest
from PIL import Image
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QEnterEvent,QHoverEvent,QColor,QImage,QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle,QStyleOptionSlider,QWidget
from test_phase2_interaction import surface,settle,card
from test_l1_l3_interaction import settings
from test_softframe_compact import painted
from fluent_ui import visual


def enter(widget,point=None):
    p=QPointF(point or widget.rect().center())
    widget.event(QEnterEvent(p,p,QPointF(widget.mapToGlobal(p.toPoint()))))


def test_fast_send_does_not_select_or_import(surface,monkeypatch):
    s=surface;g=s.g;s.config.set('gallery_click_action','send')
    send=Mock();imports=Mock()
    monkeypatch.setattr(g.send_target_service,'send',send)
    monkeypatch.setattr(g,'import_paths_to',imports)
    for path in s.paths[:2]:
        QTest.mouseClick(card(s,path),Qt.LeftButton)
        assert not g.selected_keys and not g._selection_parents
        assert not any(w.is_selected for w in g._all_card_widgets)
    assert send.call_count==2 and [c.args[0] for c in send.call_args_list]==s.paths[:2]
    imports.assert_not_called()


def test_select_then_enter_reuses_send_once_and_keeps_editing_safe(surface,monkeypatch):
    s=surface;g=s.g;s.config.set('gallery_click_action','select')
    send=Mock();monkeypatch.setattr(g.send_target_service,'send',send)
    QTest.mouseClick(card(s,s.paths[0]),Qt.LeftButton);settle(s.app)
    assert g.selected_keys=={s.paths[0]} and not send.called
    QTest.keyClick(g,Qt.Key_Return);settle(s.app)
    send.assert_called_once();assert send.call_args.args[0]==s.paths[0]
    g.search_box.setFocus();settle(s.app)
    assert not g._view_shortcuts[Qt.Key_Return].isEnabled()
    QTest.keyClick(g.search_box,Qt.Key_Return);assert send.call_count==1
    g.sidebar.tree.setFocus();settle(s.app)
    assert not g._view_shortcuts[Qt.Key_Return].isEnabled()
    g.search_box.clearFocus();g.setFocus();g.set_mode('manage');settle(s.app)
    QTest.keyClick(g,Qt.Key_Return);assert send.call_count==1
    g.set_mode('normal');g._select_single(s.paths[0]);g._toggle_selection(s.paths[1]);settle(s.app)
    QTest.keyClick(g,Qt.Key_Return);assert send.call_count==1


def test_fast_send_modifiers_only_select(surface,monkeypatch):
    g=surface.g;surface.config.set('gallery_click_action','send');send=Mock()
    monkeypatch.setattr(g.send_target_service,'send',send)
    g.on_image_clicked(surface.paths[0],Qt.ControlModifier)
    assert g.selected_keys=={surface.paths[0]};send.assert_not_called()
    g.set_mode('manage');g.on_image_clicked(surface.paths[1],Qt.NoModifier)
    assert surface.paths[1] in g.selected_keys;send.assert_not_called()


def test_hover_and_selection_use_distinct_accent_contours(surface):
    c=card(surface,surface.paths[0]);c.set_selected(False);c._hovered=False
    c.setPixmap(QPixmap());color=visual.colors()['accent']
    def accent_pixels(image,x):
        return sum(image.pixelColor(x,y).name()==color for y in range(12,image.height()-12))
    enter(c);hover=painted(c)
    c.set_selected(True);selected=painted(c)
    assert accent_pixels(hover,1)>0 and accent_pixels(selected,1)>0
    # Selected uses one edge column; hover fills a second column.
    accent=QColor(color)
    def distance(pixel):return sum(abs(a-b) for a,b in zip(pixel.getRgb()[:3],accent.getRgb()[:3]))
    assert distance(hover.pixelColor(2,c.height()//2))<distance(selected.pixelColor(2,c.height()//2))
    assert all(selected.pixelColor(x,2).name()==color for x in range(12,c.width()-12))
    c.set_selected(False);c.event(QEvent(QEvent.Leave));assert not c._hovered


def test_esc_preferences_are_staged_and_discardable(surface,settings):
    c=settings;c._select_page(2);c._show_tab(0);settle(surface.app)
    rows=[c._rows[k][0] for k in ('esc_hide_main','esc_hide_quick')]
    for r in rows:r.switch.click()
    assert set(c.pending)>={'esc_hide_main','esc_hide_quick'}
    assert not surface.config.get('esc_hide_main') and not surface.config.get('esc_hide_quick')
    assert all(r.property('pending') for r in rows)
    c.discard();assert not c.pending and all(not r.value() for r in rows)
    rows[0].switch.click();c.save()
    assert surface.config.get('esc_hide_main') and not c.pending


def test_icon_preview_fits_and_uses_existing_thumbnail_frame(surface,settings):
    s=surface;c=settings
    path=s.tmp/'two-frames.gif'
    Image.new('RGB',(90,40),'red').save(path,save_all=True,append_images=[Image.new('RGB',(90,40),'blue')],duration=100,loop=0)
    saved,_=s.storage.save_file(str(path));s.storage.set_resource_metadata(saved,{'thumb_frame':1})
    c._select_page(1);c._show_tab(3);c._set_icon(saved);settle(s.app)
    from services.app_icon import ApplicationIconService
    icon=QImage(ApplicationIconService(s.config).current_path())
    assert icon.pixelColor(icon.width()//2,icon.height()//2).blue()>200
    pix=c.icon_preview.pixmap()
    assert pix.width()<c.icon_preview.width() and pix.height()<c.icon_preview.height()
    # Transparent letterboxing matches the same square icon shown in Windows.
    assert pix.toImage().pixelColor(0,0).alpha()==0


def test_number_field_is_centered_and_track_reclaims_width(surface,settings):
    c=settings;c._select_page(1);c._show_tab(1);settle(surface.app)
    row=c._rows['thumbnail_size'][0]
    assert row.spin.width()<80 and row.spin.editor.alignment()&Qt.AlignHCenter
    assert abs(row.spin.editor.geometry().center().x()-row.spin.rect().center().x())<=1
    assert row.slider.width()>=180
    assert row.spin.up_button.geometry().bottom()<row.spin.height()
    before=row.value();row.spin.up_button.click();assert row.value()==before+10
    assert row.slider.value()==row.value()


def test_slider_handle_hover_is_local_and_resets(surface):
    slider=surface.g.size_slider;opt=QStyleOptionSlider();slider.initStyleOption(opt)
    handle=slider.style().subControlRect(QStyle.CC_Slider,opt,QStyle.SC_SliderHandle,slider)
    baseline=painted(slider);p=QPointF(handle.center())
    slider.event(QHoverEvent(QEvent.HoverMove,p,p,p))
    assert slider._handle_hover and painted(slider)!=baseline
    slider.event(QHoverEvent(QEvent.HoverLeave,p,p,p))
    assert not slider._handle_hover and painted(slider)==baseline


@pytest.mark.parametrize('placement',['left','right','top','bottom'])
def test_collapse_lines_and_chevron_share_one_hover_hit(surface,placement,monkeypatch):
    from fluent_ui.components import panel_host
    g=surface.g;host=g.tag_panel_host;host.set_placement(placement);host.set_expanded(True);settle(surface.app)
    h=host.splitter.handle(1);h.clearFocus();states=[]
    original=panel_host.paint_dock_chevron
    def record(p,points,active=False):states.append(active);original(p,points,active)
    monkeypatch.setattr(panel_host,'paint_dock_chevron',record)
    middle=h.rect().center();point=middle+ (QPoint(0,25) if h.orientation()==Qt.Horizontal else QPoint(25,0))
    h.event(QHoverEvent(QEvent.HoverMove,QPointF(point),QPointF(point),QPointF(point)))
    h.grab();assert states[-1] and h._ear_hover and h.cursor().shape()==Qt.PointingHandCursor
    h.event(QHoverEvent(QEvent.HoverMove,QPointF(0,0),QPointF(0,0),QPointF(point)))
    h.grab();assert not states[-1] and not h._ear_hover
    QTest.mouseClick(h,Qt.LeftButton,pos=point);settle(surface.app);assert not host.expanded


def test_centered_task_is_long_and_notice_has_visible_summary(surface):
    caption=QWidget();caption.resize(1020,80)
    from fluent_ui.components.feedback import FeedbackHost
    host=FeedbackHost(caption);host.dock_to_caption(caption);caption.show()
    host.task('正在导入',total=100,cancel=lambda:None);host.update_task(31,100);settle(surface.app)
    assert host.progress.width()>=400
    assert abs(host.strip.geometry().center().x()-caption.rect().center().x())<=1
    assert host.strip.height()==24
    host.finish('导入完成','已导入 100 个表情');settle(surface.app)
    assert host.count_label.isVisible() and host.count_label.text()=='已导入 100 个表情'
    assert host.finish_timer.interval()>=3000
    host.notice('无法导入','请检查文件后重试');settle(surface.app)
    assert host.count_label.text()=='请检查文件后重试'
    assert abs(host.strip.geometry().center().x()-caption.rect().center().x())<=1
    caption.close();caption.deleteLater();settle(surface.app)


def test_keycaps_are_painted_objects_and_wrap_without_losing_text(surface,settings):
    from fluent_ui.components.keycap_label import KeycapLabel,KEY_OBJECT,KEY_TEXT
    c=settings;c._select_page(2);c._show_tab(1);settle(surface.app)
    label=c._rows['gallery_click_action'][0].hint_label
    assert isinstance(label,KeycapLabel) and 'Enter' in label.text() and '拖动表情至聊天窗口' in label.text()
    assert '回车' not in label.text()
    block=label._document.begin();keys=[]
    while block.isValid():
        it=block.begin()
        while not it.atEnd():
            fmt=it.fragment().charFormat()
            if fmt.objectType()==KEY_OBJECT:keys.append(fmt.property(KEY_TEXT))
            it+=1
        block=block.next()
    assert keys==['Enter']
    assert label.heightForWidth(200)>label.heightForWidth(600)
    # Typed shortcut settings are still regular editing fields, not keycaps.
    c._show_tab(0);assert not isinstance(c._rows['global_hotkey'][0].editor,KeycapLabel)


def test_pgup_pgdown_jump_and_editors_keep_the_keys(surface):
    g=surface.g;bar=g.scroll_area.verticalScrollBar();bar.setRange(0,3000)
    g.setFocus();settle(surface.app)
    QTest.keyClick(g,Qt.Key_PageDown);assert bar.value()==bar.maximum()
    QTest.keyClick(g,Qt.Key_PageUp);assert bar.value()==0
    g.search_box.setFocus();settle(surface.app)
    assert not g._view_shortcuts[Qt.Key_PageDown].isEnabled()
    QTest.keyClick(g.search_box,Qt.Key_PageDown);assert bar.value()==0


def test_back_top_has_translucent_rest_surface_and_no_sticky_hover(surface):
    b=surface.g.btn_back_top;b.show();b.clearFocus();settle(surface.app)
    base=painted(b);assert 0<base.pixelColor(5,b.height()//2).alpha()<255
    enter(b);b._hover_animation.setCurrentTime(b._hover_animation.duration());assert b._hover>0
    b.event(QEvent(QEvent.Leave));assert b._hover==0 and not b.isDown()
    assert painted(b)==base


def test_sidebar_scroll_thumb_is_wider_with_a_small_edge_gap(surface):
    from fluent_ui.presentation.scrollbar import install_scrollbars
    from PySide6.QtWidgets import QScrollBar
    assert surface.g.sidebar.tree.verticalScrollBar().property('sidebarThumb')
    assert surface.g.sidebar.icons.verticalScrollBar().property('sidebarThumb')
    holder=QWidget();bar=QScrollBar(Qt.Vertical,holder);bar.setFixedSize(10,150)
    bar.setProperty('sidebarThumb',True);install_scrollbars(holder)
    bar.setRange(0,1000);bar.setPageStep(100);holder.show();settle(surface.app)
    image=painted(bar);xs={x for x in range(image.width()) if any(image.pixelColor(x,y).alpha() for y in range(image.height()))}
    assert len(xs)>=6 and image.width()-1-max(xs)>=1
    holder.close();holder.deleteLater();settle(surface.app)


@pytest.mark.parametrize('language',['zh','en','zh_TW','ja'])
def test_settings_hints_and_controls_fit_in_four_languages(surface,settings,language):
    from PySide6.QtWidgets import QLabel
    from services.i18n import i18n_engine
    c=settings;i18n_engine.set_language(language)
    for width in (720,950):
        c.resize(width,720)
        for page,tab in ((2,1),(2,0),(1,1),(1,3),(3,2)):
            c._select_page(page);c._show_tab(tab);settle(surface.app)
            for row,_ in c._rows.values():
                hint=getattr(row,'hint_label',None)
                if hint is not None and hint.isVisible():
                    height=hint.heightForWidth(hint.width())
                    assert height<=hint.height()+1,(language,width,tab,hint.text(),hint.size(),height)
            assert not any('[MISSING:' in l.text() for l in c.findChildren(QLabel) if l.isVisible())
    i18n_engine.set_language('zh')


def test_new_terms_keep_legacy_navigation_alias_and_user_names(surface):
    from services.library_index import ROOT
    g=surface.g
    assert g.sidebar._as_node_id('全部资源')==ROOT
    assert g.sidebar._as_node_id('全部表情')==ROOT
    g.set_category('全部资源');assert g.current_node==ROOT
    node=surface.storage.create_node('我的图片收藏')
    g.sidebar.refresh_list(node);g.set_node(node);settle(surface.app)
    assert surface.storage.node(node)['name']=='我的图片收藏'
    assert g.location_rail.path[-1][1]=='我的图片收藏'


def test_enter_on_a_category_keeps_existing_navigation(surface,monkeypatch):
    from fluent_ui.components.node_card import NodeCard
    g=surface.g;send=Mock();monkeypatch.setattr(g.send_target_service,'send',send)
    g._select_single(surface.child)
    node=next(w for w in g._all_card_widgets if isinstance(w,NodeCard) and w.node_id==surface.child)
    node.setFocus();settle(surface.app)
    assert not g._view_shortcuts[Qt.Key_Return].isEnabled()
    QTest.keyClick(node,Qt.Key_Return);settle(surface.app)
    assert g.current_node==surface.child;send.assert_not_called()
