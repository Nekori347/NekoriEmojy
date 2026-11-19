"""Representative save signal, existing widgets and real image pixels."""
import json
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import Mock
import pytest
from PIL import Image
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtGui import QImage,QColor,QPixmap,QPixmapCache
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from services.resource_import import ImportTarget
from fluent_ui.components.quick_panel import QuickPanel
from fluent_ui.components.dialogs import FramePickerDialog


def wait_until(predicate):
    deadline=monotonic()+5
    while not predicate() and monotonic()<deadline:
        QApplication.processEvents();sleep(.01)
    assert predicate()


def animation(s):
    path=s.tmp/'representative.gif';frames=[]
    for left,right in [('red','blue'),('green','yellow')]:
        image=Image.new('RGB',(100,60),left);image.paste(right,(50,0,100,60));frames.append(image)
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=100)
    saved,_=s.storage.save_file(str(path),target=ImportTarget(s.parent))
    s.g.refresh_content_incremental(paths=[saved],parents={s.parent})
    return saved


def gallery_cards(s,path):
    return [c for c in s.g.renderer.active.values() if getattr(c,'image_path',None)==path]


def save_through_menu(s,path,frame,crop,reset=False):
    errors=[]
    def accept():
        try:
            d=QApplication.activeModalWidget();assert isinstance(d,FramePickerDialog)
            if reset:d._reset()
            else:
                d.slider.setValue(frame)
                # Crop editing uses the current preview's real mouse events.
                d.preview.reset_crop()
                if crop:
                    r=d.preview._image_rect
                    a=QPoint(round(r.left()+r.width()*crop[0]),round(r.top()+r.height()*crop[1]))
                    b=QPoint(round(r.left()+r.width()*crop[2]),round(r.top()+r.height()*crop[3]))
                    QTest.mousePress(d.preview,Qt.LeftButton,pos=a);QTest.mouseMove(d.preview,b);QTest.mouseRelease(d.preview,Qt.LeftButton,pos=b)
                d._apply()
        except Exception as exc:
            errors.append(exc)
            if QApplication.activeModalWidget():QApplication.activeModalWidget().reject()
    QTimer.singleShot(100,accept);s.g._choose_thumbnail_frame(path)
    assert not errors,errors


