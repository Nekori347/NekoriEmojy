"""Round 2: isolated data; no desktop input, formal Library or installed app."""
from pathlib import Path
from unittest.mock import Mock
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from services.library_index import ROOT
from services.resource_import import ImportTarget


def test_one_time_icons_preserve_manual_and_canonical_order(surface,monkeypatch):
    s=surface;s.config.set('auto_category_icons',True)
    s.storage.set_node_icon(s.other,'manual')
    before=s.storage.index.content(s.parent)
    s.storage.fill_missing_category_icons()
    icon=s.storage.node(s.parent)['icon'];assert icon.startswith('category_icons/')
    assert s.storage.node(s.other)['icon']=='manual'
    assert s.storage.index.content(s.parent)==before
    s.storage.move_resources_to([s.paths[3]],s.parent,copy=True)
    assert s.storage.node(s.parent)['icon']==icon
    empty=s.storage.create_node('Empty parent');s.storage.move_node(s.child,empty)
    s.storage.fill_missing_category_icons();assert not s.storage.node(empty)['icon']
    fresh=s.storage.create_node('Fresh')
    s.storage.move_resources_to([s.paths[4]],fresh,copy=True)
    assert s.storage.node(fresh)['icon'].endswith('.png')
    s.storage.set_node_icon(fresh,'manual wins')
    assert not s.storage.ensure_category_icon(fresh,s.paths[0])
    assert s.storage.node(fresh)['icon']=='manual wins'
    failed=s.storage.create_node('Failed icon')
    monkeypatch.setattr(s.storage,'_store_node_icon_file',Mock(side_effect=OSError('synthetic failure')))
    assert s.storage.move_resources_to([s.paths[0]],failed,copy=True)==1
    assert not s.storage.node(failed)['icon']
    with monkeypatch.context() as patch:
        patch.setattr(s.storage.index,'connect',Mock(side_effect=PermissionError('synthetic database unavailable')))
        assert s.storage.fill_missing_category_icons()==0


def test_icons_cover_import_duplicate_enable_restart_and_manual_race(surface,monkeypatch):
    from PIL import Image
    from services.storage import StorageService
    s=surface;node=s.storage.create_node('Enabled later')
    s.storage.save_file(s.paths[0],target=ImportTarget(node))
    assert not s.storage.node(node)['icon']
    s.config.set('auto_category_icons',True);s.storage.fill_missing_category_icons()
    assert s.storage.node(node)['icon']
    fresh=s.storage.create_node('New import')
    for index,color in enumerate(('lavender','olive')):
        path=s.tmp/f'import-{index}.png';Image.new('RGB',(37+index,43),color).save(path)
        s.storage.save_file(str(path),target=ImportTarget(fresh))
        if index==0:first=s.storage.node(fresh)['icon']
        assert s.storage.node(fresh)['icon']==first
    assert StorageService(config=s.config).node(fresh)['icon']==first
    raced=s.storage.create_node('Concurrent manual icon')
    original=s.storage._store_node_icon_file
    def manual_during_render(path,*,frame=0,crop=None):
        s.storage.index.update_node(raced,icon='manual raced')
        return original(path,frame=frame,crop=crop)
    monkeypatch.setattr(s.storage,'_store_node_icon_file',manual_during_render)
    assert not s.storage.ensure_category_icon(raced,s.paths[0])
    assert s.storage.node(raced)['icon']=='manual raced'


def test_subtree_title_counts_are_distinct_without_changing_direct_counts(surface):
    s=surface;g=s.g
    s.storage.move_resources_to([s.paths[0]],s.child,copy=True)
    direct=s.storage.node_counts()[s.parent]['resources']
    counts=s.storage.subtree_resource_counts()
    assert counts[s.parent]==direct+1
    assert s.storage.node_counts()[s.parent]['resources']==direct
    g.set_node(s.parent,force=True)
    assert str(counts[s.parent]) in g.location_rail.count_label.text()
    s.storage.move_node(s.child,s.other)
    assert s.storage.subtree_resource_counts()[s.parent]==direct


def test_frame_buttons_share_slider_boundaries_and_saved_frame(surface):
    from fluent_ui.components.dialogs import FramePickerDialog
    s=surface;dialog=FramePickerDialog(s.g,s.storage,s.paths[4]);dialog.slider.setValue(0)
    assert not dialog.previous_frame.isEnabled() and dialog.next_frame.isEnabled()
    dialog.next_frame.click();assert dialog.slider.value()==1 and not dialog.next_frame.isEnabled()
    dialog.previous_frame.click();assert dialog.slider.value()==0
    dialog.next_frame.click();dialog._apply()
    assert s.storage.resource_metadata(s.paths[4])['thumb_frame']==1
    dialog.deleteLater()


def test_unsupported_resume_does_not_construct_an_orphan_worker(surface):
    from fluent_ui.views.gallery_view import ImportThread
    q=surface.g.imports
    rid=q.submit(['http://127.0.0.1/never-accessed.png'],ImportTarget(surface.parent),surface.g)
    q.requests[rid].phase='restored'
    q._next()
    assert q.requests[rid].state=='interrupted' and q.worker is None
    assert not q.findChildren(ImportThread)


