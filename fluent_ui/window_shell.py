"""The two desktop windows share a quiet rounded shell and theme palette."""
import ctypes
import os
from ctypes import wintypes
import win32con
import win32gui
from services.i18n import t, bind_text
from PySide6.QtCore import QEvent, Qt, QRectF, QPoint, QPropertyAnimation
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette, QPainter, QPainterPath, QPen,QIcon
from PySide6.QtWidgets import QApplication, QWidget, QStackedWidget, QVBoxLayout
from qframelesswindow import FramelessWindow, StandardTitleBar
from qframelesswindow.titlebar.title_bar_buttons import TitleBarButtonState,TitleBarButton

from fluent_ui import visual
from fluent_ui.components.dialogs import center_on_owner

# An auxiliary window must never swallow its owner. These gaps keep the owner's
# caption bar and side frames visible and reachable while a child is open, so
# the owner can still be dragged, focused and closed.
OWNER_SIDE_GAP = 48
OWNER_TITLE_GAP = 44


def fit_inside_owner(window, owner, preferred, minimum):
    """Clamp an auxiliary window to the owner frame and the owner's screen."""
    owner_rect = owner.frameGeometry()
    screen = QGuiApplication.screenAt(owner_rect.center()) or owner.screen()
    available = screen.availableGeometry()
    max_width = min(owner_rect.width() - 2 * OWNER_SIDE_GAP, available.width())
    max_height = min(owner_rect.height() - 2 * OWNER_TITLE_GAP, available.height())
    window.resize(max(minimum[0], min(preferred[0], max_width)),
                  max(minimum[1], min(preferred[1], max_height)))


def apply_shell_theme(window):
    c = visual.colors()
    if not getattr(window,'_shell_typography_applied',False):
        visual.apply_typography(window)
        window._shell_typography_applied=True
    palette = QPalette()
    for role, color in ((QPalette.Window, c['background']), (QPalette.Base, c['surface']),
                        (QPalette.AlternateBase, c['surface_alt']), (QPalette.Button, c['surface']),
                        (QPalette.WindowText, c['text']), (QPalette.Text, c['text']),
                        (QPalette.ButtonText, c['text']), (QPalette.PlaceholderText, c['muted']),
                        (QPalette.Highlight, c['hover']), (QPalette.HighlightedText, c['text'])):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(c['muted']))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(c['muted']))
    palette.setColor(QPalette.Mid,QColor(c['border']))
    palette.setColor(QPalette.BrightText,QColor(c['danger']))
    if not getattr(window,'owner',None):
        QApplication.instance().setPalette(palette)
    window.setPalette(palette)
    visual.theme.material(window)
    sheet=visual.window_style(background='transparent')
    if window.styleSheet()!=sheet:window.setStyleSheet(sheet)
    window.setAutoFillBackground(False)
    window.titleBar.titleLabel.setStyleSheet(f"color:{c['text']};background:transparent;padding:0 5px;")
    for button in (window.titleBar.minBtn, window.titleBar.maxBtn, window.titleBar.closeBtn):
        button.setNormalColor(QColor(c['muted']))
        button.setHoverColor(QColor(c['text']))
        button.setPressedColor(QColor(c['text']))
        button.setHoverBackgroundColor(QColor(c['hover']))
        button.setPressedBackgroundColor(QColor(c['selected']))
        button.setFixedSize(28,24)
    window.titleBar.closeBtn.setHoverColor(QColor('white'))
    window.titleBar.closeBtn.setHoverBackgroundColor(QColor(c['danger']))
    window.titleBar.closeBtn.setPressedBackgroundColor(QColor(c['danger']))


