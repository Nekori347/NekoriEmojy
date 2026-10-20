"""L4 acceptance: deployed resources, native control input, layout and ownership.

Run offscreen, including QT_SCALE_FACTOR=1.5; never inject desktop input.
"""
import os
from pathlib import Path
import pytest
from PySide6.QtCore import Qt, QPoint, QRect, QEvent
from PySide6.QtGui import QColor, QFontInfo, QRawFont
from PySide6.QtWidgets import QApplication, QAbstractButton, QLineEdit
from PySide6.QtTest import QTest,QSignalSpy
from qfluentwidgets import Theme, setTheme
from test_phase2_interaction import surface, settle
from test_demo_local_fixes import main
from test_l1_l3_interaction import settings
from fluent_ui import visual
from fluent_ui.components.setting_rows import SettingRow
from fluent_ui.components.controls import PushButton, SwitchButton
from services.i18n import i18n_engine

OUT=Path('../DevData/softframe-rebuild-1016')/('150dpi' if os.getenv('QT_SCALE_FACTOR')=='1.5' else '100dpi')


def capture(widget,name):
    OUT.mkdir(parents=True,exist_ok=True)
    assert widget.grab().save(str(OUT/f'{name}.png'))


def test_deployed_font_roles_and_tabler_assets(surface):
    from fluent_ui.icons import Icon
    expected={'body':'Sarasa UI SC','page_title':'Sarasa UI SC','brand':'Rajdhani','data':'JetBrains Mono'}
    for role,family in expected.items():
        assert QFontInfo(visual.font(role)).family()==family
    assert QFontInfo(visual.font('page_title')).styleName()=='SemiBold'
    raw=QRawFont.fromFont(visual.font())
    assert all(raw.supportsCharacter(ord(ch)) for ch in '设置分類語日本語AZ09')
    for icon in Icon:
        assert Path(icon.path()).is_file()
        assert not icon.icon().pixmap(24,24).isNull()


def test_settings_keyboard_values_pending_and_narrow_footer(surface,settings):
    c=settings;c.resize(700,660);c._select_page(1);c._show_tab(1);settle(surface.app)
    row=c._rows['thumbnail_size'][0]
    row.spin.editor.setFocus()
    row.spin.editor.selectAll();QTest.keyClicks(row.spin.editor,'180');QTest.keyClick(row.spin.editor,Qt.Key_Return)
    assert row.slider.value()==180 and c.pending['thumbnail_size']==180
    before=row.spin.value();QTest.keyClick(row.spin.editor,Qt.Key_Up)
    assert row.spin.value()==before+10 and row.slider.value()==before+10
    c.discard();assert row.spin.value()==surface.config.get('thumbnail_size',120)
    section=c._sections[0]
    finished=QSignalSpy(section._motion.finished)
    section.toggle_collapsed()
    for _ in range(75):
        if finished.count():break
        QTest.qWait(20)
    assert finished.count(), (section._motion.state(),section._motion.currentTime())
    assert section.body.isHidden()
    section.toggle_collapsed()
    for _ in range(75):
        if finished.count()>=2:break
        QTest.qWait(20)
    assert finished.count()>=2
    assert section.body.isVisible() and section.body.maximumHeight()==16777215
    assert section.body.height()>0
    toggle=c._rows['sidebar_show_labels'][0].switch
    c._rows['sidebar_mode'][0].set_value('categorized_icons')
    c._rows['sidebar_mode'][0].changed.emit();settle(surface.app)
    before=toggle.isChecked();toggle.setFocus();QTest.keyClick(toggle,Qt.Key_Space)
    assert toggle.isChecked()!=before
    c.discard()


@pytest.mark.parametrize('language',['zh','zh_TW','en','ja'])
def test_four_language_settings_narrow_layout(surface,settings,language):
    c=settings;i18n_engine.set_language(language)
    c.resize(700,700)
    for page,(_,tabs) in enumerate(c._icon_pages()):
        c._select_page(page)
        for index in range(len(tabs)):
            c._show_tab(index);settle(surface.app)
            # A page may scroll vertically, never beyond its horizontal viewport.
            assert c.scroll.horizontalScrollBar().maximum()==0,(language,page,index,c.body_widget.minimumSizeHint())
            for row in c.body_widget.findChildren(SettingRow):
                if not row.isVisible():continue
                for widget in row.findChildren(QAbstractButton):
                    if widget.isVisible() and isinstance(widget,PushButton) and widget.text():
                        assert widget.width()>=widget.sizeHint().width(),(language,widget.text(),widget.size(),widget.sizeHint())
                if hasattr(row,'spin'):
                    assert row.spin.width()>=80
            footer=c.btn_save.parentWidget()
            for button in (c.btn_save,c.btn_discard,c.btn_defaults):
                assert footer.rect().contains(button.geometry()),(language,button.text(),button.geometry(),footer.rect())
    c._select_page(1);c._show_tab(1);settle(surface.app)
    capture(c,'settings-narrow-'+language)
    i18n_engine.set_language('zh')


