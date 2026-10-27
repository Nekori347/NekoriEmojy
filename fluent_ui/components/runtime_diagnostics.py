"""Passive application evidence, using the existing T-07 storage and export."""
import ctypes
from ctypes import wintypes
from importlib.metadata import version, PackageNotFoundError
import platform
import time
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, QTimer, QAbstractNativeEventFilter, Qt
from PySide6.QtWidgets import QApplication, QWidget
import PySide6
from services import crash_evidence as evidence


class DiagnosticApplication(QApplication):
    def notify(self, receiver, event):
        observer = getattr(self, 'runtime_diagnostics', None)
        session = observer.session if observer else None
        if session is not None and receiver is observer.session_window and event.type() in (
                QEvent.Move, QEvent.Resize, QEvent.Paint):
            start = time.perf_counter()
            try:return super().notify(receiver, event)
            finally:
                elapsed = (time.perf_counter()-start)*1000
                session['qt_dispatches'] += 1
                if event.type()==QEvent.Move:session['qt_moves']+=1
                if event.type()==QEvent.Resize:session['qt_resizes']+=1
                session['max_dispatch_ms'] = max(session['max_dispatch_ms'], elapsed)
        return super().notify(receiver, event)


def environment():
    try:frameless = version('PySideSix-Frameless-Window')
    except PackageNotFoundError:frameless = 'unknown'
    build='packaged' if getattr(__import__('sys'),'frozen',False) else 'source'
    # Source checkout identity, without spawning Git or inspecting user data.
    root=Path(__file__).resolve().parents[2]
    try:
        git=root/'.git';head=(git/'HEAD').read_text(encoding='ascii').strip()
        commit=(git/head[5:]).read_text(encoding='ascii').strip() if head.startswith('ref: refs/heads/') else head
        if len(commit)==40 and all(c in '0123456789abcdef' for c in commit):build=commit[:12]
    except (OSError,UnicodeError):pass
    return dict(version=evidence._version(),build=build,python=platform.python_version(),
                windows_release=platform.release(),windows_build=platform.version(),
                pyside6=PySide6.__version__,qframelesswindow=frameless,
                timing_scope='top-level Qt notify dispatch only; not Win32/DWM/pointer lag')


