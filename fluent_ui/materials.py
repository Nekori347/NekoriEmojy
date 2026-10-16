"""Native desktop Acrylic. Mica is not used as a substitute for glass."""
import ctypes
from ctypes import wintypes
import os
import sys
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from fluent_ui import visual


def _transparency_allowed():
    if os.environ.get('NEKORI_OPAQUE_MATERIAL') == '1': return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            if not winreg.QueryValueEx(key, 'EnableTransparency')[0]: return False
    except OSError: pass
    class HighContrast(ctypes.Structure):
        _fields_ = [('size', wintypes.UINT), ('flags', wintypes.DWORD), ('scheme', ctypes.c_void_p)]
    value = HighContrast(ctypes.sizeof(HighContrast), 0, None)
    ctypes.windll.user32.SystemParametersInfoW(0x42, value.size, ctypes.byref(value), 0)
    return not value.flags & 1 and not ctypes.windll.user32.GetSystemMetrics(0x1000)


def native_material(window, *, overlay=False):
    if sys.platform != 'win32' or QApplication.platformName() in ('offscreen', 'minimal'):
        window.setProperty('nativeMaterial', 'opaque'); return 'opaque'
    hwnd = wintypes.HWND(int(window.winId()))
    dark = visual.colors()['content_base'] == visual.INK
    enabled = sys.getwindowsversion().build >= 17763 and _transparency_allowed()
    key = (int(window.winId()), dark, enabled, overlay)
    if getattr(window, '_material_key', None) == key: return window.property('nativeMaterial')
    dwm = ctypes.windll.dwmapi
    dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    def attribute(name, value):
        data = ctypes.c_int(value)
        return dwm.DwmSetWindowAttribute(hwnd, name, ctypes.byref(data), ctypes.sizeof(data))
    attribute(20, int(dark)); attribute(33, 2); attribute(3, 0)
    attribute(38, 1)  # Remove the old Mica brush before desktop Acrylic.
    class Accent(ctypes.Structure):
        _fields_ = [('state', ctypes.c_int), ('flags', ctypes.c_int), ('color', wintypes.DWORD), ('animation', ctypes.c_int)]
    class Data(ctypes.Structure):
        _fields_ = [('attribute', ctypes.c_int), ('data', ctypes.c_void_p), ('size', ctypes.c_size_t)]
    color = QColor('#171b18' if dark else '#eef0e8')
    alpha = (205 if overlay else 112) if dark else (212 if overlay else 125)
    tint = (alpha << 24) | (color.blue() << 16) | (color.green() << 8) | color.red()
    accent = Accent(4 if enabled else 0, 0, tint, 0)
    data = Data(19, ctypes.addressof(accent), ctypes.sizeof(accent))
    setter = ctypes.windll.user32.SetWindowCompositionAttribute
    setter.argtypes = [wintypes.HWND, ctypes.POINTER(Data)]; setter.restype = wintypes.BOOL
    accepted = bool(setter(hwnd, ctypes.byref(data)))
    kind = 'acrylic' if enabled and accepted else 'opaque'
    window.setProperty('nativeMaterial', kind)
    window.setProperty('nativeMaterialAccepted', accepted)
    window._material_key = key
    window.update()
    return kind


def shell_color(window):
    color = QColor(visual.colors()['window_base'])
    if window.property('nativeMaterial') == 'acrylic': color.setAlpha(12)
    return color


def shell_fill(window):
    native_material(window)
    c = shell_color(window)
    return f'rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})'


def sync_native_clip(window):
    """One 14px contour clips both the native material and the Qt contents."""
    if sys.platform != 'win32' or QApplication.platformName() in ('offscreen', 'minimal'): return
    key=(int(window.winId()),window.width(),window.height(),window.devicePixelRatioF(),window.isMaximized())
    if getattr(window,'_native_clip_key',None)==key:return
    user = ctypes.windll.user32; gdi = ctypes.windll.gdi32
    user.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
    gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6; gdi.CreateRoundRectRgn.restype = wintypes.HRGN
    scale = window.devicePixelRatioF(); r = round(visual.WINDOW_RADIUS * 2 * scale)
    if window.isMaximized(): r = 0
    region = gdi.CreateRoundRectRgn(0, 0, round(window.width()*scale)+1, round(window.height()*scale)+1, r, r)
    if not user.SetWindowRgn(wintypes.HWND(int(window.winId())), region, True):gdi.DeleteObject(region)
    else:window._native_clip_key=key
