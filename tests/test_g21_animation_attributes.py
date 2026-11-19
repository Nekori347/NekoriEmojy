"""G2-1 intrinsic attributes, post-commit enrichment and UI cache regressions."""
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from PIL import Image
from test_phase2_interaction import surface
from services.animation_attributes import probe_animation, _Batch
from threading import Event


def test_import_reuses_decode_after_commit_and_duplicate_uses_existing(surface, monkeypatch):
    s=surface
    path=s.tmp/'new.gif'
    Image.new('RGB',(21,23),'red').save(path,save_all=True,
        append_images=[Image.new('RGB',(21,23),'blue')],duration=100)
    observed=[];original=s.storage.index.set_animation_attribute
    def persist(record, animated):
        assert s.storage.index.resource(record['id'])  # catalog already committed
        assert Path(s.storage.index.absolute_path(record)).is_file()
        observed.append(animated)
        return original(record,animated)
    monkeypatch.setattr(s.storage.index,'set_animation_attribute',persist)
    monkeypatch.setattr('services.animation_attributes.probe_animation',Mock(side_effect=AssertionError('reuse decode')))
    saved,duplicate=s.storage.save_file(str(path))
    assert not duplicate and observed==[True]
    assert s.storage.index.animation_attribute(s.storage.resource_of(saved)) is True
    again,duplicate=s.storage.save_file(str(path))
    assert duplicate and again==saved and observed==[True]


def test_enrichment_failure_does_not_fail_import(surface, monkeypatch):
    import sqlite3
    s=surface;p=s.tmp/'new.png';Image.new('RGB',(31,27),'orange').save(p)
    monkeypatch.setattr(s.storage.index,'set_animation_attribute',Mock(side_effect=sqlite3.OperationalError('busy')))
    saved,duplicate=s.storage.save_file(str(p))
    assert not duplicate and s.storage.resource_of(saved)


def test_backfill_persists_unknown_and_preserves_presentation(surface):
    s=surface;record=s.storage.resource_of(s.paths[4]);idx=s.storage.index
    with idx.connect() as db:
        db.execute('UPDATE resources SET metadata_json=? WHERE id=?',
            (json.dumps({'thumb_frame':1,'thumb_crop':[.1,.2,.8,.9]}),record['id']))
    before=idx.resource_metadata(record['id'])
    worker=_Batch(idx,'',Event());results=[]
    worker.signals.completed.connect(lambda changed,*_:results.append(changed));worker.run()
    after=idx.resource_metadata(record['id'])
    assert results[0][record['id']] is True
    assert all(after[k]==v for k,v in before.items())
    # Stale frame picker metadata cannot remove intrinsic enrichment.
    idx.set_resource_metadata(record['id'],before)
    assert idx.animation_attribute(idx.resource(record['id'])) is True
    idx.set_resource_metadata(record['id'],{})
    assert idx.resource_metadata(record['id'])=={'animation':{'v':1,'animated':True}}
    # No repeated parsing after persisted completion.
    from unittest.mock import patch
    with patch('services.animation_attributes.probe_animation',side_effect=AssertionError('already enriched')):
        _Batch(idx,'',Event()).run()


def test_stale_probe_and_cancel_never_overwrite_new_metadata(surface):
    s=surface;idx=s.storage.index;record=idx.resource(s.paths[0])
    idx.set_resource_metadata(record['id'],{'thumb_frame':2})
    assert not idx.set_animation_attribute(record,True)
    stopped=Event();stopped.set();task=_Batch(idx,'',stopped);result=[]
    task.signals.completed.connect(lambda changed,*_:result.append(changed));task.run()
    assert result==[{}]


def test_gallery_cache_reads_record_without_image_probe_or_pixmap_conversion(surface,monkeypatch):
    s=surface;loader=s.g.renderer.loader
    cards=[c for c in s.g.renderer.active.values() if c.content_entry['kind']=='resource']
    monkeypatch.setattr(Image,'open',Mock(side_effect=AssertionError('no animation parsing in gallery')))
    for c in cards:
        loader.request([c]);assert c._animated is (c.image_path==s.paths[4])
    # Setting controls paint visibility only, never the intrinsic flag.
    s.config.set('show_animation_badges',False)
    loader.request(cards)
    assert next(c for c in cards if c.image_path==s.paths[4])._animated
    s.config.set('show_animation_badges',True)


