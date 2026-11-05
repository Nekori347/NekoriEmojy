import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_wpb_drop import gallery, resource_mime
from test_phase2_interaction import surface
from test_l1_l3_interaction import settings


def test_new_import_is_actually_painted_outside_card(gallery,tmp_path):
    from PySide6.QtGui import QImage,QColor
    from services.resource_import import ImportTarget
    from fluent_ui import visual
    g,storage,parent,children,paths=gallery
    source=tmp_path/'never-imported-before.png'
    image=QImage(39,37,QImage.Format_RGB32);image.fill(QColor('#193753'));image.save(str(source))
    saved,duplicate=storage.save_file(str(source),target=ImportTarget(parent,0))
    assert not duplicate
    rid=storage.index.resource(saved)['id']
    g.refresh_content_incremental(paths=[saved],parents={parent})
    QTest.qWait(200)
    card=next(c for c in g._all_card_widgets if getattr(c,'entry_id',None)==rid)
    layer=g.new_markers
    assert rid in layer.ids and rid in storage.unseen_resource_ids()
    assert layer.isVisible()
    point=card.mapTo(g.grid_container,QPoint())
    picture=layer.grab().toImage();picture.save(str(tmp_path/'marker-layer.png'))
    accent=QColor(visual.accent())
    pixels=[picture.pixelColor(x,y) for x in range(point.x()-4,point.x()+12)
            for y in range(point.y()-4,point.y()+12)]
    assert any(c.alpha()>0 and c.red()==accent.red() and c.green()==accent.green() for c in pixels), (layer.geometry(),point)


def test_shared_slots_same_row_wrap_and_sizes(gallery):
    from fluent_ui.components.drop_contract import INSERT_AFTER, INSERT_BEFORE
    g,storage,parent,children,paths=gallery
    for size in (60,120,300):
        g.config.config['thumbnail_size']=size
        for width in (680,1000):
            g.resize(width,740);QApplication.processEvents();g.renderer.relayout()
            entries=g._entries;rects=g.renderer.index.rects
            for i in range(len(entries)-1):
                a,b=entries[i:i+2]
                if a['kind']!='resource' or b['kind']!='resource' or a['_parent']!=b['_parent']:continue
                left=g._resource_slot(i,INSERT_AFTER,'move')[0]
                right=g._resource_slot(i+1,INSERT_BEFORE,'move')[0]
                assert (left.target_id,left.index,left.container_id)==(right.target_id,right.index,right.container_id)
                assert left.feedback_rect==right.feedback_rect
                mark=left.feedback_rect
                assert .80 <= mark.height()/size <= .85
                assert mark.width()==2
                if rects[i].top()==rects[i+1].top():
                    assert abs((mark.x()+mark.width()/2)-(rects[i].right()+1+rects[i+1].left())/2)<=.5


def test_unseen_registration_persistence_duplicates_and_old_library(tmp_path,monkeypatch):
    from services.library_index import LibraryIndex
    from services.config import ConfigService
    from services.storage import StorageService
    root=tmp_path/'library';root.mkdir();(root/'images').mkdir()
    image=root/'images/a.png';image.write_bytes(b'fixture')
    index=LibraryIndex(root);rid=index.register(image)
    with index.connect() as db:db.execute('DROP TABLE resource_unseen')
    config=ConfigService(tmp_path/'app');storage=StorageService(root,config)
    assert storage.unseen_resource_ids()==set()  # upgrade never marks old rows
    newer=root/'images/b.png';newer.write_bytes(b'new')
    new_id=storage.index.register(newer)
    assert storage.unseen_resource_ids()=={new_id}
    assert StorageService(root,config).unseen_resource_ids()=={new_id}
    storage.mark_resource_seen(new_id);storage.index.register(newer)
    category=storage.create_node('copy');storage.move_resources_to([str(newer)],category)
    assert not storage.unseen_resource_ids()
    config.config['show_new_resource_markers']=False
    latest=root/'images/c.png';latest.write_bytes(b'new2');storage.index.register(latest)
    assert not storage.unseen_resource_ids()
    config.config['show_new_resource_markers']=True
    last=root/'images/d.png';last.write_bytes(b'new3');last_id=storage.index.register(last)
    with storage.index.connect() as db:db.execute('DELETE FROM resources WHERE id=?',(last_id,))
    assert not storage.unseen_resource_ids()


