"""Representative frames and small UI revisions; isolated Library only."""
from pathlib import Path
from unittest.mock import Mock

from PySide6.QtGui import QImage
from test_phase2_interaction import surface


def assert_magenta(path):
    image=QImage(str(path));color=image.pixelColor(image.width()//2,image.height()//2)
    assert color.red()>240 and color.blue()>240 and color.green()<20


def test_existing_nonzero_representatives_before_convergence(surface,monkeypatch):
    from services.app_icon import ApplicationIconService
    from fluent_ui.components.emoji_card import _ThumbnailLoadTask
    s=surface;path=s.paths[4];s.storage.set_resource_metadata(path,{'thumb_frame':1})
    # Real picker flow notifies the existing incremental thumbnail refresh.
    s.g._reload_resource_thumbnail(path)
    entry=next(e for e in s.g._entries if e.get('path')==path)
    key,tier,frame,disk=s.g.renderer.loader.key(entry,120)
    assert frame==1
    images=[];task=_ThumbnailLoadTask(path,64,1,frame=frame)
    task.signals.finished.connect(lambda p,image,*_:images.append(image));task.run()
    assert images[0].pixelColor(8,8).green()<20
    manual=s.storage.create_node('Manual');s.g._set_category_icon(path,manual)
    assert_magenta(s.storage.node_icon_path(manual))
    s.config.config['auto_category_icons']=True
    auto=s.storage.create_node('First direct resource')
    s.storage.move_resources_to([path],auto,copy=True)
    assert_magenta(s.storage.node_icon_path(auto))
    s.config.config['auto_category_icons']=False
    fill=s.storage.create_node('Enable backfill');s.storage.move_resources_to([path],fill,copy=True)
    s.config.config['auto_category_icons']=True;s.storage.fill_missing_category_icons()
    assert_magenta(s.storage.node_icon_path(fill))
    from fluent_ui.views import gallery_view
    with monkeypatch.context() as patch:
        patch.setattr(gallery_view.dialogs,'confirm',lambda *a,**k:True)
        patch.setattr(s.g,'reload_application_icon',Mock())  # Fixture has no MainWindow.
        s.g._set_application_icon(path)
    assert_magenta(ApplicationIconService(s.config).current_path())
    s.storage.set_resource_metadata(path,{})
    for node in (manual,auto,fill):assert_magenta(s.storage.node_icon_path(node))


def test_nonmanual_reorder_is_silent(surface):
    s=surface;g=s.g;g.set_content_sort('recent_added');g.feedback_host.hint=Mock()
    assert not g._resource_drop_available([s.paths[0]],s.parent,{s.paths[0]:s.parent})
    assert not g._manual_order_available()
    g.feedback_host.hint.assert_not_called()
    assert g._resource_drop_available([s.paths[0]],s.child,{s.paths[0]:s.parent})
    g.set_content_sort('manual')
    assert g._resource_drop_available([s.paths[0]],s.parent,{s.paths[0]:s.parent})
    assert g._manual_order_available()


def test_quick_panel_uses_resource_representative(surface):
    from fluent_ui.components.quick_panel import QuickPanel
    s=surface;path=s.paths[4];s.storage.set_resource_metadata(path,{'thumb_frame':1})
    s.storage.add_recent_image(path)
    panel=QuickPanel(s.storage,s.clipboard,s.config,s.g,send_target_service=s.g.send_target_service)
    try:
        panel._perform_search(force=True)
        assert next(c for c in panel._all_card_widgets if c.image_path==path).frame==1
    finally:
        panel.shutdown();panel.close();panel.deleteLater()


def test_shared_resolver_identity_overrides_external_and_replacement(surface):
    import hashlib,io
    from PIL import Image
    from services.storage import StorageService
    from services.app_icon import ApplicationIconService
    from fluent_ui.components.dialogs import FramePickerDialog
    s=surface;path=s.paths[4];rid=s.storage.index.resource(path)['id']
    s.storage.set_resource_metadata(path,{'thumb_frame':1})
    s.storage.move_resources_to([path],s.child,copy=True)
    assert s.storage.representative_frame(rid)==1
    assert s.storage.representative_frame(s.storage.index.resource(path))==1
    assert s.storage.representative_frame(path,frame=0)==0
    assert StorageService(config=s.config).representative_frame(path)==1
    external=s.tmp/'outside.gif';external.write_bytes(Path(path).read_bytes())
    assert s.storage.representative_frame(str(external))==0
    explicit=s.storage.create_node('Explicit external')
    s.storage.set_node_icon(explicit,str(external),frame=1)
    assert_magenta(s.storage.node_icon_path(explicit))
    ApplicationIconService(s.config,storage=s.storage).set_from_image(str(external),frame=1)
    assert_magenta(ApplicationIconService(s.config).current_path())
    ApplicationIconService(s.config,storage=s.storage).set_from_image(str(external))
    icon=QImage(ApplicationIconService(s.config).current_path())
    assert icon.pixelColor(icon.width()//2,icon.height()//2).green()>240
    for bad in ('{broken','[]','{"thumb_frame":-1}','{"thumb_frame":"bad"}'):
        assert s.storage.representative_frame({'metadata_json':bad})==0
    picker=FramePickerDialog(s.g,s.storage,path);assert picker.slider.value()==1
    picker._reset();picker.deleteLater();assert s.storage.representative_frame(path)==0
    s.storage.set_resource_metadata(path,{'thumb_frame':1})
    data=io.BytesIO();Image.new('RGB',(18,18),'orange').save(data,format='PNG');payload=data.getvalue()
    replaced=s.storage.replace_normalized(path,(payload,'.png',hashlib.md5(payload).hexdigest()))
    assert s.storage.index.resource(replaced)['id']==rid
    assert s.storage.representative_frame(replaced)==0
    assert any(e['id']==rid for e in s.storage.index.content(s.child))


def test_consumers_use_shared_resource_rule_without_per_card_lookup(surface,monkeypatch):
    from services.app_icon import ApplicationIconService
    from services.ocr_data import source_stamp
    from fluent_ui.components.dialogs import FramePickerDialog
    s=surface;path=s.paths[4];record=s.storage.index.resource(path)
    resolver=Mock(wraps=s.storage.index.representative_frame)
    monkeypatch.setattr(s.storage.index,'representative_frame',resolver)
    s.storage.set_resource_metadata(path,{'thumb_frame':1});s.g._reload_resource_thumbnail(path)
    entry=next(e for e in s.g._entries if e.get('path')==path)
    with monkeypatch.context() as patch:
        patch.setattr(s.storage.index,'resource',Mock(side_effect=AssertionError('record path must not query')))
        assert s.g.renderer.loader.key(entry,120)[2]==1
        widget=s.g._create_widget(entry,120);assert widget.frame==1;widget.deleteLater()
    node=s.storage.create_node('Unified icon');s.storage.set_node_icon(node,path)
    assert_magenta(s.storage.node_icon_path(node))
    ApplicationIconService(s.config,storage=s.storage).set_from_image(path)
    assert_magenta(ApplicationIconService(s.config).current_path())
    assert source_stamp(s.storage.index,s.storage.index.resource(path))['thumbnail']==1
    picker=FramePickerDialog(s.g,s.storage,path);assert picker.slider.value()==1;picker.deleteLater()
    assert resolver.call_count>=6


def test_inline_anim_and_gallery_share_same_painter(surface,monkeypatch):
    from fluent_ui import visual
    from fluent_ui.components.keycap_label import KeycapLabel
    from fluent_ui.components.emoji_card import EmojiCard
    from PySide6.QtGui import QTextCursor
    s=surface;calls=[];original=visual.paint_animation_badge
    def paint(painter,rect):
        # Never retain a widget's active QPainter in Mock.call_args.
        calls.append((rect.width(),rect.height()));original(painter,rect)
    monkeypatch.setattr(visual,'paint_animation_badge',paint)
    label=KeycapLabel('Before {animation_badge} after',s.g);label.resize(300,35)
    label.grab();assert calls
    document=label._document;cursor=QTextCursor(document)
    assert '\ufffc' in document.toPlainText() and '{animation_badge}' not in document.toPlainText()
    calls.clear();card=EmojiCard(s.paths[4],parent=s.g,load_image=False)
    card._animated=True;card.grab();assert calls
    label.deleteLater();card.deleteLater()
