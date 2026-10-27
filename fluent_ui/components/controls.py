"""Softframe native controls. Input and command routing remain Qt/Fluent's.

The painters own the full surface and centered icon/text composition, rather
than layering a second skin over Fluent's default indicator paint.
"""
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QVariantAnimation, QEvent, QTimer, QObject
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QCursor
from PySide6.QtWidgets import QAbstractButton, QLineEdit, QWidget, QHBoxLayout, QBoxLayout, QApplication
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


def pointer_hits(widget, rect=None):
    """Current hit relation, including covers; never business selection/focus."""
    if not widget.isVisible() or not widget.isEnabled() or not widget.window().isActiveWindow():
        return False
    position = QCursor.pos()
    if rect is not None and not rect.contains(widget.mapFromGlobal(position)):
        return False
    hit = QApplication.widgetAt(position)
    return hit is widget or (hit is not None and widget.isAncestorOf(hit))


class _ButtonFocusInput(QObject):
    """Track input origin without changing Qt focus or business selection."""
    def __init__(self,app):
        super().__init__(app);self.keyboard=False;app.installEventFilter(self)

    def eventFilter(self,obj,event):
        pointer=event.type()==QEvent.MouseButtonPress
        navigation=(event.type()==QEvent.KeyPress and event.key() in
                    (Qt.Key_Tab,Qt.Key_Backtab,Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down,Qt.Key_Space,Qt.Key_Return,Qt.Key_Enter))
        if pointer or navigation:
            self.keyboard=not pointer
            focused=QApplication.focusWidget()
            if isinstance(focused,ButtonPaint):
                focused._focus_visible=self.keyboard
            if focused is not None:
                focused.update()
        return False


def focus_input():
    """One existing input-origin tracker for buttons and splitter cues."""
    app = QApplication.instance()
    if not hasattr(app, '_button_focus_input'):
        app._button_focus_input = _ButtonFocusInput(app)
    return app._button_focus_input


