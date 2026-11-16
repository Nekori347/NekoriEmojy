"""Category projection, receive policy and shared subtree search: isolated Library."""
import json
from unittest.mock import Mock
from PySide6.QtCore import QMimeData,QPoint,Qt
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from services.library_index import ROOT
from fluent_ui.components.drop_contract import RESOURCE_MIME,RESOURCE_SOURCES_MIME,DropTarget,INTO,MOVE


def packet(paths,parent):
    mime=QMimeData();mime.setData(RESOURCE_MIME,json.dumps(paths).encode())
    mime.setData(RESOURCE_SOURCES_MIME,json.dumps({p:parent for p in paths}).encode());return mime


def test_category_defaults_independent_sort_and_canonical_positions(surface):
    s=surface;g=s.g
    before={n:s.storage.index.content(n) for n in (ROOT,s.parent,s.child,s.other)}
    g.set_node(ROOT);assert g.content_sort=='recent_added'
    g.set_node(s.parent);assert g.content_sort=='manual'
    g.set_content_sort('oldest_added');g.set_node(s.child);assert g.content_sort=='manual'
    g.set_content_sort('recent_added');g.set_node(s.parent);assert g.content_sort=='oldest_added'
    from fluent_ui.icons import Icon
    assert g.btn_content_sort._icon == Icon.OLDEST_ADDED
    assert not hasattr(g,'resource_sort_actions')
    g.set_node(ROOT);assert g.content_sort=='recent_added'
    state=s.config.get('library_view_states')[g._view_state_key]
    assert state['content_sorts'][s.parent]=='oldest_added'
    assert state['content_sorts'][s.child]=='recent_added'
    g.set_node(s.parent);g.set_relative_view(s.child)
    assert g.content_scope_node()==s.child and g.content_sort=='recent_added'
    assert before=={n:s.storage.index.content(n) for n in before}


