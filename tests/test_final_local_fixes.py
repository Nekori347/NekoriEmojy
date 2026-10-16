"""Final local feedback: source/destination roles and real HS picker input."""
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette, QMouseEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_phase2_interaction import surface, settle
from test_l1_l3_interaction import settings
from fluent_ui.components.accent_picker import AccentColorPicker
from fluent_ui import visual
from services.i18n import i18n_engine

OUT=Path('../DevData/final-local-fixes-1015')


@pytest.fixture(autouse=True)
def font(surface):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    surface.app.setFont(QFont('Microsoft YaHei',9))
    OUT.mkdir(exist_ok=True)


def test_parent_press_keeps_roles_then_weight_and_position_interpolate(surface,monkeypatch):
    h=surface.g.location_rail
    path=[{'id':str(i),'name':f'Level {i}'} for i in range(5)]
    h.set_path(path)
    initial=h._display_rows()
    QTest.mousePress(h,Qt.LeftButton,pos=QPoint(40,12))
    assert h._display_rows()==initial and h._preview is None
    monkeypatch.setattr(QApplication,'platformName',lambda:'animation-test')
    h.navigate_requested.disconnect()
    h.navigate_requested.connect(lambda _: h.set_path(path[:-1],path[-1]))
    QTest.mouseRelease(h,Qt.LeftButton,pos=QPoint(40,12))
    h.animation.pause();h.animation.setCurrentTime(0)
    first={r[0]:r for r in h._display_rows()}
    assert first['3'][5]==400 and first['4'][5]==600
    assert first['3'][2]==initial[0][2] and first['4'][2]==initial[1][2]
    h.animation.setCurrentTime(80)
    middle={r[0]:r for r in h._display_rows()}
    assert 400<middle['3'][5]<600 and middle['3'][2]!=first['3'][2]
    h.grab().save(str(OUT/'rail-transition.png'))
    h.animation.setCurrentTime(180)
    last={r[0]:r for r in h._display_rows()}
    assert last['3'][5]==600 and last['4'][5]==400
    assert last['3'][2]==visual.HIERARCHY_CURRENT_TOP


def test_rail_three_tick_centers_independent_decoration_and_counts(surface):
    h=surface.g.location_rail
    h.set_path([{'id':str(i),'name':f'Level {i}'} for i in range(7)],{'id':'child','name':'Child'})
    h.set_counts('22 resources\n3 children')
    rows=h._display_rows();ticks=h._ticks(rows)
    assert len(rows)==len(ticks)==3
    assert [r[0] for r in rows]==['5','6','child']
    assert all(tick[0]==row[2]+row[4]/2 for row,tick in zip(rows,ticks))
    assert all(not r[1].startswith('//') for r in rows)
    assert h.height()-(rows[-1][2]+rows[-1][4])>=4
    assert h.count_label.font().pixelSize()>=11 and h.count_label.font().weight()>=500
    first=h.grab().toImage().copy(12,0,10,24)
    path=[{'id':str(i),'name':f'Level {i}'} for i in range(7)]
    path[-2]['name']='A much longer parent name'
    h.set_path(path,{'id':'child','name':'Child'})
    assert first==h.grab().toImage().copy(12,0,10,24)
    h.grab().save(str(OUT/'rail.png'))


def test_sidebar_complete_row_has_no_native_selection_gutter(surface):
    tree=surface.g.sidebar.tree
    palette=tree.palette();palette.setColor(QPalette.Highlight,QColor('#1545ff'));tree.setPalette(palette)
    assert tree.indentation()==0
    parent=tree._find_item(surface.parent);parent.setExpanded(True)
    child=tree._find_item(surface.child)
    tree.select_node(surface.child,reveal=True);QTest.qWait(visual.MOTION.select+20);settle(surface.app)
    assert tree.visualItemRect(child).left()==tree.visualItemRect(parent).left()
    image=tree.viewport().grab().toImage()
    row=tree.visualItemRect(child)
    assert not any(image.pixelColor(x,y).name()=='#1545ff' for x in range(image.width()) for y in range(row.top(),row.bottom()))
    accent=visual.colors()['accent']
    assert image.pixelColor(round(tree.itemDelegate()._indicator_target().center().x()),row.center().y()).name()==accent
    pixels=[x for x in range(30) if image.pixelColor(x,row.center().y()).name()==accent]
    # A 3 DIP antialiased stroke has two fully covered columns at 100% DPI.
    assert 2<=len(pixels)<=3 and pixels==list(range(min(pixels),max(pixels)+1))
    image.save(str(OUT/'sidebar.png'))


