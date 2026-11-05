"""Numeric resets and preview controls with no native audio or desktop input."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Signal, QUrl, Qt, QPointF
from PySide6.QtWidgets import QPushButton
from PySide6.QtMultimedia import QSoundEffect

from test_settings_ia import settings, page
from fluent_ui.components.setting_rows import RangeRow, SoundEventRow
from services.i18n import i18n_engine


class FakeEffect(QObject):
    playingChanged=Signal()
    statusChanged=Signal()
    Status=QSoundEffect.Status

    def __init__(self,parent=None):
        super().__init__(parent)
        self.url=QUrl();self.playing=False;self.state=self.Status.Null
        self.gain=0;self.play_count=0;self.stop_count=0

    def setLoopCount(self,count):assert count==1
    def setVolume(self,value):self.gain=value
    def source(self):return self.url
    def setSource(self,url):
        self.url=url;self.state=self.Status.Ready;self.statusChanged.emit()
    def status(self):return self.state
    def isPlaying(self):return self.playing
    def play(self):
        self.play_count+=1;self.playing=True;self.playingChanged.emit()
    def stop(self):
        self.stop_count+=1
        if self.playing:self.playing=False;self.playingChanged.emit()
    def finish(self):self.playing=False;self.playingChanged.emit()
    def fail(self):self.state=self.Status.Error;self.statusChanged.emit()


@pytest.fixture
def audio(settings,monkeypatch):
    monkeypatch.setattr('PySide6.QtMultimedia.QSoundEffect',FakeEffect)
    page(settings,2,2)
    return settings


def test_all_numeric_rows_have_canonical_pending_resets(settings):
    s=settings;c=s.center;keys=set()
    # Includes count-only recent_limit; no OCR or tasks are started.
    for nav,tab in [(1,1),(1,2),(2,2),(2,3),(3,0)]:
        page(s,nav,tab)
        for key,(row,_) in list(c._rows.items()):
            if not isinstance(row,RangeRow):continue
            keys.add(key);default=s.config.default_config[key]
            assert row.default_value==default
            assert row.reset_button.toolTip()=='恢复默认'
            assert row.range_controls.itemAt(0).widget() is row.reset_button
            assert row.range_controls.itemAt(1).widget() is row.slider
            assert row.height()==86 or '\n' in row.hint_label.text()
            custom=default+row.spin._step if default+row.spin._step<=row.spin.maximum() else default-row.spin._step
            s.config.set(key,custom);row.set_value(custom)
            assert row.reset_button.isEnabled()
            row.reset_button.click()
            assert row.value()==default and c.pending[key]==default
            assert not row.reset_button.isEnabled()
            assert s.config.config[key]==custom
            if key in __import__('fluent_ui.views.settings_center',fromlist=['PREVIEW_KEYS']).PREVIEW_KEYS:
                assert s.config.preview_values[key]==default
            c.discard()
            assert row.value()==custom and row.reset_button.isEnabled()
    assert keys=={'thumbnail_size','sidebar_icon_size','gallery_node_icon_size',
        'quick_panel_thumbnail_size','quick_panel_width','quick_panel_height',
        'sound_volume','preview_size','preview_delay','recent_limit'}
    assert c.save()  # no pending remains


def test_numeric_reset_can_be_saved_and_does_not_toggle_other_preferences(settings):
    s=settings;c=s.center;s.config.set('sound_volume',35)
    page(s,2,2)
    c._rows['sound_volume'][0].reset_button.click()
    assert c.pending=={'sound_volume':85}
    assert c.save() and s.config.get('sound_volume')==85
    assert not s.config.get('send_sound_enabled') and not s.config.get('import_sound_enabled')


def test_two_line_sound_card_light_actions_and_path_default(audio):
    s=audio;c=s.center
    assert len(c.body_widget.findChildren(SoundEventRow))==5
    row=c._sound_rows['send']
    assert not row.reset_button.isEnabled()
    assert row.preview_button.toolTip()=='试听'
    assert row.reset_button.toolTip()=='恢复默认音效'
    assert [button.text() for button in row.findChildren(QPushButton)]==['选择文件…']
    assert row.actions.itemAt(0).widget() is row.reset_button
    assert row.actions.itemAt(1).widget() is row.preview_button
    assert row.actions.itemAt(2).widget() is row.choose_button
    custom=str(s.tmp/'soft-custom.wav');c._set_sound('send',custom)
    assert row.file_label._full_value=='自定义：soft-custom.wav'
    assert row.file_label.toolTip()==custom and row.reset_button.isEnabled()
    row.reset_button.click()
    assert row.path=='' and not row.reset_button.isEnabled()
    assert not row.switch.isChecked() and s.config.get('sound_volume')==85
    assert not c.pending  # original was built-in


def test_footer_reset_geometry_reused_and_speaker_motion_respects_setting(audio):
    from PySide6.QtGui import QPainterPath,QTransform
    from PySide6.QtCore import QRectF,QAbstractAnimation
    from fluent_ui.presentation.action_glyphs import default_reset_path
    from fluent_ui import visual
    legacy=QPainterPath();legacy.addEllipse(QRectF(-10,-10,20,20))
    hole=QPainterPath();hole.addEllipse(QRectF(-6,-6,12,12));legacy=legacy.subtracted(hole)
    cut=QPainterPath();cut.addRect(QRectF(-2,-13,4,26));legacy=legacy.subtracted(QTransform().rotate(35).map(cut))
    assert legacy==default_reset_path() and not legacy.contains(QPointF(0,0))
    row=audio.center._sound_rows['send'];row.preview_button.click()
    assert row.preview_button.wave.state()==QAbstractAnimation.Running
    audio.config.config['ui_animations_enabled']=False;visual.theme.motion_changed.emit()
    assert row.previewing and row.preview_button.wave.state()==QAbstractAnimation.Stopped
    row.preview_button.click();assert not row.previewing


def test_preview_toggles_mutually_exclusive_finishes_and_uses_pending(audio):
    s=audio;c=s.center;send=c._sound_rows['send'];added=c._sound_rows['import']
    custom=s.tmp/'pending.wav';custom.write_bytes(b'controlled fake audio')
    c._set_sound('import',str(custom));c._rows['sound_volume'][0].spin.setValue(40)
    send.preview_button.click()
    player=s.config.ui_sound;effect=player.effect
    assert isinstance(effect,FakeEffect) and send.previewing
    assert send.preview_button.toolTip()=='停止试听' and not send.switch.isChecked()
    send.preview_button.click()
    assert not send.previewing and not effect.playing
    assert effect.play_count==1
    send.preview_button.click();added.preview_button.click()
    assert added.previewing and not send.previewing
    assert effect.source()==QUrl.fromLocalFile(str(custom.resolve()))
    from services.send_sound import perceptual_volume
    assert effect.gain==perceptual_volume(40)
    effect.finish()
    assert not added.previewing and added.preview_button.toolTip()=='试听'
    send.preview_button.click();c.discard()
    assert not effect.playing and not send.previewing


def test_preview_failure_feedback_normal_send_interruption_and_page_exit(audio):
    s=audio;c=s.center;send=c._sound_rows['send'];added=c._sound_rows['import']
    c.show_error=Mock()
    c._set_sound('send',str(s.tmp/'missing.wav'));send.preview_button.click()
    assert not send.previewing and c.show_error.call_count==1
    assert 'WAV' in str(c.show_error.call_args.args[1])
    send.reset_button.click();send.preview_button.click()
    player=s.config.ui_sound;effect=player.effect
    effect.fail()
    assert not send.previewing and c.show_error.call_count==2
    # Cached decode error also reports failure without latching a stop icon.
    send.preview_button.click()
    assert not send.previewing and c.show_error.call_count==3
    added.preview_button.click()
    s.config.set('send_sound_enabled',True)
    player.play(s.config)
    assert not added.previewing and player.preview_event==''
    added.preview_button.click();page(s,2,1)
    assert not effect.playing and player.preview_event==''


@pytest.mark.parametrize('lang',['zh','zh_TW','en','ja'])
def test_translated_source_tooltips_and_live_preview_state(audio,lang):
    s=audio;c=s.center;i18n_engine.load_language(lang)
    row=c._sound_rows['send']
    c._set_sound('send',str(s.tmp/'custom.wav'))
    row.preview_button.click()  # nonexistent source, uses existing error host
    row.set_previewing(True)
    assert '[MISSING:' not in row.preview_button.toolTip()
    assert '[MISSING:' not in row.reset_button.toolTip()
    assert '[MISSING:' not in str(row.file_label._full_value)
    assert '[MISSING:' not in c._rows['sound_volume'][0].reset_button.toolTip()
