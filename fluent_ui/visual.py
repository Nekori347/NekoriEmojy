"""Small shared visual foundation, consumed by the existing desktop UI.

Nekori Softframe: soft shell, paper/ink content, restrained industrial structure. Neutral surfaces dominate, #FFF500 is a signal accent only,
rounded shells and quiet surface hierarchy frame thin editorial rules.

Components read semantic tokens instead of colour literals, and ask for a
surface by role rather than describing its material. The tokens below are the
only place a theme is allowed to decide what a colour or a surface is, so a
later theme pass (gradient, texture, acrylic) does not have to touch pages.

Legacy key names (`background`, `elevated`, `hover`, `text`, ...) are still
returned so existing call sites keep working while they migrate.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QEasingCurve
from PySide6.QtGui import QColor, QFont, QFontDatabase
from qfluentwidgets import isDarkTheme, setThemeColor

DEFAULT_ACCENT = '#FFF500'

# -- geometry ---------------------------------------------------------------
CONTROL_RADIUS = 8
PANEL_RADIUS = 12
WINDOW_RADIUS = 14
RADIUS = CONTROL_RADIUS          # legacy alias
SHELL_RADIUS = WINDOW_RADIUS     # legacy alias
SPACING_S = 6
SPACING_M = 10
SPACING_L = 16
LINE_WIDTH = 1
TOOLBAR_HEIGHT = 50
ICON_SIZE = 20
@dataclass(frozen=True)
class CompactControlMetrics:
    padding: int = 2
    spacing: int = 4
    icon: int = 14
    action_extent: int = 24
    top_inset: int = 2
    index_extent: int = 20
    index_step: int = 22
    hierarchy_row: int = 18
    splitter_extent: int = 8
    ear_length: int = 24
    ear_hit_length: int = 40
    chevron_size: int = 7
    chevron_stroke: float = 1.5
    rail_visual_extent: int = 24


COMPACT_CONTROLS = CompactControlMetrics()
APP_CONTENT_TOP_INSET = COMPACT_CONTROLS.top_inset
SECTION_INDEX_COMPACT_EXTENT = COMPACT_CONTROLS.index_extent
HIERARCHY_ROW_HEIGHT = COMPACT_CONTROLS.hierarchy_row
HIERARCHY_TITLE_HEIGHT = 32
HIERARCHY_ANCESTOR_STEP = 18
HIERARCHY_CURRENT_TOP = 20
HIERARCHY_HEADER_HEIGHT = 72
@dataclass(frozen=True)
class Motion:
    hover: int = 110
    select: int = 180
    expand: int = 220
    window: int = 160
    feedback: int = 180
    easing = QEasingCurve.OutCubic


MOTION = Motion()
HIERARCHY_DURATION_MS = MOTION.select
HIERARCHY_SCRUB_STEP = 22
TAB_DIVIDER_WIDTH = 2
TAB_LOCATION_GAP = 12
@dataclass(frozen=True)
class TagCollapsedMetrics:
    icon_size: int = COMPACT_CONTROLS.icon
    visual_extent: int = 16
    compact_padding: int = COMPACT_CONTROLS.padding
    edge_padding: int = 4
    separator_extent: int = LINE_WIDTH

    @property
    def extent(self):
        # Transparent hit padding never determines the thickness of the rail.
        return max(self.icon_size, self.visual_extent) + 2*self.compact_padding


TAG_COLLAPSED_METRICS = TagCollapsedMetrics()
TAG_PANEL_COLLAPSED_EXTENT = TAG_COLLAPSED_METRICS.extent  # compatibility alias

# -- typography -------------------------------------------------------------
BODY_FONT = 'Sarasa UI SC'
TITLE_FONT = 'Sarasa UI SC'
BRAND_FONT = 'Rajdhani'
DATA_FONT = 'JetBrains Mono'
TYPOGRAPHY = {
    'page_title': {'family': TITLE_FONT, 'size': 26, 'weight': 600},
    'section_title': {'family': TITLE_FONT, 'size': 13, 'weight': 600},
    'brand': {'family': BRAND_FONT, 'size': 20, 'weight': 600},
    'body': {'family': BODY_FONT, 'size': 13, 'weight': 400},
    'secondary': {'family': BODY_FONT, 'size': 12, 'weight': 400, 'color': 'text_secondary'},
    'data': {'family': DATA_FONT, 'size': 13, 'weight': 400, 'color': 'text_muted'},
    'data_small': {'family': DATA_FONT, 'size': 10, 'weight': 400, 'color': 'text_muted'},
    'tooltip': {'family': BODY_FONT, 'size': 12, 'weight': 400},
}

_fonts_loaded = False


def load_fonts():
    global _fonts_loaded
    from PySide6.QtWidgets import QApplication
    if _fonts_loaded or QApplication.instance() is None:
        return
    for path in sorted((Path(__file__).parent / 'assets' / 'fonts').glob('*.ttf')):
        QFontDatabase.addApplicationFont(str(path))
    _fonts_loaded = True


def font(role='body'):
    load_fonts()
    spec = TYPOGRAPHY[role]
    result = QFont()
    result.setFamilies([spec['family'], BODY_FONT, 'Microsoft YaHei UI', 'Yu Gothic UI', 'sans-serif'])
    result.setPixelSize(spec['size'])
    result.setWeight(QFont.Weight(spec['weight']))
    # Subpixel glyph masks assume an opaque RGB backdrop. Glass needs alpha
    # antialiasing, otherwise ClearType leaves pale rectangles around strokes.
    result.setStyleStrategy(QFont.PreferAntialias | QFont.NoSubpixelAntialias)
    if role == 'data':
        result.setStyleHint(QFont.Monospace)
    return result


def apply_typography(root):
    """Scope fonts to actual text roles; explicit brand/data roles stay distinct."""
    from PySide6.QtWidgets import QWidget, QLabel, QAbstractButton, QLineEdit, QAbstractItemView, QTextEdit, QPlainTextEdit, QTabBar
    load_fonts()
    from fluent_ui.presentation.scrollbar import install_scrollbars
    install_scrollbars(root)
    for widget in [root, *root.findChildren(QWidget)]:
        if widget is not root and not isinstance(widget, (QLabel, QAbstractButton, QLineEdit, QAbstractItemView, QTextEdit, QPlainTextEdit, QTabBar)):
            continue
        role = widget.property('typography') or widget.property('role')
        role = {'title': 'page_title', 'section': 'section_title', 'hint': 'secondary', 'hierarchy-count': 'data'}.get(role, role)
        if role not in TYPOGRAPHY:
            role = {'TitleLabel':'page_title','SubtitleLabel':'section_title','CaptionLabel':'secondary'}.get(type(widget).__name__,role)
        if role in ('brand', 'data', 'hierarchy-count') and hasattr(widget, 'text') and any(ord(ch)>127 for ch in widget.text()):
            role = 'body'
        target = font(role if role in TYPOGRAPHY else 'body')
        if role not in TYPOGRAPHY and widget.font().bold():
            target.setWeight(QFont.DemiBold)
        widget.setFont(target)

# -- semantic status --------------------------------------------------------
STATUS_COLORS = {'missing': '#898D89', 'danger': '#C7433A', 'success': '#2F9E44',
                 'warning': '#D9822B'}
STATUS = {'missing': STATUS_COLORS['missing'], 'error': STATUS_COLORS['danger'],
          'success': STATUS_COLORS['success'], 'warning': STATUS_COLORS['warning']}

# Regions that may later take their own material. Pages ask by role; nothing
# outside this module decides whether a surface is solid, textured or frosted.
SURFACE_ROLES = ('window', 'sidebar', 'content', 'raised_panel', 'popover', 'dialog')


class UiTheme(QObject):
    changed = Signal()
    accent_changed = Signal()

    def __init__(self):
        super().__init__()
        self.config = None
        self._material_batch=None

    @contextmanager
    def transition(self):
        """Commit a theme once: prepare Qt styles, then native tint, then paint."""
        if self._material_batch is not None:
            yield;return
        from PySide6.QtWidgets import QApplication
        windows=[w for w in QApplication.topLevelWidgets() if w.updatesEnabled()]
        self._material_batch={}
        for window in windows:window.setUpdatesEnabled(False)
        try:
            yield
            # setUpdatesEnabled only queues a new backing store. Flush that
            # store synchronously before changing DWM's immediately visible tint.
            for window in windows:window.setUpdatesEnabled(True)
            for window in windows:
                if window.isVisible():window.repaint()
            for window in windows:window.setUpdatesEnabled(False)
            from fluent_ui.materials import native_material
            for window in windows:
                key=getattr(window,'_material_key',None)
                if key:self._material_batch.setdefault(window,key[-1])
            for window,overlay in self._material_batch.items():native_material(window,overlay=overlay)
        finally:
            self._material_batch=None
            for window in windows:window.setUpdatesEnabled(True);window.update()

    def material(self,window,*,overlay=False):
        if self._material_batch is not None:self._material_batch[window]=overlay
        else:
            from fluent_ui.materials import native_material
            native_material(window,overlay=overlay)

    def configure(self, config):
        self.config = config
        load_fonts()

    def refresh(self):
        with self.transition():
            current=accent()
            if current != getattr(self,'_applied_accent',None):
                setThemeColor(QColor(current),lazy=True)
                self._applied_accent=current
            self.changed.emit()

    def preview_accent(self):
        # Preview only repaints token consumers; final apply refreshes QSS.
        self.accent_changed.emit()


theme = UiTheme()


def accent():
    value = theme.config.get('accent_color', DEFAULT_ACCENT) if theme.config else DEFAULT_ACCENT
    color = QColor(value)
    return color.name() if color.isValid() else DEFAULT_ACCENT


INK = '#101110'


def colors(dark=None):
    dark = isDarkTheme() if dark is None else dark
    a = QColor(accent())
    base = QColor('#101110' if dark else '#e8e8e2')
    selected = QColor(*[round(base.getRgb()[i]*.90+a.getRgb()[i]*.10) for i in range(3)])
    palette = dict(
        window_base='#222520' if dark else '#dfe2d8',
        content_base=base.name(),
        surface='#181a18' if dark else '#f2f2ec',
        surface_raised='#262a24' if dark else '#fafaf5',
        surface_alt='#1e201d' if dark else '#dcddd6',
        surface_overlay='#292d27' if dark else '#f7f8f0',
        surface_hover='#2d322a' if dark else '#dfe3d7',
        navigation='#20241e' if dark else '#e0e4d9',
        border_soft='#30352e' if dark else '#ced2c7',
        scrim='#80000000',
        surface_selected=selected.name(),
        control='#30342f' if dark else '#d7dacf',
        track='#747b70' if dark else '#737c6d',
        thumb='#f5f5ef' if dark else '#ffffff',
        highlight='#4a4d49' if dark else '#ffffff',
        text_primary='#eeeee8' if dark else '#222720',
        text_secondary='#bec3b8' if dark else '#4b5547',
        text_muted='#a8afa3' if dark else '#586451',
        border='#4a4d49' if dark else '#b6b8b3',
        accent=accent(),
        accent_text=INK if a.lightnessF()>.48 else '#ffffff',
        danger=STATUS_COLORS['danger'], warning=STATUS_COLORS['warning'],
        success=STATUS_COLORS['success'], missing=STATUS_COLORS['missing'])
    # Legacy names, kept so existing call sites read the same palette.
    palette.update(background=palette['window_base'], elevated=palette['surface_raised'],
                   overlay=palette['surface_overlay'], hover=palette['surface_hover'],
                   selected=palette['surface_selected'], text=palette['text_primary'],
                   muted=palette['text_muted'], signal=palette['accent'])
    return palette


def typography(role):
    """QSS fragment for a typography role, e.g. typography('page_title')."""
    spec = TYPOGRAPHY[role]
    parts = [f"font-family: {spec['family']}", f"font-size: {spec['size']}px",
             f"font-weight: {spec['weight']}"]
    if spec.get('letter_spacing'):
        parts.append(f"letter-spacing: {spec['letter_spacing']}px")
    if spec.get('color'):
        parts.append(f"color: {colors()[spec['color']]}")
    return '; '.join(parts)


def surface_style(role, dark=None):
    """Background declaration for a named surface role.

    Stable opaque fallback materials: shell / paper-ink content / raised overlay.
    Native Mica/Acrylic is not enabled or implied by these colour layers.
    """
    c = colors(dark)
    fill = {'window': c['window_base'], 'sidebar': c['navigation'], 'content': c['content_base'],
            'raised_panel': c['surface'], 'popover': c['surface_overlay'],
            'dialog': c['surface_raised']}.get(role, c['surface'])
    return f'background: {fill};'


def window_style(dark=None, background=None):
    # Colors inherit the live palette. Replacing a window-wide color sheet
    # repolishes every pooled gallery renderer and delays the selection motion.
    return f'''
        MainWindow, SettingsWindow, ToolWindow {{ background: {background or 'palette(window)'}; border: none; }}
        QLabel {{ color: palette(window-text); background: transparent; }}
        QWidget#WindowAccent {{ background: transparent; }}
        QWidget#GalleryInterface {{ background: transparent; }}
        QWidget#GalleryContent {{ background: transparent; border: none; }}
        QWidget#GalleryTopBar {{ background: transparent; }}
        QWidget#InlineContentRow {{ border-left: {LINE_WIDTH}px solid palette(mid); background: palette(base); }}
        QLabel#GalleryHeading {{ {typography('page_title')} }}
        QToolTip {{ color: palette(text); background: palette(base); border: {LINE_WIDTH}px solid palette(mid); padding: {SPACING_S}px 9px; border-radius: 6px; {typography('tooltip')} }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 1px; }}
        QScrollBar::handle:vertical {{ background: palette(mid); min-height: 24px; border-radius: 3px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QLabel[role="title"] {{ font-family: {TITLE_FONT}; font-weight: 600; }}
        QLabel[role="data"] {{ color: palette(placeholder-text); }}
        QLabel[role="brand"] {{ color: palette(window-text); }}
        QLabel[role="section"] {{ {typography('section_title')};
            color: palette(window-text); padding: 4px 0; }}
        QLabel[role="chip"] {{ font-family: {BODY_FONT}; color: palette(window-text);
            border: {LINE_WIDTH}px solid palette(mid); border-radius: {CONTROL_RADIUS}px; padding: 2px 8px; }}
        QLabel[role="chip"][state="active"] {{ border-color: palette(highlight); }}
        QLabel[role="crumb"] {{ color: palette(placeholder-text); }}
        QLabel[role="crumb"][state="current"] {{ color: palette(window-text); font-weight: 600; }}
        QFrame[role="rule"] {{ background: palette(mid); border: none; }}
        QFrame[role="surface"] {{ background: palette(base); border: {LINE_WIDTH}px solid palette(mid); border-radius: {CONTROL_RADIUS}px; }}
        QScrollArea[role="bare"] {{ border: none; background: transparent; }}
        QLabel[state="missing"], QLabel[state="error"] {{ color: palette(bright-text); }}
    '''


def sidebar_style(dark=None):
    c = colors(dark)
    return f'''
        CategorySidebar {{ background: transparent; border: none; }}
        CategorySidebar QLabel[role="section"] {{ {typography('data')};
            font-size: 10px; padding: 10px 10px 4px 10px; }}
        QTreeWidget {{ background: transparent; border: none; outline: none; color: {c['text_primary']}; }}
        QTreeWidget::item {{ background: transparent; padding: 0; margin: 0; }}
        QTreeWidget::item:hover {{ background: transparent; }}
        QTreeWidget::item:selected {{ background: transparent; color: {c['text_primary']}; border: none; }}
        QTreeWidget::branch {{ background: transparent; }}
        QHeaderView::section {{ background: transparent; border: none; }}
    '''


def resource_style(selected=False):
    c = colors()
    return f'''
        QLabel#EmojiCard {{ border-radius: {CONTROL_RADIUS}px; background: {c['surface']};
            border: 1px solid {c['accent'] if selected else c['border_soft']}; }}
        QLabel#EmojiCard:hover {{ background: {c['surface_hover']}; border: 1px solid {c['accent'] if selected else c['border']}; }}
        QLabel#EmojiCard[state="missing"] {{ color: {c['missing']}; font-family: {DATA_FONT}; }}
    '''


def command_bar_style(dark=None):
    c = colors(dark)
    return f'''
        QWidget#CommandBar {{ background: {c['surface_alt']};
            border-top: {LINE_WIDTH}px solid {c['border']}; }}
        QWidget#CommandBar QLabel {{ color: {c['text_primary']}; }}
        QLabel#CommandCount {{ font-family: '{BODY_FONT}'; color: {c['text_muted']}; }}
    '''


def strip_style(dark=None):
    c = colors(dark)
    return f'''
        QWidget#ContextStrip {{ background: transparent;
            border-bottom: {LINE_WIDTH}px solid {c['border']}; }}
        QWidget#ContextStrip QLabel {{ color: {c['text_muted']}; }}
        QWidget#ContextStrip QLabel[role="crumb"]:hover {{ color: {c['text_primary']}; }}
    '''


def dialog_style(dark=None):
    c = colors(dark)
    return f'''{control_style(c)}
        QDialog {{ {surface_style('dialog', dark)} border: {LINE_WIDTH}px solid {c['border']}; border-radius: {WINDOW_RADIUS}px; }}
        QWidget#DialogHeader {{ background: transparent; }}
        QComboBox {{ background: {c['surface']}; color: {c['text_primary']}; border: {LINE_WIDTH}px solid {c['border']}; border-radius: {CONTROL_RADIUS}px; padding: 6px 10px; }}
        QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text_primary']}; selection-background-color: {c['surface_hover']}; }}
        QLabel {{ background: transparent; color: {c['text_primary']}; }}
        QLabel[role="hint"] {{ color: {c['text_muted']}; }}
        QLabel[role="data"] {{ color: {c['text_muted']}; }}
        QLineEdit, QPlainTextEdit, QTextEdit {{
            background: {c['surface']}; border: {LINE_WIDTH}px solid {c['border']};
            border-radius: {CONTROL_RADIUS}px; padding: 6px 8px; color: {c['text_primary']}; }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {c['accent']}; }}
        QListWidget {{ background: {c['surface']}; border: {LINE_WIDTH}px solid {c['border']};
            border-radius: {CONTROL_RADIUS}px; color: {c['text_primary']}; outline: none; }}
        QListWidget::item {{ padding: 6px 8px; }}
        QListWidget::item:selected {{ background: {c['surface_hover']}; border-left: 3px solid {c['accent']}; }}
        QFrame[role="rule"] {{ background: {c['border']}; border: none; }}
    '''


def settings_style(dark=None):
    c = colors(dark)
    return f'''{control_style(c)}
        QWidget#SettingsCenter {{ background: transparent; }}
        QWidget#SettingsBody, QWidget#SettingsViewport {{ background: transparent; }}
        QWidget#SettingsGroup {{ background: transparent; border: none; }}
        QWidget#SettingsSectionBody {{ background: transparent; border: none; }}
        QLabel {{ color: {c['text_primary']}; background: transparent; }}
        QLabel[role=hint] {{ color: {c['text_muted']}; font-weight: normal; }}
        QListWidget#SettingsNav {{ background: transparent; border: none;
            outline: none; }}
        QListWidget#SettingsNav::item, QListWidget#SettingsNav::item:selected, QListWidget#SettingsNav::item:hover {{ background: transparent; border: none; padding: 0; margin: 0; }}
        QLabel#SettingsPageTitle {{ {typography('page_title')} }}
        QWidget#SettingsTabBar {{ background: transparent;
            border-bottom: {LINE_WIDTH}px solid {c['border']}; }}
        QWidget#SettingsSectionHead {{ background: transparent; border: none; }}
        QLabel#SettingsSectionTitle {{ {typography('section_title')};
            color: {c['text_primary']}; }}
        QWidget#SettingsFooter {{ background: transparent;
            border-top: {LINE_WIDTH}px solid {c['border']}; }}
        QLabel#SettingsDirty {{ color: {c['warning']}; }}
    '''


def menu_style():
    c = colors()
    return (f"QListWidget {{ background: {c['surface_overlay']}; color: {c['text_primary']}; "
            f"border: {LINE_WIDTH}px solid {c['border']}; border-radius: {PANEL_RADIUS}px; }} "
            f"QListWidget::item {{ border-radius: {CONTROL_RADIUS}px; padding: 6px; }} "
            f"QListWidget::item:hover, QListWidget::item:selected {{ background: {c['surface_hover']}; }}")


def control_style(c=None):
    c = c or colors()
    return f"""
        QPushButton {{ background: {c['control']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 5px 10px; }}
        QPushButton:hover {{ background: {c['hover']}; }}
        QPushButton:pressed {{ background: {c['selected']}; }}
        QPushButton:focus {{ border-color: {c['accent']}; }}
        QPushButton:disabled {{ color: {c['muted']}; background: transparent; border-color: {c['border']}; }}
        QPushButton[role='primary'] {{ background: {c['accent']}; color: {c['accent_text']}; border-color: {c['accent']}; font-weight: 600; }}
        QPushButton[role='primary']:disabled {{ background: transparent; color: {c['muted']}; border-color: {c['border']}; }}
        QPushButton[role='danger'] {{ color: {c['danger']}; }}
        QToolButton {{ color: {c['text']}; background: transparent; border: none; border-radius: 6px; }}
        QToolButton:hover {{ background: {c['hover']}; }}
        QToolButton:checked {{ background: {c['selected']}; }}
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{ color: {c['text']}; background: {c['control']}; border: 1px solid {c['border_soft']}; border-radius: 8px; padding: 5px 8px; selection-background-color: {c['selected']}; }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
        QListWidget {{ background: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border_soft']}; border-radius: 8px; outline: none; }}
        QListWidget::item {{ padding: 5px; border: none; }}
        QListWidget::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
        QComboBox QAbstractItemView {{ background: {c['surface_overlay']}; color: {c['text']}; border: 1px solid {c['border']}; selection-background-color: {c['selected']}; }}
        QScrollArea {{ background: transparent; border: none; }}
    """