@pytest.mark.parametrize('theme',['light','dark'])
def test_complete_surfaces_and_owner_scrim(surface,main,theme):
    from fluent_ui.components.accent_picker import AccentColorPicker
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    from qfluentwidgets import Action
    setTheme(Theme.DARK if theme=='dark' else Theme.LIGHT);visual.theme.refresh()
    w=main;w.resize(1080,790);w.gallery_interface.set_node(surface.parent)
    QTest.qWait(visual.MOTION.select+20);settle(surface.app)
    capture(w,'main-'+theme)
    w.resize(780,650);settle(surface.app);capture(w,'main-narrow-'+theme)
    w.resize(1080,790)
    w.show_settings();c=w.setting_interface;c._select_page(1);c._show_tab(1);settle(surface.app)
    capture(w.settings_window,'settings-'+theme)
    picker=AccentColorPicker('#5d795c',w.settings_window);picker.show();settle(surface.app)
    assert picker.parentWidget() is w.settings_window
    assert picker._scrim.isVisible() and picker._scrim.parentWidget() is w.settings_window
    capture(picker,'accent-'+theme)
    picker.reject();assert not picker._scrim.isVisible();picker.deleteLater();w.settings_window.hide()
    q=w.quick_panel;q._activation_guard=True;q.resize(360,480);q.show();q._perform_search(force=True);settle(surface.app)
    capture(q,'quick-'+theme);q.hide()
    for show,attr,name in ((w.show_qq_scan,'qq_window','qq'),(w.show_tg_sticker,'tg_window','telegram'),(w.show_similarity,'_similarity_window','similarity')):
        show();tool=getattr(w,attr);settle(surface.app)
        assert tool.owner is w and tool.windowModality()==Qt.NonModal
        capture(tool,name+'-'+theme);tool.hide()
    menu=SafeRoundMenu(parent=w);menu.addAction(Action('复制',parent=menu));menu.addAction(Action('删除',parent=menu))
    menu.exec(w.mapToGlobal(QPoint(100,100)));settle(surface.app);capture(menu,'menu-'+theme);menu.hide();menu.deleteLater()
    setTheme(Theme.LIGHT);visual.theme.refresh()


def test_interrupted_rail_and_tab_selection_continue(surface,monkeypatch):
    rail=surface.g.location_rail
    path=[{'id':str(i),'name':'分类 '+str(i)} for i in range(5)]
    rail.set_path(path)
    monkeypatch.setattr(QApplication,'platformName',lambda:'animation-test')
    rail.set_path(path[:-1],path[-1]);rail.animation.pause();rail.animation.setCurrentTime(70)
    before=rail._display_rows()
    QTest.mousePress(rail,Qt.LeftButton,pos=QPoint(40,12))
    assert rail._display_rows()==before
    rail.set_path(path[:-2],path[-2]);rail.animation.pause();rail.animation.setCurrentTime(0)
    after={r[0]:r for r in rail._display_rows()}
    for row in before:
        assert after[row[0]][2:7]==row[2:7]
    rail.animation.setCurrentTime(visual.MOTION.select)
    assert rail.current_rect().top()==visual.HIERARCHY_CURRENT_TOP


def test_import_forms_fit_both_responsive_compositions(surface,main):
    from PySide6.QtWidgets import QScrollBar
    from fluent_ui.presentation.scrollbar import install_scrollbars
    main.resize(1080,790)
    for show,attr in ((main.show_qq_scan,'qq_window'),(main.show_tg_sticker,'tg_window')):
        show();tool=getattr(main,attr);view=tool.view
        for width in (700,1000):
            tool.resize(width,740);settle(surface.app);QTest.qWait(60)
            assert view.configFormWidget.width()<=view.configScrollArea.viewport().width()
            for button in view.configFormWidget.findChildren(PushButton):
                if button.isVisible():
                    assert button.width()>=button.sizeHint().width(),(width,button.text())
            capture(tool,f'import-{attr}-{width}')
        tool.hide()
    # Painting does not replace the original scrollbar value/input controller.
    bar=QScrollBar(Qt.Vertical);bar.setRange(0,100);bar.setPageStep(10);bar.setValue(40)
    from fluent_ui.presentation.scrollbar import ScrollPaint
    paint=ScrollPaint(bar);bar.installEventFilter(paint);bar.resize(16,200);bar.show()
    bar.setFocus();QTest.keyClick(bar,Qt.Key_Down)
    assert bar.value()==41
    assert not bar.grab().isNull()
    bar.close()
