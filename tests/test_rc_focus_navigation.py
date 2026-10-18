"""Bounded regressions for notification dismissal, focus origin and navigation paint."""
import json
import pytest
from pathlib import Path
from PySide6.QtCore import QObject,QEvent,Qt,QPoint
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest
from test_phase2_interaction import surface,settle
from test_demo_local_fixes import main


def test_mouse_focus_relocation_does_not_invent_keyboard_input(surface,main):
    app=surface.app;g=main.gallery_interface;b=g.btn_settings;rows=[];events=[]
    class Watch(QObject):
        def eventFilter(self,obj,event):
            if event.type() in (QEvent.FocusIn,QEvent.FocusOut):
                events.append(dict(widget=type(obj).__name__,settings=obj is b,reason=str(event.reason())))
            return False
    watch=Watch();app.installEventFilter(watch)
    def record(stage):
        f=app.focusWidget();rows.append(dict(stage=stage,focus=b.hasFocus(),under=b.underMouse(),hover=b._hover,
            keyboard=b._focus_input.keyboard,visible=b.keyboard_focus_visible(),active=main.isActiveWindow(),
            focused=type(f).__name__ if f else None,events=list(events)));events.clear()
    app.setActiveWindow(main);settle(app);record('initial')
    QTest.mouseClick(g.btn_manage,Qt.LeftButton);settle(app);record('manage')
    # Qt automatically transfers focus when the current child disappears.
    transient=QWidget(main);transient.setFocusPolicy(Qt.StrongFocus);transient.show()
    QWidget.setTabOrder(transient,b)
    QTest.mouseClick(transient,Qt.LeftButton);transient.setFocus(Qt.MouseFocusReason);transient.hide();settle(app);record('hidden-mouse-child')
    assert b.hasFocus() and not b.keyboard_focus_visible()
    # Actual Tab input still enables the normal keyboard focus indication.
    transient.show();transient.setFocus(Qt.MouseFocusReason)
    QTest.keyClick(transient,Qt.Key_Tab);settle(app);record('real-tab')
    assert b.hasFocus() and b.keyboard_focus_visible()
    QTest.mouseClick(g.btn_manage,Qt.LeftButton);settle(app);record('mouse-after-tab')
    assert not b.keyboard_focus_visible()
    QTest.mouseClick(g.btn_settings,Qt.LeftButton);settle(app);record('settings-open')
    main.settings_window.close();settle(app);record('settings-closed')
    (Path('../DevData/rc-interaction')/'focus-after.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
    app.removeEventFilter(watch)
    assert not next(r for r in rows if r['stage']=='hidden-mouse-child')['visible']


@pytest.mark.parametrize('appearance',['light','dark'])
def test_tree_transition_background_crosses_row_gaps(surface,appearance):
    from PySide6.QtCore import QRectF
    from fluent_ui import visual
    surface.config.config['appearance_mode']=appearance;visual.theme.configure(surface.config)
    tree=surface.g.sidebar.tree;delegate=tree.itemDelegate()
    tree.expandAll();tree.select_node(surface.parent);settle(surface.app)
    QTest.qWait(220)
    selected=tree.visualItemRect(tree._find_item(surface.parent)).adjusted(4,3,-4,-3)
    x=tree.viewport().width()-40
    color=tree.viewport().grab().toImage().pixelColor(x,selected.center().y())
    tree.select_node(surface.other);settle(surface.app)
    tree._hovered_index=tree.indexFromItem(tree._find_item(surface.child))
    checked=0
    for ms in (20,40,65,95):
        delegate._selection_motion.setCurrentTime(ms)
        image=tree.viewport().grab().toImage()
        r=QRectF(delegate._indicator).adjusted(-6,-8,0,8)
        ys=range(round(r.top())+5,round(r.bottom())-4)
        gaps=[y for y in ys if image.pixelColor(x,y)!=color]
        assert not gaps,(ms,gaps)
        checked+=1
    assert checked==4
    tree.clearSelection()
    for node in (surface.parent,surface.other):tree._find_item(node).setSelected(True)
    QTest.qWait(220);settle(surface.app)
    image=tree.viewport().grab().toImage()
    assert all(image.pixelColor(x,tree.visualItemRect(tree._find_item(node)).center().y())==color
               for node in (surface.parent,surface.other))


def test_mouse_popups_and_panel_changes_keep_settings_ring_off(surface,main):
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    from qfluentwidgets import Action
    app=surface.app;g=main.gallery_interface;b=g.btn_settings
    app.setActiveWindow(main)
    QTest.mouseClick(g.btn_manage,Qt.LeftButton)
    assert not b.keyboard_focus_visible()
    h=g.feedback_host;u=h._caption_ui
    for key in ('a','b'):h.upsert_task(key,'补充识别',kind='ocr',state='running',current=1,total=10,cancel=lambda:None)
    QTest.mouseClick(u.ear,Qt.LeftButton);QTest.qWait(240)
    assert u.opened and not b.keyboard_focus_visible()
    QTest.mouseClick(u.ear,Qt.LeftButton);QTest.qWait(240)
    assert not u.opened and not b.keyboard_focus_visible()
    handle=g.tag_panel_host.splitter.handle(1)
    QTest.mouseClick(handle,Qt.LeftButton,pos=handle.ear_rect(True).center());QTest.qWait(240)
    QTest.mouseClick(g.tag_panel.chrome,Qt.LeftButton);QTest.qWait(240)
    assert not b.keyboard_focus_visible()
    menu=SafeRoundMenu(parent=main);sub=SafeRoundMenu('子菜单',menu);sub.addAction(Action('操作',sub));menu.addMenu(sub)
    menu.popup_at(g.btn_tools);settle(app)
    sub._show_menu(menu.pos()+QPoint(30,30));settle(app)
    QTest.mouseClick(g.btn_manage,Qt.LeftButton);sub.hide();menu.hide();settle(app)
    assert not b.keyboard_focus_visible()
    QTest.mouseClick(b,Qt.LeftButton);settle(app)
    QTest.mouseClick(main.settings_window.titleBar.closeBtn,Qt.LeftButton);settle(app)
    app.setActiveWindow(main);settle(app)
    assert not b.keyboard_focus_visible()
    main.settings_window.show();app.setActiveWindow(main.settings_window);settle(app)
    app.setActiveWindow(main);settle(app)
    assert not b.keyboard_focus_visible()
    main.settings_window.hide();menu.deleteLater()
