"""Small interaction controls used by the main library surface."""
from PySide6.QtCore import Qt, QEvent, QPoint, QRect, QRectF, QSize, Signal, QVariantAnimation
from PySide6.QtGui import QGuiApplication, QPen, QColor, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QHBoxLayout, QSizePolicy, QWidget, QAbstractButton
from qfluentwidgets import FluentIconBase, Theme
from fluent_ui.components.controls import DropDownPushButton, CheckBox, PushButton, TransparentToolButton

from services.i18n import translated
from fluent_ui import visual


class SegmentOption(QAbstractButton):
    def __init__(self,text,parent):
        super().__init__(parent);self.setText(text);self.setFont(visual.font())
        self.setCheckable(True);self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
    def sizeHint(self):return QSize(self.fontMetrics().horizontalAdvance(self.text())+28,36)
    def minimumSizeHint(self):return self.sizeHint()
    def paintEvent(self,event):
        p=QPainter(self);c=visual.colors();p.setFont(self.font())
        p.setPen(QColor('#30382d' if self.isChecked() else c['text_secondary']))
        p.drawText(self.rect(),Qt.AlignCenter,self.text())
        if self.hasFocus():
            p.setRenderHint(QPainter.Antialiasing);p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(c['accent']),1))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(3,3,-3,-3),14,14)


class ModeSegment(QWidget):
    """One shared flat track and one moving selection, with native buttons."""
    currentItemChanged=Signal(str)
    def __init__(self,choices,parent=None):
        super().__init__(parent);self.items={};self._key=None;self._selection=QRectF()
        row=QHBoxLayout(self);row.setContentsMargins(3,3,3,3);row.setSpacing(0)
        self.slideAni=QVariantAnimation(self);self.slideAni.setDuration(visual.MOTION.select)
        self.slideAni.setEasingCurve(visual.MOTION.easing);self.slideAni.valueChanged.connect(self._slide)
        for key,label in choices:
            item=SegmentOption(label,self);item.setToolTip(label);item.setAccessibleName(label)
            item.setMinimumWidth(max(96,max(item.fontMetrics().horizontalAdvance(text) for _,text in choices)+28))
            item.clicked.connect(lambda checked=False,k=key:self.setCurrentItem(k))
            self.items[key]=item;row.addWidget(item)
        self.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
        visual.theme.changed.connect(self.update)
        if self.items:self.setCurrentItem(next(iter(self.items)))
    def _slide(self,value):self._selection=value;self.update()
    def currentRouteKey(self):return self._key
    def currentItem(self):return self.items.get(self._key)
    def setCurrentItem(self,key):
        if key not in self.items:return
        changed=key!=self._key;self._key=key
        for k,item in self.items.items():item.setChecked(k==key)
        self.layout().activate();target=QRectF(self.items[key].geometry())
        self.slideAni.stop()
        if self.isVisible() and not self._selection.isEmpty() and changed:
            self.slideAni.setStartValue(self._selection);self.slideAni.setEndValue(target);visual.start_animation(self.slideAni, visual.MOTION.select)
        else:self._selection=target;self.update()
        if changed:self.currentItemChanged.emit(key)
    def resizeEvent(self,event):
        super().resizeEvent(event);self.layout().activate()
        if self.currentItem():self._selection=QRectF(self.currentItem().geometry())
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        p.setPen(QPen(QColor(c['border_soft']),1));p.setBrush(QColor(c['surface_alt']))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),self.height()/2,self.height()/2)
        p.setBrush(QColor('#eeeee8'));p.setPen(Qt.NoPen)
        p.drawRoundedRect(self._selection,self._selection.height()/2,self._selection.height()/2)


class ResourceSortIcon(FluentIconBase):
    def path(self, theme=Theme.AUTO):
        return ''

    def render(self, painter, rect, theme=Theme.AUTO, indexes=None, **attributes):
        from fluent_ui.icons import Icon
        Icon.MANUAL_ORDER.render(painter, rect, theme, **attributes)


class ThemeModeIcon(FluentIconBase):
    def __init__(self, mode):
        self.mode = mode

    def path(self, theme=Theme.AUTO):
        return ''

    def render(self, painter, rect, theme=Theme.AUTO, indexes=None, **attributes):
        from fluent_ui.icons import Icon
        {'system': Icon.SYSTEM, 'light': Icon.SUN, 'dark': Icon.MOON}[self.mode].render(painter, rect, theme, **attributes)


class IconDropDownButton(TransparentToolButton):
    """Square menu trigger; the icon and tooltip identify its current operation."""
    def __init__(self, icon, parent=None):
        super().__init__(parent)
        self.setIcon(icon)
        self.dropMenu = None
        self.setFixedSize(visual.COMPACT_CONTROLS.action_extent, visual.COMPACT_CONTROLS.action_extent)
        self.clicked.connect(self._show_menu)

    def setMenu(self, menu):
        self.dropMenu = menu

    def _show_menu(self):
        if self.dropMenu:
            self.dropMenu.exec(self.mapToGlobal(self.rect().bottomLeft()))