def test_marker_settings_discard_and_save(settings):
    c=settings;storage=c.storage
    ids={r['id'] for r in storage.index.resources()}
    with storage.index.connect() as db:
        db.executemany('INSERT OR IGNORE INTO resource_unseen VALUES (?)',[(rid,) for rid in ids])
    c._stage('show_new_resource_markers',False)
    assert storage.unseen_resource_ids()==ids
    c.discard();assert c.config.get('show_new_resource_markers',True)
    assert storage.unseen_resource_ids()==ids
    c._stage('show_new_resource_markers',False);assert c.save()
    assert not storage.unseen_resource_ids()
    c._stage('show_new_resource_markers',True);assert c.save()
    assert not storage.unseen_resource_ids()


def test_hover_confirmation_rejects_rebind_scroll_and_drag(gallery,monkeypatch):
    g,storage,parent,children,paths=gallery
    controller=g.new_markers
    card=next(c for c in g._all_card_widgets if hasattr(c,'entry_id'))
    identity=card.entry_id
    controller.refresh();assert identity in controller.ids
    monkeypatch.setattr(QApplication,'widgetAt',lambda pos:card)
    controller.pending=(card,identity,card.mapToGlobal(QPoint()))
    controller.cancel();controller.confirm();assert identity in storage.unseen_resource_ids()
    controller.pending=(card,'a-different-id',card.mapToGlobal(QPoint()))
    controller.confirm();assert identity in storage.unseen_resource_ids()
    controller.pending=(card,identity,card.mapToGlobal(QPoint()))
    card._is_dragging=True;controller.confirm();assert identity in storage.unseen_resource_ids()
    card._is_dragging=False
    controller.pending=(card,identity,card.mapToGlobal(QPoint()))
    controller.confirm();assert identity not in storage.unseen_resource_ids()
    assert identity not in controller.ids


def test_hover_waits_300ms_and_short_hover_is_cancelled(gallery,monkeypatch):
    from PySide6.QtCore import QEvent,QPointF
    g,storage,parent,children,paths=gallery
    controller=g.new_markers
    card=next(c for c in g._all_card_widgets if hasattr(c,'entry_id'))
    identity=card.entry_id
    monkeypatch.setattr(QApplication,'widgetAt',lambda pos:card)
    pointer=[QPoint(100,100)]
    monkeypatch.setattr(QCursor,'pos',lambda:pointer[0])
    def move():
        event=QMouseEvent(QEvent.MouseMove,QPointF(10,10),QPointF(10,10),Qt.NoButton,Qt.NoButton,Qt.NoModifier)
        controller.eventFilter(card,event)
    move();assert controller.timer.isActive()
    QTest.qWait(100);controller.cancel();QTest.qWait(230)
    assert identity in storage.unseen_resource_ids()
    pointer[0]=QPoint(101,100);move();QTest.qWait(330)
    assert identity not in storage.unseen_resource_ids()


def test_delayed_cross_category_commit_uses_stable_slot(gallery):
    from fluent_ui.components.drop_contract import INSERT_BEFORE
    g,storage,parent,children,paths=gallery
    target=storage.create_node('target-slot')
    storage.move_resources_to(paths[3:5],target)
    anchor=storage.entries_of(target)[1]['id']
    storage.move_resources_to([paths[5]],target,position=0)
    moving=[paths[0],paths[2]]
    g._apply_drop_action(moving,target,True,{p:parent for p in moving},1,(anchor,INSERT_BEFORE))
    assert [e['path'] for e in storage.entries_of(target)]==[paths[5],paths[3],*moving,paths[4]]


def test_failed_settings_save_does_not_clear_unseen(settings,monkeypatch):
    c=settings;before=c.storage.unseen_resource_ids()
    assert before
    c._stage('show_new_resource_markers',False)
    monkeypatch.setattr(c.config,'_save_config',lambda *_:(_ for _ in ()).throw(RuntimeError('disk full')))
    assert not c.save()
    assert c.storage.unseen_resource_ids()==before
    assert c.config.config.get('show_new_resource_markers',True)
