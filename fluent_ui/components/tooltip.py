"""One global tooltip presentation for the whole application.

Icon-first interfaces need the meaning of a button almost immediately, while
Qt's built-in wake-up delay is far longer than that. Every widget keeps using
plain ``setToolTip``; a single application-level filter supplies one short,
consistent delay instead of per-button configuration.
"""
from PySide6.QtCore import QEvent, QObject, QPoint, QTimer, Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QAbstractItemView, QApplication, QWidget, QLabel, QVBoxLayout, QToolTip


class TooltipSurface(QWidget):
    """One alpha-safe painted popup; no second Fluent/native tooltip window."""
    def __init__(self, owner):
        super().__init__(owner,Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.label=QLabel(self);self.label.setWordWrap(True);self.label.setMaximumWidth(380)
        layout=QVBoxLayout(self);layout.setContentsMargins(10,7,10,7);layout.addWidget(self.label)
        self.expiry=QTimer(self);self.expiry.setSingleShot(True);self.expiry.timeout.connect(self.hide)

    def text(self):return self.label.text()

    def paintEvent(self,event):
        from fluent_ui import visual
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode_Source);p.fillRect(self.rect(),Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        c=visual.colors();p.setPen(QPen(QColor(c['border']),1));p.setBrush(QColor(c['surface_overlay']))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),8,8)

try:
    from shiboken6 import isValid as _is_alive
except ImportError:  # pragma: no cover - shiboken always ships with PySide6
    def _is_alive(obj):
        return True

DEFAULT_TOOLTIP_DELAY = 120
_WATCHED = (QEvent.Enter, QEvent.Leave, QEvent.Hide, QEvent.MouseButtonPress, QEvent.ToolTip)


class GlobalToolTipFilter(QObject):
    """Show any widget tooltip after one short application-wide delay."""

    def __init__(self, app, delay=DEFAULT_TOOLTIP_DELAY):
        super().__init__(app)
        self._delay = int(delay)
        self._pending = None   # widget waiting for the delay to elapse
        self._shown_for = None  # widget the visible tooltip belongs to
        self._tooltip = None
        self._owner_window = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._show_pending)

    def delay(self):
        return self._delay

    def set_delay(self, delay):
        self._delay = max(0, int(delay))

    def eventFilter(self, obj, event):
        kind = event.type()
        # Cheapest possible rejection first: this filter sees every event.
        if kind not in _WATCHED:
            return False

        if kind == QEvent.ToolTip:
            # Widgets with a tooltip are already served by the fast timer; item
            # views carry their text on the item, so keep Qt's delivery there
            # but render it through the same Fluent surface.
            if isinstance(obj,QWidget):
                QToolTip.hideText()
                text = self._item_tooltip(obj, event) or obj.toolTip()
                if text:
                    self._timer.stop();self._pending=None
                    self._show_text(obj, text, event.globalPos())
                return True
            return False

        if not isinstance(obj, QWidget):
            return False

        if kind == QEvent.Enter:
            text = obj.toolTip()
            if text and obj.isEnabled():
                self._pending = obj
                self._timer.start(self._delay)
            elif obj is self._pending or obj is self._shown_for:
                self._hide()
        elif obj is self._pending or obj is self._shown_for:
            # The tooltip must disappear with the same widget it was shown for.
            self._hide()
        return False

    @staticmethod
    def _item_tooltip(obj, event):
        view=obj if isinstance(obj,QAbstractItemView) else obj.parentWidget() if isinstance(obj,QWidget) else None
        if not isinstance(view, QAbstractItemView) or view.toolTip():
            return ''
        index = view.indexAt(view.viewport().mapFromGlobal(event.globalPos()))
        if not index.isValid():
            return ''
        return index.data(3) or ''  # Qt.ToolTipRole

    def _show_pending(self):
        target = self._pending
        if target is None or not _is_alive(target) or not target.isVisible():
            return
        text = target.toolTip()
        if not text:
            return
        self._shown_for = target
        duration = target.toolTipDuration()
        self._show_text(target, text, None, duration if duration > 0 else -1)

    def _show_text(self, widget, text, position=None, duration=-1):
        if not _is_alive(widget):
            return
        window = widget.window()
        if self._tooltip is None or not _is_alive(self._tooltip) or self._owner_window is not window:
            if self._tooltip is not None and _is_alive(self._tooltip):
                self._tooltip.hide()
                self._tooltip.deleteLater()
            self._tooltip = TooltipSurface(window)
            self._owner_window = window
        self._tooltip.label.setText(text)
        from fluent_ui import visual
        c=visual.colors()
        self._tooltip.label.setFont(visual.font('tooltip'))
        self._tooltip.label.setStyleSheet(f'color:{c["text"]};background:transparent;border:none;')
        self._tooltip.adjustSize()
        anchor=position or widget.mapToGlobal(widget.rect().topLeft())
        screen=QApplication.screenAt(anchor) or widget.screen();area=screen.availableGeometry()
        x=anchor.x()+12 if position else anchor.x()+(widget.width()-self._tooltip.width())//2
        y=anchor.y()+20 if position else anchor.y()-self._tooltip.height()-5
        if y<area.top():y=anchor.y()+widget.height()+5
        self._tooltip.move(max(area.left(),min(x,area.right()-self._tooltip.width()+1)),max(area.top(),min(y,area.bottom()-self._tooltip.height()+1)))
        self._shown_for = widget
        self._tooltip.expiry.start(duration if duration>0 else 6000)
        self._tooltip.show()

    def _hide(self):
        QToolTip.hideText()
        self._timer.stop()
        self._pending = None
        self._shown_for = None
        if self._tooltip is not None and _is_alive(self._tooltip):
            self._tooltip.hide()


def install_global_tooltips(app=None, delay=DEFAULT_TOOLTIP_DELAY):
    """Install the one tooltip filter for this process. Safe to call twice."""
    app = app or QApplication.instance()
    if app is None:
        return None
    existing = getattr(app, '_nekori_tooltip_filter', None)
    if existing is not None:
        existing.set_delay(delay)
        return existing
    tooltip_filter = GlobalToolTipFilter(app, delay)
    app.installEventFilter(tooltip_filter)
    app._nekori_tooltip_filter = tooltip_filter
    return tooltip_filter
