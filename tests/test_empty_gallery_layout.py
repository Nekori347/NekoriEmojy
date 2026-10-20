"""Empty content must belong to the viewport, independent of dock geometry."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from fluent_ui import visual
from fluent_ui.main_window import MainWindow

@pytest.fixture
def empty_gallery(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'library'))
    cfg=ConfigService();cfg.config.update(global_hotkey='',quick_panel_hotkey='',ocr_auto=False)
    visual.theme.configure(cfg);i18n_engine.init(cfg)
    storage=StorageService(config=cfg)
    window=MainWindow(storage,ClipboardService(cfg),cfg)
    g=window.gallery_interface;g.focus_timer.stop()
    window.resize(1080,740);window.show()
    for _ in range(8):app.processEvents()
    yield g
    g.imports.shutdown();g.ocr.close();window.hide();window.deleteLater()
    app.processEvents()

@pytest.mark.parametrize('lang',['zh','zh_TW','en','ja'])
def test_empty_prompt_inside_visible_content(empty_gallery,lang):
    g=empty_gallery
    assert g.placeholder.width()>=g.scroll_area.viewport().width()-48,(g.placeholder.size(),g.scroll_area.viewport().size())
    i18n_engine.load_language(lang)
    for _ in range(8):QApplication.processEvents()
    label=g.placeholder;viewport=g.scroll_area.viewport()
    top=label.mapTo(viewport,QPoint())
    assert label.width()>=viewport.width()-48,(label.size(),viewport.size())
    assert top.x()>=0 and top.y()>=0,(top,label.size(),viewport.size())
    assert top.x()+label.width()<=viewport.width()
    assert top.y()+label.height()<=viewport.height()
    assert label.height()>=label.heightForWidth(label.width()),(label.height(),label.heightForWidth(label.width()))
    button=g.empty_import_button
    assert viewport.rect().contains(button.mapTo(viewport,QPoint()))
    assert viewport.rect().contains(button.mapTo(viewport,button.rect().bottomRight()))


def test_japanese_header_has_available_intrinsic_width(empty_gallery):
    g=empty_gallery;i18n_engine.load_language('ja')
    for _ in range(8):QApplication.processEvents()
    rail=g.location_rail
    from PySide6.QtGui import QFontMetrics
    width=QFontMetrics(visual.font('page_title')).horizontalAdvance(rail.path[-1][1])
    assert rail.current_rect().width()>=width,(rail.width(),width,g.search_surface.width())


def settle():
    for _ in range(10):QApplication.processEvents()


def assert_prompt(g):
    viewport=g.scroll_area.viewport();state=g.empty_state;label=g.placeholder
    assert state.geometry()==viewport.rect()
    assert label.width()==max(0,viewport.width()-48)
    assert label.height()>=label.heightForWidth(label.width())
    assert state.rect().contains(label.geometry())
    if g.empty_import_button.isVisible():
        assert state.rect().contains(g.empty_import_button.geometry())
        assert g.empty_import_button.y()>label.geometry().bottom()


def test_docks_resize_and_language_switch(empty_gallery):
    g=empty_gallery
    for width in (1080,760,900,1080):
        g.window().resize(width,740);settle()
        for placement in ('top','bottom','left','right'):
            g.tag_panel_host.set_placement(placement)
            for expanded in (False,True):
                g.tag_panel_host.set_expanded(expanded,persist=False);settle()
                for lang in ('en','ja','zh_TW','zh'):
                    i18n_engine.load_language(lang);settle();assert_prompt(g)


def test_first_import_and_return_to_empty_category(empty_gallery,tmp_path,monkeypatch):
    from PIL import Image
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    g=empty_gallery
    calls=[];monkeypatch.setattr(g,'_pick_import_files',lambda:calls.append('import'))
    QTest.mouseClick(g.empty_import_button,Qt.LeftButton)
    assert calls==['import']
    node=g.storage.create_node('Empty test')
    source=tmp_path/'test.png';Image.new('RGB',(16,16),'red').save(source)
    g.import_paths_to([str(source)],node)
    for _ in range(1000):
        QTest.qWait(20)
        if g.imports.requests and all(r.state in ('completed','failed','cancelled') for r in g.imports.requests.values()):break
    assert g.storage.get_images_by_category(node),[(r.state,r.errors,r.saved,r.paths) for r in g.imports.requests.values()]
    g.set_node(node);settle()
    assert g._entries and not g.empty_state.isVisible()
    path=g.storage.get_images_by_category(node)[0]
    g.storage.remove_image_from_category(path,node)
    g.on_images_changed();settle()
    assert not g._entries and g.empty_state.isVisible()
    assert not g.empty_import_button.isVisible()
    assert_prompt(g)


def test_empty_overlay_drop_route(empty_gallery,tmp_path,monkeypatch):
    from PySide6.QtCore import Qt,QMimeData,QUrl,QPointF
    from PySide6.QtGui import QDragEnterEvent,QDropEvent
    g=empty_gallery;calls=[]
    monkeypatch.setattr(g,'import_paths_to',lambda *args,**kw:calls.append((args,kw)))
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(tmp_path/'test.png'))])
    point=g.empty_state.rect().center()
    enter=QDragEnterEvent(point,Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(g.empty_state,enter);assert enter.isAccepted()
    drop=QDropEvent(QPointF(point),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(g.empty_state,drop);assert drop.isAccepted()
    assert len(calls)==1
