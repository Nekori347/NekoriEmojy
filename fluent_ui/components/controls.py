"""Softframe native controls. Input and command routing remain Qt/Fluent's.

The painters own the full surface and centered icon/text composition, rather
than layering a second skin over Fluent's default indicator paint.
"""
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QLineEdit, QWidget, QHBoxLayout, QBoxLayout
from qfluentwidgets import (PushButton as FluentButton, TransparentToolButton as FluentTool,
    DropDownPushButton as FluentDropDown, ComboBox as FluentCombo,
    SearchLineEdit as FluentSearch, LineEdit as FluentLineEdit, CheckBox as FluentCheck,
    CardWidget as FluentCard, TextEdit as FluentTextEdit)
from qfluentwidgets.common.icon import FluentIconBase
from fluent_ui import visual
from fluent_ui.icons import Icon


def _own_presentation(widget):
    # These controls paint/theme themselves. Fluent's deferred first-paint
    # sheet must not overwrite the Softframe sheet after a theme change.
    from qfluentwidgets.common.style_sheet import styleSheetManager
    styleSheetManager.deregister(widget)
    widget.setProperty('dirty-qss',False)


def draw_icon(icon, painter, rect, color):
    if isinstance(icon, FluentIconBase):
        icon.render(painter, rect, fill=color)
    elif icon is not None and not icon.isNull():
        icon.paint(painter, rect.toRect())


