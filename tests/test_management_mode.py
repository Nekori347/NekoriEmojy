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


def test_assignment_clears_only_completed_selection(management,monkeypatch):
    view,storage,parent,dest,paths,sent=management
    QTest.mouseClick(view.btn_manage,Qt.LeftButton)
    for path in paths[:3]:click_resource(view,path)
    # Cancel the actual target-picker boundary: no transaction or early clearing.
    monkeypatch.setattr(view,'choose_target_node',lambda *args,**kwargs:None)
    view._batch_assign(copy=True)
    assert set(view.get_selected_paths())==set(paths[:3])
    view.assign_resources(paths[:2],dest,copy=True)
    assert set(view.get_selected_paths())=={paths[2]}
    assert all(not c.is_selected for c in view._all_card_widgets if getattr(c,'image_path',None) in paths[:2])
    assert {storage._resource_id(p) for p in paths[:2]} <= {e['id'] for e in storage.entries_of(dest)}
    assert all(any(e['path']==p for e in storage.entries_of(parent) if e['kind']=='resource') for p in paths[:2])
    # Failure keeps a still-operable selection; duplicate target membership is success.
    def fail(*args,**kwargs):raise OSError('controlled write failure')
    move=storage.move_resources_to;monkeypatch.setattr(storage,'move_resources_to',fail)
    view.assign_resources([paths[2]],dest,copy=False)
    assert view.get_selected_paths()==[paths[2]]
    monkeypatch.setattr(storage,'move_resources_to',move)
    view.assign_resources([paths[2]],dest,copy=False)
    assert not view.get_selected_paths() and not any(e.get('path')==paths[2] for e in storage.entries_of(parent))


def test_assignment_partial_groups_preserve_unfinished_selection(management,monkeypatch):
    view,storage,parent,dest,paths,sent=management
    child=storage.create_node('Nested',parent)
    storage.move_resources_to([paths[1]],child,copy=False,source_node=parent)
    view._expanded_nodes.add(child);view.entry_model.invalidate();view.refresh_content()
    loop=QEventLoop();QTimer.singleShot(200,loop.quit);loop.exec();view.renderer.sync()
    view.set_mode('manage')
    for path in paths[:3]:click_resource(view,path)
    move=storage.move_resources_to;calls=[]
    def partial(subset,*args,**kwargs):
        calls.append((subset,kwargs.get('source_node')))
        if kwargs.get('source_node')==child:raise OSError('controlled second group failure')
        return move(subset,*args,**kwargs)
    monkeypatch.setattr(storage,'move_resources_to',partial)
    view.assign_resources(paths[:2],dest,copy=False)
    assert calls==[([paths[0]],parent),([paths[1]],child)],calls
    assert set(view.get_selected_paths())==set(paths[1:3])
    assert any(e['id']==storage._resource_id(paths[0]) for e in storage.entries_of(dest))
    assert any(e['id']==storage._resource_id(paths[1]) for e in storage.entries_of(child))
