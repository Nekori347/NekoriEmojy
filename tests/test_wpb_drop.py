"""Isolated real-widget/data regressions for WP-B drop contracts."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def gallery(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from services.resource_import import ImportTarget
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui import visual
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    config = ConfigService(); visual.theme.configure(config); i18n_engine.init(config)
    storage = StorageService(config=config)
    parent = storage.create_node('Mixed')
    children = [storage.create_node(f'Child {i}', parent) for i in range(3)]
    paths = []
    for i in range(90):
        source = tmp_path/f'{i}.png'
        image = QImage(24,24,QImage.Format_RGB32); image.fill(QColor(i,100,90)); image.save(str(source))
        paths.append(storage.save_file(str(source), target=ImportTarget(parent))[0])
    view = GalleryInterface(storage, ClipboardService(config), config)
    view.resize(1000,740); view.show(); view.set_node(parent); QTest.qWait(120)
    yield view, storage, parent, children, paths
    view.focus_timer.stop(); view.preview_controller.cancel(); view.hide()
    view.deleteLater(); app.processEvents()


def resource_mime(paths):
    from fluent_ui.components.drop_contract import RESOURCE_MIME
    mime = QMimeData(); mime.setData(RESOURCE_MIME, json.dumps(paths).encode())
    return mime


def test_gallery_drop_forwards_actual_global_position(gallery, monkeypatch):
    view, storage, parent, children, paths = gallery
    # Dropping in the category centre requests a membership menu at the drop.
    i = next(i for i,e in enumerate(view._entries) if e['id']==children[0])
    point = view.grid_container.mapTo(view, view.renderer.index.rects[i].center())
    mime = resource_mime(paths[:1]); calls=[]
    monkeypatch.setattr(view, 'request_resource_drop', lambda *a,**kw:calls.append((a,kw)))
    enter=QDragEnterEvent(point,Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    view._begin_drop(enter,point)
    drop=QDropEvent(QPointF(point),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
    view._complete_drop(drop,point)
    assert drop.isAccepted()
    assert calls[0][0][1] == children[0]
    assert calls[0][1]['global_pos'] == view.mapToGlobal(point)