class RuntimeDiagnostics(QObject, QAbstractNativeEventFilter):
    def __init__(self, app, window):
        QObject.__init__(self, app)
        QAbstractNativeEventFilter.__init__(self)
        self.app, self.main = app, window
        self.windows = {}
        self.session = self.session_window = None
        self.normal_saved = 0
        self.last_abnormal = None
        self.drag_totals = dict(sessions=0,unclassified_loops=0,max_dispatch_ms=0.0)
        self.environments = {}
        self.pending_environment = set()
        evidence.set_environment(environment())
        evidence.breadcrumb('startup')
        evidence.persist_context('startup')
        app.installEventFilter(self)
        app.installNativeEventFilter(self)
        app.aboutToQuit.connect(self.shutdown)
        self.maintenance_timer = QTimer(self)
        self.maintenance_timer.setTimerType(Qt.PreciseTimer)
        self.maintenance_timer.setInterval(86400000)
        self.maintenance_timer.timeout.connect(evidence.maintenance)
        self.maintenance_timer.start()
        self.note_environment(window)

    def role(self, window):
        if window is self.main:return 'main'
        name=type(window).__name__.lower()
        if 'setting' in name:return 'settings'
        if 'quick' in name:return 'quick'
        if 'qq' in name:return 'qq_tool'
        return 'tool'

    def note_environment(self, window):
        hwnd=int(window.internalWinId())
        for old,owner in tuple(self.windows.items()):
            if owner is window:self.windows.pop(old)
        if hwnd:self.windows[hwnd]=window
        role=self.role(window)
        value=dict(material=window.property('nativeMaterial') or 'qt',
                   dpi=round(window.logicalDpiX(),2),scale=round(window.devicePixelRatioF(),3),
                   state=window.windowState().value,window_type=window.windowType().value)
        if self.environments.get(role)!=value:
            self.environments[role]=value
            evidence.set_environment(dict(windows=dict(self.environments)))
            evidence.breadcrumb('window_environment',role=role)
            evidence.persist_context('environment')

    def eventFilter(self, watched, event):
        kind=event.type()
        if kind not in (QEvent.Show,QEvent.Hide,QEvent.WindowStateChange,QEvent.WinIdChange,
                        QEvent.ScreenChangeInternal,QEvent.DevicePixelRatioChange,
                        QEvent.DynamicPropertyChange,QEvent.ThemeChange,QEvent.Close):return False
        if not isinstance(watched,QWidget) or not watched.isWindow():return False
        # Exclude hover previews, tooltips and menus; these are not tools whose
        # lifecycle helps diagnose the host. Never capture their text.
        if watched is not self.main and self.role(watched)=='tool':return False
        if kind==QEvent.DynamicPropertyChange and bytes(event.propertyName())!=b'nativeMaterial':return False
        if kind==QEvent.Close:
            for hwnd,owner in tuple(self.windows.items()):
                if owner is watched:self.windows.pop(hwnd)
            return False
        if kind in (QEvent.Show,QEvent.Hide,QEvent.WindowStateChange):
            code={QEvent.Show:'window_show',QEvent.Hide:'window_hide',QEvent.WindowStateChange:'window_state'}[kind]
            evidence.breadcrumb(code,role=self.role(watched),state=watched.windowState().value)
        if kind!=QEvent.Hide and watched not in self.pending_environment:
            self.pending_environment.add(watched)
            def sample():
                self.pending_environment.discard(watched)
                try:self.note_environment(watched)
                except RuntimeError:pass  # The tool may have been destroyed before delivery.
            QTimer.singleShot(0,self,sample)
        return False

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) not in (b'windows_generic_MSG',b'windows_dispatcher_MSG'):return False,0
        msg=wintypes.MSG.from_address(int(message))
        code=msg.message
        if code not in (0x231,0x232,0x46,0x47,0x83,0x84):return False,0
        window=self.windows.get(msg.hWnd)
        if window is None:return False,0
        self.native_message(window,code)
        return False,0

    def native_message(self, window, code):
        # No disk I/O, environment inspection, JSON, coordinates or child
        # traversal here. Top-level Qt Move/Resize events classify the loop.
        if code==0x231:
            if self.session is not None and self.session_window is window:return
            self.session_window=window
            self.session=dict(start=time.perf_counter(),native_events=0,
                              qt_dispatches=0,max_dispatch_ms=0.0,hit_tests=0,
                              nc_calculations=0,position_changes=0,qt_moves=0,qt_resizes=0)
        elif self.session is not None and window is self.session_window:
            self.session['native_events']+=1
            if code==0x84:self.session['hit_tests']+=1
            if code==0x83:self.session['nc_calculations']+=1
            if code in (0x46,0x47):self.session['position_changes']+=1
            if code==0x232:
                session=self.session
                session['duration_ms']=round((time.perf_counter()-session.pop('start'))*1000,3)
                self.session=self.session_window=None
                QTimer.singleShot(0,self,lambda:self.finish_session(session))

    def finish_session(self, session):
        # WM_MOVING is not exposed consistently by Qt's native filter. Use
        # the move/size loop plus actual top-level Qt geometry events instead.
        if not session['qt_moves'] or session['qt_resizes']:
            self.drag_totals['unclassified_loops']+=1
            evidence.set_environment(dict(drag_totals=dict(self.drag_totals)))
            return
        self.drag_totals['sessions']+=1
        self.drag_totals['max_dispatch_ms']=max(self.drag_totals['max_dispatch_ms'],session['max_dispatch_ms'])
        evidence.set_environment(dict(drag_totals=dict(self.drag_totals)))
        now=time.monotonic()
        abnormal=session['max_dispatch_ms']>=100
        if (not abnormal and self.normal_saved<3) or (abnormal and (self.last_abnormal is None or now-self.last_abnormal>=3600)):
            if not abnormal:self.normal_saved+=1
            if abnormal:self.last_abnormal=now
            evidence.breadcrumb('drag_summary',kind='move',duration_ms=session['duration_ms'],
                max_dispatch_ms=round(session['max_dispatch_ms'],3),
                **{key:session[key] for key in ('native_events','qt_dispatches','hit_tests','nc_calculations','position_changes')})
            evidence.persist_context('window_move')

    def shutdown(self):
        self.maintenance_timer.stop()
        evidence.breadcrumb('shutdown')
        evidence.persist_context('shutdown')
        self.app.removeNativeEventFilter(self)
        self.app.removeEventFilter(self)


def install_runtime_diagnostics(app, window):
    if not hasattr(app,'runtime_diagnostics'):
        app.runtime_diagnostics=RuntimeDiagnostics(app,window)
    return app.runtime_diagnostics
