"""Cross-surface commit and reentrant source failures, no desktop input."""
import json
from unittest.mock import Mock
import pytest
from PySide6.QtCore import QMimeData,QPoint,QPointF,Qt
from PySide6.QtGui import QMouseEvent
from test_phase1_logic import app,sender
from test_phase2_interaction import surface
from fluent_ui.components.drop_contract import DragSession,DropTarget,RESOURCE_MIME,MOVE,INTO
from services.send_target import SendResult


def packet():
    mime=QMimeData();mime.setData(RESOURCE_MIME,json.dumps(['resource.gif']).encode())
    return mime


def test_one_drag_cannot_commit_again_after_receiver_reentry(app):
    mime=packet();writes=[]
    first=DragSession(mime);second=DragSession(mime)
    assert first.commit(DropTarget(INTO,MOVE,'a','a'),lambda target,block:writes.append('a'))
    assert not second.commit(DropTarget(INTO,MOVE,'b','b'),lambda target,block:writes.append('b'))
    assert writes==['a']


def test_drop_claim_captures_independent_stable_target(app):
    mime=packet();target=DropTarget(INTO,MOVE,'a','a');accepted=[]
    assert DragSession(mime).commit(target,lambda resolved,block:accepted.append(resolved))
    target.target_id='b';target.container_id='b';target.index=999
    assert (accepted[0].target_id,accepted[0].container_id,accepted[0].index)==('a','a',None)


def test_rejected_domain_commit_is_not_accepted_or_retried(app):
    mime=packet();session=DragSession(mime)
    assert not session.commit(DropTarget(INTO,MOVE,'a','a'),lambda target,block:False)
    assert not DragSession(mime).commit(DropTarget(INTO,MOVE,'b','b'),lambda *args:None)