class ButtonPaint:
    ghost = False
    dropdown = False

    def _init_surface(self):
        _own_presentation(self)
        self.setFont(visual.font())
        self.setCursor(Qt.PointingHandCursor)
        self._hover = 0.0
        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(visual.MOTION.hover)
        self._hover_animation.valueChanged.connect(self._set_hover)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def _set_hover(self, value):
        self._hover = value
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._animate_hover(1.0)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._animate_hover(0.0)

    def _animate_hover(self, target):
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover)
        self._hover_animation.setEndValue(target)
        self._hover_animation.start()

    def sizeHint(self):
        width = self.fontMetrics().horizontalAdvance(self.text())
        icon = getattr(self, '_icon', None)
        has_icon = icon is not None and (not hasattr(icon, 'isNull') or not icon.isNull())
        width += self.iconSize().width() + (7 if self.text() else 0) if has_icon else 0
        return QSize(max(28, width + (28 if not self.ghost else 12) + (22 if self.dropdown else 0)), 32)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = visual.colors()
        enabled = self.isEnabled()
        primary = self.property('role') == 'primary'
        selected = self.isChecked() if self.isCheckable() else False
        fill = c['accent'] if primary and enabled else c['selected'] if selected else c['control']
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        p.setOpacity(1 if enabled else .45)
        p.setPen(Qt.NoPen if self.ghost else QPen(QColor(c['border_soft']), 1))
        p.setBrush(Qt.NoBrush if (self.ghost and not selected) or not enabled else QColor(fill))
        p.drawRoundedRect(r, visual.CONTROL_RADIUS, visual.CONTROL_RADIUS)
        if enabled and (self._hover or self.isDown()):
            p.setPen(Qt.NoPen)
            overlay = QColor(c['text'])
            overlay.setAlphaF(.11 if self.isDown() else .06 * self._hover)
            p.setBrush(overlay)
            p.drawRoundedRect(r, visual.CONTROL_RADIUS, visual.CONTROL_RADIUS)
        if self.hasFocus():
            p.setPen(QPen(QColor(c['accent']), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(2, 2, -2, -2), visual.CONTROL_RADIUS-2, visual.CONTROL_RADIUS-2)
        color = c['accent_text'] if primary and enabled else c['danger'] if self.property('role') == 'danger' else c['text']
        p.setFont(self.font())
        text = self.text()
        icon = getattr(self, '_icon', None)
        has_icon = icon is not None and (not hasattr(icon, 'isNull') or not icon.isNull())
        iw = self.iconSize().width() if has_icon else 0
        gap = 7 if has_icon and text else 0
        available = self.width() - (24 if self.dropdown else 0)
        if self.dropdown:
            text=p.fontMetrics().elidedText(text,Qt.ElideRight,max(0,available-iw-gap-16))
        tw = p.fontMetrics().horizontalAdvance(text)
        x = (available - tw - iw - gap) / 2
        if has_icon:
            draw_icon(icon, p, QRectF(x, (self.height()-iw)/2, iw, iw), color)
        p.setPen(QColor(color))
        p.drawText(QRectF(x+iw+gap, 0, tw+1, self.height()), Qt.AlignCenter, text)
        if self.dropdown:
            Icon.DOWN.render(p, QRectF(self.width()-22, (self.height()-12)/2, 12, 12), fill=color)


class PushButton(ButtonPaint, FluentButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_surface()


class PrimaryPushButton(PushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty('role', 'primary')


class MetaButton(PushButton):
    """C09: separated active contours, transparent single-outline disabled state."""
    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text())+94,44)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        p.setPen(QPen(QColor(c['border'] if self.isEnabled() else c['border_soft']),1));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r,r.height()/2,r.height()/2)
        if self.isEnabled():
            p.setBrush(QColor(c['accent'] if self.property('role')=='primary' else c['hover'] if self.underMouse() else c['control']));p.setPen(Qt.NoPen)
            inside=r.adjusted(4,4,-4,-4)
            p.drawRoundedRect(inside,inside.height()/2,inside.height()/2)
            from fluent_ui.components.softframe import _contours,paint_setting_surface
            # Use a clipped fragment of the same master on the symbol end.
            if _contours:
                p.save();clip=QPainterPath();clip.addRoundedRect(inside,inside.height()/2,inside.height()/2)
                p.setClipPath(clip);p.setOpacity(.25)
                p.drawPixmap(self.width()-135,-68,next(iter(_contours.values())))
                p.restore()
        p.setFont(visual.font());p.setPen(QColor(c['text'] if self.isEnabled() else c['muted']))
        p.drawText(r.adjusted(46,0,-34,0),Qt.AlignCenter,self.text())
        p.setPen(QPen(QColor(c['border']),1));p.drawLine(15,self.height()//2,36,self.height()//2)
        p.drawPoint(15,self.height()//2);p.drawPoint(36,self.height()//2)
        ring=QRectF(self.width()-33,self.height()/2-11,22,22)
        p.setPen(Qt.NoPen);p.setBrush(QColor(c['text_secondary']));p.drawEllipse(ring)
        p.setPen(QPen(QColor(c['surface']),2.5,Qt.SolidLine,Qt.RoundCap));p.setBrush(Qt.NoBrush)
        if self.property('command') in ('save','discard'):
            Icon.ACCEPT.render(p,ring.adjusted(4,4,-4,-4),fill=c['surface']) if self.property('command')=='save' else Icon.CANCEL.render(p,ring.adjusted(4,4,-4,-4),fill=c['surface'])
        else:
            for start in (10,100,190,280):p.drawArc(ring.adjusted(5,5,-5,-5),start*16,56*16)


class TransparentToolButton(ButtonPaint, FluentTool):
    ghost = True
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_surface()
        self.setIconSize(QSize(16, 16))


class DropDownPushButton(ButtonPaint, FluentDropDown):
    dropdown = True
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_surface()


class SplitPushButton(QWidget):
    clicked = Signal()
    def __init__(self, *args, **kwargs):
        parent = kwargs.get('parent')
        if args and isinstance(args[-1], QWidget):
            parent, args = args[-1], args[:-1]
        super().__init__(parent)
        self.button = PushButton(*args, self)
        self.button.clicked.connect(self.clicked)
        self.dropButton = TransparentToolButton(Icon.DOWN, self)
        self.dropButton.clicked.connect(self.showFlyout)
        self.flyout = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(1)
        layout.addWidget(self.button)
        layout.addWidget(self.dropButton)

    def setText(self,text):
        self.button.setText(text)

    def text(self):
        return self.button.text()

    def setIcon(self,icon):
        self.button.setIcon(icon)

    def setFlyout(self,flyout):
        self.flyout=flyout

    def showFlyout(self):
        if self.flyout:
            self.flyout.exec(self.mapToGlobal(self.rect().bottomLeft()))


class AdaptiveCommandBar(QWidget):
    """Two command groups stay complete when their combined width no longer fits."""
    def resizeEvent(self,event):
        super().resizeEvent(event)
        layout=self.layout()
        groups=[layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
        needed=sum(w.minimumSizeHint().width() for w in groups)+48
        stacked=self.width()<needed
        layout.setDirection(QBoxLayout.TopToBottom if stacked else QBoxLayout.LeftToRight)
        margins=layout.contentsMargins()
        heights=[max(w.minimumSizeHint().height(),w.minimumHeight(),w.layout().heightForWidth(max(0,self.width()-margins.left()-margins.right())) if w.layout() and w.layout().hasHeightForWidth() else 0) for w in groups]
        height=(sum(heights)+layout.spacing() if stacked else max(heights,default=0))+margins.top()+margins.bottom()
        self.setFixedHeight(max(66,height))


class CardWidget(FluentCard):
    def paintEvent(self,event):
        if self.property('industrial'):
            from fluent_ui.components.softframe import paint_setting_surface
            p=QPainter(self);paint_setting_surface(p,QRectF(self.rect()));return
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        c=visual.colors()
        p.setBrush(QColor(c['surface']))
        p.setPen(QPen(QColor(c['border_soft']),1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),10,10)


class TextEdit(FluentTextEdit):
    def __init__(self,parent=None):
        super().__init__(parent)
        _own_presentation(self)
        self.setFont(visual.font())
        self.layer.hide()
        visual.theme.changed.connect(self.refresh_theme)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(visual.control_style())


class ComboBox(ButtonPaint, FluentCombo):
    dropdown = True
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_surface()

    def _createComboMenu(self):
        from fluent_ui.components.safe_round_menu import SafeRoundMenu
        return SafeRoundMenu(parent=self)

    def sizeHint(self):
        width = max([self.fontMetrics().horizontalAdvance(item.text) for item in getattr(self, 'items', [])] + [40])
        return QSize(width + 44, 32)

    def minimumSizeHint(self):
        # A selected path/category may be long; it is elided in the button and
        # shown in full by the popup, never a minimum width for its whole form.
        return QSize(90,32)


class SwitchButton(QAbstractButton):
    checkedChanged = Signal(bool)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(104, 34)
        self.setCursor(Qt.PointingHandCursor)
        self._position = 0.0
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(visual.MOTION.select)
        self._slide.setEasingCurve(visual.MOTION.easing)
        self._slide.valueChanged.connect(self._set_position)
        self.toggled.connect(self._toggle)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def setOnText(self, text):
        self._on_text = text

    def setOffText(self, text):
        self._off_text = text

    def _set_position(self, value):
        self._position = value
        self.update()

    def _toggle(self, checked):
        self._slide.stop()
        self._slide.setStartValue(self._position)
        self._slide.setEndValue(float(checked))
        self._slide.start()
        self.checkedChanged.emit(checked)

    def setChecked(self, checked):
        super().setChecked(checked)
        if not self.isVisible() or self.signalsBlocked():
            self._slide.stop()
            self._position = float(checked)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = visual.colors()
        p.setOpacity(1 if self.isEnabled() else .4)
        p.setPen(QPen(QColor(c['border_soft']), 1));p.setBrush(QColor(c['surface_alt']))
        p.drawRoundedRect(QRectF(.5,.5,103,33),16.5,16.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c['surface']))
        p.drawRoundedRect(QRectF(3+49*(1-self._position),3,49,28),14,14)
        from services.i18n import t
        p.setFont(visual.font())
        for label,x,selected in ((t('开'),3,self.isChecked()),(t('关'),52,not self.isChecked())):
            p.setPen(QColor(c['text'] if selected else c['muted']))
            p.drawText(QRectF(x,0,49,34),Qt.AlignCenter,label)
        if self.hasFocus():
            p.setPen(QPen(QColor(c['accent']), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(.5,.5,103,33),16.5,16.5)


class CheckBox(FluentCheck):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFont(visual.font())
        visual.theme.changed.connect(self.update)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = visual.colors()
        p.setOpacity(1 if self.isEnabled() else .4)
        r = QRectF(2, (self.height()-18)/2, 18, 18)
        p.setPen(QPen(QColor(c['accent'] if self.isChecked() else c['border']), 1))
        p.setBrush(QColor(c['selected'] if self.isChecked() else c['control']))
        p.drawRoundedRect(r, 5, 5)
        if self.isChecked():
            Icon.ACCEPT.render(p, r.adjusted(2, 2, -2, -2), fill=c['text'])
        p.setPen(QColor(c['text']))
        p.setFont(self.font())
        p.drawText(self.rect().adjusted(29, 0, -2, 0), Qt.AlignVCenter, self.text())
        if self.hasFocus():
            p.setPen(QPen(QColor(c['accent']), 1, Qt.DotLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 5, 5)


class LineEdit(FluentLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        _own_presentation(self)
        self.setFont(visual.font())
        self.clearButton.setIcon(Icon.CLOSE)
        visual.theme.changed.connect(self.refresh_theme)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(visual.control_style())

    def paintEvent(self, event):
        QLineEdit.paintEvent(self, event)


class SearchLineEdit(FluentSearch):
    def __init__(self, parent=None):
        super().__init__(parent)
        _own_presentation(self)
        self.setFont(visual.font())
        self.setFixedHeight(34)
        self.searchButton.setIcon(Icon.SEARCH)
        self.searchButton.setIconSize(QSize(16, 16))
        self.clearButton.setIcon(Icon.CLOSE)
        self.clearButton.setIconSize(QSize(14, 14))
        visual.theme.changed.connect(self.refresh_theme)
        self.refresh_theme()

    def refresh_theme(self):
        self.setStyleSheet(visual.control_style())

    def paintEvent(self, event):
        QLineEdit.paintEvent(self, event)