class CaptionButton(TitleBarButton):
    """One centre and one rounded hit surface for every window command."""
    def __init__(self,kind,parent):
        super().__init__(parent);self.kind=kind;self._maximized=False
        self.setFixedSize(28,24)
        bind_text(self,{'minimize':'最小化','maximize':'最大化','close':'关闭'}[kind],'setToolTip')
        self.setAccessibleName(self.toolTip())

    def setMaxState(self,maximized):
        self._maximized=bool(maximized);self.update()
        if self.kind=='maximize':
            bind_text(self,'还原' if maximized else '最大化','setToolTip');self.setAccessibleName(self.toolTip())

    def icon_rect(self):
        return QRectF((self.width()-14)/2,(self.height()-14)/2,14,14)

    def highlight_rect(self):
        return QRectF(self.rect()).adjusted(1,1,-1,-1)

    def paintEvent(self,event):
        from fluent_ui.icons import Icon
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        foreground,background=self._getColors()
        p.setPen(Qt.NoPen);p.setBrush(background);p.drawRoundedRect(self.highlight_rect(),6,6)
        r=self.icon_rect()
        if self.kind in ('minimize','close'):
            (Icon.REMOVE if self.kind=='minimize' else Icon.CLOSE).render(p,r,fill=foreground)
        else:
            p.setPen(QPen(foreground,1.3,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(Qt.NoBrush)
            if self._maximized:
                back=r.adjusted(4,1,-1,-4);front=r.adjusted(1,4,-4,-1)
                # Draw only the exposed rear edges; transparent states cannot
                # use the front rectangle's background to hide rear strokes.
                outline=QPainterPath();outline.moveTo(back.left(),front.top())
                outline.lineTo(back.topLeft());outline.lineTo(back.topRight())
                outline.lineTo(back.bottomRight());outline.lineTo(front.right(),back.bottom())
                p.drawPath(outline);p.drawRect(front)
            else:p.drawRect(r.adjusted(2,2,-2,-2))

    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        self.setState(TitleBarButtonState.HOVER if self.rect().contains(event.position().toPoint()) else TitleBarButtonState.NORMAL)


class NekoriTitleBar(StandardTitleBar):
    def __init__(self,parent):
        super().__init__(parent)
        from qframelesswindow.utils import toggleMaxState
        for attr,kind,callback in [('minBtn','minimize',self.window().showMinimized),('maxBtn','maximize',lambda:toggleMaxState(self.window())),('closeBtn','close',self.window().close)]:
            old=getattr(self,attr);button=CaptionButton(kind,self)
            self.hBoxLayout.replaceWidget(old,button);old.hide();old.deleteLater();setattr(self,attr,button)
            button.clicked.connect(callback)
        self.setAutoFillBackground(False)
        self.titleLabel.setStyleSheet('background: transparent; padding: 0 5px;')
        self.titleLabel.setFont(visual.font('brand'))

    def setIcon(self,icon):
        self.iconLabel.setFixedSize(22,22)
        self.iconLabel.setPixmap(QIcon(icon).pixmap(22,22))

    def setTitle(self,title):
        self.titleLabel.setFont(visual.font('body' if any(ord(ch)>127 for ch in title) else 'brand'))
        super().setTitle(title)

    def canDrag(self, pos):
        for name in ('settingsButton', 'themeButton'):
            button = getattr(self, name, None)
            if button is not None and button.isVisible() and button.geometry().contains(pos):
                return False
        return super().canDrag(pos)

    def mouseDoubleClickEvent(self, event):
        if (event.button() == Qt.LeftButton and self._isDoubleClickEnabled
                and QApplication.platformName() == 'windows'):
            capture = win32gui.GetCapture()
            host = int(self.window().internalWinId())
            if capture and capture != host and win32gui.GetAncestor(capture, win32con.GA_ROOT) == host:
                # Qt's native caption child still owns the implicit grab here.
                # The library posts SC_MAXIMIZE before its synthetic release;
                # Windows ignores that command while this child has capture.
                win32gui.ReleaseCapture()
        super().mouseDoubleClickEvent(event)


class AccentDecoration(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)
        parent.installEventFilter(self)
        parent.titleBar.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.LayoutRequest, QEvent.Show, QEvent.FontChange):
            self.reposition()
        return False

    def reposition(self):
        window = self.parentWidget()
        logo=window.titleBar.iconLabel
        start=max(10,logo.mapTo(window,QPoint(logo.width(),0)).x()+10)
        self.setGeometry(start,3,max(0,window.width()-start-10),3)
        self.setVisible(window.width()>64)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(visual.accent()))
        painter.drawRoundedRect(QRectF(self.rect()), 1.5, 1.5)


