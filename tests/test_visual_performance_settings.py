"""Saved visual preferences use the existing rows and real transition endpoints."""
from PySide6.QtCore import QAbstractAnimation,Qt
from PySide6.QtTest import QTest
from test_l1_l3_interaction import settings
from test_phase2_interaction import surface,settle
from fluent_ui import visual


def test_animation_switch_pending_discard_save_and_persistence(surface,settings):
    from services.config import ConfigService
    from fluent_ui.components.setting_rows import SwitchRow
    c=settings;c._select_page(1);row=c._rows['ui_animations_enabled'][0]
    assert isinstance(row,SwitchRow) and row.value() is True
    row.switch.click()
    assert c.pending['ui_animations_enabled'] is False
    assert visual.animations_enabled() and surface.config.get('ui_animations_enabled')
    c.discard();assert row.value() and not c.pending
    row.switch.click();assert c.save()
    assert not visual.animations_enabled()
    assert ConfigService(surface.config.base_dir).get('ui_animations_enabled') is False
    row.switch.click();assert c.save() and visual.animations_enabled()


def test_disabled_transitions_reach_endpoints_and_keep_completion(surface,settings):
    from fluent_ui.components.controls import SwitchButton
    from fluent_ui.components.setting_rows import SettingSection
    from fluent_ui.components.feedback import Toast
    from PySide6.QtWidgets import QWidget
    surface.config.config['ui_animations_enabled']=False
    switch=SwitchButton(surface.g);switch.show();switch.click()
    assert switch.isChecked() and switch._position==1 and switch._slide.state()==QAbstractAnimation.Stopped
    section=SettingSection('Test',surface.g);section.show();section.toggle_collapsed()
    assert section.is_collapsed() and section.body.isHidden()
    section.toggle_collapsed();assert not section.body.isHidden() and section.body.maximumHeight()==16777215
    host=surface.g.tag_panel_host
    host.set_expanded(False,persist=False);host.set_expanded(True,persist=False)
    assert host._motion.state()==QAbstractAnimation.Stopped and host.expanded
    tabs=settings.tab_bar;tabs.setCurrentIndex(1)
    assert tabs._line_motion.state()==QAbstractAnimation.Stopped
    assert tabs._line_state.y()==1 and tabs._line_state.x()==0
    toast=Toast('Done',surface.g,1000);expired=[];toast.expired.connect(expired.append)
    toast.show();toast._expire();assert expired==[toast]
    for widget in (switch,section,toast):widget.hide();widget.deleteLater()


def test_save_off_finishes_running_motion_and_preserves_movie(surface,settings,tmp_path):
    from PySide6.QtCore import QVariantAnimation
    from PySide6.QtGui import QMovie
    from PIL import Image
    animation=QVariantAnimation(surface.g);animation.setStartValue(0.);animation.setEndValue(1.)
    finished=[];animation.finished.connect(lambda:finished.append(True))
    visual.start_animation(animation,500)
    assert animation.state()==QAbstractAnimation.Running
    path=tmp_path/'playing.gif';images=[Image.new('RGB',(25,25),c) for c in ('red','blue')]
    images[0].save(path,save_all=True,append_images=images[1:],duration=50,loop=0)
    movie=QMovie(str(path));frames=[];movie.frameChanged.connect(frames.append);movie.start()
    settings._stage('ui_animations_enabled',False);assert settings.save()
    assert finished and animation.currentValue()==1 and animation.state()==QAbstractAnimation.Stopped
    for _ in range(100):
        QTest.qWait(10)
        if len(frames)>1:break
    assert movie.state()==QMovie.Running and len(frames)>1
    movie.stop()