def test_actual_save_crop_reedit_reset_updates_all_occurrences_and_existing_panel(surface,monkeypatch):
    s=surface;path=animation(s);s.storage.move_resources_to([path],s.child,copy=True)
    s.g._expanded_nodes.add(s.child);s.g.set_node(s.parent,force=True)
    s.storage.add_recent_image(path)
    panel=QuickPanel(s.storage,s.clipboard,s.config,representative_source=s.g)
    panel._perform_search();panel.show();panel._trigger_responsive_layout()
    try:
        wait_until(lambda:len(gallery_cards(s,path))==2)
        card=panel._all_card_widgets[0];identity=id(card);notifications=[]
        s.g.representative_changed.connect(notifications.append)
        monkeypatch.setattr(panel,'_perform_search',Mock(side_effect=AssertionError('single-resource change must not search')))
        save_through_menu(s,path,1,(.55,.1,.95,.9))
        panel.show();panel._trigger_responsive_layout();panel._apply_lazy_loading()
        wait_until(lambda:card._is_loaded and all(c._is_loaded and c.frame==1 for c in gallery_cards(s,path)))
        assert notifications==[path] and id(panel._all_card_widgets[0])==identity
        expected=s.storage.representative_crop(path)
        assert card.crop==expected and all(c.crop==expected for c in gallery_cards(s,path))
        for c in [card,*gallery_cards(s,path)]:
            color=c.pixmap().toImage().pixelColor(c.pixmap().width()//2,c.pixmap().height()//2)
            assert color.red()>230 and color.green()>230 and color.blue()<30
        save_through_menu(s,path,0,(.1,.1,.4,.9))
        panel.show();panel._trigger_responsive_layout();panel._apply_lazy_loading()
        wait_until(lambda:card._is_loaded and all(c._is_loaded and c.frame==0 for c in gallery_cards(s,path)))
        assert card.pixmap().toImage().pixelColor(1,1).red()>230
        save_through_menu(s,path,0,None,reset=True)
        panel.show();panel._trigger_responsive_layout();panel._apply_lazy_loading()
        wait_until(lambda:card._is_loaded and all(c._is_loaded and c.crop is None for c in gallery_cards(s,path)))
        assert notifications==[path]*3 and card.frame==0 and card.crop is None
        assert s.storage.index.animation_attribute(s.storage.resource_of(path)) is True
        assert id(panel._all_card_widgets[0])==identity
    finally:
        panel.shutdown();panel.deleteLater()


def test_hidden_panel_updates_parameters_without_loading_search_or_rebuild(surface,monkeypatch):
    s=surface;path=animation(s);panel=QuickPanel(s.storage,s.clipboard,s.config,representative_source=s.g)
    try:
        panel.search_box.setText('representative');panel.search_timer.stop();panel._perform_search()
        card=next(c for c in panel._all_card_widgets if c.image_path==path);old_id=id(card)
        search=Mock(wraps=s.storage.search_records);monkeypatch.setattr(s.storage,'search_records',search)
        load=Mock(wraps=card._load_thumbnail_async);monkeypatch.setattr(card,'_load_thumbnail_async',load)
        revision=s.storage.index.search_revision
        save_through_menu(s,path,1,(.55,.1,.95,.9))
        assert not panel.isVisible() and card.frame==1 and card.crop and not card._is_loaded
        assert not load.called and s.storage.index.search_revision==revision
        # Activate the same explicit search with real existing show logic, with
        # the native foreground request suppressed in this offscreen test only.
        monkeypatch.setattr('fluent_ui.components.quick_panel.user32.SetForegroundWindow',Mock())
        panel.show_at_cursor(search_text='representative')
        wait_until(lambda:card._is_loaded)
        assert id(panel._all_card_widgets[0])==old_id and not search.called
    finally:
        panel.shutdown();panel.deleteLater()


def test_atomic_pair_cancels_old_load_and_rejects_queued_stale_pixels(surface,monkeypatch):
    from fluent_ui.components import emoji_card as module
    s=surface;path=animation(s);tasks=[]
    card=module.EmojiCard(path,size=80,load_image=False)
    monkeypatch.setattr(module._thumbnail_pool,'start',lambda task,*args:tasks.append(task))
    try:
        card.update_size(80);old=tasks[-1]
        card.set_representative(1,(.55,.1,.95,.9))
        assert len(tasks)==2 and old._cancelled
        current=tasks[-1];key=card._cache_key(72)
        stale=QImage(12,12,QImage.Format_RGB32);stale.fill(QColor('magenta'))
        old.signals.finished.emit(path,stale,old.request_id,72)
        assert not card._is_loaded and not QPixmapCache.find(key,QPixmap())
        current.run();assert card._is_loaded
        old.signals.finished.emit(path,stale,old.request_id,72)
        color=card.pixmap().toImage().pixelColor(1,1)
        assert color.red()>230 and color.green()>230 and color.blue()<30
    finally:
        card.close();card.deleteLater()


def test_picker_snapshot_and_backfill_each_preserve_newer_metadata(surface,monkeypatch):
    from services.animation_attributes import _Batch,probe_animation
    s=surface;path=animation(s);idx=s.storage.index;record=idx.resource(path)
    def legacy():
        with idx.connect() as db:db.execute('UPDATE resources SET metadata_json=? WHERE id=?',('{}',record['id']))
    legacy();picker=FramePickerDialog(s.g,s.storage,path)
    try:
        # Enrichment while a stale picker is open must survive its actual save.
        assert idx.set_animation_attribute(idx.resource(path),True)
        picker.preview.crop=(.55,.1,.95,.9);picker.slider.setValue(1);picker._apply()
        assert idx.resource_metadata(record['id'])['animation']['animated'] is True
        assert s.storage.representative_crop(path)==(.55,.1,.95,.9)
        legacy();original=probe_animation
        def crop_during_probe(value):
            animated=original(value)
            s.storage.set_resource_metadata(path,{'thumb_frame':1,'thumb_crop':[.1,.2,.4,.8]})
            return animated
        with monkeypatch.context() as patch:
            patch.setattr('services.animation_attributes.probe_animation',crop_during_probe)
            _Batch(idx,'',Event(),s.storage.lock,targets=[record['id']]).run()
        assert s.storage.representative_crop(path)==(.1,.2,.4,.8)
        # The stale CAS was rejected, then an ordinary fresh pass merges it.
        _Batch(idx,'',Event(),s.storage.lock,targets=[record['id']]).run()
        data=idx.resource_metadata(record['id'])
        assert data['animation']['animated'] is True and data['thumb_frame']==1
        assert data['thumb_crop']==[.1,.2,.4,.8]
    finally:picker.deleteLater()

def test_hidden_search_retires_unlaid_cards_and_uses_result_records(surface, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from shiboken6 import isValid
    s = surface
    panel = QuickPanel(s.storage, s.clipboard, s.config)
    try:
        expected = s.storage.search_images('alpha')[:30]
        assert expected
        with monkeypatch.context() as patch:
            patch.setattr(s.storage.index, 'resource', Mock(side_effect=AssertionError('individual lookup')))
            panel.search_box.setText('alpha')
            panel.search_timer.stop()
            panel._perform_search()
        assert list(panel._cached_results) == expected
        cards = list(panel._all_card_widgets)
        assert cards and all(not card._is_loading for card in cards)
        panel.search_box.setText('no-match-opaque-test')
        panel.search_timer.stop()
        panel._perform_search()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        assert not panel._cached_results and all(not isValid(card) for card in cards)
    finally:
        panel.shutdown()
        panel.deleteLater()
