"""Ordering, mutation and recycler contracts; visual smoothness needs the Demo."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtTest import QTest
from fluent_ui.components.virtual_gallery import FlowIndex
from fluent_ui.components.tray_activation import TrayActivation


def test_mixed_flow_layout():
    entries=[dict(kind='resource',id=str(i),_parent='a',_depth=0) for i in range(9)]
    entries.insert(2,dict(kind='node',id='node',_parent='a',_depth=0))
    entries.insert(3,dict(kind='resource',id='nested',_parent='node',_depth=1))
    index=FlowIndex(); index.layout(entries,700,120)
    assert index.rects[2].width()==676
    assert index.rects[2].top()>index.rects[1].bottom()
    assert index.rects[3].top()>index.rects[2].bottom()
    assert index.rects[4].top()>index.rects[3].bottom()
    entries.insert(7,dict(kind='resource',id='inserted',_parent='a',_depth=0))
    index.layout(entries,700,120,first=7)
    fresh=FlowIndex(); fresh.layout(entries,700,120)
    assert index.rects==fresh.rects
    for top in range(0,index.height,7):
        expected={i for i,r in enumerate(index.rects) if r.bottom()>=top and r.top()<=top+150}
        assert set(index.between(top,top+150))==expected


def test_tray_uses_system_interval_and_double_wins():
    app=QApplication.instance() or QApplication([])
    calls=[]
    tray=TrayActivation({QSystemTrayIcon.Trigger:lambda:calls.append('single'),
                         QSystemTrayIcon.DoubleClick:lambda:calls.append('double'),
                         QSystemTrayIcon.MiddleClick:lambda:calls.append('middle')},lambda:None)
    tray.activate(QSystemTrayIcon.Trigger)
    assert tray.timer.interval()==app.styleHints().mouseDoubleClickInterval()
    assert calls==[]
    tray.activate(QSystemTrayIcon.DoubleClick)
    tray.activate(QSystemTrayIcon.Trigger)
    assert calls==['double'] and not tray.timer.isActive()
    tray.activate(QSystemTrayIcon.Trigger); tray.finish(); tray.timer.stop()
    assert calls==['double','single']
    # Middle click is outside the single / double pair and runs at once.
    tray.activate(QSystemTrayIcon.MiddleClick)
    assert calls==['double','single','middle'] and not tray.timer.isActive()


def test_real_mutation_paths_preserve_view_and_recycled_identity(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from services.library_index import ROOT
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui.components import dialogs
    from fluent_ui import visual
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'library'))
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    config=ConfigService(); visual.theme.configure(config); i18n_engine.init(config)
    storage=StorageService(config=config)
    node=storage.create_node('A'); target=storage.create_node('B')
    paths=[]
    for i in range(160):
        path=tmp_path/f'{i}.png'
        image=QImage(24,24,QImage.Format_RGB32); image.fill(QColor(i,100,90)); image.save(str(path))
        paths.append(storage.save_file(str(path))[0])
    storage.move_resources_to(paths,node)
    g=GalleryInterface(storage,ClipboardService(config),config)
    g.resize(1000,740); g.show(); g.set_node(node); QTest.qWait(100)
    bar=g.scroll_area.verticalScrollBar()
    try:
        bar.setValue(1100); app.processEvents()
        anchor=g.renderer.anchor()
        untouched=g._entries[100]
        calls=[]
        layout=g.renderer.index.layout
        monkeypatch.setattr(g.renderer.index,'layout',lambda *a,**kw:(calls.append(1),layout(*a,**kw))[1])
        monkeypatch.setattr(g,'_collect_entries',lambda:(_ for _ in ()).throw(AssertionError('bulk entry rebuild during mutation')))
        g._quick_tag(paths[100],'tag')
        assert not calls and g._entries[100] is untouched
        assert g.renderer.anchor()==anchor
        assert 'tag' in g._entries[100]['tags']
        # Exercise the real batch-tag entry, previously still a full refresh.
        g.selected_keys={paths[100]}
        class Editor:
            def __init__(self,*args): pass
            def exec(self):
                storage.apply_tags([paths[100]],['batch'],'add'); return True
        monkeypatch.setattr(dialogs,'TagEditorDialog',Editor)
        g._batch_tags()
        assert not calls and 'batch' in g._entries[100]['tags']
        def anchor_offset(value):
            from fluent_ui.components.gallery_model import occurrence_id
            i=next(i for i,e in enumerate(g._entries) if occurrence_id(e)==value[0])
            return bar.value()-g.renderer.index.rects[i].top()
        g.assign_resources([paths[0]],target,copy=False,source_node=node)
        assert len(g._entries)==159 and all(e.get('path')!=paths[0] for e in g._entries)
        assert anchor_offset(anchor)==anchor[1]
        anchor=g.renderer.anchor()
        incoming=tmp_path/'new.png'; image.fill(QColor(240,30,90)); image.save(str(incoming))
        g.import_paths_to([str(incoming)],node)
        until=time.monotonic()+10
        while ((g.import_thread is not None and g.import_thread.isRunning()) or len(g._entries)!=160) and time.monotonic()<until:
            QTest.qWait(20)
        assert len(g._entries)==160 and g._entries[0]['name'].startswith('new')
        assert anchor_offset(anchor)==anchor[1]
        monkeypatch.setattr(dialogs,'prompt_text',lambda *a,**kw:('Child',True))
        g.sidebar.create_node(node,position=2)
        assert g._entries[2]['kind']=='node'
        # Recycling must never keep a closure pointing at a previous resource.
        for fraction in (1,0,.5):
            bar.setValue(int(bar.maximum()*fraction)); app.processEvents()
        card=next(c for c in g._all_card_widgets if c.content_entry['kind']=='resource')
        card.clicked.emit(card.image_path,Qt.NoModifier)
        assert g.selected_keys=={card.image_path}
        assert g._nearest_entry(card.mapTo(g,QPoint(20,20)))[0] is card.content_entry
        assert len(g._all_card_widgets)<100
        assert g.renderer.created<120
    finally:
        g.focus_timer.stop(); g.preview_controller.cancel(); g.renderer.loader.wanted.clear()
        from fluent_ui.components.emoji_card import _thumbnail_pool
        _thumbnail_pool.waitForDone(10000); app.processEvents()
        g.hide(); g.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