class DropDownButton(DropDownPushButton):
    """Use Fluent's vector chevron and keep the full label when eliding."""

    def __init__(self, parent=None):
        self._full_text = ''
        super().__init__(parent)
        self.setMinimumWidth(54)
        self.setFixedHeight(visual.COMPACT_CONTROLS.action_extent)

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(text)
        self.setAccessibleName(text)
        self._elide()
        self.updateGeometry()

    def sizeHint(self):
        size = super().sizeHint()
        size.setWidth(self.fontMetrics().horizontalAdvance(self._full_text) + 46)
        return size

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(
            self._full_text, Qt.ElideRight, max(0, self.width() - 40)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


class FilterOption(QAbstractButton):
    """The whole row toggles; a reserved rectangular marker is not a check glyph."""
    def __init__(self,text,parent=None):
        super().__init__(parent);self.setText(text);self.setFont(visual.font())
        self.setCheckable(True);self.setCursor(Qt.PointingHandCursor);self.setFocusPolicy(Qt.TabFocus)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
    def sizeHint(self):return QSize(max(180,self.fontMetrics().horizontalAdvance(self.text())+44),32)
    def hitButton(self,pos):return self.rect().contains(pos)
    def enterEvent(self,event):super().enterEvent(event);self.update()
    def leaveEvent(self,event):super().leaveEvent(event);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        if self.underMouse() or (self.hasFocus() and getattr(self,'_keyboard_focus',False)):
            p.setPen(Qt.NoPen);p.setBrush(QColor(c['hover']))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),5,5)
        p.setPen(QPen(QColor(c['border_soft']),.7) if not self.isChecked() else Qt.NoPen)
        p.setBrush(QColor(c['accent'] if self.isChecked() else c['surface_alt']))
        p.drawRoundedRect(QRectF(5,(self.height()-10)/2,10,10),2.5,2.5)
        p.setFont(self.font());p.setPen(QColor(c['text']))
        p.drawText(self.rect().adjusted(24,0,-8,0),Qt.AlignVCenter|Qt.AlignLeft,self.text())

    def focusInEvent(self,event):
        self._keyboard_focus=event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason)
        super().focusInEvent(event);self.update()

    def focusOutEvent(self,event):
        self._keyboard_focus=False;super().focusOutEvent(event);self.update()


class FilterCheckboxFlyout(QFrame):
    """A non-modal checkbox popup, anchored to its trigger, with no replay."""
    changed = Signal(str, bool)
    clear_requested = Signal()

    FIELDS = (('no_tag', '无标签'), ('unclassified', '未分类'),
              ('is_gif', '动图'), ('is_static', '静态表情'), ('missing', '找不到文件的表情'))

    def __init__(self, trigger):
        super().__init__(trigger, Qt.Popup)
        self.trigger = trigger
        self.setObjectName('FilterCheckboxFlyout')
        self.setAttribute(Qt.WA_NoMouseReplay)
        self.setFrameShape(QFrame.StyledPanel)
        self._refresh_surface()
        visual.theme.changed.connect(self._refresh_surface)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.checkboxes = {}
        for key, label in self.FIELDS:
            checkbox = translated(FilterOption, label, self)
            checkbox.toggled.connect(lambda checked, key=key: self.changed.emit(key, checked))
            layout.addWidget(checkbox)
            self.checkboxes[key] = checkbox
        divider = QFrame(self)
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)
        self.clear_button = translated(PushButton, '清除筛选', self)
        self.clear_button.clicked.connect(self.clear_requested)
        layout.addWidget(self.clear_button)

    def _refresh_surface(self):
        c=visual.colors()
        self.setStyleSheet(f"QFrame#FilterCheckboxFlyout {{ background: {c['surface_overlay']}; border: 1px solid {c['border']}; border-radius: 10px; }}")

    def sync(self, state):
        for key, checkbox in self.checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(getattr(state, key)))
            checkbox.blockSignals(False)

    def toggle(self, state):
        if self.isVisible():
            self.hide()
            return
        self.sync(state)
        self.adjustSize()
        anchor = QRect(self.trigger.mapToGlobal(QPoint()), self.trigger.size())
        screen = QGuiApplication.screenAt(anchor.center()) or self.trigger.screen()
        area = screen.availableGeometry()
        x = max(area.left(), min(anchor.left(), area.right() - self.width() + 1))
        y = anchor.bottom() + 1
        if y + self.height() > area.bottom() + 1:
            y = anchor.top() - self.height()
        y = max(area.top(), min(y, area.bottom() - self.height() + 1))
        self.move(x, y)
        self.show()
        self.checkboxes['no_tag'].setFocus(Qt.PopupFocusReason)

    def showEvent(self, event):
        QApplication.instance().installEventFilter(self)
        super().showEvent(event)

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.ShortcutOverride and event.key() == Qt.Key_Escape:
            event.accept()
            return True
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.hide()
            return True
        if event.type() == QEvent.MouseButtonPress:
            pos = event.globalPosition().toPoint()
            trigger_rect = QRect(self.trigger.mapToGlobal(QPoint()), self.trigger.size())
            if trigger_rect.contains(pos):
                self.hide()
                return True
            if not self.geometry().contains(pos):
                self.hide()
        return super().eventFilter(obj, event)
