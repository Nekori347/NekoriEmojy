"""Focused regressions for the next Source-only round, using isolated Qt/data."""
from unittest.mock import Mock
from types import SimpleNamespace
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from test_wpb_closeout import gallery
from test_phase2_interaction import surface, settle
import pytest


def test_single_notice_has_persistent_expand_entry(surface):
    h=surface.g.feedback_host;h.dock_to_caption(surface.g)
    h.notice('one retained notice', error=True)
    settle(surface.app)
    assert h._caption_ui.ear.isHidden()
    h._caption_ui.expand();settle(surface.app)
    assert h._caption_ui.opened


def test_drag_end_drops_transient_hover_not_multi_selection(gallery, monkeypatch):
    g,storage,parent,children,paths=gallery
    card=next(c for c in g._all_card_widgets if hasattr(c,'image_path'))
    g.selected_keys=set(paths[:2]);g._commit_selection_visuals()
    card.set_hovered(True)
    card._drag_start_pos=__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(1,1)
    monkeypatch.setattr('services.external_drag.execute_resource_drag',lambda drag:False)
    event=QMouseEvent(QMouseEvent.MouseMove,QPointF(40,30),QPointF(40,30),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(card,event)
    assert not card._hovered
    assert g.selected_keys==set(paths[:2])


def test_default_new_import_precedes_manual_sequence(gallery, tmp_path):
    from PIL import Image
    from services.resource_import import ImportTarget
    g,s,parent,children,paths=gallery
    old=s.index.content(parent)
    sources=[]
    for i in range(2):
        p=tmp_path/f'fresh{i}.png';Image.new('RGB',(19,19),(230,i*100,90)).save(p);sources.append(str(p))
    result=s.importer.paths(sources,ImportTarget(parent))
    assert not result.errors
    assert [e['id'] for e in s.index.content(parent)[:2]]==[s._resource_id(p) for p in result.paths]
    assert [(e['kind'],e['id']) for e in s.index.content(parent)[2:]]==[(e['kind'],e['id']) for e in old]


def test_plain_single_reorder_releases_selection(gallery):
    from fluent_ui.components.drop_contract import DropTarget, INSERT_BEFORE
    g,s,parent,children,paths=gallery
    g._select_key(paths[0],Qt.NoModifier)
    target=SimpleNamespace(container_id=parent,target_id=s._resource_id(paths[3]),placement=INSERT_BEFORE,index=3)
    g._reorder_by_drop(paths[:1],target)
    assert not g.selected_keys


def test_progress_press_reaches_window_move(surface, monkeypatch):
    from PySide6.QtCore import QPoint
    g=surface.g;g.titleBar=QWidget(g);g.titleBar.setGeometry(0,0,g.width(),40)
    g.titleBar.minBtn=QWidget(g.titleBar);g.titleBar.minBtn.move(g.width()-90,0)
    g.titleBar.show()
    h=g.feedback_host;h.dock_to_caption(g);h.upsert_task('work','running',current=1,total=10)
    settle(surface.app)
    handle=Mock();handle.startSystemMove.return_value=True
    monkeypatch.setattr(g,'windowHandle',lambda:handle)
    p=h.progress.rect().center();gp=h.progress.mapToGlobal(p)
    event=QMouseEvent(QMouseEvent.MouseButtonPress,QPointF(p),QPointF(gp),Qt.LeftButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(h.progress,event)
    handle.startSystemMove.assert_called_once()


def test_tab_double_click_enters_category_once(gallery):
    from PySide6.QtTest import QTest
    g,s,parent,children,paths=gallery
    tabs=g.category_tabs
    index=g._tab_nodes.index(children[0])
    calls=[];original=g.set_node
    g.set_node=lambda node:(calls.append(node),original(node))[-1]
    QTest.mouseDClick(tabs,Qt.LeftButton,pos=tabs.content_tab_rect(index).center())
    assert calls==[children[0]] and g.current_node==children[0]
    QTest.mouseDClick(tabs,Qt.LeftButton,pos=tabs.rect().bottomRight())
    assert calls==[children[0]]


def test_quick_search_survives_wake_and_updates_open_panel(surface,monkeypatch):
    from fluent_ui.components.quick_panel import QuickPanel
    from fluent_ui.main_window import MainWindow
    from PySide6.QtCore import QMimeData
    monkeypatch.setattr('fluent_ui.components.quick_panel.user32',Mock())
    service=Mock()
    quick=QuickPanel(surface.storage,surface.clipboard,surface.config,send_target_service=service)
    window=SimpleNamespace(quick_panel=quick)
    app=surface.app
    mime=QMimeData();mime.setText('  alpha  ');app.clipboard().setMimeData(mime)
    MainWindow.search_clipboard_text(window)
    assert quick.isVisible() and quick.search_box.text()=='alpha'
    assert quick._cached_query[0]=='alpha'
    app.clipboard().setText('beta');MainWindow.search_clipboard_text(window)
    assert quick.isVisible() and quick.search_box.text()=='beta'
    assert quick._cached_query[0]=='beta' and not quick.search_timer.isActive()
    app.clipboard().setText(' ');MainWindow.search_clipboard_text(window)
    assert quick.search_box.text()=='beta' and app.clipboard().text()==' '
    quick.show_at_cursor();assert quick.search_box.text()==''
    assert service.capture_foreground.call_count==3
    quick.close();quick.deleteLater();settle(app)


def test_search_hotkey_conflicts_with_all_existing_keys(surface):
    from fluent_ui.views.settings_center import SettingsCenter
    center=SettingsCenter(surface.config,surface.storage)
    for text in ('ctrl+shift+e','alt+2','ctrl+alt+v'):
        assert not center._hotkeys_valid({'clipboard_search_hotkey':text})
    assert center._hotkeys_valid({'clipboard_search_hotkey':''})
    assert center._hotkeys_valid({'clipboard_search_hotkey':'ctrl+alt+F8'})
    assert not center._hotkeys_valid({'clipboard_search_hotkey':'bogus'})
    center.close();center.deleteLater()


def test_existing_panel_hooks_keep_their_bindings(surface,monkeypatch):
    import sys
    from fluent_ui.main_window import MainWindow,HotkeySignal
    config={'global_hotkey':'ctrl+shift+e','quick_panel_hotkey':'alt+2',
            'clipboard_search_hotkey':'ctrl+alt+F8'}
    listener=Mock();callbacks={}
    def register(values):callbacks.update(values);return listener
    monkeypatch.setitem(sys.modules,'pynput',SimpleNamespace(keyboard=SimpleNamespace(GlobalHotKeys=register)))
    search=Mock();window=SimpleNamespace(config=config,hotkey_listener=None,
        _request_toggle_window=Mock(),_request_toggle_quick_panel=Mock(),search_clipboard_text=search)
    window._parse_pynput_hotkey=lambda text:MainWindow._parse_pynput_hotkey(window,text)
    window.bind_global_hotkey=lambda:MainWindow.bind_global_hotkey(window)
    window.hotkey_signal=HotkeySignal()
    window.bind_global_hotkey()
    assert len(callbacks)==2
    assert '<ctrl>+<alt>+<f8>' not in callbacks
    search.assert_not_called()
    listener.start.assert_called_once()


def test_ctrl_single_selection_survives_sort(gallery):
    from fluent_ui.components.drop_contract import INSERT_BEFORE
    g,s,parent,children,paths=gallery
    g._select_key(paths[0],Qt.ControlModifier)
    target=SimpleNamespace(container_id=parent,target_id=s._resource_id(paths[3]),placement=INSERT_BEFORE,index=3)
    g._reorder_by_drop(paths[:1],target)
    assert g.selected_keys==set(paths[:1])


@pytest.mark.parametrize('outcome',['sent','copy','failed'])
def test_only_successful_send_plays_once(surface,monkeypatch,outcome):
    from test_phase1_logic import sender
    from services.send_target import SendResult
    play=Mock();monkeypatch.setattr('services.send_sound.SendSound.play',play)
    service,api,pending,injector=sender();service.remember(101)
    clipboard=Mock();clipboard.copy_image_to_clipboard.return_value=outcome!='failed'
    if outcome=='copy':api.windows.pop(101)
    result=[]
    service.send(surface.paths[0],clipboard,surface.storage,result.append)
    while pending:pending.pop(0)()
    assert result==[{'sent':SendResult.SENT,'copy':SendResult.COPIED_ONLY,'failed':SendResult.COPY_FAILED}[outcome]]
    assert play.call_count==int(outcome=='sent')


def test_sound_default_custom_preview_and_no_overlap(surface,tmp_path):
    from services.send_sound import SendSound,DEFAULT_SOUND
    from PySide6.QtCore import QUrl
    sound=SendSound();effect=Mock();sound.effect=effect;effect.source.return_value=QUrl()
    sound.play(surface.config);effect.play.assert_not_called()
    surface.config.config['send_sound_enabled']=True
    from pathlib import Path
    sound.play(surface.config);assert Path(effect.setSource.call_args.args[0].toLocalFile())==DEFAULT_SOUND.resolve()
    custom=tmp_path/'custom.wav';custom.write_bytes(DEFAULT_SOUND.read_bytes())
    surface.config.config['send_sound_path']=str(custom)
    sound.play(surface.config);sound.play(surface.config)
    assert effect.stop.call_count==effect.play.call_count==3
    surface.config.config['send_sound_enabled']=False
    sound.play(surface.config,preview=True,path='');assert effect.play.call_count==4
    effect.play.side_effect=RuntimeError('audio unavailable')
    sound.play(surface.config,preview=True)


def test_sound_settings_staged_save_and_discard(surface):
    from fluent_ui.views.settings_center import SettingsCenter
    center=SettingsCenter(surface.config,surface.storage)
    center._select_page(2);center._show_tab(2)
    center._set_send_sound('test.wav')
    assert surface.config.get('send_sound_path')=='' and center.pending['send_sound_path']=='test.wav'
    center.discard();assert center._all_rows['send_sound_path'][0].value()==''
    center._set_send_sound('test.wav');center._stage('send_sound_enabled',True)
    assert center.save()
    assert surface.config.get('send_sound_path')=='test.wav' and surface.config.get('send_sound_enabled')
    center.close();center.deleteLater()


def test_real_title_layout_and_buttons_keep_their_input(surface,monkeypatch):
    from PySide6.QtWidgets import QWidget
    from PySide6.QtTest import QTest
    from fluent_ui.window_shell import NekoriTitleBar
    from fluent_ui.components.controls import TransparentToolButton
    from fluent_ui.components.feedback import FeedbackHost
    owner=QWidget();owner.resize(1100,700)
    title=owner.titleBar=NekoriTitleBar(owner);title.resize(1100,40)
    title.titleLabel.hide()  # The real MainWindow uses the icon, not title text.
    title.themeButton=TransparentToolButton(title);title.themeButton.setFixedSize(24,24)
    title.hBoxLayout.insertSpacing(3,12)
    title.hBoxLayout.insertWidget(4,title.themeButton)
    owner.show();title.show()
    h=FeedbackHost(owner);h.dock_to_caption(owner)
    cancel=Mock();h.upsert_task('work','progress',current=1,total=10,cancel=cancel)
    settle(surface.app)
    u=h._caption_ui;ear=u.ear
    button=title.notificationButton
    assert button is not ear and isinstance(button,TransparentToolButton)
    assert ear.parentWidget() is u.controls and title.hBoxLayout.indexOf(ear)==-1
    assert title.hBoxLayout.indexOf(button)==title.hBoxLayout.indexOf(title.themeButton)+1
    assert button.isVisible() and button.size()==title.themeButton.size()
    assert button.x()>=title.themeButton.geometry().right()
    assert not title.canDrag(button.geometry().center())
    button.click();assert u.opened
    button.click();assert not u.opened
    h.notice('retained',error=True);settle(surface.app)
    handle=Mock();monkeypatch.setattr(owner,'windowHandle',lambda:handle)
    u.cover.hide();QTest.mouseClick(h.action_button,Qt.LeftButton)
    cancel.assert_called_once();handle.startSystemMove.assert_not_called()
    button.click();assert u.opened
    owner.resize(400,700);title.resize(400,40);settle(surface.app)
    assert h.strip.x()>=button.geometry().right()+1
    assert h.strip.geometry().right()<title.minBtn.x()
    from fluent_ui import visual
    visual.theme.refresh();settle(surface.app)
    assert title.notificationButton is button and u.ear.parentWidget() is u.controls
    h.remove_task('work');h.remove_task(next(iter(h.named_tasks)))
    assert button.isHidden() and ear.isHidden() and title.canDrag(button.geometry().center())
    owner.close();owner.deleteLater();settle(surface.app)


def test_empty_category_queue_preserves_batch_order_and_restart(surface):
    from fluent_ui.components.import_queue import ImportQueue
    from services.resource_import import ImportTarget
    from PySide6.QtTest import QTest
    from PIL import Image
    s=surface.storage;node=s.create_node('empty destination');sources=[]
    for i in range(3):
        p=surface.tmp/f'queue{i}.png';Image.new('RGB',(17,17),(i*70,180,240)).save(p);sources.append(str(p))
    rid=surface.g.imports.submit(sources,ImportTarget(node),surface.g)
    for _ in range(300):
        QTest.qWait(20)
        if surface.g.imports.requests[rid].state in {'completed','failed','cancelled'}:break
    request=surface.g.imports.requests[rid]
    assert request.state=='completed'
    entries=s.entries_of(node)
    assert [e['resource']['display_name'] for e in entries]==[f'queue{i}.png' for i in range(3)]
    from services.library_index import LibraryIndex
    assert LibraryIndex(s.library_root).content(node)==s.index.content(node)
    assert {e['id'] for e in entries}<=s.unseen_resource_ids()
