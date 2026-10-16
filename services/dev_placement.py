"""Where a development instance puts its windows.

Development rule, not a product default: `NEKORI_DEV_SCREEN` only places an
independent app/test top-level window initially. Owned dialogs follow their
owner; menus and hover popups follow their trigger point or target.

The monitor is resolved from the real QScreen list (name / model /
manufacturer), never from a fixed screen index, because indices change when a
display is added, removed or reordered. A selector that matches nothing leaves
windows where they are and prints the available monitors once, so the selector
can be corrected instead of silently placing windows on the wrong screen.

Placement is runtime only: `MainWindow` skips saving window geometry while the
rule is active, so a development launch never overwrites the geometry the user
saved for normal use.
"""
import os
import re
import sys
import weakref

# Values that mean "keep the normal placement".
DISABLED = {'0', 'off', 'none', 'no', 'false', 'disable', 'disabled'}
_SPLIT = re.compile(r'[;,|]')
_resolved = {}
_reported = set()
# The rectangle each window was last placed at by the development rule. A
# window still sitting exactly there has not been positioned by the user.
_placed = weakref.WeakKeyDictionary()

# Platforms with no physical screen. Qt gives them a synthetic one -- offscreen
# reports an 800x800 screen named '' -- and a window that is "saved" there
# describes nothing the user ever chose.
HEADLESS_PLATFORMS = {'offscreen', 'minimal', 'vnc'}
# How much of the window has to sit on a real screen to count as placed there:
# enough to see it and grab it, which is what `ensure_window_visible` needs.
ON_SCREEN_MINIMUM = (120, 60)


def selector():
    """The raw development monitor selector, or '' when unset."""
    return (os.environ.get('NEKORI_DEV_SCREEN') or '').strip()


def _tokens(screen):
    values = []
    for attribute in ('name', 'model', 'manufacturer', 'description'):
        getter = getattr(screen, attribute, None)
        if not callable(getter):
            continue
        try:
            text = str(getter() or '').strip().lower()
        except Exception:
            continue
        if text:
            values.append(text)
    return values


def _match(screen, token):
    values = _tokens(screen)
    return any(value == token for value in values) or any(token in value for value in values)


def dev_screen():
    """The QScreen a development instance should use, or None."""
    wanted = selector().lower()
    if not wanted or wanted in DISABLED:
        return None
    from PySide6.QtGui import QGuiApplication
    screens = list(QGuiApplication.screens())
    key = (wanted, tuple(screen.name() for screen in screens))
    if key in _resolved:
        return _resolved[key]
    target = None
    for token in _SPLIT.split(wanted):
        token = token.strip()
        if not token:
            continue
        target = next((screen for screen in screens if _match(screen, token)), None)
        if target is not None:
            break
    if target is None and wanted not in _reported:
        _reported.add(wanted)
        available = ' / '.join(f"{screen.name()} ({screen.model() or '?'})" for screen in screens)
        print(f'[dev-placement] no screen matches NEKORI_DEV_SCREEN={selector()!r}; '
              f'available: {available}', flush=True)
    _resolved.clear()
    _resolved[key] = target
    return target


def move_to_dev_screen(widget):
    """Center a window on the development monitor. No-op when unconfigured."""
    target = dev_screen()
    if target is None or widget is None:
        return False
    area = target.availableGeometry()
    if widget.width() > area.width() or widget.height() > area.height():
        widget.resize(min(widget.width(), area.width()), min(widget.height(), area.height()))
    widget.move(area.center() - widget.rect().center())
    _placed[widget] = list(widget.geometry().getRect())
    return True


def active():
    """True while a development monitor is in effect."""
    return dev_screen() is not None


def headless():
    """True when Qt is running without physical screens."""
    from PySide6.QtGui import QGuiApplication
    return QGuiApplication.platformName() in HEADLESS_PLATFORMS


def on_real_screen(window, minimum=ON_SCREEN_MINIMUM):
    """Whether a window really sits on a screen the user can see it on."""
    from PySide6.QtGui import QGuiApplication
    rect = window.frameGeometry()
    for screen in QGuiApplication.screens():
        overlap = screen.geometry().intersected(rect)
        if overlap.width() >= minimum[0] and overlap.height() >= minimum[1]:
            return True
    return False


def geometry_writable(window=None):
    """Whether this run may write the user's saved window geometry.

    Three runs must never do it, and each is a real way the saved position was
    destroyed: a headless run (its synthetic screen has nothing to do with
    where the user wants the window), a smoke run (it exists to prove
    start-up, not to move the user's window), and the development placement --
    but only *while the window is still where that placement put it*.

    That last distinction is the whole point. The rule is "the AI's own
    placement must not become the user's position", not "nothing is saved
    during a development session". The acceptance instance is this very
    instance, so freezing every save meant the user could move the window,
    exit, and find their position never remembered: a development session is
    exactly when they are most likely to set it. A window the user has since
    moved is the user's choice and is saved like any other.
    """
    if headless():
        return False
    if any(argument == '--smoke-test' for argument in sys.argv):
        return False
    if active():
        if window is None:
            return False
        if _placed.get(window) == list(window.geometry().getRect()):
            return False
    return window is None or on_real_screen(window)