def test_category_card_reentrant_move_does_not_start_second_drag(surface,monkeypatch):
    from fluent_ui.components.node_card import NodeCard
    import fluent_ui.components.node_card as module
    entry=surface.storage.node(surface.parent)
    card=NodeCard(entry,surface.storage);card._drag_start=QPoint(0,0)
    event=QMouseEvent(QMouseEvent.MouseMove,QPointF(40,40),QPointF(40,40),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    calls=[]
    class Drag:
        def __init__(self,*args):calls.append(self)
        def setMimeData(self,*args):pass
        def setPixmap(self,*args):pass
        def setHotSpot(self,*args):pass
        def exec(self,*args):
            if len(calls)==1:card.mouseMoveEvent(event)
            return Qt.IgnoreAction
    monkeypatch.setattr(module,'QDrag',Drag)
    card.mouseMoveEvent(event)
    assert len(calls)==1
    assert not card._dragging and card._drag_start is None
    card.deleteLater()


@pytest.mark.parametrize('failure',['input','activation','copy'])
def test_native_send_exceptions_still_finish_exactly_once(app,failure):
    service,api,pending,injector=sender();service.remember(101);api.current=101
    storage=Mock();storage.config=None;clipboard=Mock();results=[]
    if failure=='input':injector.paste.side_effect=OSError('input refused')
    elif failure=='activation':api.acquire_foreground=Mock(side_effect=OSError('target refused'))
    else:clipboard.copy_image_to_clipboard.side_effect=OSError('clipboard busy')
    service.send('resource.gif',clipboard,storage,results.append)
    while pending:pending.pop(0)()
    assert results==[SendResult.COPY_FAILED if failure=='copy' else SendResult.COPIED_ONLY]


def test_exact_nearest_hit_matches_original_full_scan(app):
    import random
    from fluent_ui.components.virtual_gallery import FlowIndex
    rng=random.Random(20261105);entries=[]
    for i in range(1200):
        entries.append({'id':str(i),'kind':'node' if i%37==0 else 'resource','_parent':str(i//37),'_depth':i//37%5,'_source_label':i%11==0})
    index=FlowIndex();index.layout(entries,713,120)
    for _ in range(1500):
        point=QPoint(rng.randint(-250,1000),rng.randint(-150,index.height+200))
        def distance(rect):return max(rect.left()-point.x(),0,point.x()-rect.right())+max(rect.top()-point.y(),0,point.y()-rect.bottom())
        expected=min(range(len(index.rects)),key=lambda i:distance(index.rects[i]))
        assert index.nearest(point)==expected


def test_destroyed_drag_source_cancels_and_releases_active_identity(app):
    from PySide6.QtWidgets import QWidget
    from shiboken6 import delete
    from fluent_ui.components.drop_contract import begin_drag,finish_drag,prepare_drag
    source=QWidget();cleanup=Mock();source._drag_cleanup=cleanup;mime=packet()
    assert begin_drag(source,mime);operation=prepare_drag(mime)
    delete(source);assert operation.state=='cancelled'
    finish_drag(mime);cleanup.assert_called_once()
    next_source=QWidget();next_mime=packet()
    assert begin_drag(next_source,next_mime);finish_drag(next_mime);next_source.deleteLater()


def test_deferred_action_commits_once_and_never_after_cancel(app):
    from fluent_ui.components.drop_contract import current_drop_operation,prepare_drag
    mime=packet();session=DragSession(mime)
    assert session.commit(DropTarget(INTO,MOVE,'a','a'),lambda *args:current_drop_operation().defer())
    operation=prepare_drag(mime);assert operation.state=='awaiting_choice'
    writes=[];assert operation.complete(lambda:writes.append('a'))
    assert operation.state=='committed' and not operation.complete(lambda:writes.append('b'))
    assert writes==['a']
    other=DragSession(packet());other.operation.defer=lambda:None
    other.operation.cancel('receiver_destroyed')
    assert not other.operation.complete(lambda:writes.append('bad'))


def test_membership_menu_waits_for_source_end_and_real_close(surface):
    from PySide6.QtTest import QTest
    from fluent_ui.components.drop_contract import begin_drag,finish_drag,prepare_drag
    from PySide6.QtWidgets import QWidget
    g=surface.g;source=QWidget();mime=packet()
    assert begin_drag(source,mime)
    operation=prepare_drag(mime);writes=[]
    assert DragSession(mime).commit(DropTarget(INTO,MOVE,surface.parent,surface.parent),
        lambda *args:g.request_resource_drop(['resource.gif'],surface.parent,sources={'resource.gif':'other'}))
    QTest.qWait(5)
    assert not getattr(g,'_drop_action_menu',None)
    finish_drag(mime);QTest.qWait(10)
    menu=g._drop_action_menu
    assert menu.isVisible() and operation.state=='awaiting_choice' and len(operation._receivers)==1
    menu.close();QTest.qWait(10)
    assert operation.state=='cancelled' and not operation._receivers
    source.deleteLater()


def test_queued_send_keeps_each_clipboard_payload_until_its_own_input(app):
    from PySide6.QtTest import QTest
    service,api,pending,injector=sender();service.remember(101);api.acquire=False
    storage=Mock();storage.config=None
    copied=[];pasted=[];results=[]
    clipboard=Mock();clipboard.copy_image_to_clipboard.side_effect=lambda path:copied.append(path) or True
    injector.paste.side_effect=lambda:pasted.append(copied[-1]) or True
    a=service.send('a.gif',clipboard,storage,lambda result:results.append(('a',result)))
    b=service.send('b.gif',clipboard,storage,lambda result:results.append(('b',result)))
    assert a!=b and copied==['a.gif']
    api.current=101;api.acquire=True
    while pending:pending.pop(0)()
    QTest.qWait(5)
    assert copied==pasted==['a.gif','b.gif']
    assert results==[('a',SendResult.SENT),('b',SendResult.SENT)]


def test_clipboard_change_during_activation_never_injects_stale_request(app):
    service,api,pending,injector=sender();service.remember(101);api.acquire=False
    class Clipboard:
        revision=0
        def copy_image_to_clipboard(self,path):self.revision+=1;return True
        def delivery_revision(self):return self.revision
    clip=Clipboard();storage=Mock();storage.config=None;results=[]
    service.send('a.gif',clip,storage,results.append)
    clip.revision+=1;api.current=101
    while pending:pending.pop(0)()
    assert results==[SendResult.COPIED_ONLY]
    assert service.last_outcome.reason=='clipboard_changed'
    injector.paste.assert_not_called()


def test_cleanup_exception_still_releases_drag_gate(app):
    from PySide6.QtWidgets import QWidget
    from shiboken6 import delete
    from services.drag_activity import drag_activity
    from fluent_ui.components.drop_contract import begin_drag,finish_drag
    source=QWidget();source._drag_cleanup=Mock(side_effect=RuntimeError('deleted visuals'))
    mime=packet();assert begin_drag(source,mime);delete(source)
    with pytest.raises(RuntimeError):finish_drag(mime)
    assert drag_activity().operation is None


def test_send_waits_for_native_drag_lifetime_without_polling(app):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.drop_contract import begin_drag,finish_drag
    service,api,pending,injector=sender();api.current=101
    clip=Mock();storage=Mock();storage.config=None;results=[]
    source=QWidget();mime=packet();assert begin_drag(source,mime)
    service.send('a.gif',clip,storage,results.append)
    clip.copy_image_to_clipboard.assert_not_called();assert pending==[]
    finish_drag(mime)
    assert results==[SendResult.SENT];injector.paste.assert_called_once()
    source.deleteLater()


@pytest.mark.parametrize('changed',['clipboard','foreground'])
def test_async_preparation_does_not_steal_changed_user_context(app,changed):
    service,api,pending,injector=sender();api.current=101
    class Clipboard:
        revision=0
        publish=Mock(return_value=True)
        def delivery_revision(self):return self.revision
        def prepare_image_async(self,path,callback):self.callback=callback
        def publish_prepared(self,data):return self.publish(data)
    clip=Clipboard();storage=Mock();storage.config=None;results=[]
    service.send('a.gif',clip,storage,results.append)
    if changed=='clipboard':clip.revision+=1
    else:api.current=303
    clip.callback(('a.gif',None),'')
    assert results==[SendResult.COPIED_ONLY]
    assert service.last_outcome.reason==changed+'_changed'
    if changed=='clipboard':clip.publish.assert_not_called()
    injector.paste.assert_not_called()