def add_shell_accent(window):
    window.titleBar.setFixedHeight(34)
    window.titleBar.hBoxLayout.setContentsMargins(8,7,6,2)
    window.titleBar.hBoxLayout.setSpacing(2)
    for button in (window.titleBar.iconLabel,window.titleBar.minBtn,window.titleBar.maxBtn,window.titleBar.closeBtn):
        window.titleBar.hBoxLayout.setAlignment(button,Qt.AlignBottom)
    window.titleBar.titleLabel.setProperty('role', 'brand')
    window.titleBar.titleLabel.setFont(visual.font('brand'))
    window.titleBar.iconLabel.show()
    window.titleBar.setIcon(window.windowIcon())
    window.accent_line = AccentDecoration(window)
    window.accent_line.setObjectName('WindowAccent')
    window.accent_line.setAttribute(Qt.WA_TransparentForMouseEvents)
    # Keep the decoration inside the caption, clear of the native resize edge.
    window.accent_line.reposition()
    window.accent_line.raise_()


class NekoriWindow(FramelessWindow):
    # Reused across messages: WM_SETCURSOR arrives continuously while the mouse
    # moves, so a per-message Structure allocation is pure overhead.
    _native_message = wintypes.MSG()

    def __init__(self, parent=None):
        self._native_state_log = None
        if os.environ.get('NEKORI_NATIVE_CHECK') == '1' and os.environ.get('NEKORI_APP_DATA'):
            from fluent_ui.components.native_state_log import NativeStateLog
            self._native_state_log = NativeStateLog()
        super().__init__(parent)
        # The frameless constructor has already created the native surface.
        # Enabling Qt alpha here only takes effect after HWND recreation,
        # switching the backing-store path and freezing maximized content.
        self.setAutoFillBackground(False)
        self._title_bar_buttons = []
        from fluent_ui.components.native_resize import install_native_child_edges
        install_native_child_edges()
        self._reveal=QPropertyAnimation(self,b'windowOpacity',self)
        self._reveal.setDuration(visual.MOTION.window)
        self._reveal.setEasingCurve(visual.MOTION.easing)

    def showEvent(self, event):
        self.clear_transient_button_states()
        super().showEvent(event)
        from fluent_ui.materials import native_material
        native_material(self)
        from fluent_ui.materials import sync_native_clip
        sync_native_clip(self)
        # Animating native alpha on Acrylic changes the layered HWND surface
        # and can briefly composite the owner over its child. Keep the native
        # backdrop stable; opaque fallback windows can still use the reveal.
        if hasattr(self,'_reveal') and self.property('nativeMaterial')!='acrylic' and QApplication.platformName() not in ('offscreen','minimal'):
            self._reveal.stop();self._reveal.setStartValue(.94);self._reveal.setEndValue(1.0);self._reveal.start()

    def paintEvent(self,event):
        from fluent_ui.materials import shell_color,shell_radius
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(),Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setBrush(shell_color(self));p.setPen(QPen(QColor(visual.colors()['border']),1))
        radius=shell_radius(self)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),radius,radius)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        from fluent_ui.materials import sync_native_clip
        sync_native_clip(self)

    def setTitleBar(self, title_bar):
        super().setTitleBar(title_bar)
        # qframelesswindow only ever clears a caption button in leaveEvent, and
        # it has no mouseReleaseEvent, so a button that was pressed stays
        # PRESSED for good whenever the pointer cannot leave it -- exactly what
        # happens when clicking the close button, because the window hides with
        # the pointer still on the button. StandardTitleBar.canDrag() asks
        # isPressed(), so one stuck button makes the whole title bar undraggable
        # and the button keeps its pressed paint. Settle the state here instead
        # of patching Settings, where the symptom is merely most visible.
        self._title_bar_buttons = [button for button in
                                   (title_bar.minBtn, title_bar.maxBtn, title_bar.closeBtn)
                                   if button is not None]
        for button in self._title_bar_buttons:
            button.released.connect(lambda button=button: self._settle_title_button(button))

    def _settle_title_button(self, button):
        """Restore the caption button state after a release.

        The pointer is normally still on the button, so the honest state is
        HOVER; QAbstractButton emits released before clicked, which keeps this
        ahead of the close button's own handler.
        """
        if button.isEnabled() and button.underMouse() and self.isActiveWindow():
            button.setState(TitleBarButtonState.HOVER)
        else:
            button.setState(TitleBarButtonState.NORMAL)

    def clear_transient_button_states(self):
        """Reset every caption button to NORMAL.

        Called on the lifecycle nodes where no Leave can arrive: the window is
        hidden, or it lost activation while a button was hovered or pressed.
        """
        for button in self._title_bar_buttons:
            button.setState(TitleBarButtonState.NORMAL)

    def hideEvent(self, event):
        self.clear_transient_button_states()
        if hasattr(self,'_reveal'):
            self._reveal.stop()
            self.setWindowOpacity(1)
        super().hideEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and not self.isActiveWindow():
            self.clear_transient_button_states()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.WinIdChange:
            # QWidget.close() destroys the HWND. A later show creates a new one
            # without rerunning qframelesswindow's constructor-only frame setup.
            hwnd = int(self.internalWinId())
            if hwnd and getattr(self, '_isResizeEnabled', True) and not self.isFullScreen():
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                frame_style = win32con.WS_CAPTION | win32con.WS_THICKFRAME
                if style & frame_style != frame_style:
                    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style | frame_style)
                    win32gui.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER |
                        win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED)
        return result

    def nativeEvent(self, event_type, message):
        msg = self._native_message
        ctypes.memmove(ctypes.byref(msg), int(message), ctypes.sizeof(msg))
        # Qt owns the resolved child cursor. DefWindowProc would replace it
        # with the native class cursor after Qt's Enter/Leave processing.
        if msg.message == win32con.WM_SETCURSOR and (msg.lParam & 0xffff) == win32con.HTCLIENT:
            return True, 1
        event_code, hwnd = msg.message, msg.hWnd
        if event_code == win32con.WM_STYLECHANGING and ctypes.c_ssize_t(msg.wParam).value == win32con.GWL_STYLE:
            # Qt can rebuild GWL_STYLE without recreating the HWND. Preserve the
            # host contract at that boundary, before Windows commits the style.
            class StyleStruct(ctypes.Structure):
                _fields_ = [('old', wintypes.DWORD), ('new', wintypes.DWORD)]
            style = StyleStruct.from_address(msg.lParam)
            if getattr(self, '_isResizeEnabled', True) and not self.isFullScreen():
                style.new |= win32con.WS_CAPTION | win32con.WS_THICKFRAME
        if (event_code == win32con.WM_NCHITTEST and self._isResizeEnabled
                and not self.isMaximized() and not self.isFullScreen()):
            from fluent_ui.components.native_resize import resize_hit
            return True, resize_hit(self, hwnd, msg.lParam)
        result = super().nativeEvent(event_type, message)
        if (event_code == win32con.WM_NCCALCSIZE and msg.wParam
                and not self.isMaximized() and not self.isFullScreen()
                and result[0] and result[1] == win32con.WVR_REDRAW):
            # The backend's WVR_REDRAW asks Windows to repaint the entire
            # client on every edge-resize step. Keep its native frame
            # calculation, while letting Qt repaint only exposed regions.
            result = (True, 0)
        logger = self._native_state_log
        if logger is not None and event_code in (0x84, 0x83, 0x7c, 0x7d, 0x231, 0x232, 0x18):
            logger.record(self, hex(event_code), hwnd, list(result) if event_code in (0x83, 0x84) else None)
        return result


