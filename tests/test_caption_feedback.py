"""Caption presentation contract using the real FeedbackHost and Gallery widgets."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_phase2_interaction import surface, settle


def dock(surface):
    host=surface.g.feedback_host;host.dock_to_caption(surface.g)
    return host,host._caption_ui


def test_inline_single_and_long_title_keep_identical_bar_geometry(surface):
    h,u=dock(surface);layout=surface.g.scroll_area.geometry()
    h.upsert_task('a','正在导入表情',current=31,total=100,cancel=lambda:None)
    settle(surface.app);bar=h.progress.geometry()
    assert h.strip.isVisible() and u.panel.isHidden() and u.ear.isHidden()
    assert h.strip.parentWidget() is surface.g and not h.strip.isWindow()
    assert h.strip.y()>=0 and h.strip.geometry().bottom()<34
    h.upsert_task('a','非常长的导入表情任务名称'*12,current=32,total=100,cancel=lambda:None)
    settle(surface.app)
    assert h.progress.geometry()==bar and h.title_label.toolTip().startswith('非常长')
    assert surface.g.scroll_area.geometry()==layout
    surface.g.resize(800,760);settle(surface.app)
    assert h.strip.x()>=u.bounds()[0] and h.strip.geometry().right()<=u.bounds()[1]
    assert h.progress.width()>=80


def test_task_actions_paint_danger_only_for_live_cancel(surface):
    from PySide6.QtGui import QColor
    from fluent_ui import visual
    h,u=dock(surface)
    h.upsert_task('a','正在导入表情',current=1,total=10,cancel=lambda:None)
    settle(surface.app)
    header,row=h.action_button,h._named_widgets['a'][5]
    assert header.property('role')=='danger' and row.property('role')=='danger'
    # ButtonPaint reads the dynamic property itself; confirm the rendered text
    # really uses the shared danger token instead of trusting the property.
    c=visual.colors();danger=QColor(c['danger']);normal=QColor(c['text'])
    image=header.grab().toImage()
    pixels=[QColor(image.pixelColor(x,y)) for x in range(image.width()) for y in range(image.height())]
    def close(color,target):
        return all(abs(getattr(color,channel)()-getattr(target,channel)())<=8
                   for channel in ('red','green','blue'))
    assert any(p.alpha()>200 and close(p,danger) for p in pixels)
    assert not any(p.alpha()>200 and close(p,normal) for p in pixels)
    # A finished job offers no destructive action, including its row button.
    h.upsert_task('a','导入处理完成',state='success',content='新增 1 张')
    settle(surface.app)
    assert row.property('role')==''
    assert header.property('role')==''
    # A replacement live job recalculates both shared action surfaces.
    h.upsert_task('a','等待导入表情',state='waiting',cancel=lambda:None)
    settle(surface.app)
    assert header.property('role')=='danger' and row.property('role')=='danger'
    h.upsert_task('a','等待导入表情',state='waiting')
    settle(surface.app)
    assert header.property('role')=='' and row.property('role')==''
    h.remove_task('a')


def test_legacy_task_cancel_uses_same_danger_role(surface):
    from PySide6.QtWidgets import QWidget
    from fluent_ui.components.feedback import FeedbackHost
    host=FeedbackHost(QWidget())
    host.task('正在扫描…',cancel=lambda:None)
    assert host.action_button.property('role')=='danger'
    host.finish('扫描完成')
    host.notice('扫描完成','已完成')
    assert host.action_button.property('role')==''
    host.task('正在扫描…')
    assert host.action_button.property('role')==''


def test_main_stable_internal_scroll_list_and_hover_bridge(surface):
    h,u=dock(surface);cancelled=[]
    for i in range(12):
        h.upsert_task(str(i),'补充识别',kind='ocr',current=i,total=30,
                      state='running' if i<2 else 'waiting',cancel=lambda i=i:cancelled.append(i))
    settle(surface.app)
    assert u.primary=='0' and u.panel.isHidden() and u.ear.isVisible()
    h.upsert_task('1','补充识别',kind='ocr',current=12,total=30)
    assert u.primary=='0'
    QApplication.sendEvent(u.ear,QEvent(QEvent.Enter));settle(surface.app)
    QTest.qWait(250)
    assert u.panel.isVisible() and not u.panel.isWindow()
    assert surface.g.rect().contains(u.panel.geometry()) and u.panel.height()<=300
    assert u.scroll.verticalScrollBar().maximum()>0
    QApplication.sendEvent(u.ear,QEvent(QEvent.Leave))
    QApplication.sendEvent(u.panel,QEvent(QEvent.Enter));QTest.qWait(220)
    assert u.panel.isVisible()
    h._named_widgets['0'][5].click();assert cancelled==[0]
    QApplication.sendEvent(u.panel,QEvent(QEvent.Leave));QTest.qWait(450)
    assert u.panel.isHidden()
    u.ear.click();assert u.panel.isVisible()
    u.ear.click();QTest.qWait(250);assert u.panel.isHidden()


def test_sequential_overlay_restores_latest_job_and_retains_warning(surface):
    h,u=dock(surface)
    h.upsert_task('a','正在导入表情',current=1,total=30,cancel=lambda:None)
    h.toast('复制成功',kind='success');first=u.overlay
    h.toast('导入部分完成',content='新增 1 张，失败 1 张',warning=True)
    assert u.overlay==first and len(u.pending)==1
    h.upsert_task('a','正在导入表情',current=17,total=30,cancel=lambda:None)
    assert h.progress.isVisible() and u.cover.isVisible() and h.named_tasks['a']['current']==17
    u.expire_overlay();assert u.overlay!=first
    warning=u.overlay;u.expire_overlay()
    assert u.overlay is None and h.progress.isVisible() and h.progress.value()==17
    assert warning in h.named_tasks and u.ear.isVisible() and u.primary=='a'
    h.remove_task(warning);h.remove_task('a')
    assert h.strip.isHidden() and u.ear.isHidden()


def test_legacy_progress_keeps_updating_under_notice_and_new_run_is_not_expired(surface):
    h,u=dock(surface)
    h.task('正在导入表情',total=10,cancel=lambda:None)
    h.toast('复制成功',kind='success');h.update_task(current=7)
    u.expire_overlay()
    assert h.progress.value()==7 and h.title_label.text()=='正在导入表情'
    h.finish('导入处理完成')
    assert u.overlay=='legacy'
    h.task('正在导入表情',total=20,cancel=lambda:None)
    assert u.overlay is None and not u.overlay_timer.isActive()
    assert h.named_tasks['legacy']['state']=='running'


def test_update_button_matches_real_install_capability_and_check_state(surface,monkeypatch,tmp_path):
    from fluent_ui.components import update_center as module
    from services.update_protocol import MANIFEST
    center=module.update_center();button=module.UpdateCheckButton(surface.g)
    version=module.VersionLabel('v0.2.0',surface.g)
    monkeypatch.setattr(module,'install_root',lambda:tmp_path)
    try:
        center.set_release({'version':'0.2.1'})
        assert button.text()=='获取更新'
        (tmp_path/MANIFEST).write_text('{}')
        center.set_release({'version':'0.2.1'})
        assert button.text()=='立即更新'
        center.set_release({'version':'0.2.1','manual_only':True})
        assert button.text()=='获取更新'
        width=version.sizeHint().width();version.set_update_available(True)
        assert version.sizeHint().width()==width
        center.set_check_state('checking')
        assert center.release is None and button.text()=='检查中…' and not button.isEnabled()
        center.set_check_state('error')
        assert center.release is None and button.text()=='检查更新' and button.isEnabled()
        assert not button.available
    finally:center.set_release(None)


def test_exchange_caller_emits_one_result_and_failure_is_only_in_details(surface):
    import pytest
    from fluent_ui.components.exchange_task_dialog import run_exchange_task
    h,u=dock(surface)
    result=run_exchange_task(surface.g,'正在导出表情合集',lambda progress:42)
    assert result==42 and not h.named_tasks and not h.task_active
    h.toast('导出完成',kind='success')
    assert len(h.named_tasks)==1 and h.named_tasks[u.overlay]['title']=='导出完成'
    h.remove_task(u.overlay)
    def fail(progress):raise OSError('isolated internal failure')
    with pytest.raises(OSError):run_exchange_task(surface.g,'正在导出表情合集',fail)
    assert not h.named_tasks and not h.task_active
    surface.g.show_error('导出失败','isolated internal failure')
    assert len(h.named_tasks)==1
    assert 'isolated internal failure' not in h.title_label.text()
    assert h.named_tasks[u.overlay]['details']=='isolated internal failure'
