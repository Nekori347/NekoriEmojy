"""Category feedback is transient, not the resource selection decoration."""
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
    assert (s.child in g.selected_keys)==(not manage),'existing category selection semantics changed'
    assert node.grab().toImage()==normal,'click left a persistent selected fill'
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
    QApplication.sendEvent(node,QEvent(QEvent.Leave));assert node.grab().toImage()==normal
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
