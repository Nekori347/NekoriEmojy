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


def test_management_controls_describe_the_current_action(management):
    from pathlib import Path
    view,storage,parent,dest,paths,sent=management
    view.set_mode('manage')
    shots=Path(__file__).resolve().parents[2]/'DevData/management-check'
    shots.mkdir(exist_ok=True)
    phase='before' if view.btn_more.isEnabled() else 'after'
    view.grab().save(str(shots/f'G18-{phase}.png'))
    assert not view.btn_more.isEnabled() and not view.btn_delete.isEnabled()
    assert view.btn_exit_mode.text()=='退出管理' and view.btn_manage.accessibleName()=='退出管理模式'
    click_resource(view,paths[0]);assert view.btn_more.isEnabled()
    Path(paths[0]).unlink();storage.availability.exists(paths[0],revalidate=True)
    assert view.btn_delete.text()=='移除记录' and '失效' in view.btn_delete.toolTip()
    view.grab().save(str(shots/'G18-missing.png'))
    view._drop_selection_only();view.select_all_cards()
    assert view.btn_select_all.toolTip()=='取消全选'
    QTest.mouseClick(view.btn_exit_mode,Qt.LeftButton)
    assert view.btn_manage.accessibleName()=='进入管理模式'


@pytest.mark.parametrize('batch,escape',[(False,False),(True,False),(True,True)])
def test_resource_drag_cancel_surface_consumes_without_writes(management,monkeypatch,batch,escape):
    from pathlib import Path
    from PySide6.QtCore import QEvent,QPoint,QPointF
    from PySide6.QtGui import QDrag,QDragEnterEvent,QDropEvent,QMouseEvent
    view,storage,parent,dest,paths,sent=management
    if batch:
        view.set_mode('manage')
        for path in paths[:2]:click_resource(view,path)
    selected=set(view.selected_keys)
    before=storage.entries_of(parent);records=storage.index.resources()
    contents={p:Path(p).read_bytes() for p in paths}
    card=next(c for c in view._all_card_widgets if getattr(c,'image_path',None)==paths[0])
    observed=[]
    def drag_loop(drag,*args):
        zone=view.drop_cancel_zone
        assert zone.isVisible() and view.scroll_area.viewport().rect().contains(zone.geometry())
        if not escape:
            enter=QDragEnterEvent(QPoint(20,20),Qt.CopyAction|Qt.MoveAction,drag.mimeData(),Qt.LeftButton,Qt.NoModifier)
            QApplication.sendEvent(zone,enter)
            assert enter.isAccepted() and zone._hovered
            if batch:view.grab().save(str(Path(__file__).resolve().parents[2]/'DevData/management-check/G21-cancel.png'))
            drop=QDropEvent(QPointF(20,20),Qt.CopyAction|Qt.MoveAction,drag.mimeData(),Qt.LeftButton,Qt.NoModifier)
            QApplication.sendEvent(zone,drop);assert drop.isAccepted()
        assert drag.mimeData()._exports is None
        observed.append(True)
        return Qt.IgnoreAction
    monkeypatch.setattr(QDrag,'exec',drag_loop)
    QTest.mousePress(card,Qt.LeftButton)
    move=QMouseEvent(QEvent.MouseMove,QPointF(10,10),QPointF(card.mapToGlobal(QPoint(10,10))),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(card,move)
    QTest.mouseRelease(view,Qt.LeftButton)
    assert observed and not view.drop_cancel_zone.isVisible()
    assert set(view.selected_keys)==selected and not sent
    assert storage.entries_of(parent)==before and storage.index.resources()==records
    assert all(Path(p).read_bytes()==data for p,data in contents.items())


def test_mixed_selection_and_current_filtered_projection(management):
    view,storage,parent,dest,paths,sent=management
    child=storage.create_node('Nested',parent)
    storage.move_resources_to(paths[:2],child,copy=True)
    storage.apply_tags(paths[:2],['focused'],'add')
    view._expanded_nodes.add(child);view.entry_model.invalidate();view.refresh_content()
    QTest.qWait(150);view.renderer.sync()
    node=next(c for c in view._all_card_widgets if getattr(c,'node_id',None)==child)
    QTest.mouseClick(node,Qt.LeftButton);assert child in view.selected_keys
    QTest.mouseClick(view.btn_manage,Qt.LeftButton)
    assert view.selected_keys=={child} and node.is_selected
    QTest.mouseClick(node,Qt.LeftButton,Qt.ControlModifier)
    assert not view.selected_keys
    QTest.mouseClick(view.btn_select_all,Qt.LeftButton)
    assert set(view.get_selected_paths())==set(paths)
    assert view.selected_count_label.text()=='已选 7 项（6 张表情，1 个节点）'  # occurrence identities deduplicate
    QTest.mouseClick(view.btn_select_all,Qt.LeftButton)
    assert not view.selected_keys
    view.active_tags={'focused'};view.refresh_content();QTest.qWait(100)
    QTest.mouseClick(view.btn_select_all,Qt.LeftButton)
    assert set(view.get_selected_paths())==set(paths[:2])
    view.search_box.setText('0.png');view._search_timer.stop();view._execute_search()
    view._drop_selection_only();QTest.mouseClick(view.btn_select_all,Qt.LeftButton)
    assert view.get_selected_paths()==[paths[0]]
    view.search_box.setText('no-such-resource');view._search_timer.stop();view._execute_search()
    assert not view.btn_select_all.isEnabled() and view.selected_count_label.text()=='已选 0 项'
    assert view.btn_exit_mode.isEnabled() and not sent


def test_management_layout_states_and_single_level_overflow(management):
    from PySide6.QtCore import QPoint,QRect
    view,storage,parent,dest,paths,sent=management
    view.resize(1420,760);view.splitter.setSizes([220,1200]);view.set_mode('manage');QTest.qWait(80)
    height=view.command_bar.height()
    assert view.btn_select_all.text()=='全选当前结果'
    assert all(not b.isEnabled() for b in (*view._organization_buttons,view.btn_more,view.btn_delete))
    for selected in (paths[:1],paths[:3]):
        view._drop_selection_only()
        for path in selected:click_resource(view,path)
        assert view.command_bar.height()==height
        menu=view._build_selection_more_menu();labels=[a.text() for a in menu.actions()]
        assert ('查看与编辑文字' in labels)==(len(selected)==1)
        assert ('在资源管理器中显示' in labels)==(len(selected)==1)
        assert '从当前分类移除' in labels and '导出所选表情' in labels
    assert not view._selection_overflow
    for width in (1100,900,760):
        view.resize(width,760);view.splitter.setSizes([220,width-220]);QTest.qWait(60)
        direct=[view.selected_count_label,view.btn_select_all,*view._organization_buttons,view.btn_more,view.btn_delete,view.btn_exit_mode]
        rects=[QRect(w.mapTo(view.command_bar,QPoint()),w.size()) for w in direct if w.isVisible()]
        assert all(view.command_bar.rect().contains(r) for r in rects),(width,rects,view.command_bar.rect())
        assert all(not a.intersects(b) for i,a in enumerate(rects) for b in rects[i+1:])
        menu=view._build_selection_more_menu()
        assert all(a.menu() is None for a in menu.actions())
        labels=[a.text() for a in menu.actions()]
        if view.btn_arrange in view._overflow_buttons:
            assert '移到最前' in labels and '移到最后' in labels
        for button in view._organization_buttons:
            if button is not view.btn_arrange:
                assert (button.text() in labels)==(button in view._overflow_buttons)
    view.finish_selection();view.config.set('gallery_click_action','select')
    click_resource(view,paths[0]);click_resource(view,paths[1],Qt.ControlModifier)
    assert view.mode=='normal' and view.btn_exit_mode.text()=='清除选择'
    assert view.command_bar.height()==height
    QTest.mouseClick(view.btn_exit_mode,Qt.LeftButton);assert not view.selected_keys


def test_management_membership_picker_semantics_and_position(management,monkeypatch):
    from services.library_index import ROOT
    from fluent_ui.components import dialogs
    view,storage,parent,dest,paths,sent=management
    child=storage.create_node('Nested',parent)
    storage.move_resources_to([paths[1]],child,copy=False,source_node=parent)
    view._expanded_nodes.add(child);view.entry_model.invalidate();view.refresh_content()
    QTest.qWait(100);view.renderer.sync();view.set_mode('manage')
    # Select real occurrences with different source relations, not synthetic keys.
    for path,source in ((paths[0],parent),(paths[1],child)):
        card=next(c for c in view._all_card_widgets if getattr(c,'image_path',None)==path and c.content_entry['_parent']==source)
        QTest.mouseClick(card,Qt.LeftButton)
    captured=[]
    def choose(*args,**kwargs):
        captured.append((args[1],args[2]));return dest,True
    monkeypatch.setattr(dialogs,'choose_item',choose)
    view.btn_move_to.click()
    assert captured[0][0]=='移动到分类'
    assert '其它分类关系保留' in captured[0][1]
    assert all(any(e.get('path')==p for e in storage.entries_of(dest)) for p in paths[:2])
    assert not any(e.get('path')==paths[0] for e in storage.entries_of(parent))
    assert not any(e.get('path')==paths[1] for e in storage.entries_of(child))
    assert not view.selected_keys
    view.set_node(parent);QTest.qWait(80);view.renderer.sync();view.set_mode('manage')
    click_resource(view,paths[2]);view.btn_add_to.click()
    assert captured[-1][0]=='加入分类' and '不复制文件' in captured[-1][1]
    assert any(e.get('path')==paths[2] for e in storage.entries_of(parent))
    assert any(e.get('path')==paths[2] for e in storage.entries_of(dest))
    click_resource(view,paths[4]);view.arrange_menu.actions()[-1].trigger()
    assert storage.entries_of(parent)[-1]['path']==paths[4]
    order=storage.index.content(parent)
    view.set_content_sort('recent_added')
    assert not view.btn_arrange.isEnabled() and storage.index.content(parent)==order
    view.set_node(ROOT);QTest.qWait(80);view.renderer.sync();view.set_mode('manage')
    click_resource(view,paths[3])
    assert not view.btn_move_to.isEnabled()  # ROOT by itself does not offer a fictitious move.
    view.choose_target_node('移动到分类',False)
    assert '1 项来自全部表情' in captured[-1][1]
    view.assign_resources([paths[3]],dest,copy=False,source_node=ROOT)
    assert any(e.get('path')==paths[3] for e in storage.entries_of(parent))
    assert any(e.get('path')==paths[3] for e in storage.entries_of(dest))


def test_management_tags_membership_removal_and_global_delete(management,monkeypatch):
    from pathlib import Path
    from fluent_ui.components import dialogs
    view,storage,parent,dest,paths,sent=management
    storage.apply_tags(paths[:2],['common'],'add');storage.apply_tags(paths[:1],['partial'],'add')
    view.set_mode('manage')
    for path in paths[:2]:click_resource(view,path)
    seen=[]
    def edit(dialog):
        assert dialog.chips['common'].state==Qt.Checked
        assert dialog.chips['partial'].state==Qt.PartiallyChecked
        dialog.editor.setText('new-tag');dialog.apply_button.click()
        seen.append(dialog.paths);return 1
    monkeypatch.setattr(dialogs.TagEditorDialog,'exec',edit)
    view.btn_tags.click()
    assert set(seen[0])==set(paths[:2])
    assert 'partial' in storage.get_image_keywords(paths[0]) and 'partial' not in storage.get_image_keywords(paths[1])
    assert all('new-tag' in storage.get_image_keywords(p) for p in paths[:2])
    view.assign_resources(paths[:2],dest,copy=True)
    for path in paths[:2]:click_resource(view,path)
    confirmations=[]
    def confirm(*args,**kwargs):
        confirmations.append((args,kwargs));return True
    monkeypatch.setattr(dialogs,'confirm',confirm)
    menu=view._build_selection_more_menu()
    next(a for a in menu.actions() if a.text()=='从当前分类移除').trigger()
    assert all(Path(p).is_file() and storage.resource_of(p) for p in paths[:2])
    assert all(not any(e.get('path')==p for e in storage.entries_of(parent)) for p in paths[:2])
    assert all(any(e.get('path')==p for e in storage.entries_of(dest)) for p in paths[:2])
    # Card preparation intentionally yields while the existing tree navigation
    # animation is running. Wait for that real navigation before clicking.
    view.set_node(dest);QTest.qWait(350);view.renderer.sync();view.set_mode('manage')
    for path in paths[:2]:click_resource(view,path)
    Path(paths[1]).unlink();storage.availability.exists(paths[1],revalidate=True)
    view.btn_delete.click()  # only disposable fixture files can reach Windows Recycle Bin
    assert '现有文件' in confirmations[-1][1]['hint'] and '失效' in confirmations[-1][1]['hint']
    assert '所有分类关系' in confirmations[-1][1]['hint']
    assert all(storage.resource_of(p) is None and not Path(p).exists() for p in paths[:2])
    assert all(not any(e.get('path')==p for e in storage.entries_of(dest)) for p in paths[:2])
