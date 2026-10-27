"""Category selection is persistent; hover/pressed remain transient."""
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_phase2_interaction import surface,settle
import pytest


@pytest.mark.parametrize('manage',[False,True])
def test_click_selection_does_not_leave_category_background(surface,manage):
    s=surface;g=s.g
    s.config.set('gallery_click_action','send')
    if manage:QTest.mouseClick(g.btn_manage,Qt.LeftButton);settle(s.app)
    node=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==s.child)
    QApplication.sendEvent(node,QEvent(QEvent.Leave));node.clearFocus();settle(s.app)
    normal=node.grab().toImage()
    QTest.mouseClick(node,Qt.LeftButton,pos=node.rect().center())
    QApplication.sendEvent(node,QEvent(QEvent.Leave));settle(s.app)
    assert s.child in g.selected_keys,'both modes select a category'
    after=node.grab().toImage()
    assert after!=normal,'selected signal must follow real node selection'
    assert after.pixelColor(20,5)!=normal.pixelColor(20,5),'real selection has a neutral backing'
    assert node.height()==g.renderer.index.rects[next(i for i,e in enumerate(g._entries) if e['id']==s.child)].height()
    assert node.height()==30 and node._icon_extent==22


def test_hover_pressed_focus_and_move_feedback(surface,monkeypatch):
    s=surface;g=s.g
    node=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==s.child)
    QApplication.sendEvent(node,QEvent(QEvent.Leave));node.clearFocus();settle(s.app)
    normal=node.grab().toImage()
    def enter():
        QApplication.sendEvent(node,QEnterEvent(QPointF(20,10),QPointF(20,10),QPointF(node.mapToGlobal(node.rect().center()))))
    enter();hover=node.grab().toImage();assert hover!=normal
    # Feedback changes the existing line, not the broad background below it.
    assert all(hover.pixelColor(x,node.height()-2)==normal.pixelColor(x,node.height()-2) for x in range(5,node.width()-5))
    QTest.mousePress(node,Qt.LeftButton,pos=node.rect().center())
    assert node._pressed and node.grab().toImage()!=hover
    QTest.mouseRelease(node,Qt.LeftButton,pos=node.rect().center())
    assert not node._pressed
    QApplication.sendEvent(node,QEvent(QEvent.Leave));assert node.is_selected
    selected=node.grab().toImage();enter();QApplication.sendEvent(node,QEvent(QEvent.Leave))
    assert node.grab().toImage()==selected
    node.clearFocus();node.setFocus(Qt.TabFocusReason);settle(s.app)
    assert node.hasFocus() and node._keyboard_focus
    QTest.keyClick(node,Qt.Key_Space);settle(s.app)
    assert s.child in g._expanded_nodes
    # A mouse click on an already keyboard-focused row ends only its focus cue.
    QTest.mouseClick(node,Qt.LeftButton,pos=node.rect().center());assert not node._keyboard_focus
    enter();assert node._hovered
    monkeypatch.setattr(QApplication,'widgetAt',lambda point:None)
    node.move(node.x(),node.y()+3)
    assert not node._hovered


def test_rebound_node_clears_transient_feedback(surface,monkeypatch):
    s=surface;g=s.g
    node=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==s.child)
    QApplication.sendEvent(node,QEnterEvent(QPointF(20,10),QPointF(20,10),QPointF(node.mapToGlobal(node.rect().center()))))
    assert node._hovered
    incoming=dict(node.content_entry,id=s.other,name='Other')
    monkeypatch.setattr(QApplication,'widgetAt',lambda point:None)
    g.renderer.bind(node,incoming)
    assert not node._hovered,'pooled category inherited the prior hit'


