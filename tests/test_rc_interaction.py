"""Narrow regression checks for update modality, task actions and slider edges."""
import time
from unittest.mock import Mock
import pytest,requests
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QStyle,QStyleOptionSlider
from test_phase2_interaction import surface,settle
from test_demo_local_fixes import main


@pytest.mark.parametrize('owner_name',['main','settings'])
def test_update_results_and_closing_never_leave_modal_owner(surface,main,monkeypatch,owner_name):
    from fluent_ui.components.update_center import update_center
    from services.update_service import UpdateService
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    owner=main if owner_name=='main' else main.settings_window
    owner.show();center=update_center();service=UpdateService(repository='Nekori347/NekoriEmojy',asset_name='NekoriEmojy_Release.zip')
    monkeypatch.setattr('fluent_ui.components.update_center.UpdateService',lambda **kw:service)
    for scenario in ('404','empty','network','timeout','valid','close'):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.status_code=404 if scenario=='404' else 200
        response.json.return_value=[] if scenario=='empty' else dict(tag_name='v0.2.2',body='更新说明',assets=[])
        error=requests.Timeout('isolated timeout') if scenario=='timeout' else requests.ConnectionError('isolated offline') if scenario=='network' else None
        monkeypatch.setattr('services.update_service.requests.get',Mock(side_effect=error,return_value=response))
        if scenario=='close':response.json.side_effect=lambda:(time.sleep(.1) or response.json.return_value)
        center.release=None;dialog=center.open(owner)
        if scenario=='close':dialog.close()
        deadline=time.monotonic()+4
        while dialog.worker is not None and time.monotonic()<deadline:QTest.qWait(10)
        assert dialog.worker is None
        assert QApplication.activeModalWidget() is None,(scenario,dialog.windowModality())
        assert main.isEnabled() and owner.isEnabled()
        if scenario in ('404','empty'):
            assert dialog.status.text()=='目前没有可用的发布版本。' and center.release is None
            assert not dialog.latest_label.isVisible() and not dialog.notes.isVisible()
        elif scenario in ('network','timeout'):
            assert center.state=='error' and dialog.check_button.isEnabled()
        elif scenario=='valid':assert center.release['version']=='0.2.2'
        else:assert not dialog.isVisible()
        dialog.close();settle(surface.app)
        assert QApplication.activeModalWidget() is None
        # Exercise the same gallery/menu after the check has returned.
        main.gallery_interface.btn_tools.click();settle(surface.app)
        menus=[m for m in main.findChildren(SafeRoundMenu) if m.isVisible()]
        assert menus
        for menu in menus:menu.hide()
        center.dialogs.pop(owner);dialog.deleteLater();settle(surface.app)


@pytest.mark.parametrize('value',[60,300])
def test_thumbnail_handle_press_keeps_value_and_drag_uses_same_span(surface,value):
    slider=surface.g.size_slider;slider.setValue(value);settle(surface.app)
    for fraction in (.1,.5,.9):
        slider.setValue(value);option=QStyleOptionSlider();slider.initStyleOption(option)
        rect=slider.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,slider)
        point=QPoint(round(rect.left()+fraction*(rect.width()-1)),rect.center().y())
        changes=[];slider.valueChanged.connect(changes.append)
        QTest.mousePress(slider,Qt.LeftButton,pos=point)
        assert slider.value()==value and not changes and slider.isSliderDown()
        QTest.mouseRelease(slider,Qt.LeftButton,pos=point)
        slider.valueChanged.disconnect(changes.append)
    slider.setValue(60);QTest.mousePress(slider,Qt.LeftButton,pos=QPoint(17,14))
    QTest.mouseMove(slider,QPoint(69,14));QTest.mouseRelease(slider,Qt.LeftButton,pos=QPoint(69,14))
    assert slider.value()==300 and surface.config.get('thumbnail_size')==300
    slider.setValue(60);QTest.mouseClick(slider,Qt.LeftButton,pos=QPoint(slider.width()-6,14))
    assert slider.value()>60 and slider.minimum()==60 and slider.maximum()==300


def test_expanded_details_precede_action_and_close_stays_last(surface):
    h=surface.g.feedback_host;h.dock_to_caption(surface.g);u=h._caption_ui;calls=[]
    for key,state,details in [('run','running',''),('wait','waiting','错误明细'),
                              ('stopped','cancelled','错误明细'),('done','success','')]:
        h.upsert_task(key,'补充识别',kind='ocr',state=state,current=12,total=88,
                      cancel=lambda:calls.append('cancel'),resume=lambda:calls.append('resume'),details=details)
    u.expand();QTest.qWait(250);settle(surface.app)
    assert u.cover.key=='stopped'
    assert u.cover.detail.x()<u.cover.action.x()<u.cover.close.x()
    edges=[]
    for key in ('run','wait','stopped'):
        row,icon,label,bar,count,button,info,close=h._named_widgets[key]
        assert button.isVisible()
        trailing=close if not close.isHidden() else button
        edges.append(trailing.mapTo(u.window,QPoint(trailing.width(),0)).x())
        if key=='run':
            assert info.isHidden() and row.operations.width()==button.width()
        else:
            assert info.isVisible() and info.mapTo(row,QPoint(info.width(),0)).x()<button.mapTo(row,QPoint()).x()
        if not close.isHidden():
            assert button.mapTo(row,QPoint(button.width(),0)).x()<close.mapTo(row,QPoint()).x()
    assert len(set(edges))==1
    row,icon,label,bar,count,button,info,close=h._named_widgets['done']
    # Ordinary completion without a resume callback ends at Close.
    h.upsert_task('done','识别完成',state='success');settle(surface.app)
    assert button.isHidden() and close.isVisible() and row.operations.width()==close.width()
    QTest.mouseClick(close,Qt.LeftButton);assert 'done' not in h.named_tasks and not calls
    QTest.mouseClick(h._named_widgets['run'][5],Qt.LeftButton);assert calls==['cancel']
    QTest.mouseClick(h._named_widgets['stopped'][5],Qt.LeftButton);assert calls==['cancel','resume']


def test_installer_setup_failure_ends_own_modality(surface,main,monkeypatch):
    from fluent_ui.components.update_dialog import UpdateDialog
    from services.update_service import UpdateService
    service=UpdateService();dialog=UpdateDialog(main,service)
    monkeypatch.setattr('fluent_ui.components.update_dialog.active_tasks',lambda:[])
    monkeypatch.setattr('fluent_ui.components.update_dialog.dialogs.confirm',lambda *a:True)
    monkeypatch.setattr(service,'launch_installer',Mock(side_effect=OSError('isolated install setup failure')))
    dialog.show();dialog._prepared({'version':'0.2.2'});dialog.action()
    deadline=time.monotonic()+3
    while dialog.worker is not None and time.monotonic()<deadline:QTest.qWait(10)
    assert dialog.worker is None and not dialog.installing
    assert QApplication.activeModalWidget() is None and main.isEnabled()
    dialog.close();dialog.deleteLater();settle(surface.app)
