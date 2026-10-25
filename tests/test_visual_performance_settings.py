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
    # A fresh widget must render from the persisted preference as on restart.
    from fluent_ui.components.navigation import TabStrip
    from test_tab_overflow import check_paint
    visual.theme.configure(ConfigService(surface.config.base_dir))
    fresh=TabStrip();fresh.resize(400,43);fresh.set_tabs(['First','Second']);fresh.show()
    settle(surface.app)
    try:
        assert check_paint(fresh)
        for tabs in (fresh,c.tab_bar,surface.g.category_tabs):
            for index in (0,1,0):
                tabs.setCurrentIndex(min(index,tabs.count()-1))
                assert check_paint(tabs)
    finally:
        fresh.close();fresh.deleteLater();visual.theme.configure(surface.config)
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


def test_acrylic_save_waits_for_restart_and_uses_existing_opaque_path(surface,settings,monkeypatch):
    import os
    from services.config import ConfigService
    from fluent_ui.components.setting_rows import SwitchRow
    c=settings;c._select_page(1);row=c._rows['window_acrylic_enabled'][0]
    assert isinstance(row,SwitchRow) and row.value()
    monkeypatch.delenv('NEKORI_OPAQUE_MATERIAL',raising=False)
    row.switch.click()
    assert c.pending['window_acrylic_enabled'] is False and 'NEKORI_OPAQUE_MATERIAL' not in os.environ
    c.discard();assert row.value()
    row.switch.click();assert c.save()
    assert 'NEKORI_OPAQUE_MATERIAL' not in os.environ
    loaded=ConfigService(surface.config.base_dir);assert loaded.get('window_acrylic_enabled') is False
    visual.theme.configure(loaded)
    assert os.environ['NEKORI_OPAQUE_MATERIAL']=='1'
    from fluent_ui.materials import _transparency_allowed
    assert not _transparency_allowed()
    visual.theme.configure(surface.config)


def test_visual_rows_follow_themes_and_four_languages(surface,settings):
    from qfluentwidgets import Theme,setTheme
    from services.i18n import i18n_engine,t
    settings._select_page(1)
    for theme in (Theme.LIGHT,Theme.DARK):
        setTheme(theme);visual.theme.refresh()
        for language in ('zh','en','ja','zh_TW'):
            i18n_engine.set_language(language)
            for key,title in (('ui_animations_enabled','界面动效'),('window_acrylic_enabled','窗口毛玻璃')):
                row=settings._rows[key][0]
                assert row.title_label.text()==t(title) and not row.grab().isNull()
    i18n_engine.set_language('zh');setTheme(Theme.LIGHT);visual.theme.refresh()


def test_live_tab_reveal_preserves_content_switch_and_intermediate_frames(surface,settings):
    from PySide6.QtCore import QEventLoop,QTimer
    from qfluentwidgets import Theme,setTheme
    from test_tab_overflow import own_paint,check_paint
    surface.config.config['ui_animations_enabled']=True
    settings._select_page(1)
    settle(surface.app)
    try:
        for theme in (Theme.LIGHT,Theme.DARK):
            setTheme(theme);visual.theme.refresh()
            for tabs in (surface.g.category_tabs,settings.tab_bar):
                for index in (1,0):
                    tabs.setCurrentIndex(index)
                    # Selection/content commits synchronously, not on animation.finished.
                    if tabs is settings.tab_bar:assert settings._current_tab==index
                    else:assert surface.g.content_scope_node()==surface.g._tab_nodes[index]
                    samples=[]
                    def sample():
                        image=own_paint(tabs)
                        samples.append((tabs._line_state.x(),tabs._line_state.y(),
                                        tabs._target_line().center().x(),image.isNull()))
                    timer=QTimer();timer.setInterval(16);timer.timeout.connect(sample)
                    loop=QEventLoop();timer.start();QTimer.singleShot(340,loop.quit);loop.exec();timer.stop()
                    visible=[s for s in samples if 0<s[1]<1]
                    assert len(visible)>=2 and not any(s[3] for s in samples)
                    assert len({s[2] for s in samples})==1
                    assert min(s[0] for s in samples)<0<max(s[0] for s in samples)
                    assert tabs._line_state.x()==0 and tabs._line_state.y()==1
                    assert check_paint(tabs)
    finally:
        setTheme(Theme.LIGHT);visual.theme.refresh()