class NekoriOwnedWindow(NekoriWindow):
    """Shared owner / presentation behaviour for every Nekori-owned window.

    Ownership, modality, placement, caption state and the show/close lifecycle
    live here so Settings, Tools and future Nekori windows cannot drift into
    separate implementations. Subclasses only declare their content.
    """

    preferred_size = (960, 720)
    minimum_size = (700, 520)
    window_title = ''

    def __init__(self, owner, *, modal=False):
        # FramelessWindow creates its HWND during construction. Creating it as
        # a native child and promoting it afterwards leaves an incorrect owner
        # relationship on Windows. Start as an independent window instead.
        super().__init__(None)
        self.owner = owner
        self.setWindowModality(Qt.WindowModal if modal else Qt.NonModal)
        # Native ownership keeps this window above a topmost owner; a Python
        # owner attribute alone does not establish Windows Z order.
        self.windowHandle().setTransientParent(owner.windowHandle())
        self.setWindowIcon(owner.windowIcon())
        self.setTitleBar(NekoriTitleBar(self))
        if self.window_title:
            bind_text(self, t(self.window_title), 'setWindowTitle')
            bind_text(self.titleBar.titleLabel, t(self.window_title))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6,40,6,6)
        layout.setSpacing(0)
        self.body_layout = layout
        self.setMinimumSize(*self.minimum_size)
        self.resize(*self.preferred_size)
        add_shell_accent(self)
        visual.theme.changed.connect(self.refresh_theme)

    def prepare_show(self):
        """Hook for subclasses: bring the wanted page forward before showing."""

    def present(self):
        if self.isVisible():
            self.raise_()
            self.activateWindow()
            return
        self.prepare_show()
        # Size against the owner every time it is reopened, so a resized owner
        # still leaves its own caption bar reachable.
        fit_inside_owner(self, self.owner, self.preferred_size, self.minimum_size)
        center_on_owner(self, self.owner)
        self.showNormal()
        center_on_owner(self, self.owner)
        self.owner.apply_window_flags()
        # The owner is covered while this window has focus; clear the caption
        # states it can no longer receive Leave for.
        self.owner.clear_transient_button_states()
        self.raise_()
        self.activateWindow()

    def refresh_theme(self):
        apply_shell_theme(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'accent_line'):
            self.accent_line.reposition()

    def closeEvent(self, event):
        self.owner.clear_transient_button_states()
        event.accept()


