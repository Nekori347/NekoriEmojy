"""Three RC layout corrections; real controls and disposable data only."""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from fluent_ui import visual
from test_phase2_interaction import surface, settle
from test_l1_l3_interaction import settings


def test_expanded_tasks_share_columns_with_balanced_edge_padding(surface):
    h=surface.g.feedback_host;h.dock_to_caption(surface.g);u=h._caption_ui
    for key,state in [('running','running'),('waiting','waiting'),('stopped','cancelled')]:
        h.upsert_task(key,'补充识别',kind='ocr',state=state,current=12,total=88,
                      content='完成 12 张，失败 1 张，跳过 2 张',cancel=lambda:None,resume=lambda:None)
    u.expand();QTest.qWait(250);settle(surface.app)
    for row,icon,label,bar,count,button,info,close in h._named_widgets.values():
        assert icon.mapTo(u.panel,QPoint()).x()>=12
        assert icon.mapTo(u.window,QPoint()).x()==h.state_icon.mapTo(u.window,QPoint()).x()
        assert label.mapTo(u.window,QPoint()).x()==h.title_label.mapTo(u.window,QPoint()).x()
        assert info.width()==close.width()==20
        trailing=close if not close.isHidden() else button
        assert 0<=u.material.geometry().right()-trailing.mapTo(u.window,QPoint(trailing.width()-1,0)).x()<=8
    assert u.panel.width()<=h.strip.width()+14


@pytest.mark.parametrize('size',[60,120,240])
def test_selected_decoration_is_inside_card_frame(surface,size):
    from fluent_ui.components.emoji_card import EmojiCard
    c=EmojiCard(surface.paths[0],size=size,load_image=False)
    pix=QPixmap(size,size);pix.fill(QColor('#777777'));c.setPixmap(pix)
    c.set_selected(True)
    image=c.grab().toImage();scale=image.devicePixelRatio();accent=QColor(visual.accent())
    def same(x,y):return image.pixelColor(round(x*scale),round(y*scale)).name()==accent.name()
    rows=[y for y in range(3,12) if sum(same(x,y) for x in range(9,size-9))>=size-20]
    assert rows and min(rows)>=5 and max(rows)<=7,rows
    y=rows[len(rows)//2]
    xs=[x for x in range(3,size-3) if same(x,y)]
    # Ignore the two vertical sides; the central segment has its own inset.
    assert not same(4,y) and same(7,y) and same(size-8,y) and not same(size-5,y)
    assert abs((min(x for x in xs if x>4)+max(x for x in xs if x<size-5))/2-(size-1)/2)<=.5
    c.deleteLater()


def test_retry_body_padding_and_independent_arrow(settings,monkeypatch):
    c=settings;c._select_page(3);c._show_tab(1);ocr=c.ocr_controls;s=ocr.service
    monkeypatch.setattr(type(s),'available',property(lambda _:True))
    monkeypatch.setattr(type(s),'library_busy',property(lambda _:False))
    monkeypatch.setattr(type(s),'busy',property(lambda _:False))
    ocr._has_failures=True;ocr._failure_revision=s.storage.index.search_revision;ocr.refresh();settle(QApplication.instance())
    group=ocr.retry_group;body=group.button;arrow=group.dropButton
    assert body.width()-body.fontMetrics().horizontalAdvance(body.text())>=28
    assert arrow.width()==24 and arrow.height()==body.height()==group.height()==32
    calls=[];monkeypatch.setattr(s,'supplement',lambda **kw:calls.append(kw))
    menus=[];monkeypatch.setattr(ocr,'show_more',lambda anchor:menus.append(anchor))
    before=group.geometry();QTest.mouseClick(body,Qt.LeftButton);QTest.mouseClick(arrow,Qt.LeftButton)
    assert calls==[{'failed_only':True}] and menus==[arrow]
    ocr.refresh();assert group.geometry()==before