def test_compact_cancel_consumes_internal_drop_without_order_changes(surface):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QDragEnterEvent,QDropEvent
    s=surface;g=s.g;g._commit_thumbnail_size(60);g._show_drag_cancel()
    zone=g.drop_cancel_zone;mime=packet([s.paths[0]],s.parent)
    before=s.storage.index.content(s.parent)
    enter=QDragEnterEvent(zone.rect().center(),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    zone.dragEnterEvent(enter);assert enter.isAccepted()
    drop=QDropEvent(QPointF(zone.rect().center()),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    zone.dropEvent(drop)
    assert drop.isAccepted() and not zone.isVisible()
    assert before==s.storage.index.content(s.parent) and zone.height()<60


def test_sort_survives_node_identity_changes_and_new_process(surface):
    import subprocess,sys,os
    s=surface;g=s.g
    s.config.set('resource_sort','oldest_added')  # legacy global must not seed new nodes
    g.set_content_sort('recent_added');g.set_node(s.child);g.set_content_sort('oldest_added')
    s.storage.rename_node(s.child,'Renamed child');s.storage.move_node(s.child,s.other)
    g.set_node(s.other);assert g.content_sort=='manual'
    g.set_node(s.child);assert g.content_sort=='oldest_added';g.save_session_state()
    code='''import json
from PySide6.QtWidgets import QApplication
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from fluent_ui import visual
from fluent_ui.views.gallery_view import GalleryInterface
app=QApplication([]);config=ConfigService();i18n_engine.init(config);visual.theme.configure(config)
storage=StorageService(config=config);g=GalleryInterface(storage,ClipboardService(config),config)
print('RESTORED='+json.dumps({'mode':g.content_sort,'scope':g.content_scope_node(),'sorts':g._content_sorts}))
g.imports.shutdown();g.ocr.close()
'''
    result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode==0,result.stderr[-1500:]
    record=json.loads(next(line[9:] for line in result.stdout.splitlines() if line.startswith('RESTORED=')))
    assert record['mode']=='oldest_added' and record['scope']==s.child
    assert record['sorts'][s.parent]=='recent_added'
    s.storage.delete_node(s.child);g.set_node(s.parent);g.save_session_state()
    assert s.child not in s.config.get('library_view_states')[g._view_state_key]['content_sorts']


def test_sorted_receive_allows_cross_category_but_blocks_same_parent(surface):
    s=surface;g=s.g;g.set_content_sort('recent_added');QTest.qWait(100)
    index=next(i for i,e in enumerate(g._entries) if e['kind']=='resource')
    p=g.grid_container.mapTo(g,g.renderer.index.rects[index].center())
    paths=[s.paths[0]];same=packet(paths,s.parent);cross=packet([s.paths[3]],s.child)
    assert not g._resolve_drop(p,same)[0].valid
    target=g._resolve_drop(p,cross)[0]
    assert target.valid and target.placement==INTO and target.index is None
    assert not g.sidebar.tree.resolve_category_target(s.parent,.5,same).valid
    assert g.sidebar.tree.resolve_category_target(s.other,.5,same).valid
    before=s.storage.index.content(s.parent)
    assert g._reorder_by_drop(paths,DropTarget(INTO,MOVE,None,s.parent,0),sources={paths[0]:s.parent}) is False
    assert before==s.storage.index.content(s.parent)
    # A stale exact target cannot bypass a later non-manual sort. Cross-copy
    # appends instead of moving the displayed rank into content.position.
    g._apply_drop_action([s.paths[3]],s.parent,True,{s.paths[3]:s.child},0,('not-a-slot','insert_before'))
    after=s.storage.index.content(s.parent)
    assert after[:len(before)]==before and after[-1]['id']==s.storage.index.resource(s.paths[3])['id']
    g._apply_drop_action([s.paths[3]],s.parent,False,{s.paths[3]:s.child},0)
    assert s.storage.index.content(s.parent)==after
    assert not any(row['id']==after[-1]['id'] for row in s.storage.index.content(s.child))


def test_sorted_external_image_import_and_internal_drag_source_remain_available(surface):
    import time
    from PySide6.QtGui import QImage,QColor
    s=surface;g=s.g;g.set_content_sort('oldest_added');QTest.qWait(60)
    mime=QMimeData();image=QImage(47,53,QImage.Format_ARGB32);image.fill(QColor('gold'));mime.setImageData(image)
    p=g.grid_container.mapTo(g,g.renderer.index.rects[0].center())
    target=g._resolve_drop(p,mime)[0];assert target.valid and target.index is None and target.placement==INTO
    before=list(s.storage.index.content(target.container_id));rid=g._import_urls(mime,target)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        s.app.processEvents();time.sleep(.01)
        if g.imports.requests[rid].state not in {'waiting','running','finalizing'}:break
    request=g.imports.requests[rid]
    assert request.state=='completed' and request.saved==1
    # Import uses the existing append/prepend default, never a displayed rank.
    assert len(s.storage.index.content(target.container_id))==len(before)+1


def test_search_scope_subtree_deduplicated_and_empty_toggle_does_not_refresh(surface):
    s=surface;g=s.g;g.set_node(s.parent)
    # All children are collapsed; filename search still reaches the child.
    g.search_box.setText('child');g._search_timer.stop();g._execute_search()
    assert len([e for e in g._entries if e['kind']=='resource'])==1
    keyword=g.search_box.text();sort=g.content_sort
    g.btn_search_scope.click();assert g.search_scope=='all'
    assert g.search_box.text()==keyword and g.content_sort==sort and g.current_node==s.parent
    g.set_node(s.other);assert g.search_scope=='all'
    g.search_box.setText('alpha');g._search_timer.stop();g._execute_search()
    assert len(g._entries)==1
    g.btn_search_scope.click();assert g.search_scope=='here' and not g._entries
    g.search_box.clear();g._search_timer.stop();g._execute_search()
    refresh=Mock(wraps=g.refresh_content);g.refresh_content=refresh
    g.btn_search_scope.click();refresh.assert_not_called()


def test_subtree_duplicates_tags_and_sort_survive_scope_changes(surface):
    s=surface;g=s.g
    grand=s.storage.create_node('Grandchild',s.child)
    s.storage.move_resources_to([s.paths[3]],grand,copy=True,source_node=s.child)
    g.set_node(s.parent);g.set_content_sort('oldest_added')
    g.search_box.setText('child');g._search_timer.stop();g._execute_search()
    assert len(g._entries)==1 and g.content_sort=='oldest_added'
    g.set_node(s.other);g.search_box.setText('Cat');g._search_timer.stop();g.active_tags={'Cat'};g._execute_search()
    assert not g._entries
    g.btn_search_scope.click();assert len(g._entries)==1
    assert g.active_tags=={'Cat'} and g.content_sort=='manual'
    g.set_node(ROOT);g.search_box.setText('Cat');g._search_timer.stop();g._execute_search();all_ids=[e['id'] for e in g._entries]
    g.btn_search_scope.click();assert [e['id'] for e in g._entries]==all_ids


def test_keyword_scope_is_not_silently_restricted_to_recent_items(surface):
    s=surface;g=s.g;s.storage.add_recent_image(s.paths[0],60)
    g.toggle_recent_view(True);assert len(g._entries)==1
    g.search_box.setText('child');g._search_timer.stop();g._execute_search()
    assert len(g._entries)==1 and g._entries[0]['path']==s.paths[3]
    g.btn_search_scope.click();assert len(g._entries)==1
    g.search_box.clear();g._search_timer.stop();g._execute_search()
    assert len(g._entries)==1 and g._entries[0]['path']==s.paths[0]