def test_thumbnail_disk_cache_never_reopens_original_for_anim(surface,monkeypatch):
    from PIL import Image
    from fluent_ui.components.emoji_card import _ThumbnailLoadTask
    from services.animation_attributes import probe_animation
    s=surface
    for fmt,suffix in (('GIF','.gif'),('WEBP','.webp'),('PNG','.png')):
        path=s.tmp/('animated'+suffix);disk=s.tmp/('cached'+suffix+'.png')
        Image.new('RGBA',(39,35),'red').save(path,format=fmt,save_all=True,
            append_images=[Image.new('RGBA',(39,35),'blue')],duration=100,loop=0)
        assert probe_animation(path) is True
        task=_ThumbnailLoadTask(str(path),64,1,cache_file=str(disk));images=[]
        task.signals.finished.connect(lambda p,image,*_:images.append(image));task.run()
        assert not images[0].isNull() and not images[0].text('nekori.animation_frames')
        path.unlink()  # Disk cache is sufficient, not an animation metadata carrier.
        with monkeypatch.context() as patch:
            patch.setattr(Image,'open',Mock(side_effect=AssertionError('thumbnail must not probe animation')))
            cached=_ThumbnailLoadTask(str(path),64,2,cache_file=str(disk));result=[]
            cached.signals.finished.connect(lambda p,image,*_:result.append(image));cached.run()
            assert not result[0].isNull()


def test_badge_state_survives_gallery_cache_and_clears_on_card_reuse(surface):
    import time
    s=surface;g=s.g;deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        s.app.processEvents();time.sleep(.01)
        cards={c.image_path:c for c in g._all_card_widgets if hasattr(c,'image_path')}
        if cards[s.paths[4]]._is_loaded:break
    animated=cards[s.paths[4]];still=cards[s.paths[0]]
    assert animated._animated and not still._animated
    animated.clear_resources();assert animated._animated
    g.renderer.loader.request([animated]);s.app.processEvents()
    assert animated._animated  # resource index supplies animation independently of the pixmap


def test_animation_count_ignores_apng_poster_and_untrusted_source_text(surface):
    from PIL import Image,PngImagePlugin
    from services.image_frames import frame_count
    from fluent_ui.components.emoji_card import _ThumbnailLoadTask
    s=surface
    path=s.tmp/'single-with-text.png';info=PngImagePlugin.PngInfo();info.add_text('nekori.animation_frames','99')
    Image.new('RGB',(23,25),'red').save(path,pnginfo=info)
    task=_ThumbnailLoadTask(str(path),64,1);result=[]
    task.signals.finished.connect(lambda p,image,*_:result.append(image));task.run()
    from services.animation_attributes import probe_animation
    assert probe_animation(path) is False
    for count in (1,2):
        path=s.tmp/f'poster-{count}.png'
        Image.new('RGBA',(29,31),'red').save(path,save_all=True,default_image=True,
            append_images=[Image.new('RGBA',(29,31),color) for color in ('blue','green')[:count]],duration=100,loop=0)
        assert frame_count(path)==count+1  # Picker still sees the poster as a selectable frame.
        assert frame_count(path,animation_only=True)==count
        assert probe_animation(path) is (count > 1)


def test_new_resource_focus_is_independent_and_rejects_quick_pass_reuse_drag(surface,monkeypatch):
    from PySide6.QtCore import QPoint,QPointF,QEvent,Qt
    from PySide6.QtGui import QCursor,QMouseEvent
    from PySide6.QtWidgets import QApplication
    s=surface;g=s.g;markers=g.new_markers
    s.config.set('preview_delay',3000)
    card=next(c for c in g._all_card_widgets if getattr(c,'image_path',None)==s.paths[0])
    identity=card.entry_id;position=[100,100]
    monkeypatch.setattr(QCursor,'pos',lambda:QPoint(*position))
    monkeypatch.setattr(QApplication,'widgetAt',lambda *_:card)
    event=QMouseEvent(QEvent.MouseMove,QPointF(4,4),QPointF(100,100),Qt.NoButton,Qt.NoButton,Qt.NoModifier)
    markers.last_pointer=QPoint();markers.eventFilter(card,event)
    assert markers.timer.interval()==300 and markers.timer.isActive()
    QTest.qWait(80);markers.eventFilter(card,QEvent(QEvent.Leave));QTest.qWait(250)
    assert identity in s.storage.unseen_resource_ids()
    position[0]+=1;markers.eventFilter(card,event);card.entry_id='reused-card';markers.confirm();card.entry_id=identity
    assert identity in s.storage.unseen_resource_ids()
    markers.cancel();position[0]+=1;card._is_dragging=True;markers.eventFilter(card,event)
    assert markers.pending is None;card._is_dragging=False
    position[0]+=1;markers.eventFilter(card,event);QTest.qWait(350)
    assert identity not in s.storage.unseen_resource_ids()
    markers.pending=(card,identity,card.mapToGlobal(card.rect().topLeft()))
    g.set_node(s.other);assert markers.pending is None


def test_setting_hint_uses_real_star_and_new_settings_have_save_semantics(surface):
    from fluent_ui.views.settings_center import SettingsCenter,PREVIEW_KEYS
    from fluent_ui.components.keycap_label import KEY_OBJECT,KEY_TEXT
    s=surface;center=SettingsCenter(s.config,s.storage)
    center._select_page(1);center._show_tab(1)
    row=center._all_rows['show_new_resource_markers'][0]
    doc=row.hint_label._document;found=False
    for position in range(doc.characterCount()-1):
        from PySide6.QtGui import QTextCursor
        cursor=QTextCursor(doc);cursor.setPosition(position);cursor.movePosition(QTextCursor.NextCharacter,QTextCursor.KeepAnchor)
        fmt=cursor.charFormat()
        found=found or (fmt.objectType()==KEY_OBJECT and fmt.property(KEY_TEXT)=='{new_resource_icon}')
    assert found and 'show_animation_badges' in PREVIEW_KEYS
    assert 'auto_category_icons' not in PREVIEW_KEYS  # enabling must wait for Save
    center._stage('auto_category_icons',True);assert not s.storage.node(s.parent)['icon']
    assert center.save() and s.storage.node(s.parent)['icon']
    center.discard();center.close();center.deleteLater()
