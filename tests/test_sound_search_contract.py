"""Registration/transaction tests; desktop keyboard acceptance is separate."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PySide6.QtCore import QObject,Signal,QUrl
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QWidget
from PySide6.QtTest import QTest
from test_phase2_interaction import surface,settle


def test_native_search_registration_rebind_failure_and_clear(surface):
    from fluent_ui.components.clipboard_search_command import ClipboardSearchCommand
    from services.import_hotkey import hotkey_parts
    center=SimpleNamespace(pending={},_hotkeys_valid=Mock())
    class Events(QObject):settings_changed=Signal(str)
    events=Events();center.settings_changed=events.settings_changed
    w=QWidget();w.settings_window=SimpleNamespace(center=center);w.search_clipboard_text=Mock()
    command=ClipboardSearchCommand(w,surface.config)
    assert command.hotkey.binding is None
    api=command.hotkey.api=Mock();api.RegisterHotKey.return_value=True
    assert command.configure({'clipboard_search_hotkey':'ctrl+alt+shift+F9'})
    first=command.hotkey.registration
    assert command.hotkey.binding==hotkey_parts('ctrl+alt+shift+F9')
    api.RegisterHotKey.return_value=False
    assert not command.configure({'clipboard_search_hotkey':'ctrl+alt+shift+F10'})
    assert command.hotkey.registration==first
    api.UnregisterHotKey.assert_not_called()
    api.RegisterHotKey.return_value=True
    assert command.configure({'clipboard_search_hotkey':'ctrl+alt+shift+F10'})
    api.UnregisterHotKey.assert_called_once_with(None,first)
    command.hotkey.activated.emit();settle(surface.app);w.search_clipboard_text.assert_called_once()
    assert not command.configure({'clipboard_search_hotkey':'alt+2'})
    assert command.configure({'clipboard_search_hotkey':''}) and command.hotkey.binding is None
    command.hotkey.close();w.deleteLater();settle(surface.app)


def test_save_failure_restores_previous_native_binding(surface,monkeypatch):
    from fluent_ui.views.settings_center import SettingsCenter
    center=SettingsCenter(surface.config,surface.storage);command=Mock();command.configure.return_value=True
    surface.config.clipboard_search_command=command
    center._stage('clipboard_search_hotkey','ctrl+alt+shift+F9')
    monkeypatch.setattr(surface.config,'_save_config',Mock(side_effect=OSError('not writable')))
    assert not center.save()
    assert command.configure.call_count==2
    assert command.configure.call_args.args[0]['clipboard_search_hotkey']==''
    center.close();center.deleteLater()


@pytest.mark.parametrize('mode,expected',[('batch',1),('image',1),('duplicates',0),('failed',0),('partial',0),('cancelled',0)])
def test_one_import_sound_only_after_successful_new_acceptance(surface,mode,expected,monkeypatch):
    from services.resource_import import ImportTarget
    from PIL import Image
    g=surface.g;q=g.imports;config=surface.config;config.config['import_sound_enabled']=True
    player=config.ui_sound=Mock()
    sources=[]
    for i in range(4):
        p=surface.tmp/f'sfx-{i}.png';Image.new('RGB',(19,21),(20+i*45,150,90)).save(p);sources.append(str(p))
    if mode=='image':
        image=QImage(23,19,QImage.Format_RGB32);image.fill(QColor('purple'));sources=[image]
    elif mode=='duplicates':
        sources=[surface.paths[0]]
        monkeypatch.setattr(q,'_ask_batch',lambda request,candidates:['reuse']*len(candidates))
    elif mode in {'failed','partial'}:
        invalid=surface.tmp/'invalid.png';invalid.write_bytes(b'not a PNG file')
        save=surface.storage._save_file_source
        def fail_invalid(source,*args,**kwargs):
            if source==str(invalid):raise ValueError('invalid test image')
            return save(source,*args,**kwargs)
        monkeypatch.setattr(surface.storage,'_save_file_source',fail_invalid)
        sources=([str(invalid)] if mode=='failed' else sources[:1]+[str(invalid)])
    rid=q.submit(sources,ImportTarget(surface.other),g)
    if mode=='cancelled':q.cancel(rid)
    from PySide6.QtCore import QEventLoop,QTimer
    loop=QEventLoop();timeout=QTimer();timeout.setSingleShot(True);timeout.timeout.connect(loop.quit)
    def changed(_identity):
        if q.requests[rid].state in {'completed','failed','cancelled'} and q.worker is None:loop.quit()
    q.changed.connect(changed)
    if q.worker is not None or q.requests[rid].state not in {'completed','failed','cancelled'}:
        timeout.start(20000);loop.exec();timeout.stop()
    q.changed.disconnect(changed)
    r=q.requests[rid];assert r.state in {'completed','failed','cancelled'}
    assert player.play.call_count==expected
    if expected:player.play.assert_called_once_with(config,event='import')


def test_events_share_one_voice_and_preview_uses_same_perceptual_gain(surface,tmp_path):
    from services.send_sound import sound_for,perceptual_volume,DEFAULT_SOUND,DEFAULT_IMPORT_SOUND
    config=surface.config;player=sound_for(config);assert sound_for(config) is player
    player.effect=effect=Mock();effect.source.return_value=QUrl()
    config.config.update(send_sound_enabled=True,import_sound_enabled=True,sound_volume=85)
    player.play(config);assert effect.setSource.call_args.args[0]==QUrl.fromLocalFile(str(DEFAULT_SOUND))
    player.play(config,event='import');assert effect.setSource.call_args.args[0]==QUrl.fromLocalFile(str(DEFAULT_IMPORT_SOUND))
    gain=effect.setVolume.call_args.args[0]
    player.play(config,event='import',preview=True)
    assert effect.setVolume.call_args.args[0]==gain==perceptual_volume(85)
    assert 0<perceptual_volume(50)<.5 and perceptual_volume(0)==0 and perceptual_volume(100)==1
    assert effect.stop.call_count==effect.play.call_count==3
    player.play(config,path=str(tmp_path/'missing.wav'));assert effect.play.call_count==3
    effect.play.side_effect=RuntimeError('decode failure');player.play(config)


def test_sound_settings_independent_save_discard_and_preview(surface,monkeypatch):
    from fluent_ui.views.settings_center import SettingsCenter
    center=SettingsCenter(surface.config,surface.storage);center._select_page(2);center._show_tab(2)
    player=surface.config.ui_sound=Mock()
    center._stage('send_sound_enabled',True);center._stage('import_sound_enabled',True)
    center._set_sound('send','press-custom.wav');center._set_sound('import','uncheck-custom.wav')
    center._stage('sound_volume',40);center._preview_sound('import')
    player.play.assert_called_once_with(surface.config,event='import',preview=True,path='uncheck-custom.wav',volume=40)
    center.discard()
    assert not surface.config.get('send_sound_enabled') and not surface.config.get('import_sound_enabled')
    assert surface.config.get('sound_volume')==85
    center._set_sound('import','uncheck-custom.wav');center._stage('import_sound_enabled',True)
    assert center.save()
    assert surface.config.get('import_sound_enabled') and not surface.config.get('send_sound_enabled')
    assert surface.config.get('send_sound_path')=='' and surface.config.get('import_sound_path')=='uncheck-custom.wav'
    center._set_sound('import','');assert center.save() and surface.config.get('import_sound_path')==''
    center.close();center.deleteLater()


def test_replaying_already_committed_import_does_not_sound_again(surface):
    from PIL import Image
    from services.resource_import import ImportTarget
    from services.task_recovery import ImportCheckpoint
    s=surface.storage;source=surface.tmp/'already-committed.png'
    Image.new('RGB',(31,29),(10,140,170)).save(source)
    checkpoint=ImportCheckpoint(s,'sound-replay')
    checkpoint.create([str(source)],ImportTarget(surface.other),None,False)
    unit=checkpoint.prepare()[0]
    s.import_context.checkpoint=('sound-replay',unit['id'])
    try:s.save_file(str(source),target=checkpoint.target(unit))
    finally:s.import_context.checkpoint=None
    player=surface.config.ui_sound=Mock();surface.config.config['import_sound_enabled']=True
    q=surface.g.imports;q.restore(surface.g);q.resume('sound-replay')
    for _ in range(200):
        QTest.qWait(20)
        if q.requests['sound-replay'].state=='completed':break
    assert q.requests['sound-replay'].state=='completed'
    assert q.requests['sound-replay'].saved==1
    player.play.assert_not_called()
