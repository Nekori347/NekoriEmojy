"""Synthetic notifications only; no resources, network or business workers."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt, QEvent, QPoint, QAbstractAnimation, QRect
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
from fluent_ui import visual
from fluent_ui.components.feedback import FeedbackHost, Toast
from services.i18n import i18n_engine

COPY=json.loads((Path(__file__).parent/'fixtures/notification_tooltip_copy.json').read_text(encoding='utf-8'))

@pytest.fixture
def scene(monkeypatch):
    app=QApplication.instance() or QApplication([])
    from fluent_ui.components.controls import focus_input
    focus_input().keyboard=False
    monkeypatch.setattr(visual.theme,'config',{'ui_animations_enabled':False})
    w=QWidget();w.resize(1080,520);w.show()
    h=FeedbackHost(w);h.dock_to_caption(w)
    yield app,w,h,h._caption_ui
    w.close();w.deleteLater();app.processEvents();i18n_engine.load_language('zh')

def enter(app,widget):
    app.sendEvent(widget,QEnterEvent(QPoint(1,1),QPoint(1,1),widget.mapToGlobal(QPoint(1,1))))

def test_controls_visibility_and_hit_geometry(scene):
    app,w,h,u=scene
    h.toast('Generated first',kind='success')
    assert not u.ear.isVisible() and not u.clear_button.isVisible()
    h.toast('Generated second',kind='success')
    assert not u.ear.isVisible()
    enter(app,u.cover);app.processEvents()
    assert u.ear.isVisible() and not u.clear_button.isVisible()
    enter(app,u.controls);u.ear.click();app.processEvents()
    assert u.opened and u.clear_button.isVisible()
    assert not QRect(u.clear_button.mapTo(w,QPoint()),u.clear_button.size()).intersects(u.cover.geometry())
    assert not QRect(u.clear_button.mapTo(w,QPoint()),u.clear_button.size()).intersects(u.panel.geometry())
    for x,y in [(1,1),(20,1),(1,20),(20,20),(11,11)]:
        hit=w.childAt(u.clear_button.mapTo(w,QPoint(x,y)))
        assert hit is u.clear_button
    h.remove_task(u.pending[0]);app.processEvents()
    assert not u.opened and not u.ear.isVisible() and not u.clear_button.isVisible()

def test_task_and_result_have_disjoint_regions(scene):
    _,w,h,u=scene
    cancel=Mock();h.upsert_task('job','Generated task',current=3,total=10,cancel=cancel)
    h.toast('Generated result',kind='success')
    assert h.strip.isVisible() and u.cover.isVisible() and h.progress.isVisible()
    assert not h.strip.geometry().intersects(u.cover.geometry())
    h.upsert_task('job','Generated task',current=7,total=10,cancel=cancel)
    assert h.progress.value()==7
    h.clear_completed()
    assert h.named_tasks['job']['current']==7 and not cancel.called

def test_toast_hover_keeps_remaining_time(scene):
    app,w,_,_=scene
    item=Toast('Generated',w,220);item.show();QTest.qWait(70)
    enter(app,item);left=item.deadline.remaining
    QTest.qWait(80);assert abs(item.deadline.remaining-left)<8
    app.sendEvent(item,QEvent(QEvent.Leave))
    assert item.deadline.remaining<=left and item.deadline.remaining<item.duration

def test_caption_pause_reannounce_queue_and_retained_history(scene):
    app,w,h,u=scene
    h.toast('Generated first');first=u.overlay
    h.toast('Generated warning',warning=True);second=u.pending[0]
    u.deadline.start(240,first)
    QTest.qWait(50);enter(app,u.cover);left=u.deadline.remaining
    QTest.qWait(80)
    assert u.deadline.paused and abs(u.deadline.remaining-left)<5
    assert u.overlay==first and second in u.pending
    generation=u.deadline.generation
    h.toast('Generated first')
    assert u.overlay==first and u.deadline.generation==generation+1
    assert u.deadline.paused and u.deadline.remaining>2500
    app.sendEvent(u.cover,QEvent(QEvent.Leave))
    u.deadline.start(50,first);QTest.qWait(90)
    assert u.overlay==second and first not in h.named_tasks
    u.expire_overlay()
    assert second in h.named_tasks and u.overlay is None
    assert not u.ear.isVisible() and not u.clear_button.isVisible()

def test_motion_and_accent_do_not_restart_time(scene):
    app,w,h,u=scene
    visual.theme.config['ui_animations_enabled']=True
    h.toast('Generated timer');u.deadline.start(300,u.overlay)
    app.sendEvent(u.cover,QEvent(QEvent.Leave))
    QTest.qWait(50);before=u.deadline.remaining;generation=u.deadline.generation
    visual.theme.config['ui_animations_enabled']=False
    visual.finish_ui_animations();visual.theme.motion_changed.emit()
    assert not u.cover.countdown.isVisible()
    assert u.deadline.paint_motion.state()!=QAbstractAnimation.Running
    QTest.qWait(45)
    assert u.deadline.remaining<before
    visual.theme.config['ui_animations_enabled']=True
    visual.theme.motion_changed.emit();visual.theme.accent_changed.emit()
    assert u.cover.countdown.isVisible() and u.deadline.generation==generation
    assert u.deadline.fraction<1
    visual.theme.config['ui_animations_enabled']=False
    visual.theme.motion_changed.emit();QTest.qWait(260)
    assert u.overlay is None and not h.named_tasks

def test_clear_scope_preserves_active_and_actionable_results(scene):
    app,w,h,u=scene
    cancel=Mock();resume=Mock()
    h.upsert_task('job','Generated task',current=1,total=9,cancel=cancel)
    h.upsert_task('warning','Generated warning',state='warning')
    h.upsert_task('detail','Generated detail',state='info',details='Generated details')
    h.upsert_task('resume','Generated resume',state='success',resume=resume)
    h.upsert_task('plain','Generated plain',state='success')
    enter(app,h.strip);enter(app,u.controls);u.ear.click();app.processEvents()
    assert u.clear_button.isVisible()
    u.clear_button.click()
    assert set(h.named_tasks)=={'job','warning','detail','resume'}
    assert not cancel.called and not resume.called and not u.opened
    assert not u.clear_button.isVisible()

def test_focus_bridge_and_one_record_collapse(scene):
    app,w,h,u=scene
    from fluent_ui.components.controls import focus_input
    h.upsert_task('a','Generated task A',cancel=lambda:None)
    h.upsert_task('b','Generated task B')
    assert not u.ear.isVisible()
    app.setActiveWindow(w);focus_input().keyboard=True
    h.action_button.setFocus(Qt.TabFocusReason);QTest.keyClick(h.action_button,Qt.Key_Tab);app.processEvents()
    assert u.ear.isVisible(), (app.focusWidget(), h.action_button.isVisible(), h.action_button.isHidden(), u.actions.isVisible(), u._has_focus(), focus_input().keyboard)
    u.ear.setFocus(Qt.TabFocusReason);u.ear.click();app.processEvents()
    assert u.opened and u.ear.accessibleName()==u.ear.toolTip()
    h.remove_task('b');app.processEvents()
    assert not u.opened and not u.ear.isVisible() and not u.clear_button.isVisible()

def test_window_hide_continues_timeout_and_old_timeout_cannot_expire_new(scene):
    app,w,h,u=scene
    h.toast('Generated old');u.deadline.start(80,u.overlay)
    enter(app,u.cover);assert u.deadline.paused
    w.hide();app.processEvents();assert not u.deadline.paused
    QTest.qWait(120);assert not h.named_tasks
    w.show();h.toast('Generated new');current=u.overlay
    u.deadline._timeout()
    assert u.overlay==current and u.deadline.active

@pytest.mark.parametrize('states', [[], ['running'], ['success'], ['warning'],
    ['running','waiting'], ['warning','error'], ['success','info'], ['running','success','partial']])
def test_distinct_record_visibility_matrix(scene,states):
    app,w,h,u=scene
    for n,state in enumerate(states):h.upsert_task(str(n),'Generated',state=state)
    app.processEvents()
    assert not u.clear_button.isVisible()
    assert not u.ear.isVisible()
    if len(states)>=2:
        enter(app,h.strip if u.primary else u.cover);app.processEvents()
        assert u.ear.isVisible()
        enter(app,u.controls);u.ear.click();app.processEvents()
        assert u.opened
        assert u.clear_button.isVisible()==bool(h.clearable_tasks())
    elif states:
        h.upsert_task('0','Generated update',state=states[0],current=3)
        assert len(h.named_tasks)==1 and not u.ear.isVisible()

def test_control_copy_and_detail_actions_stay_with_their_channel(scene):
    app,w,h,u=scene
    h.upsert_task('job','Generated task',details='Generated task detail')
    h.upsert_task('notice','Generated notice',state='warning',details='Generated notice detail')
    h._task_details=Mock()
    u.detail.click();assert h._task_details.call_args.args==('job',)
    u.cover.detail.click();assert h._task_details.call_args.args==('notice',)
    enter(app,u.cover)
    for lang in ('zh','zh_TW','en','ja'):
        i18n_engine.load_language(lang)
        expected=next(r for r in COPY if r.get('id')=='expand')['values'][lang]
        assert u.ear.toolTip()==u.ear.accessibleName()==expected
        u.ear.click()
        expected=next(r for r in COPY if r.get('id')=='collapse')['values'][lang]
        assert u.ear.toolTip()==u.ear.accessibleName()==expected
        assert u.clear_button.toolTip()==next(r for r in COPY if r.get('id')=='clear')['values'][lang]
        u.ear.click()
