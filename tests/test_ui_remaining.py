"""Business-facing checks for the remaining explicitly requested corrections."""
from test_phase2_interaction import surface,settle
from PySide6.QtCore import Qt,QPoint,QEvent
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtTest import QTest


def test_caption_columns_share_coordinates_and_notice_is_shorter_than_bar(surface):
    h=surface.g.feedback_host;h.dock_to_caption(surface.g);u=h._caption_ui
    for i in range(3):h.upsert_task(str(i),'正在导入表情',current=i,total=30,cancel=lambda:None)
    ear_x=u.ear.x()
    u.expand();QTest.qWait(250);settle(surface.app);u.reposition()
    assert u.ear.x()==ear_x
    for widgets in h._named_widgets.values():
        row,icon,label,bar,count,action,detail,close=widgets
        assert count.mapTo(surface.g,QPoint()).x()==h.count_label.mapTo(surface.g,QPoint()).x()
        assert action.mapTo(surface.g,QPoint()).x()==h.action_button.mapTo(surface.g,QPoint()).x()
        assert bar.mapTo(surface.g,QPoint()).x()==h.progress.mapTo(surface.g,QPoint()).x()+10
        assert bar.width()==h.progress.width()-20
    h.toast('复制成功',kind='success');settle(surface.app)
    assert 0<u.cover.width()<h.progress.width()
    centre=h.progress.mapTo(surface.g,h.progress.rect().center()).x()
    assert abs(u.cover.geometry().center().x()-centre)<=1
    h.upsert_task('0','很长的任务名称'*20,current=18,total=30)
    assert h.progress.value()==18 and u.cover.isVisible()
    h.upsert_task('failed','导入失败',state='error',details='文件无法读取',resume=lambda:None)
    row,icon,label,bar,count,action,detail,close=h._named_widgets['failed']
    assert not detail.isHidden() and not close.isHidden() and not detail.geometry().intersects(close.geometry())


def test_filter_blank_right_edge_toggles_and_toolbar_targets_match(surface):
    fly=surface.g.filter_flyout;fly.toggle(surface.g.filter_state);settle(surface.app)
    row=fly.checkboxes['no_tag'];before=row.isChecked()
    QTest.mouseClick(row,Qt.LeftButton,pos=QPoint(row.width()-3,row.height()//2))
    assert row.isChecked()!=before and surface.g.filter_state.no_tag==row.isChecked()
    buttons=(surface.g.btn_paste.button,surface.g.btn_paste.dropButton,surface.g.btn_manage,surface.g.btn_content_sort)
    assert all(b.width()==32 and b.height()==32 and b.iconSize().width()==18 for b in buttons)


def test_shortcut_capture_is_native_and_still_records(surface):
    from fluent_ui.components.setting_rows import HotkeyRow,HotkeyEditor
    assert 'paintEvent' not in HotkeyEditor.__dict__
    row=HotkeyRow('快捷键','按下组合键','shortcut','ctrl+e',surface.g);row.show();settle(surface.app)
    assert isinstance(row.editor,QLineEdit) and row.editor.isReadOnly()
    QTest.keyClick(row.editor,Qt.Key_Q,Qt.ControlModifier|Qt.ShiftModifier)
    assert row.value()=='ctrl+shift+q'
    row.set_value('');assert row.value()==''


def test_deactivation_only_clears_transient_button_state(surface):
    b=surface.g.btn_manage;b.setChecked(True);b._set_hover(1.0);b.setDown(True)
    QApplication.sendEvent(surface.g,QEvent(QEvent.WindowDeactivate));settle(surface.app)
    assert b._hover==0 and not b.isDown() and b.isChecked()
    QApplication.sendEvent(b,QEvent(QEvent.Enter));QTest.qWait(150)
    assert b._hover==1 and b.isChecked()
    QApplication.sendEvent(b,QEvent(QEvent.Leave));assert b._hover==0


def test_collapsed_tags_use_same_small_extent_on_all_four_docks(surface):
    g=surface.g;host=g.tag_panel_host
    for placement in ('top','bottom','left','right'):
        host.set_placement(placement);host.set_expanded(False,persist=False);QTest.qWait(250);settle(surface.app)
        extent=g.tag_panel.height() if placement in ('top','bottom') else g.tag_panel.width()
        assert extent==20,(placement,extent)


def test_time_sort_keeps_existing_descending_and_ascending_semantics(surface):
    from services.resource_sort import ResourceSort
    from fluent_ui.icons import Icon
    entries=[dict(kind='resource',resource={'library_added_seq':i}) for i in (2,1,3)]
    for mode,icon,values in ((ResourceSort.RECENT_ADDED,Icon.TIME_DESC,[3,2,1]),(ResourceSort.OLDEST_ADDED,Icon.TIME_ASC,[1,2,3])):
        surface.g.set_content_sort(mode)
        assert surface.g.btn_content_sort._icon==icon
        assert [e['resource']['library_added_seq'] for e in mode.project(entries)]==values


def test_popup_anchors_are_upwards_and_left_aligned(surface):
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    from fluent_ui.components.controls import ComboBox
    from qfluentwidgets import Action
    g=surface.g;menu=SafeRoundMenu(parent=g)
    for label in ('相似表情','QQ 导入','Telegram 导入'):menu.addAction(Action(label,parent=menu))
    menu.popup_at(g.btn_tools,prefer_up=True);settle(surface.app)
    anchor=g.btn_tools.mapToGlobal(QPoint())
    assert menu.view.mapToGlobal(menu.view.rect().bottomLeft()).y()<anchor.y()
    assert menu.view.mapToGlobal(QPoint()).x()==anchor.x()
    menu.hide()
    combo=ComboBox(g);combo.setProperty('popup_left_aligned',True);combo.setFixedWidth(180);combo.move(100,100)
    combo.addItem('较长分类名称'*3);combo.show();combo._showComboMenu();settle(surface.app)
    assert combo.dropMenu.view.mapToGlobal(QPoint()).x()==combo.mapToGlobal(QPoint()).x()
    combo.dropMenu.hide();combo.hide()


def test_icon_mode_preserves_root_tile_grid_and_separates_groups(surface):
    g=surface.g
    names=('独立甲','独立乙','独立丙')
    for name in names:surface.storage.create_node(name)
    g.sidebar.refresh_list();surface.config.config['sidebar_mode']='categorized_icons';g.sidebar.apply_presentation();settle(surface.app)
    canvas=g.sidebar.icons.canvas
    tiles=[canvas.rects[i] for i,item in enumerate(canvas.items) if item[1] in names]
    assert len(tiles)==3 and len({r.y() for r in tiles})==1
    assert all(r.width()>=32 and r.height()>=32 for r in tiles)
    assert canvas.font().pixelSize()==12
    for i,rect in canvas.group_by_index.items():
        following=next((j for j in range(i+1,len(canvas.items)) if canvas.items[j][3]==0),None)
        if following is not None:assert canvas.rects[following].top()-rect.bottom()>=6