def test_active_tag_has_no_bottom_decoration(surface):
    g=surface.g;flow=g.tag_panel.flow
    index=next(i for i,x in enumerate(flow._items) if x.name=='Cat')
    g._toggle_tag('Cat');settle(surface.app)
    rect=flow._rects[index];point=QPoint(rect.center().x(),rect.bottom()-3)
    image=flow.grab().toImage();accent=visual.colors()['accent']
    assert flow.active_filters=={'Cat'}
    assert image.pixelColor(point).name()!=accent
    image.save(str(OUT/'tag-active.png'))
    g._toggle_tag('Cat');flow._set_selection(['Cat'])
    assert flow.grab().toImage().pixelColor(point).name()!=accent


def test_hs_palette_direct_cross_hue_hsv_hex_and_value_render(surface):
    picker=AccentColorPicker('#ff0000',surface.g);picker.show();settle(surface.app)
    spectrum=picker.spectrum;rect=spectrum.selection_rect()
    for hue in (0,60,120,180,240,300):
        point=QPoint(round(rect.left()+hue/359*(rect.width()-1)),rect.top())
        QTest.mouseClick(spectrum,Qt.LeftButton,pos=point)
        assert abs(picker.color.hsvHue()-hue)<=2
        assert picker.color.hsvSaturation()>=250
        assert abs(picker.hsv_numbers[0].value()-hue)<=2
    QTest.mousePress(spectrum,Qt.LeftButton,pos=rect.topLeft())
    point=QPoint(round(rect.left()+270/359*(rect.width()-1)),rect.top()+rect.height()//4)
    move=QMouseEvent(QMouseEvent.MouseMove,QPointF(point),QPointF(spectrum.mapToGlobal(point)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(spectrum,move)
    assert abs(picker._hsv[0]-270)<=1 and 73<=picker._hsv[1]<=76
    QTest.mouseRelease(spectrum,Qt.LeftButton,pos=point)
    picker.hsv_numbers[2].setValue(40)
    sample=QPoint(rect.left()+rect.width()//3,rect.top()+3)
    assert spectrum.grab().toImage().pixelColor(sample).value()<=103
    QTest.mouseClick(spectrum,Qt.LeftButton,pos=QPoint(rect.center().x(),rect.center().y()))
    assert picker._hsv[2]==40
    picker.hsv_numbers[0].setValue(120);picker.hsv_numbers[1].setValue(75)
    selected=spectrum.selection_point()
    assert abs(selected.x()-(rect.left()+120/359*(rect.width()-1)))<1
    assert abs(selected.y()-(rect.top()+.25*(rect.height()-1)))<1
    picker.hex_editor.selectAll();QTest.keyClicks(picker.hex_editor,'#336699')
    assert picker.color.name()=='#336699' and picker.current_swatch.color.name()=='#336699'
    assert picker.previous_swatch.color.name()=='#ff0000'
    picker.grab().save(str(OUT/'picker.png'))
    for swatch in (picker.previous_swatch,picker.current_swatch):
        assert picker.rect().contains(swatch.geometry())
        image=swatch.grab().toImage()
        assert image.pixelColor(swatch.rect().center()).name()==swatch.color.name()
        assert swatch.size().width()==72 and swatch.size().height()==36
    picker.reject();picker.deleteLater()


@pytest.mark.parametrize('language,labels',[
    ('zh',('分类树','分类图标')),('en',('Category tree','Category icon')),
    ('zh_TW',('分類樹','分類圖標')),('ja',('カテゴリツリー','カテゴリアイコン'))])
def test_sidebar_mode_uses_existing_translations(surface,settings,language,labels):
    i18n_engine.load_language(language)
    settings._select_page(1);settings._show_tab(1)
    row=settings._rows['sidebar_mode'][0]
    assert tuple(item.text() for item in row.segment.items.values())==labels
    row.set_value('categorized_icons');assert row.value()=='categorized_icons'
    i18n_engine.load_language('zh')
