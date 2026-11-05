"""Settings IA contracts, using offscreen Qt and disposable configuration only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import sqlite3
from contextlib import contextmanager
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtTest import QTest

from services.config import ConfigService
from services.i18n import i18n_engine
from services.autostart import AutostartService
from fluent_ui import visual
from fluent_ui.components.setting_rows import SoundEventRow
from fluent_ui.views.settings_center import SettingsCenter, PREVIEW_KEYS


@pytest.fixture
def settings(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(AutostartService, 'is_enabled', lambda _: False)
    monkeypatch.setattr(AutostartService, 'set_enabled', Mock())
    config = ConfigService(tmp_path/'app')
    i18n_engine.init(config); visual.theme.configure(config)
    center = SettingsCenter(config)
    center.setAttribute(Qt.WA_DontShowOnScreen)
    center.resize(948, 674); center.show()
    for _ in range(4): app.processEvents()
    yield SimpleNamespace(app=app, center=center, config=config, tmp=tmp_path)
    center.hide(); center.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete); app.processEvents()


def page(s, navigation, tab):
    s.center._select_page(navigation); s.center._show_tab(tab)
    for _ in range(4): s.app.processEvents()


def test_exact_structure_and_single_ownership(settings):
    s=settings; c=s.center
    assert sum(len(tabs) for _,tabs in c._icon_pages()) == 17
    assert [name for name,_ in c._icon_pages()[2][1]] == ['快捷键','发送','音效','悬停预览']
    ownership={}
    for nav,(_,tabs) in enumerate(c._icon_pages()):
        for tab,(name,_) in enumerate(tabs):
            # Avoid constructing OCR or any data actions in this unit fixture.
            if name in ['文字识别','表情库管理','表情合集','Suzu 迁移','软件信息','软件图标']: continue
            page(s,nav,tab)
            for key in c._rows:
                assert key not in ownership, (key,ownership[key],name)
                ownership[key]=name
    assert ownership['hide_main_after_paste']=='发送'
    assert ownership['send_sound_path']==ownership['import_sound_enabled']=='音效'
    page(s,2,1)
    assert set(c._rows)=={'gallery_click_action','convert_static_to_gif','hide_main_after_paste'}
    assert [x.title_label.text() for x in c._sections]==['发送行为']
    page(s,1,1)
    assert [r.key for r in c._sections[0].body.findChildren(type(c._rows['thumbnail_size'][0]))]==['thumbnail_size','gallery_node_icon_size']
    assert [x.title_label.text() for x in c._sections]==['图库显示','分类栏','标签面板']


def test_sound_composite_pending_preview_discard_and_save(settings,monkeypatch):
    s=settings; c=s.center; page(s,2,2)
    cards=c.body_widget.findChildren(SoundEventRow)
    assert len(cards)==5 and len(c._rows)==11
    send,added=cards[:2]
    assert send.file_label.toolTip()=='内置音效'
    assert not send.file_label.clickable
    assert c._rows['sound_volume'][0].unit_label.text()=='%'
    player=s.config.ui_sound=Mock()
    QTest.mouseClick(send.switch,Qt.LeftButton)
    assert c.pending=={'send_sound_enabled':True}
    custom=str(s.tmp/'very-long-custom-sound.wav')
    c._set_sound('send',custom)
    assert send.path_field.value()==custom
    assert send.file_label.toolTip()==custom
    QTest.mouseClick(send.file_label,Qt.LeftButton)
    assert send.full_path_label.isVisible() and send.full_path_label.text()==custom
    assert send.full_path_label.textInteractionFlags() & Qt.TextSelectableByMouse
    c._rows['sound_volume'][0].spin.setValue(40)
    c._preview_sound('send')
    player.play.assert_called_once_with(s.config,event='send',preview=True,path=custom,volume=40)
    # Returning one field to its persisted value must not erase the other
    # field's pending visual state on their shared card.
    c._set_sound('send','')
    assert send.property('pending') and send.enabled_field.pending
    c.discard()
    assert not c.pending and not send.switch.isChecked() and not send.property('pending')
    assert send.path_field.value()=='' and not send.full_path_label.isVisible()
    c._set_sound('import',custom); QTest.mouseClick(added.switch,Qt.LeftButton)
    assert c.save()
    saved=ConfigService(s.tmp/'app')
    assert saved.get('import_sound_enabled') and saved.get('import_sound_path')==custom
    assert not saved.get('send_sound_enabled') and saved.get('send_sound_path')==''
    c._set_sound('import','')
    assert c.save() and s.config.get('import_sound_enabled')


def test_sound_page_defaults_and_all_defaults_use_existing_keys(settings,monkeypatch):
    s=settings; c=s.center
    for key,value in {'send_sound_enabled':True,'import_sound_enabled':True,
        'send_sound_path':'send.wav','import_sound_path':'add.wav','sound_volume':35}.items():
        s.config.set(key,value)
    page(s,2,2)
    monkeypatch.setattr('fluent_ui.components.dialogs.confirm',lambda *a,**k:True)
    c._restore_page_defaults()
    assert c.pending=={'send_sound_enabled':False,'import_sound_enabled':False,
        'send_sound_path':'','import_sound_path':'','sound_volume':85}
    assert s.config.get('send_sound_path')=='send.wav'
    c.discard()
    assert c._rows['send_sound_path'][0].value()=='send.wav'
    c._restore_all_defaults()
    assert c.pending['send_sound_path']=='' and c.pending['sound_volume']==85
    assert c.save()
    assert s.config.get('sound_volume')==85 and not s.config.get('import_sound_enabled')


def test_hotkey_status_preserves_help_and_native_rebind(settings):
    s=settings; c=s.center; page(s,2,0)
    assert [x.title_label.text() for x in c._sections]==['面板快捷键','快捷导入','Esc 隐藏面板']
    row=c._rows['clipboard_search_hotkey'][0]; help_text=row.hint_label.text()
    row._set(s.config.get('global_hotkey'))
    assert not c.btn_save.isEnabled()
    assert row.hint_label.text()==help_text
    assert '不能' in row.status_label.text()
    command=s.config.clipboard_search_command=Mock()
    command.hotkey.error=''; command.hotkey.binding=('test',)
    command.configure.return_value=True
    row._set('ctrl+alt+shift+f10')
    assert c.btn_save.isEnabled() and row.status_label.text()=='快捷键已生效'
    assert row.hint_label.text()==help_text
    assert c.save(); command.configure.assert_called_once()
    assert s.config.get('clipboard_search_hotkey')=='ctrl+alt+shift+f10'


def test_minimum_sound_layout_keeps_paths_controls_and_units_together(settings):
    s=settings; c=s.center; c.resize(688,474); page(s,2,2)
    volume=c._rows['sound_volume'][0]
    assert volume.unit_label.parentWidget() is volume.spin.parentWidget()
    long_path='C:/Audio/'+('Long sound folder name/'*7)+'Gentle notification with a long filename.wav'
    c._set_sound('send',long_path)
    row=c._rows['send_sound_path'][0].row
    QTest.mouseClick(row.file_label,Qt.LeftButton)
    for _ in range(5):s.app.processEvents()
    assert row.file_label.toolTip()==row.full_path_label.text()==long_path
    assert c.scroll.horizontalScrollBar().maximum()==0
    from PySide6.QtCore import QPoint,QRect
    for widget in [row.switch,row.file_label,row.full_path_label]+[row.actions.itemAt(i).widget() for i in range(3)]:
        assert row.rect().contains(QRect(widget.mapTo(row,QPoint()),widget.size()))
    page(s,2,3)
    assert c._rows['preview_delay'][0].unit_label.text()=='毫秒'


@pytest.mark.parametrize('key,value',[('sound_volume',-1),('sound_volume',101),('gallery_node_icon_size',13),('gallery_node_icon_size',49)])
def test_import_rejects_new_out_of_range_values(settings,monkeypatch,key,value):
    s=settings; c=s.center
    path=s.tmp/'settings.json';path.write_text(json.dumps({key:value}),encoding='utf-8')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    c.show_error=Mock();c._import_settings()
    c.show_error.assert_called_once();assert not c.pending


def test_import_bounds_accept_and_preview_rollback(settings,monkeypatch):
    s=settings; c=s.center
    path=s.tmp/'settings.json';path.write_text(json.dumps({'sound_volume':100,'gallery_node_icon_size':48}),encoding='utf-8')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    c._import_settings()
    assert c.pending=={'sound_volume':100,'gallery_node_icon_size':48}
    assert s.config.preview_values=={'gallery_node_icon_size':48}
    c.discard();assert not s.config.preview_values
    assert s.config.get('sound_volume')==85 and s.config.get('gallery_node_icon_size')==22
    assert 'sound_volume' not in PREVIEW_KEYS and 'show_new_resource_markers' in PREVIEW_KEYS


def test_star_clear_remains_a_save_side_effect(settings):
    s=settings; c=s.center; page(s,1,1)
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE resource_unseen(id INTEGER)')
    db.execute('INSERT INTO resource_unseen VALUES(1)');db.commit()
    @contextmanager
    def connect(**kwargs):
        with db:yield db
    c.storage=SimpleNamespace(lock=RLock(),index=SimpleNamespace(connect=connect),unseen_changed=Mock())
    row=c._rows['show_new_resource_markers'][0]
    assert '关闭并保存' in row.hint_label.text()
    row.switch.setChecked(False);c.discard()
    assert db.execute('SELECT COUNT(*) FROM resource_unseen').fetchone()[0]==1
    row.switch.setChecked(False);assert c.save()
    assert db.execute('SELECT COUNT(*) FROM resource_unseen').fetchone()[0]==0
    c.storage.unseen_changed.emit.assert_called_once();db.close();c.storage=None


@pytest.mark.parametrize('lang',['zh','zh_TW','en','ja'])
def test_language_labels_fit_and_no_new_untranslated_copy(settings,lang):
    s=settings; c=s.center
    i18n_engine.load_language(lang)
    page(s,0,2)
    index=c._current_tab;bar=c.tab_bar
    font=bar.font();font.setBold(True)
    required=QFontMetrics(font).horizontalAdvance(bar.tabText(index))+48
    assert bar.tabRect(index).width()>=required
    for button in (c.btn_defaults,c.btn_discard,c.btn_save):
        assert button.content_geometry()[1].width() >= QFontMetrics(visual.font()).horizontalAdvance(button.text())
    c.resize(688,474)
    for _ in range(4):s.app.processEvents()
    for button in (c.btn_defaults,c.btn_discard,c.btn_save):
        assert button.content_geometry()[1].width() >= QFontMetrics(visual.font()).horizontalAdvance(button.text())
    assert c._decision_bar.actions.x() >= 0
    for nav,tab in [(2,0),(2,1),(2,2),(2,3),(1,1)]:
        page(s,nav,tab)
        from PySide6.QtWidgets import QLabel,QAbstractButton
        for w in c.body_widget.findChildren(QLabel)+c.body_widget.findChildren(QAbstractButton):
            assert '[MISSING:' not in w.text(),w.text()
    assert c._rows['tag_panel_placement'][0].value()=='bottom'
