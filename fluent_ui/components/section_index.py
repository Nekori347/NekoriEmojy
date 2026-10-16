"""Reusable sort projection and section navigation, independent of Tag data."""
from enum import Enum
from string import ascii_uppercase
from functools import lru_cache
from PySide6.QtCore import Qt, QRect, QRectF, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget
from pypinyin import lazy_pinyin
from fluent_ui import visual
from services.i18n import bind_text


class SortProjection(str, Enum):
    MANUAL = 'manual'
    A_Z = 'a_z'
    Z_A = 'z_a'

    def next(self):
        modes = tuple(type(self))
        return modes[(modes.index(self) + 1) % len(modes)]

    @classmethod
    def from_display(cls, value):
        return cls({'name_asc': 'a_z', 'name_desc': 'z_a'}.get(value, value))

    @property
    def display_mode(self):
        return {self.MANUAL: 'manual', self.A_Z: 'name_asc', self.Z_A: 'name_desc'}[self]

    def project(self, items, name=lambda item: item.name):
        return SectionedProjection(items, self, name).items


class SectionKeyProvider:
    @staticmethod
    @lru_cache(maxsize=2048)
    def sort_key(text):
        return ''.join(lazy_pinyin(text)).casefold()

    @classmethod
    def section(cls, text):
        initial = cls.sort_key(text.strip())[:1].upper()
        return initial if initial and initial in ascii_uppercase else '#'


class SectionedProjection:
    """Single result for content headers, items and navigation in every view."""

    def __init__(self, items=(), mode=SortProjection.MANUAL, name=lambda item: item.name):
        self.mode = SortProjection(mode)
        self.items = list(items)
        self.sections, self.itemsBySection, self.positions = [], {}, {}
        if self.mode == SortProjection.MANUAL:
            return
        for item in self.items:
            key = SectionKeyProvider.section(name(item))
            self.itemsBySection.setdefault(key, []).append(item)
        reverse = self.mode == SortProjection.Z_A
        self.sections = sorted(self.itemsBySection, reverse=reverse)
        self.items = []
        for key in self.sections:
            group = sorted(self.itemsBySection[key],
                           key=lambda item: SectionKeyProvider.sort_key(name(item)), reverse=reverse)
            self.itemsBySection[key] = group
            self.positions[key] = len(self.items)
            self.items.extend(group)


class SectionHeader:
    HEIGHT = 22
    ROLE = Qt.UserRole + 2

    @staticmethod
    def paint(painter, rect, key):
        painter.save()
        painter.setFont(visual.font('data'))
        painter.setPen(QColor(visual.accent()))
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, key)
        painter.setPen(QPen(QColor(visual.colors()['border']), 1))
        painter.drawLine(rect.left()+24, rect.center().y(), rect.right()-4, rect.center().y())
        painter.drawLine(rect.right()-4,rect.center().y()-2,rect.right()-4,rect.center().y()+2)
        painter.restore()


class SectionContentLayout:
    """Where each section group and its items sit, along the panel's axis.

    The alphabet index and the section content are two different presentation
    concerns that consume the *same* placement. The index is a strip of letters
    running along the panel's axis; the content is a flow of section groups
    running along that same axis. Which axis it is comes from the placement
    alone, never from the widget's own width, height or aspect ratio.

    horizontal (TOP / BOTTOM)
        sections flow left to right; each group is a column with its header on
        top and its items listed downward inside it

            A            B            C
            ────         ────         ────
            啊啊啊        笨蛋          测试
            啊哦哦

    vertical (LEFT / RIGHT)
        sections flow top to bottom; each group is a full-width header with its
        items flowing under it

            A ───────────────────────
            啊啊啊  啊哦哦
            B ───────────────────────
            笨蛋

    Content with no sections at all (manual order) keeps the plain wrapping
    flow in both axes: there is no section group to arrange.
    """

    def __init__(self, horizontal=True, padding=6, gap=6, chip_height=24, min_chip=46,
                 header_height=SectionHeader.HEIGHT):
        self.horizontal = horizontal
        self.padding = padding
        self.gap = gap
        self.chip_height = chip_height
        self.min_chip = min_chip
        self.header_height = header_height

    @staticmethod
    def groups(items, projection):
        """[(section key or None, [item indices])] in projection order."""
        starts = {index: key for key, index in projection.positions.items()}
        result = []
        for index in range(len(items)):
            key = starts.get(index)
            if key is not None or not result:
                result.append([key, []])
            result[-1][1].append(index)
        return result

    def build(self, items, projection, width, measure):
        """Returns (header rects, item rects, content height)."""
        groups = self.groups(items, projection)
        if self.horizontal and any(key is not None for key, _ in groups):
            return self._columns(groups, items, width, measure)
        return self._flow(groups, items, width, measure)

    def _flow(self, groups, items, width, measure):
        available = max(self.min_chip+self.padding, width-self.padding)
        x, y, headers, rects = self.padding, self.padding, [], []
        for key, indices in groups:
            if key is not None:
                if x != self.padding:
                    y += self.chip_height+self.gap
                headers.append((key, QRect(self.padding, y, max(1, width-2*self.padding),
                                           self.header_height)))
                y += self.header_height
                x = self.padding
            for index in indices:
                chip = min(measure(items[index]), max(1, width-2*self.padding))
                if x > self.padding and x+chip > available:
                    x, y = self.padding, y+self.chip_height+self.gap
                rects.append(QRect(x, y, chip, self.chip_height))
                x += chip+self.gap
        if items:
            height = y+self.chip_height+self.padding
        else:
            height = self.chip_height+self.padding*2
        return headers, rects, height

    def _columns(self, groups, items, width, measure):
        available = max(self.min_chip, width-self.padding)
        x, y, row_height = self.padding, self.padding, 0
        headers, rects = [], []
        for key, indices in groups:
            column = max([measure(items[index]) for index in indices] or [self.min_chip])
            column = min(max(column, self.min_chip), max(1, width-2*self.padding))
            if x > self.padding and x+column > available:
                x, y = self.padding, y+row_height+self.gap
                row_height = 0
            top = y+(self.header_height if key is not None else 0)
            if key is not None:
                headers.append((key, QRect(x, y, column, self.header_height)))
            for offset, index in enumerate(indices):
                rects.append(QRect(x, top+offset*(self.chip_height+self.gap),
                                   min(measure(items[index]), column), self.chip_height))
            row_height = max(row_height, top-y+len(indices)*(self.chip_height+self.gap))
            x += column+self.gap
        if items:
            height = y+row_height+self.padding
        else:
            height = self.chip_height+self.padding*2
        return headers, rects, height