def test_quick_panel_uses_indexed_flag_and_ignores_thumbnail_text(surface):
    from fluent_ui.components.quick_panel import QuickPanel
    s=surface;panel=QuickPanel(s.storage,s.clipboard,s.config)
    try:
        # Use the normal result renderer with a deterministic search result.
        panel.storage.search_images=Mock(return_value=[s.paths[4],s.paths[0]])
        # Existing recent lookup path is used below after recording resources.
        for path in [s.paths[0],s.paths[4]]:s.storage.add_recent_image(path)
        panel._perform_search(force=True)
        flags={c.image_path:c._animated for c in panel._all_card_widgets}
        assert flags[s.paths[4]] and not flags[s.paths[0]]
    finally:
        panel.shutdown();panel.deleteLater()


def test_probe_static_gif_webp_and_unreadable(tmp_path):
    for fmt,suffix in [('GIF','.gif'),('WEBP','.webp'),('PNG','.png')]:
        path=tmp_path/('still'+suffix);Image.new('RGB',(19,17),'red').save(path,format=fmt)
        assert probe_animation(path) is False
    assert probe_animation(tmp_path/'absent.gif') is None


def test_backfill_updates_inactive_cached_category_and_does_not_relayout(surface):
    s=surface;g=s.g;idx=s.storage.index;rid=idx.resource(s.paths[4])['id']
    g.set_node(s.parent);cached=g.entry_model.direct[s.parent]
    record=next(e['resource'] for e in cached if e['kind']=='resource' and e['id']==rid)
    metadata=json.loads(record['metadata_json']);metadata.pop('animation')
    record['metadata_json']=json.dumps(metadata)
    with idx.connect() as db:
        db.execute('UPDATE resources SET metadata_json=? WHERE id=?',(record['metadata_json'],rid))
    g.set_node(s.child)
    worker=_Batch(idx,'',Event());results=[]
    worker.signals.completed.connect(lambda changed,*_:results.append(changed));worker.run()
    from unittest.mock import patch
    with patch.object(g.renderer,'relayout',side_effect=AssertionError('metadata only')):
        g.renderer.loader.animation_changed(results[0])
    assert idx.animation_attribute(record) is True
    g.set_node(s.parent)
    from PySide6.QtTest import QTest
    from time import monotonic
    deadline=monotonic()+2
    candidates=[]
    while not candidates and monotonic()<deadline:
        QTest.qWait(20)  # normal navigation animation yields before card binding
        candidates=[c for c in g.renderer.active.values() if getattr(c,'entry_id',None)==rid]
    assert candidates
    assert candidates[0]._animated


def test_animation_enrichment_does_not_invalidate_search(surface):
    s=surface;idx=s.storage.index;record=idx.resource(s.paths[0]);revision=idx.search_revision
    assert idx.set_animation_attribute(record,False)
    assert idx.search_revision==revision


def test_replacement_invalidates_old_attribute_then_accepts_new_decode(surface):
    import io
    from services.animation_attributes import store_import_animation
    s=surface;path=s.paths[4];idx=s.storage.index;record=idx.resource(path)
    idx.set_resource_metadata(record['id'],{'thumb_frame':1,'thumb_crop':[.1,.1,.9,.9]})
    output=io.BytesIO();Image.new('RGB',(24,26),'orange').save(output,format='PNG')
    data=output.getvalue()
    updated=s.storage.replace_normalized(path,(data,'.png',s.storage._calculate_bytes_hash(data)))
    current=idx.resource(record['id'])
    assert current and idx.animation_attribute(current) is None
    assert 'thumb_frame' not in idx.resource_metadata(record['id'])
    store_import_animation(s.storage,updated,False)
    assert idx.animation_attribute(idx.resource(record['id'])) is False


def test_badge_defaults_and_saved_choices_are_independent(surface):
    from services.config import ConfigService
    s=surface
    assert s.config.get('show_animation_badges') is True
    assert s.config.get('show_new_resource_markers') is True
    s.config.set('show_animation_badges',False)
    restored=ConfigService(s.tmp/'app')
    assert restored.get('show_animation_badges') is False
    assert restored.get('show_new_resource_markers') is True
