"""Product action icons with shared outline styling and theme foregrounds."""
from enum import Enum
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QByteArray, QRectF
from PySide6.QtSvg import QSvgRenderer
from qfluentwidgets import FluentIconBase, Theme

ASSETS = Path(__file__).parent / 'assets' / 'icons'


@lru_cache(maxsize=192)
def _renderer(name, color):
    source = (ASSETS / f'{name}.svg').read_text(encoding='utf-8')
    return QSvgRenderer(QByteArray(source.replace('currentColor', color).encode()))


class Icon(FluentIconBase, Enum):
    ACCEPT = 'check'
    ADD = 'plus'
    IMPORT_MENU = 'mood-plus'
    NEW_TAG = 'tag-plus'
    NEW_CATEGORY = 'playlist-add-mirrored'
    TREE_VIEW = 'list-tree-stroke-2.25'
    MANUAL_ORDER = 'menu-order'
    RECENT_ADDED = 'clock-down'
    OLDEST_ADDED = 'clock-up'
    CATEGORY_ICON = 'sticker'
    APPLICATION_ICON = 'photo-circle'
    APPLICATION = 'apps'
    CANCEL = 'x'
    CHAT = 'message-circle'
    CHEVRON_DOWN_MED = 'chevron-down'
    CHEVRON_RIGHT = 'chevron-right'
    CHEVRON_LEFT = 'chevron-left'
    CLOSE = 'x'
    CLOUD_DOWNLOAD = 'cloud-download'
    UPDATE = 'circle-arrow-up'
    SCAN_TEXT = 'scan-text'
    SUCCESS = 'check-circle'
    WARNING = 'alert-triangle'
    ERROR = 'circle-x'
    IMPORT = 'folder-input'
    COMMAND_PROMPT = 'terminal-2'
    COPY = 'copy'
    DELETE = 'trash'
    DOCUMENT = 'file-description'
    DOWN = 'chevron-down'
    DOWNLOAD = 'download'
    FILTER = 'filter'
    FOLDER = 'folder'
    GITHUB = 'brand-github'
    HEART = 'heart'
    HISTORY = 'recent-history'
    HELP = 'help-circle'
    INFO = 'info-circle'
    EYE = 'eye'
    EYE_OFF = 'eye-off'
    IOT = 'devices'
    LEFT_ARROW = 'arrow-left'
    LINK = 'link'
    MENU = 'list-tree'
    MANAGE = 'list-check'
    MORE = 'dots'
    MOVE = 'folder-symlink'
    PASTE = 'clipboard'
    PASTE_ADD = 'clipboard-plus'
    LANGUAGE = 'language-hiragana'
    BRAND_X = 'brand-x'
    BILIBILI = 'brand-bilibili'
    PEOPLE = 'users'
    PHOTO = 'photo'
    REMOVE = 'minus'
    RIGHT_ARROW = 'arrow-right'
    SAVE = 'device-floppy'
    SEARCH = 'search'
    SEND = 'send'
    SETTING = 'settings-2'
    SHARE = 'share'
    SYNC = 'refresh'
    TAG = 'tag'
    TILES = 'layout-grid'
    UP = 'chevron-up'
    ZOOM_IN = 'zoom-in'
    ZOOM_OUT = 'zoom-out'
    SUN = 'sun'
    MOON = 'moon'
    SYSTEM = 'device-desktop'
    SORT = 'sort-descending'
    SORT_ASC = 'sort-ascending-letters'
    SORT_DESC = 'sort-descending-letters'
    TIME_ASC = 'sort-ascending-2'
    TIME_DESC = 'sort-descending-2'

    def path(self, theme=Theme.AUTO):
        return str(ASSETS / f'{self.value}.svg')

    def icon(self, theme=Theme.AUTO, color=None):
        from PySide6.QtGui import QIcon,QPixmap,QPainter
        from PySide6.QtCore import Qt
        from fluent_ui import visual
        pix=QPixmap(48,48);pix.setDevicePixelRatio(2);pix.fill(Qt.transparent)
        p=QPainter(pix)
        self.render(p,QRectF(0,0,24,24),fill=color or visual.colors()['text'])
        p.end();return QIcon(pix)

    def render(self, painter, rect, theme=Theme.AUTO, indexes=None, **attributes):
        from fluent_ui import visual
        color = attributes.get('fill') or attributes.get('stroke') or visual.colors()['text']
        if hasattr(color, 'name'):
            color = color.name()
        painter.save()
        _renderer(self.value, color).render(painter, QRectF(rect))
        painter.restore()
