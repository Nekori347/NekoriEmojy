"""Management behavior through real card/button input, with no system send side effects."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import Qt,QEventLoop,QTimer
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def management(tmp_path,monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.resource_import import ImportTarget
    from services.i18n import i18n_engine
    from fluent_ui import visual
    from fluent_ui.views.gallery_view import GalleryInterface
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'library'))
    config=ConfigService();config.config.update(ocr_auto=False,gallery_click_action='send')
    visual.theme.configure(config);i18n_engine.init(config)
    storage=StorageService(config=config)
    parent=storage.create_node('Source');dest=storage.create_node('Target')
    paths=[]
    for i in range(6):
        source=tmp_path/f'{i}.png';image=QImage(30,30,QImage.Format_RGB32);image.fill(QColor(20*i,60,90));image.save(str(source))
        paths.append(storage.save_file(str(source),target=ImportTarget(parent))[0])
    view=GalleryInterface(storage,ClipboardService(config),config)
    view.resize(1100,760);view.show();view.set_node(parent)
    loop=QEventLoop();QTimer.singleShot(350,loop.quit);loop.exec();view.renderer.sync()
    sent=[];monkeypatch.setattr(view,'_send_to_clipboard',sent.append)
    yield view,storage,parent,dest,paths,sent
    view.focus_timer.stop();view.preview_controller.cancel();view.imports.shutdown();view.ocr.close();view.hide();view.deleteLater();app.processEvents()


def click_resource(view,path,modifiers=Qt.NoModifier):
    card=next(c for c in view._all_card_widgets if getattr(c,'image_path',None)==path)
    QTest.mouseClick(card,Qt.LeftButton,modifiers)
    return card


def test_management_click_overrides_send_and_restores_setting(management):
    view,storage,parent,dest,paths,sent=management
    click_resource(view,paths[0]);assert sent==[paths[0]]
    QTest.mouseClick(view.btn_manage,Qt.LeftButton)
    first=click_resource(view,paths[0]);second=click_resource(view,paths[1])
    assert first.is_selected and second.is_selected and set(view.get_selected_paths())==set(paths[:2])
    click_resource(view,paths[0],Qt.ControlModifier)
    assert set(view.get_selected_paths())=={paths[1]}
    click_resource(view,paths[3],Qt.ShiftModifier)
    assert len(view.get_selected_paths())>=2 and sent==[paths[0]]
    QTest.mouseDClick(first,Qt.LeftButton);assert sent==[paths[0]]
    QTest.mouseClick(view.btn_exit_mode,Qt.LeftButton)
    click_resource(view,paths[0]);assert sent==[paths[0],paths[0]]
    view.config.set('gallery_click_action','select')
    click_resource(view,paths[1]);assert view.get_selected_paths()==[paths[1]] and len(sent)==2
    QTest.mouseClick(view.btn_manage,Qt.LeftButton)
    assert view.get_selected_paths()==[paths[1]] and view.current_node==parent
    click_resource(view,paths[2]);assert set(view.get_selected_paths())==set(paths[1:3]) and len(sent)==2