class SettingsWindow(NekoriOwnedWindow):
    """Independent, non-modal, single-instance Settings window."""

    window_title = 'NekoriEmojy · 设置'

    def __init__(self, config, storage, owner):
        self.config = config
        self.storage = storage
        super().__init__(owner)
        bind_text(self, t('NekoriEmojy · 设置'), 'setWindowTitle')
        from fluent_ui.views.setting_view import SettingInterface
        center = SettingInterface(config, self, storage=storage)
        self.center = center
        self.pages = QStackedWidget(self)
        self.pages.addWidget(center)
        self.pages.currentChanged.connect(lambda _: self.update())
        center.back_requested.connect(self.close)
        self.body_layout.addWidget(self.pages)
        self.refresh_theme()

    def prepare_show(self):
        self.pages.setCurrentWidget(self.center)

    def show_page(self, page):
        self.present()
        self.pages.setCurrentWidget(page)

    def refresh_theme(self):
        apply_shell_theme(self)
        self.center.refresh_theme()

    def closeEvent(self, event):
        if not self.center.confirm_close():
            event.ignore()
            return
        super().closeEvent(event)


class ToolWindow(NekoriOwnedWindow):
    """A reused, independent shell for the existing QQ/TG/Similarity views."""

    def __init__(self, owner, view, title):
        super().__init__(owner)
        self.view = view
        self.config = owner.config
        self.storage = owner.storage
        self.gallery_interface = owner.gallery_interface
        bind_text(self, title, 'setWindowTitle')
        bind_text(self.titleBar.titleLabel, title)
        view.setWindowFlags(Qt.Widget)
        view.setParent(self)
        self.body_layout.addWidget(view)
        self.refresh_theme()

    def prepare_show(self):
        self.view.show()

    def refresh_library(self):
        self.gallery_interface.sidebar.refresh_list(self.gallery_interface.current_node)
        self.gallery_interface.refresh_content()

    def refresh_theme(self):
        from fluent_ui.components.dialogs import _button_style
        from PySide6.QtWidgets import QPushButton
        apply_shell_theme(self)
        self.view.setStyleSheet(visual.settings_style() + _button_style())
        for button in self.view.findChildren(QPushButton):
            button.setStyleSheet(_button_style())

    def closeEvent(self, event):
        shutdown = getattr(self.view, 'shutdown', None) or getattr(self.view, 'cancel', None)
        if shutdown:
            shutdown()
        self.refresh_library()
        super().closeEvent(event)