def test_identity_accent_and_selected_line(surface):
    from fluent_ui import visual
    from PySide6.QtGui import QColor
    s=surface;g=s.g
    node=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==s.child)
    s.config.set('accent_color','#36a8d4');visual.theme.preview_accent()
    QApplication.sendEvent(node,QEvent(QEvent.Leave));node.clearFocus()
    image=node.grab().toImage()
    assert image.pixelColor(6,node.height()//2).name()!=QColor(visual.accent()).name()
    QTest.mouseClick(node,Qt.LeftButton,pos=node.rect().center())
    QApplication.sendEvent(node,QEvent(QEvent.Leave))
    image=node.grab().toImage()
    assert node.is_selected
    assert image.pixelColor(150,node.height()//2).name()==QColor(visual.accent()).name()
    s.config.set('accent_color','#c068c4');visual.theme.preview_accent()
    image=node.grab().toImage()
    assert image.pixelColor(6,node.height()//2).name()==QColor(visual.accent()).name()
    assert image.pixelColor(150,node.height()//2).name()==QColor(visual.accent()).name()


@pytest.mark.parametrize('result',[Qt.IgnoreAction,Qt.MoveAction])
def test_category_native_drag_projection_and_cleanup(surface,monkeypatch,result):
    import json
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QMouseEvent
    from fluent_ui.components import node_card
    from fluent_ui.components.drop_contract import NODE_MIME
    s=surface;g=s.g
    node=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==s.child)
    g._select_single(s.child)
    before=list(s.storage.index.content(s.parent))
    captured={}
    class Drag:
        def __init__(self,source):assert source is node
        def setMimeData(self,mime):captured['payload']=json.loads(bytes(mime.data(NODE_MIME)))
        def setPixmap(self,pixmap):captured['pixmap']=pixmap
        def setHotSpot(self,point):captured['hotspot']=point
        def exec(self,actions):
            assert node._dragging and not node._pressed and node.is_selected
            assert actions==Qt.MoveAction
            return result
    monkeypatch.setattr(node_card,'QDrag',Drag)
    # Chevron remains a disclosure click, even if moved past the drag threshold.
    QTest.mousePress(node,Qt.LeftButton,pos=node.disclosure_rect().center())
    assert node._drag_start is None
    QTest.mouseRelease(node,Qt.LeftButton,pos=node.disclosure_rect().center());settle(s.app)
    node=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==s.child)
    start=QPoint(40,12);QTest.mousePress(node,Qt.LeftButton,pos=start)
    point=start+QPoint(QApplication.startDragDistance()+2,0)
    move=QMouseEvent(QEvent.MouseMove,QPointF(point),QPointF(node.mapToGlobal(point)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(node,move)
    pm=captured['pixmap'];dpr=pm.devicePixelRatio()
    assert round(pm.height()/dpr)==node.height()+8
    assert round(pm.width()/dpr)>200,'title must not be squeezed into a thumbnail square'
    assert captured['hotspot']==start+QPoint(4,4)
    assert s.child in captured['payload']
    assert not node._dragging and not node._pressed and node._drag_start is None
    assert s.child in g.selected_keys and list(s.storage.index.content(s.parent))==before


def test_category_drop_placements_use_existing_feedback_and_data(surface):
    import json
    from PySide6.QtCore import QMimeData,QPoint
    from fluent_ui.components.drop_contract import NODE_MIME,INSERT_BEFORE,INSERT_AFTER,INTO,APPEND
    s=surface;g=s.g
    target=s.storage.create_node('Target',s.parent)
    g.refresh_content_incremental(reason='fixture',parents={s.parent});settle(s.app)
    i=next(i for i,e in enumerate(g._entries) if e['id']==target)
    rect=g.renderer.index.rects[i]
    mime=QMimeData();mime.setData(NODE_MIME,json.dumps([s.child]).encode())
    for y,placement in ((rect.top()+1,INSERT_BEFORE),(rect.center().y(),INTO),(rect.bottom()-1,INSERT_AFTER)):
        point=g.grid_container.mapTo(g,QPoint(rect.center().x(),y))
        resolved,hit,vertical=g._resolve_drop(point,mime)
        assert resolved.placement==placement
        g.drop_feedback.show_target(placement,hit,vertical)
        assert g.drop_feedback.isVisible()
        assert g.drop_feedback._mode==('outline' if placement==INTO else 'line')
        g.drop_feedback.clear();assert g.drop_feedback.isHidden()
    child_i=next(i for i,e in enumerate(g._entries) if e['id']==s.child)
    centre=g.grid_container.mapTo(g,g.renderer.index.rects[child_i].center())
    assert not g._resolve_drop(centre,mime)[0].valid
    point=g.grid_container.mapTo(g,QPoint(20,g.renderer.index.height+20))
    assert g._resolve_drop(point,mime)[0].placement==APPEND
    # The same contract commits persistent order and parentage, not a visual-only move.
    point=g.grid_container.mapTo(g,QPoint(rect.center().x(),rect.top()+1))
    before_target=g._resolve_drop(point,mime)[0];g._apply_node_drop([s.child],before_target);settle(s.app)
    ids=[e['id'] for e in s.storage.index.content(s.parent)]
    assert ids.index(s.child)+1==ids.index(target)
    g.refresh_content_incremental(reason='fixture',parents={s.parent});settle(s.app)
    i=next(i for i,e in enumerate(g._entries) if e['id']==target)
    point=g.grid_container.mapTo(g,g.renderer.index.rects[i].center())
    g._apply_node_drop([s.child],g._resolve_drop(point,mime)[0]);settle(s.app)
    assert s.storage.node(s.child)['parent_id']==target
    assert [e['id'] for e in s.storage.index.content(target)]==[s.child]


def test_state_rules_keep_one_center_line_and_neutral_backing(surface):
    from fluent_ui import visual
    from qfluentwidgets import setTheme,Theme
    from PySide6.QtGui import QColor
    s=surface;g=s.g
    node=next(c for c in g._all_card_widgets if getattr(c,'node_id',None)==s.child)
    s.config.set('accent_color','#ce357b');visual.theme.preview_accent()
    try:
        for theme in (Theme.LIGHT,Theme.DARK):
            setTheme(theme);visual.theme.refresh();node.clearFocus()
            g.selected_keys.clear();g._commit_selection_visuals()
            QApplication.sendEvent(node,QEvent(QEvent.Leave));normal=node.grab().toImage()
            point=node.rect().center()
            QApplication.sendEvent(node,QEnterEvent(QPointF(point),QPointF(point),QPointF(node.mapToGlobal(point))))
            hover=node.grab().toImage();signal=QColor(visual.accent()).name();y=node.height()//2
            xs=[x for x in range(110,node.width()-70) if hover.pixelColor(x,y).name()==signal]
            assert len(xs)>100
            g._select_single(s.child);QApplication.sendEvent(node,QEvent(QEvent.Leave));selected=node.grab().toImage()
            assert all(selected.pixelColor(x,y).name()==signal for x in xs),'selected moved structural rule'
            assert selected.pixelColor(20,5)!=normal.pixelColor(20,5)
            assert selected.pixelColor(20,5).saturationF()<.2,'backing must be neutral, not accent tinted'
            assert all(selected.pixelColor(x,node.height()-3).name()!=signal for x in xs),'no extra bottom rule'
            QApplication.sendEvent(node,QEnterEvent(QPointF(point),QPointF(point),QPointF(node.mapToGlobal(point))))
            assert node.grab().toImage().pixelColor(20,5)==selected.pixelColor(20,5)
            assert node.height()==30
    finally:
        setTheme(Theme.LIGHT);visual.theme.refresh()
