"""Live popup painting and lifetime regressions; no Library or network needed."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QEvent,QPoint,Qt
from PySide6.QtGui import QColor,QPalette,QHelpEvent
from PySide6.QtWidgets import QApplication,QWidget,QPushButton,QVBoxLayout,QToolTip
from PySide6.QtTest import QTest
from qfluentwidgets import Theme,setTheme,isDarkTheme
from fluent_ui import visual
from fluent_ui.components.tooltip import install_global_tooltips


@pytest.fixture
def popup():
    app=QApplication.instance() or QApplication([])
    dark=isDarkTheme()
    owner=QWidget();layout=QVBoxLayout(owner)
    button=QPushButton('Target',owner);button.setToolTip('Readable tooltip Ctrl+V')
    layout.addWidget(button);owner.resize(300,100);owner.show()
    tip=install_global_tooltips(app,0)
    def show():
        event=QHelpEvent(QEvent.ToolTip,QPoint(2,2),button.mapToGlobal(QPoint(2,2)))
        assert tip.eventFilter(button,event)
        QTest.qWait(20)
        return tip._tooltip
    yield app,owner,button,tip,show
    tip._hide();owner.close();owner.deleteLater();app.processEvents()
    setTheme(Theme.DARK if dark else Theme.LIGHT);visual.theme.refresh()


def assert_text_painted(popup):
    image=popup.label.grab().toImage()
    expected=QColor(visual.colors()['text'])
    # Check actual QTextDocument glyph pixels, not only stylesheet constants.
    count=sum(abs(image.pixelColor(x,y).red()-expected.red())+
              abs(image.pixelColor(x,y).green()-expected.green())+
              abs(image.pixelColor(x,y).blue()-expected.blue())<18
              for y in range(image.height()) for x in range(image.width())
              if image.pixelColor(x,y).alpha()>200)
    assert count>20
    for group in (QPalette.Active,QPalette.Inactive,QPalette.Disabled):
        assert popup.label.palette().color(group,QPalette.Text)==expected


def test_visible_tooltip_theme_change_updates_real_glyphs(popup):
    app,owner,button,tip,show=popup
    setTheme(Theme.LIGHT);visual.theme.refresh();surface=show()
    assert_text_painted(surface)
    for theme in (Theme.DARK,Theme.LIGHT):
        setTheme(theme);visual.theme.refresh();QTest.qWait(20)
        assert surface.isVisible() and tip._tooltip is surface
        assert_text_painted(surface)
        assert not QToolTip.isVisible()


@pytest.mark.parametrize('kind',[QEvent.WindowDeactivate,QEvent.Hide,QEvent.Close])
def test_owner_lifecycle_hides_popup_and_cancels_delay(popup,kind):
    app,owner,button,tip,show=popup
    surface=show();assert surface.isVisible()
    tip.eventFilter(owner,QEvent(kind))
    assert not surface.isVisible() and tip._shown_for is None
    tip.set_delay(50);tip.eventFilter(button,QEvent(QEvent.Enter))
    assert tip._timer.isActive()
    tip.eventFilter(owner,QEvent(kind));QTest.qWait(60)
    assert not tip._timer.isActive() and not surface.isVisible()


def test_leave_and_screen_edge_reuse_keep_one_readable_popup(popup):
    app,owner,button,tip,show=popup
    surface=show()
    tip._show_text(button,button.toolTip(),button.screen().availableGeometry().bottomRight())
    QTest.qWait(20)
    assert surface.screen().availableGeometry().contains(surface.geometry())
    assert_text_painted(surface)
    assert not tip.eventFilter(button,QEvent(QEvent.Leave))
    assert not surface.isVisible()
    assert show() is surface