class ButtonPaint:
    ghost = False
    dropdown = False

    def _init_surface(self):
        _own_presentation(self)
        self.setFont(visual.font())
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self._focus_input=focus_input();self._focus_visible=False
        self._hover = 0.0
        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(visual.MOTION.hover)
        self._hover_animation.valueChanged.connect(self._set_hover)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)
        self._hover_owner=self.window()
        self._hover_owner.installEventFilter(self)
        self._hover_settle_timer=QTimer(self)
        self._hover_settle_timer.setSingleShot(True)
        self._hover_settle_timer.timeout.connect(self._settle_hover)

    def showEvent(self,event):
        owner=self.window()
        if owner is not self._hover_owner:
            self._hover_owner.removeEventFilter(self)
            self._hover_owner=owner;owner.installEventFilter(self)
        super().showEvent(event)
        self._hover_settle_timer.start(0)

    def event(self, event):
        result = super().event(event)
        if hasattr(self, '_hover_settle_timer') and event.type() in (
                QEvent.Move, QEvent.Resize, QEvent.ParentChange, QEvent.EnabledChange,
                QEvent.UngrabMouse):
            if event.type() == QEvent.UngrabMouse:
                self.setDown(False)
            self._hover_settle_timer.start(0)
        return result

    def eventFilter(self, obj, event):
        if obj is self.window() and event.type() in (QEvent.WindowDeactivate, QEvent.WindowActivate):
            self._settle_hover()
            self._hover_settle_timer.start(0)
        return super().eventFilter(obj, event)

    def focusInEvent(self,event):
        if event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason):
            # Qt also uses TabFocusReason to relocate focus when a mouse-opened
            # child disappears. Only actual keyboard input enables its ring.
            self._focus_visible=self._focus_input.keyboard
        elif event.reason() not in (Qt.ActiveWindowFocusReason,Qt.PopupFocusReason):self._focus_visible=False
        super().focusInEvent(event);self.update()

    def focusOutEvent(self,event):
        super().focusOutEvent(event);self.update()

    def keyboard_focus_visible(self):
        return self.hasFocus() and self._focus_visible and self._focus_input.keyboard

    def _settle_hover(self):
        # An owned window can cover the trigger without delivering Leave.
        real_hover = pointer_hits(self)
        self._hover_animation.stop()
        self._set_hover(1.0 if real_hover else 0.0)
        if not real_hover:
            self.setDown(False)

    def _set_hover(self, value):
        self._hover = value
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._animate_hover(1.0)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover_animation.stop();self._set_hover(0.0)

    def _animate_hover(self, target):
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover)
        self._hover_animation.setEndValue(target)
        visual.start_animation(self._hover_animation, visual.MOTION.hover)

    def hideEvent(self,event):
        if hasattr(self,'_hover_animation'):
            self._hover_settle_timer.stop()
            self._hover_animation.stop();self._hover=0.0;self.setDown(False)
        super().hideEvent(event)

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
        floating=bool(self.property('floating'))
        surface=QColor(c['surface_overlay']);surface.setAlpha(190)
        border=QColor(c['border_soft']);border.setAlpha(140)
        p.setPen(QPen(border,1) if floating else Qt.NoPen if self.ghost else QPen(QColor(c['border_soft']), 1))
        p.setBrush(surface if floating else Qt.NoBrush if (self.ghost and not selected) or not enabled else QColor(fill))
        if self.property('outline_toggle'):
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(c['text_secondary'] if selected else c['muted']),1))
        p.drawRoundedRect(r, visual.CONTROL_RADIUS, visual.CONTROL_RADIUS)
        if enabled and (self._hover or self.isDown()):
            p.setPen(Qt.NoPen)
            overlay = QColor(c['text'])
            overlay.setAlphaF(.11 if self.isDown() else .06 * self._hover)
            p.setBrush(overlay)
            p.drawRoundedRect(r, visual.CONTROL_RADIUS, visual.CONTROL_RADIUS)
        if self.keyboard_focus_visible():
            p.setPen(QPen(QColor(c['accent']), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(2, 2, -2, -2), visual.CONTROL_RADIUS-2, visual.CONTROL_RADIUS-2)
        color = c['accent_text'] if primary and enabled else c['danger'] if self.property('role') == 'danger' else c['warning'] if self.property('update_available') else c['text']
        if self.property('outline_toggle'):
            color = c['text'] if selected else c['muted']
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
        return QSize(self.fontMetrics().horizontalAdvance(self.text())+68+getattr(self,'_decision_line',42)+getattr(self,'_decision_padding',12),44)

    def content_geometry(self):
        inside=QRectF(self.rect()).adjusted(4.5,4.5,-4.5,-4.5)
        cy=inside.center().y();padding=getattr(self,'_decision_padding',12)
        line=getattr(self,'_decision_line',42);lead=inside.left()+padding
        text_left=lead+line+12
        return (QRectF(lead,cy,line,0),QRectF(text_left,inside.top(),max(1,inside.right()-42-text_left),inside.height()),
                QRectF(inside.right()-34,cy-13,26,26))

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        outer=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        enabled=self.isEnabled();inside=outer.adjusted(4,4,-4,-4)
        ink=('#61695e' if self.property('command')=='discard' else '#30382d') if enabled else c['muted']
        if enabled:
            edge=visual.accent() if self._hover or self.keyboard_focus_visible() else c['border']
            p.setPen(QPen(QColor(edge),1));p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(outer,outer.height()/2,outer.height()/2)
            fill='#dcddd6' if self.isDown() else '#eeeee8'
            p.setBrush(QColor(fill));p.setPen(QPen(QColor('#b6b8b3'),1))
            p.drawRoundedRect(inside,inside.height()/2,inside.height()/2)
            from fluent_ui.components.softframe import _contours,paint_setting_surface
            # Use a clipped fragment of the same master on the symbol end.
            if _contours:
                p.save();clip=QPainterPath();clip.addRoundedRect(inside,inside.height()/2,inside.height()/2)
                p.setClipPath(clip);p.setOpacity(.25)
                p.drawPixmap(self.width()-135,-68,next(iter(_contours.values())))
                p.restore()
        else:
            p.setPen(QPen(QColor(c['border']),1));p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(outer,outer.height()/2,outer.height()/2)
        p.setFont(visual.font());p.setPen(QColor(ink))
        lead_rect,text_rect,ring=self.content_geometry();lead=lead_rect.left();cy=lead_rect.center().y()
        p.drawText(text_rect,Qt.AlignCenter,self.text())
        p.setOpacity(.35 if enabled else .25);p.setPen(QPen(QColor(ink),1));p.drawLine(int(lead),int(cy),int(lead_rect.right()),int(cy))
        p.setPen(Qt.NoPen);p.setBrush(QColor(ink))
        for x in (lead,lead_rect.right()):p.drawEllipse(QRectF(x-1.5,cy-1.5,3,3))
        p.setOpacity(1)
        command=self.property('command');signal=enabled and command=='save'
        p.setPen(Qt.NoPen);p.setBrush(QColor(c['accent'] if signal else ink));p.setOpacity(1 if enabled else .45);p.drawEllipse(ring);p.setOpacity(1)
        p.save();p.translate(ring.center());p.scale(ring.width()/32,ring.height()/32)
        symbol=c['accent_text'] if signal else '#eeeee8' if enabled else c['window_base']
        path=QPainterPath()
        if command=='save':
            path.moveTo(-10,-1);path.lineTo(-6,-4);path.lineTo(-2,1);path.lineTo(7,-9);path.lineTo(11,-6);path.lineTo(-2,9);path.closeSubpath()
        elif command=='discard':
            for angle in (45,-45):
                from PySide6.QtGui import QTransform
                bar=QPainterPath();bar.addRect(QRectF(-2,-10,4,20));path=path.united(QTransform().rotate(angle).map(bar))
        else:
            path.addEllipse(QRectF(-10,-10,20,20));hole=QPainterPath();hole.addEllipse(QRectF(-6,-6,12,12));path=path.subtracted(hole)
            from PySide6.QtGui import QTransform
            cut=QPainterPath();cut.addRect(QRectF(-2,-13,4,26));path=path.subtracted(QTransform().rotate(35).map(cut))
        p.fillPath(path,QColor(symbol));p.restore()


class TransparentToolButton(ButtonPaint, FluentTool):
    ghost = True
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_surface()
        self.setIconSize(QSize(14,14))


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

    def paintEvent(self,event):
        if not self.property('attached'):return super().paintEvent(event)
        c=visual.colors();p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        body_enabled=self.isEnabled() and self.button.isEnabled()
        primary=self.property('role')=='primary' and body_enabled
        p.setPen(QPen(QColor(c['border_soft']),1));p.setBrush(QColor(c['accent'] if primary else c['control']) if body_enabled else Qt.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),visual.CONTROL_RADIUS,visual.CONTROL_RADIUS)
        if not self.dropButton.isHidden():
            p.setPen(QPen(QColor(c['accent_text'] if primary else c['border_soft']),1))
            x=self.dropButton.x();p.drawLine(x,7,x,self.height()-7)

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
        menu=SafeRoundMenu(parent=self)
        if self.property('popup_left_aligned'):
            menu.exec=lambda *args,**kwargs: menu.popup_at(self)
        return menu

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
        self.setFocusPolicy(Qt.TabFocus)
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
        visual.start_animation(self._slide, visual.MOTION.select)
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
        p.setBrush(QColor('#eeeee8'))
        p.drawRoundedRect(QRectF(3+49*(1-self._position),3,49,28),14,14)
        from services.i18n import t
        p.setFont(visual.font())
        for label,x,selected in ((t('开'),3,self.isChecked()),(t('关'),52,not self.isChecked())):
            p.setPen(QColor('#30382d' if selected else c['muted']))
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
        if self.focus_indicator_visible():
            self.paint_focus_indicator(p)

    def focus_indicator_visible(self):
        return self.hasFocus()

    def paint_focus_indicator(self, painter):
        painter.setPen(QPen(QColor(visual.colors()['accent']), 1, Qt.DotLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 5, 5)


class LineEdit(FluentLineEdit):
    def __init__(self, text='', parent=None):
        # Keep both Qt overloads: LineEdit(parent) and LineEdit(text, parent).
        if isinstance(text, QWidget) or text is None:
            parent, text = text, ''
        super().__init__(parent)
        _own_presentation(self)
        self.setFont(visual.font())
        self.clearButton.setIcon(Icon.CLOSE)
        visual.theme.changed.connect(self.refresh_theme)
        self.refresh_theme()
        self.setText(str(text))

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
