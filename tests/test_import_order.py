"""Import-time order regression on an isolated Qt gallery."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

def test_drop_uses_visible_resource_anchor_after_import_prepends(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from services.resource_import import ImportTarget
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui.components.drop_contract import DropTarget, INSERT_BEFORE, MOVE
    from fluent_ui import visual

    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path / 'library'))
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path / 'app'))
    config = ConfigService(); visual.theme.configure(config); i18n_engine.init(config)
    storage = StorageService(config=config)
    node = storage.create_node('Manual order')
    paths = []
    for i in range(10):
        source = tmp_path / f'{i}.png'
        image = QImage(24, 24, QImage.Format_RGB32)
        image.fill(QColor(i, 100, 90)); image.save(str(source))
        paths.append(storage.save_file(str(source), target=ImportTarget(node))[0])
    view = GalleryInterface(storage, ClipboardService(config), config)
    view.resize(1000, 740); view.show(); view.set_node(node); QTest.qWait(80)
    try:
        visible = [e for e in view._entries if e['kind'] == 'resource']
        anchor = visible[7]
        moving = visible[1]
        incoming = tmp_path / 'incoming.png'
        image.fill(QColor(240, 30, 90)); image.save(str(incoming))
        imported = storage.save_file(str(incoming), target=ImportTarget(node, 0))[0]
        view._reorder_by_drop([moving['path']],
                              DropTarget(INSERT_BEFORE, MOVE, anchor['id'], node, 7))
        order = [e['path'] for e in storage.entries_of(node) if e['kind'] == 'resource']
        assert order[0] == imported
        assert order.index(moving['path']) + 1 == order.index(anchor['path'])
        assert len(order) == 11 and len(set(order)) == 11
        view.set_node(node)
        assert [e['path'] for e in storage.entries_of(node) if e['kind'] == 'resource'] == order
    finally:
        view.focus_timer.stop(); view.preview_controller.cancel(); view.hide()
        view.deleteLater(); app.processEvents()
