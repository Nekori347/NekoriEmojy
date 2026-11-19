"""Actual queue/worker + existing pool, disposable Library only."""
import json
import threading
from time import monotonic
from pathlib import Path
import pytest
from PIL import Image
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from services.resource_import import ImportTarget
from services.animation_attributes import probe_animation


def wait_until(predicate, seconds=5):
    from PySide6.QtWidgets import QApplication
    from time import sleep
    deadline=monotonic()+seconds
    while not predicate() and monotonic()<deadline:
        QApplication.processEvents()
        sleep(.01)  # release Python to the real ImportThread/pool, like app.exec
    assert predicate()


def finish_startup(s):
    backfill=s.g.renderer.loader.animation_backfill
    backfill.timer.stop();backfill._next()
    wait_until(lambda:backfill.task is None and not backfill.scan_more)
    return backfill


def remove_animation(s,path):
    record=s.storage.index.resource(path)
    metadata=json.loads(record['metadata_json']);metadata.pop('animation',None)
    with s.storage.index.connect() as db:
        db.execute('UPDATE resources SET metadata_json=? WHERE id=?',(json.dumps(metadata),record['id']))
    return record['id']


@pytest.mark.parametrize('source_kind',['legacy_reuse','new_after_write_failure'])
def test_queue_commits_and_finishes_before_extra_probe_and_updates_both_views(surface,monkeypatch,source_kind):
    import sqlite3
    from fluent_ui.components.quick_panel import QuickPanel
    s=surface;b=finish_startup(s);q=s.g.imports;commits=[];events=[]
    entered=threading.Event();release=threading.Event();probe_threads=[]
    original=probe_animation
    if source_kind=='legacy_reuse':
        path=s.paths[4];rid=remove_animation(s,path)
        monkeypatch.setattr(q,'_ask_batch',lambda request,candidates:['reuse']*len(candidates))
        s.storage.add_recent_image(path)
    else:
        path=str(s.tmp/'new-animation.gif')
        Image.new('RGB',(27,29),'orange').save(path,save_all=True,
            append_images=[Image.new('RGB',(27,29),'purple')],duration=100)
        store=s.storage.index.set_animation_attribute
        def unavailable_once(*args,**kwargs):
            monkeypatch.setattr(s.storage.index,'set_animation_attribute',store)
            raise sqlite3.OperationalError('one synthetic post-accept write failure')
        monkeypatch.setattr(s.storage.index,'set_animation_attribute',unavailable_once)
    def slow_probe(value):
        probe_threads.append(threading.get_ident());events.append({'stage':'background_probe_started','time':monotonic(),'thread':threading.get_ident()});entered.set()
        assert release.wait(5)
        value=original(value);events.append({'stage':'background_probe_finished','time':monotonic()});return value
    monkeypatch.setattr('services.animation_attributes.probe_animation',slow_probe)
    def committed(paths,parents):
        commits.extend(paths);events.append({'stage':'gui_commit','time':monotonic(),'thread':threading.get_ident()})
    q.resources_committed.connect(committed)
    panel=QuickPanel(s.storage,s.clipboard,s.config)
    try:
        job=q.submit([path],ImportTarget(s.parent),s.g)
        try:wait_until(lambda:entered.is_set())
        except AssertionError:raise AssertionError(str(q.requests[job]))
        # The original queue and QThread have completed while parsing is blocked.
        assert q.worker is None and q.requests[job].state=='completed'
        events.append({'stage':'queue_completed_while_probe_blocked','time':monotonic()})
        assert q.requests[job].failed==0 and commits
        accepted=q.requests[job].paths[0];record=s.storage.index.resource(accepted);rid=record['id']
        assert s.storage.index.animation_attribute(record) is None
        assert any(e['kind']=='resource' and e['id']==rid for e in s.g._entries)
        assert probe_threads[0]!=threading.get_ident()
        s.storage.add_recent_image(accepted);panel._perform_search(force=True)
        card=next(c for c in panel._all_card_widgets if c.entry_id==rid)
        assert not card._animated
        release.set()
        wait_until(lambda:s.storage.index.animation_attribute(s.storage.index.resource(rid)) is True)
        wait_until(lambda:card._animated)
        wait_until(lambda:any(c._animated for c in s.g.renderer.active.values() if getattr(c,'entry_id',None)==rid))
        assert not b.scan_more  # targeted request did not restart the full scan
        (s.tmp/'animation-order.json').write_text(json.dumps({'source_kind':source_kind,'events':events,'gallery_and_quick_panel_updated':True},indent=2),'utf-8')
    finally:
        release.set();panel.shutdown();panel.deleteLater()
        wait_until(lambda:b.task is None)


def test_mixed_keep_replace_reuse_keeps_each_resources_animation_and_ocr_order(surface,monkeypatch):
    from services.task_recovery import ImportCheckpoint
    s=surface;b=finish_startup(s);q=s.g.imports
    animated_id=remove_animation(s,s.paths[4]);decisions=[];ocr=[]
    def choose(request,candidates):
        assert len(candidates)==3
        decisions.append([hasattr(s.storage.import_context,name) for name in ('animation_hint','animation_replaced')])
        return ['keep','replace','reuse']
    monkeypatch.setattr(q,'_ask_batch',choose)
    monkeypatch.setattr(type(q.ocr),'available',property(lambda self:True))
    s.config.config['ocr_auto']=True
    def enqueue(ids,**kwargs):
        assert all(s.storage.index.resource(rid) for rid in ids)
        ocr.append((ids,kwargs))
    monkeypatch.setattr(q.ocr,'enqueue',enqueue)
    before=len(s.storage.index.resources())
    job=q.submit([s.paths[0],s.paths[1],s.paths[4]],ImportTarget(s.other),s.g)
    try:wait_until(lambda:bool(ocr) and q.worker is None)
    except AssertionError:raise AssertionError(str(q.requests[job]))
    wait_until(lambda:b.task is None and not b.pending)
    result=q.requests[job]
    assert result.failed==0 and len(result.paths)==3
    assert len(s.storage.index.resources())==before+1
    assert decisions==[[False,False]]
    for path in result.paths:
        record=s.storage.index.resource(path)
        assert s.storage.index.animation_attribute(record) is probe_animation(path)
    assert s.storage.index.animation_attribute(s.storage.index.resource(animated_id)) is True
    assert set(ocr[0][0])=={s.storage.index.resource(path)['id'] for path in result.paths}
    assert ocr[0][1]['origin']=='import' and ocr[0][1]['job_id']==job
    assert not any(item[0]==job for item in ImportCheckpoint.discover(s.storage.index))
    (s.tmp/'mixed-decisions.json').write_text(json.dumps({'decisions':['keep','replace','reuse'],'source_flags':[False,False,True],'accepted_flags':[s.storage.index.animation_attribute(s.storage.index.resource(p)) for p in result.paths],'source_record_count':before,'after_count':len(s.storage.index.resources()),'thread_local_fields_present':decisions,'ocr_received_accepted_ids':True,'checkpoint_forgotten':True},indent=2),'utf-8')
