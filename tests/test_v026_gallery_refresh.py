"""Focused gallery state regressions; disposable library and offscreen Qt."""
import json,hashlib
from PIL import Image,GifImagePlugin
from PySide6.QtGui import QImage
from test_phase2_interaction import surface

def test_animation_badge_probes_only_second_gif_frame(tmp_path,monkeypatch):
    from services.animation_attributes import probe_animation
    path=tmp_path/'long.gif'
    frames=[Image.new('RGB',(17,19),(i*7,0,255-i*7)) for i in range(30)]
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=10)
    calls=[];original=GifImagePlugin.GifImageFile.seek
    def seek(self,frame):calls.append(frame);return original(self,frame)
    monkeypatch.setattr(GifImagePlugin.GifImageFile,'seek',seek)
    assert probe_animation(path) is True
    assert max(calls)<=1

def test_enable_auto_icons_updates_existing_gallery_projection(surface):
    s=surface;g=s.g
    entry=next(e for e in g._entries if e['kind']=='node' and e['id']==s.child)
    assert not entry['icon']
    s.config.set('auto_category_icons',True);s.storage.fill_missing_category_icons()
    icon=s.storage.node(s.child)['icon'];assert icon
    g.on_settings_changed('auto_category_icons');s.app.processEvents()
    assert next(e for e in g._entries if e['kind']=='node' and e['id']==s.child)['icon']==icon

def test_crop_cache_preserves_uncropped_identity_and_uses_record(surface,monkeypatch):
    s=surface;loader=s.g.renderer.loader
    entry=next(e for e in s.g._entries if e['kind']=='resource' and e['path']==s.paths[0])
    monkeypatch.setattr(s.storage.index,'resource',lambda *args: (_ for _ in ()).throw(AssertionError('per-card SQL')))
    first=loader.key(entry,120)[0]
    from fluent_ui.components.emoji_card import ThumbnailCache
    identity=(ThumbnailCache.library_identity(),entry['id'],loader.revisions[entry['path']],128,s.storage.representative_frame(entry['resource']))
    assert first=='gallery:'+hashlib.sha256(repr(identity).encode()).hexdigest()
    original=entry['resource']['metadata_json']
    metadata=json.loads(original or '{}');metadata['thumb_crop']=[0.1,0.1,0.8,0.9]
    entry['resource']['metadata_json']=json.dumps(metadata)
    assert loader.key(entry,120)[0]!=first
    entry['resource']['metadata_json']=original
    assert loader.key(entry,120)[0]==first

def test_representative_apply_refreshes_once_for_multiple_occurrences(surface,monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from fluent_ui.views import gallery_view
    s=surface;g=s.g;path=s.paths[4]
    reload=Mock();monkeypatch.setattr(g,'_reload_resource_thumbnail',reload)
    dialog=Mock();dialog.exec.return_value=1
    monkeypatch.setattr(gallery_view.dialogs,'FramePickerDialog',Mock(return_value=dialog))
    with monkeypatch.context() as patch:
        patch.setattr(g,'_all_card_widgets',[SimpleNamespace(image_path=path,set_frame=lambda frame:reload(path)) for _ in range(2)])
        g._choose_thumbnail_frame(path)
    reload.assert_called_once_with(path)

def test_thumbnail_cache_namespace_follows_owner_storage_not_demo_env(surface,monkeypatch):
    from types import SimpleNamespace
    s=surface;loader=s.g.renderer.loader
    entry=next(e for e in s.g._entries if e['kind']=='resource')
    before=loader.key(entry,120)[0]
    alternate=SimpleNamespace(index=SimpleNamespace(root=s.tmp/'other-library'),representative_frame=s.storage.representative_frame,representative_crop=s.storage.representative_crop)
    with monkeypatch.context() as patch:
        patch.setattr(loader,'storage',alternate)
        assert loader.key(entry,120)[0]!=before
    assert loader.key(entry,120)[0]==before
