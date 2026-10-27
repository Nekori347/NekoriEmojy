"""Bounded real Qt host geometry; synthetic tasks, no Library or system input."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import importlib,json,subprocess
from pathlib import Path
from unittest.mock import Mock
from PySide6.QtCore import QPoint,Qt,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme,setTheme
from services.config import ConfigService
from services.i18n import i18n_engine
from fluent_ui import visual
from fluent_ui.components.feedback import FeedbackHost
from fluent_ui.components.controls import focus_input


def test_shared_host_geometry_and_dual_channels(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'unused-library'))
    monkeypatch.setattr('requests.sessions.Session.request',Mock(side_effect=AssertionError('No network')))
    config=ConfigService();config.update({'ui_animations_enabled':False,'auto_check_updates':False})
    visual.theme.configure(config);i18n_engine.init(config)
    root=Path(__file__).resolve().parents[1]
    for short in ('materials','window_shell'):
        module=importlib.import_module('fluent_ui.'+short)
        source=subprocess.check_output(['git','show',f'HEAD:fluent_ui/{short}.py'],cwd=root).decode('utf-8')
        exec(compile(source,str(root/'fluent_ui'/f'{short}.py'),'exec'),module.__dict__)
    from fluent_ui.window_shell import NekoriWindow
    from test_notification_interaction import enter
    w=NekoriWindow();w.resize(1080,540);w.move(700,180);w.show()
    h=FeedbackHost(w);h.dock_to_caption(w);u=h._caption_ui
    evidence=[]
    for lang in ('zh','zh_TW','en','ja'):
        i18n_engine.load_language(lang)
        for theme in (Theme.LIGHT,Theme.DARK):
            setTheme(theme);visual.theme.refresh()
            for width in (1080,680):
                w.resize(width,540);QTest.qWait(35)
                focus_input().keyboard=False
                for key in list(h.named_tasks):h.remove_task(key)
                h.upsert_task('job','Generated progress',current=3,total=10,cancel=lambda:None)
                h.toast('Generated result',content='Generated temporary notice',kind='success')
                h.toast('Generated second',kind='info')
                enter(app,u.cover);QTest.mouseClick(u.ear,Qt.LeftButton);QTest.qWait(25)
                assert u.opened and u.clear_button.isVisible()
                assert not h.strip.geometry().intersects(u.cover.geometry())
                assert w.rect().contains(h.strip.geometry()) and w.rect().contains(u.cover.geometry())
                assert not u.clear_button.geometry().intersects(u.panel.geometry())
                for control in (u.clear_button,u.ear):
                    for x,y in ((1,1),(control.width()-2,1),(1,control.height()-2),(control.width()-2,control.height()-2)):
                        assert w.childAt(control.mapTo(w,QPoint(x,y))) is control,(lang,width,control.geometry())
                # Both channels retain an independent working operation.
                h.upsert_task('job','Generated progress',current=7,total=10,cancel=lambda:None)
                assert h.progress.value()==7 and u.cover.isVisible()
                evidence.append((lang,theme.value,width,h.strip.geometry().getRect(),u.cover.geometry().getRect(),
                                 u.panel.geometry().getRect(),u.clear_button.geometry().getRect(),u.ear.geometry().getRect()))
                if os.environ.get('QT_QPA_PLATFORM')=='windows' and lang=='en' and width==680:
                    target=root.parent/'DevData/ui-refresh'
                    w.grab().save(str(target/f'notification-fixed-{theme.value}-{os.environ.get("QT_SCALE_FACTOR","1")}.png'))
                QTest.mouseClick(u.clear_button,Qt.LeftButton,pos=QPoint(1,1));app.processEvents()
                assert list(h.named_tasks)==['job'] and not u.opened and not u.ear.isVisible()
    # Actual intermediate frames use the same control band and disjoint channels.
    config.update({'ui_animations_enabled':True});visual.theme.motion_changed.emit()
    h.toast('Generated animation',kind='success');enter(app,h.strip);u.ear.click()
    QTest.qWait(80)
    assert 0<u.expansion<1 and not u.clear_button.isVisible()
    assert not u.ear.geometry().intersects(u.panel.geometry())
    assert not h.strip.geometry().intersects(u.cover.geometry())
    u.deadline.resume();u.deadline.start(1000,u.overlay)
    QTest.qWait(60)
    assert u.cover.countdown.isVisible() and 0<u.deadline.fraction<1
    assert u.cover.countdown.height()==1
    image=u.cover.countdown.grab().toImage()
    from PySide6.QtGui import QColor
    assert image.pixelColor(0,0)==QColor(visual.accent())
    if os.environ.get('QT_QPA_PLATFORM')=='windows':
        w.grab().save(str(root.parent/'DevData/ui-refresh'/f'notification-countdown-{os.environ.get("QT_SCALE_FACTOR","1")}.png'))
    config.update({'ui_animations_enabled':False});visual.finish_ui_animations();visual.theme.motion_changed.emit()
    assert not u.cover.countdown.isVisible()
    w.close();w.deleteLater();app.processEvents();i18n_engine.load_language('zh')
    print('NOTIFICATION_QT_GEOMETRY',json.dumps(evidence))