class SectionIndexModel:
    def __init__(self, items=(), name=lambda item: item.name):
        self.projection = items if isinstance(items, SectionedProjection) else SectionedProjection(items, SortProjection.A_Z, name)
        self.sections = self.projection.sections
        self.positions = self.projection.positions


class SectionNavigator(QWidget):
    """Auxiliary jump surface; consumes the content's SectionedProjection."""
    section_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = SectionIndexModel()
        self.orientation = Qt.Horizontal
        self._pressed = False
        self._current = None
        self.setMouseTracking(True)
        self.setAutoFillBackground(False)
        self.setStyleSheet('background: transparent; border: none;')
        bind_text(self, '字母索引', 'setAccessibleName')
        bind_text(self, '字母索引', 'setToolTip')
        self.setFocusPolicy(Qt.StrongFocus)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def set_model(self, model):
        self.model = model
        self._resize_compact()
        self.update()

    def set_orientation(self, orientation):
        self.orientation = orientation
        self._resize_compact()
        self.updateGeometry()
        self.update()

    def _resize_compact(self):
        count = len(self.model.sections)
        extent = visual.SECTION_INDEX_COMPACT_EXTENT
        length = max(extent, count*visual.COMPACT_CONTROLS.index_step)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        if self.orientation == Qt.Horizontal:
            self.setFixedHeight(extent)
            self.setMaximumWidth(length)
        else:
            self.setFixedWidth(extent)
            self.setMaximumHeight(length)
        self.updateGeometry()

    def sizeHint(self):
        length = max(visual.SECTION_INDEX_COMPACT_EXTENT, len(self.model.sections)*visual.COMPACT_CONTROLS.index_step)
        return QSize(length, visual.SECTION_INDEX_COMPACT_EXTENT) if self.orientation == Qt.Horizontal else QSize(visual.SECTION_INDEX_COMPACT_EXTENT, length)

    def _step(self):
        length = self.width() if self.orientation == Qt.Horizontal else self.height()
        return min(visual.COMPACT_CONTROLS.index_step, length / max(1, len(self.model.sections)))

    def _choose(self, pos):
        keys = self.model.sections
        if not keys:
            return
        coord = pos.x() if self.orientation == Qt.Horizontal else pos.y()
        key = keys[max(0, min(len(keys)-1, int(coord/max(1, self._step()))))]
        if key != self._current:
            self._current = key
            self.section_requested.emit(key)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self._current = None
            self._choose(event.position().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._pressed:
            self._choose(event.position().toPoint())

    def mouseReleaseEvent(self, event):
        self._pressed = False

    def keyPressEvent(self, event):
        keys = self.model.sections
        if keys and event.key() in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, Qt.Key_Down):
            pos = keys.index(self._current) if self._current in keys else -1
            pos = max(0, min(len(keys)-1, pos + (-1 if event.key() in (Qt.Key_Left, Qt.Key_Up) else 1)))
            self._current = keys[pos]
            self.section_requested.emit(self._current)
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        keys = self.model.sections
        step = self._step()
        for index, key in enumerate(keys):
            painter.setPen(QColor(visual.accent() if key == self._current else visual.colors()['muted']))
            if self.orientation == Qt.Horizontal:
                painter.drawText(QRectF(index*step, 0, step, self.height()), Qt.AlignCenter, key)
            else:
                painter.drawText(QRectF(0, index*step, self.width(), step), Qt.AlignCenter, key)


SectionIndexView = SectionNavigator  # existing consumers use the same component
