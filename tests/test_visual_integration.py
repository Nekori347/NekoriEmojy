"""Only the visual/interaction corrections explicitly requested on 18 October."""
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


def test_meta_footer_centres_and_geometry_does_not_change_with_state(settings):
    from PySide6.QtWidgets import QApplication
    c=settings;c.resize(950,760);settle(QApplication.instance())
    buttons=(c.btn_defaults,c.btn_discard,c.btn_save)
    for b in buttons:
        before=b.content_geometry();b.setEnabled(not b.isEnabled())
        assert b.content_geometry()==before and b.height()==44
    from PySide6.QtCore import QPoint
    centres=[b.mapTo(c,QPoint(0,b.height()//2)).y() for b in buttons]
    preview=c.preview_switch.mapTo(c,QPoint(0,c.preview_switch.height()//2)).y()
    assert max(centres)-min(centres)<=1 and abs(preview-centres[0])<=1


# OCR attached actions, state changes and confirmation are checked in test_ui_tail.


def test_ear_bounces_and_moves_with_panel_and_cover_keeps_live_progress(surface):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication
    h=surface.g.feedback_host;u=h._caption_ui
    for i in range(4):h.upsert_task(str(i),'正在导入表情',current=i,total=10,cancel=lambda:None)
    before=u.ear.y();samples=[u.ear.dot_offsets(t)[0] for t in range(0,700,10)]
    assert min(samples)<-2 and max(samples)>.2
    QApplication.sendEvent(u.ear,QEvent(QEvent.Enter));QTest.qWait(260)
    assert u.opened and u.expansion==1 and u.ear.y()>before
    assert abs(u.ear.y()-(u.material.geometry().bottom()-3))<=1
    assert surface.g.childAt(u.ear.geometry().center()) is u.ear
    h.toast('导入完成',kind='success');h.upsert_task('0','正在导入表情',current=7,total=10,cancel=lambda:None)
    assert h.progress.value()==7 and u.cover.isVisible()
    assert u.cover.background.graphicsEffect().blurRadius()>0
    u.expire_overlay();assert not u.cover.isVisible() and h.progress.value()==7
    u.collapse();QTest.qWait(260);assert u.ear.y()==before and u.expansion==0


def test_update_badge_is_upper_corner_without_text_width_and_owner_details_are_compact(settings):
    from fluent_ui.components.update_center import update_center,UpdateBadge
    from fluent_ui.components.update_dialog import UpdateDialog
    from services.update_service import UpdateService
    from PySide6.QtWidgets import QApplication
    c=settings;c._select_page(4);c._show_tab(0);settle(QApplication.instance())
    center=update_center();badge=UpdateBadge(c);label=c.version_label
    width=label.sizeHint().width()
    try:
        center.set_release(None);assert badge.isHidden()
        release=dict(version='0.2.1',manual_only=True,notes='')
        center.set_release(release);settle(QApplication.instance())
        assert not badge.isHidden() and label.sizeHint().width()==width
        assert label.dot.y()<label.y()+label.height()/2
        assert label.dot.x()>=label.x()+label.fontMetrics().horizontalAdvance(label.text())
        dialog=UpdateDialog(c,UpdateService(repository='Nekori347/NekoriEmojy'))
        dialog._checked(release);dialog.show();settle(QApplication.instance())
        assert dialog.notes.isHidden() and dialog.height()<300 and dialog.width()<=540
        assert dialog.action_button.text()=='获取更新'
        assert (dialog.frameGeometry().center()-c.frameGeometry().center()).manhattanLength()<=2
        dialog.close()
    finally:center.set_release(None)


# Shortcut capture uses the native field again; checked in test_ui_remaining.


def test_theme_material_is_committed_after_internal_styles(surface,monkeypatch):
    from fluent_ui.main_window import MainWindow
    from fluent_ui import visual,materials
    from qfluentwidgets import isDarkTheme
    monkeypatch.setattr(MainWindow,'_init_global_hotkey',lambda self:setattr(self,'hotkey_listener',None))
    w=MainWindow(surface.storage,surface.clipboard,surface.config);w.show()
    w.settings_window.show();settle(surface.app)
    observed=[];original=materials.native_material
    def sample(window,**kwargs):
        if window in (w,w.settings_window):
            observed.append((window.updatesEnabled(),visual.colors()['text'] in w.setting_interface.styleSheet()))
        return original(window,**kwargs)
    monkeypatch.setattr(materials,'native_material',sample)
    try:
        surface.config.set('appearance_mode','light' if isDarkTheme() else 'dark')
        w.on_settings_changed('appearance_mode');settle(surface.app)
        assert observed and all(not updating and styled for updating,styled in observed),observed
    finally:
        w.gallery_interface.imports.shutdown();w.gallery_interface.ocr.close();w.close();w.settings_window.close()
