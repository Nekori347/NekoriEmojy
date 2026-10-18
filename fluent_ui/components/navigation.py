"""Shared primary navigation and engineering secondary tabs."""
from PySide6.QtCore import Qt, QSize, QRectF, Signal, Property, QPropertyAnimation, QEasingCurve, QVariantAnimation, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QFontMetrics, QFont
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QTabBar, QWidget, QVBoxLayout, QToolButton, QApplication, QLabel, QSizePolicy
from fluent_ui import visual
from fluent_ui.components.section_index import SortProjection
from services.i18n import t, i18n_engine


class CompactTitleLabel(QLabel):
    """An intrinsic title that can yield width without losing its full tooltip."""
    def __init__(self, *args):
        super().__init__(*args)
        self.setFont(visual.font())
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setText(self, text):
        super().setText(text)
        self.setToolTip(text)
        self.setAccessibleName(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(visual.colors()['text']))
        painter.drawText(self.contentsRect(), Qt.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.contentsRect().width()))


class SortCycleButton(QToolButton):
    """One click advances the shared projection; the label shows its state."""
    mode_changed = Signal(object)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.mode = SortProjection.MANUAL
        self.setAutoRaise(True)
        self.setFixedHeight(visual.COMPACT_CONTROLS.action_extent)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._cycle)
        visual.theme.changed.connect(self.refresh)
        i18n_engine.language_changed.connect(self.refresh)
        self.refresh()

    def set_mode(self, mode):
        self.mode = SortProjection.from_display(mode)
        self.refresh()

    def _cycle(self):
        self.set_mode(self.mode.next())
        self.mode_changed.emit(self.mode)

    def refresh(self, *_):
        from fluent_ui.icons import Icon
        label = {SortProjection.MANUAL: '手动顺序', SortProjection.A_Z: '名称 A→Z', SortProjection.Z_A: '名称 Z→A'}[self.mode]
        self.setText('')
        self.setIcon({SortProjection.MANUAL: Icon.SORT, SortProjection.A_Z: Icon.SORT_ASC, SortProjection.Z_A: Icon.SORT_DESC}[self.mode].icon())
        self.setIconSize(QSize(16,16))
        self.setFixedWidth(visual.COMPACT_CONTROLS.action_extent)
        self.setToolTip(f'{t(self.title)} · {t(label)}\n{t("临时显示排序，不改动手动顺序")}')
        self.setAccessibleName(self.toolTip())
        c = visual.colors()
        self.setStyleSheet(f'QToolButton {{ color: {c["text_primary"]}; border: none; background: transparent; }} '
                          f'QToolButton:hover, QToolButton:focus {{ background: {c["surface_hover"]}; }} '
                          f'QToolButton:pressed {{ background: {c["surface_selected"]}; }} '
                          f'QToolButton:disabled {{ color: {c["text_muted"]}; }}')


class HierarchyLocationHeader(QWidget):
    """Parent/current and optional return child; scrubbing explores the full path.

    This widget only emits explicit navigation on release. Its preview and
    animation never modify Gallery state or create native child windows.
    """
    navigate_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(visual.font())
        self.path = []
        self._old_path = []
        self.return_item = None
        self._old_return = None
        self.count_label = QLabel(self)
        self.count_label.setProperty("role", "hierarchy-count")
        self.count_label.setAlignment(Qt.AlignVCenter)
        self.count_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.StrongFocus)
        self._progress = 1.0
        self._press = None
        self._preview = None
        self._scrub_position = None
        self._dragged = False
        self.setMinimumWidth(120)
        self.setCursor(Qt.PointingHandCursor)
        self.animation = QPropertyAnimation(self, b'progress', self)
        self.animation.setDuration(visual.HIERARCHY_DURATION_MS)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        visual.theme.changed.connect(self._layout_counts)
        visual.theme.accent_changed.connect(self.update)

    def _get_progress(self):
        return self._progress

    def _set_progress(self, value):
        self._progress = value
        self._layout_counts()

    progress = Property(float, _get_progress, _set_progress)

    def set_path(self, path, return_item=None):
        path = [(n['id'], n['name']) for n in path]
        return_item = (return_item["id"], return_item["name"]) if return_item else None
        if path == self.path and return_item == self.return_item:
            return
        old = self.path
        self._from_display = getattr(self,'_release_display',None) or (self._display_rows() if self.path else [])
        self._release_display = None
        self.animation.stop()
        self.path, self._old_path = path, old
        self.return_item, self._old_return = return_item, self.return_item
        self._preview = None
        self._scrub_position = None
        self.setFixedHeight(visual.HIERARCHY_HEADER_HEIGHT)
        self.setAccessibleName(' / '.join(n[1] for n in path))
        self.setToolTip(self.accessibleName() + ('\n' + t('回到刚才的子分支') + ': ' + return_item[1] if return_item else ''))
        self._layout_counts()
        self._direction = -1 if old and path and path[-1][0] in [n[0] for n in old[:-1]] else 1
        self._progress = 1.0
        if old and self.isVisible() and QApplication.platformName() not in ('offscreen','minimal'):
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(1.0)
            self.animation.start()
        self._layout_counts()

    def _rows(self, path, return_item=None):
        rows = {}
        top, step = visual.HIERARCHY_CURRENT_TOP, visual.HIERARCHY_ANCESTOR_STEP
        visible=path[-2:]
        for index,node in enumerate(visible):
            distance=len(visible)-1-index
            rows[node[0]] = (node[1], top-distance*step, distance == 0)
        if return_item:
            rows[return_item[0]] = (return_item[1], top+visual.HIERARCHY_TITLE_HEIGHT, False)
        return rows

    def current_rect(self):
        return QRectF(24, visual.HIERARCHY_CURRENT_TOP, max(0, self.width()-24), visual.HIERARCHY_TITLE_HEIGHT)

    def return_rect(self):
        r = self.current_rect()
        return QRectF(r.left(), r.bottom(), r.width(), 16)

    def set_counts(self, text):
        self.count_label.setText(text)
        self.count_label.setToolTip(text)
        self.count_label.setAccessibleName(text)
        self.setToolTip(' / '.join(n[1] for n in self.path) + '\n' + text +
                        ('\n' + t('回到刚才的子分支') + ': ' + self.return_item[1] if self.return_item else ''))
        self.setAccessibleName(self.toolTip())
        self._layout_counts()

    def _layout_counts(self):
        font = visual.font('page_title')
        title_width = QFontMetrics(font).horizontalAdvance(self.path[-1][1] if self.path else '')
        r = self.current_rect()
        gap = visual.COMPACT_CONTROLS.spacing*2
        count_font = visual.font('data');count_font.setPixelSize(11)
        count_font.setWeight(QFont.Medium)
        self.count_label.setFont(count_font)
        self.count_label.setStyleSheet(f"color: {visual.colors()['text_secondary']};")
        size = self.count_label.sizeHint()
        fits = title_width + gap + size.width() <= r.width()
        self.count_label.setVisible(fits and bool(self.count_label.text()) and self._progress == 1.0 and self._preview is None)
        self.count_label.setGeometry(int(r.left()+title_width+gap), int(r.center().y()-size.height()/2), size.width(), size.height())
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_counts()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._press is not None:
            self._press = self._preview = self._scrub_position = None
            self._layout_counts()
        elif event.key() == Qt.Key_Down and self.return_item:
            self.navigate_requested.emit(self.return_item[0])
        elif event.key() == Qt.Key_Up and len(self.path) > 1:
            self.navigate_requested.emit(self.path[-2][0])
        else:
            return super().keyPressEvent(event)
        event.accept()

    def _row_style(self, row, return_item, key):
        child = bool(return_item and key == return_item[0] and not row[2])
        return (visual.TYPOGRAPHY['page_title']['size'] if row[2] else 12 if child else 13,
                visual.HIERARCHY_TITLE_HEIGHT if row[2] else 16 if child else 18,
                600 if row[2] else 400, 1.0 if row[2] else .48 if child else .56)

    def _display_rows(self):
        """Interpolate each source role to its destination, including font weight."""
        rows = self._rows(self.path, self.return_item)
        old = self._rows(self._old_path, self._old_return) if self._progress < 1 else {}
        progress, direction = self._progress, getattr(self, '_direction', 1)
        source_return, dest_return = self._old_return, self.return_item
        snapshot = {r[0]:r for r in getattr(self,'_from_display',[]) } if old and self._scrub_position is None else {}
        if snapshot:
            old = {key:(r[1],r[2],r[5]>=550) for key,r in snapshot.items()}
        if self._scrub_position is not None:
            lower = int(self._scrub_position)
            upper = min(len(self.path)-1, lower+1)
            progress = self._scrub_position-lower
            rows = self._rows(self.path[:upper+1])
            old = self._rows(self.path[:lower+1]) if upper != lower else {}
            source_return = dest_return = None
            direction = 1
        result = []
        for key in dict.fromkeys([*old, *rows]):
            dest, source = rows.get(key), old.get(key)
            text, y, current = dest or source
            end_style = self._row_style(dest or source, dest_return if dest else source_return, key)
            size, height, weight, contrast = end_style
            opacity = 1.0
            if old:
                start_y = source[1] if source else y+direction*22
                end_y = dest[1] if dest else y-direction*22
                y = start_y+(end_y-start_y)*progress
                start_style = tuple(snapshot[key][i] for i in (3,4,5,6)) if key in snapshot else self._row_style(source, source_return, key) if source else end_style
                size, height, weight, contrast = [a+(b-a)*progress for a,b in zip(start_style,end_style)]
                opacity = progress if source is None else 1-progress if dest is None else 1.0
            result.append((key, text, y, size, height, weight, contrast, opacity))
        return result

    def _ticks(self, rows):
        # Only displayed rows have ticks: never the complete ancestor path.
        return [(y+height/2, 10 if weight >= 550 else 7, opacity)
                for _,_,y,_,height,weight,_,opacity in rows if opacity > .001]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = visual.colors()
        painter.setClipRect(self.rect())
        rows = self._display_rows()
        for key, text, y, size, height, weight, contrast, opacity in rows:
            font = visual.font()
            font.setPixelSize(round(size))
            font.setWeight(QFont.Weight(round(weight)))
            painter.setFont(font)
            color = QColor(c['text'])
            color.setAlphaF(opacity*contrast)
            painter.setPen(color)
            rect = QRectF(24, y, max(0,self.width()-24), height)
            reserve = self.count_label.width()+8 if self.path and key == self.path[-1][0] and self.count_label.isVisible() else 0
            painter.drawText(rect, Qt.AlignVCenter, painter.fontMetrics().elidedText(text, Qt.ElideRight, max(0,int(rect.width())-reserve)))
        # Parent identity is fixed geometry, not part of any animated title.
        path = self.path if self._preview is None else self.path[:self._preview+1]
        if len(path) > 1:
            y = visual.HIERARCHY_CURRENT_TOP-visual.HIERARCHY_ANCESTOR_STEP+9
            painter.setPen(QPen(QColor(c['text_secondary']),1,Qt.SolidLine,Qt.RoundCap))
            painter.drawLine(14,y+4,16,y-4)
            painter.drawLine(18,y+4,20,y-4)
        center = self.current_rect().center().y()
        painter.setPen(QPen(QColor(c['accent']),3))
        painter.drawLine(17,int(center-9),17,int(center+9))
        for y, length, opacity in self._ticks(rows):
            color = QColor(c['border'])
            color.setAlphaF(opacity)
            painter.setPen(QPen(color,1))
            painter.drawLine(2,int(y),length,int(y))
        painter.setPen(QPen(QColor(c['border']),1))
        painter.drawLine(24,self.height()-1,self.width(),self.height()-1)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.path:
            return super().mousePressEvent(event)
        self._return_pressed = bool(self.return_item and self.return_rect().contains(event.position()))
        if self._return_pressed:
            event.accept()
            return
        self._press = event.position().toPoint()
        self._dragged = False
        distance = 1 if self._press.y() < visual.HIERARCHY_CURRENT_TOP else 0
        self._pressed_index = max(0,len(self.path)-1-distance)
        # A press is not a scrub preview: keep source roles until movement.
        self._preview = self._scrub_position = None
        self._layout_counts()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._press is None:
            return super().mouseMoveEvent(event)
        dy = event.position().y()-self._press.y()
        if abs(dy) >= QApplication.startDragDistance():
            self._dragged = True
        if self._dragged:
            self.animation.stop()
            self._scrub_position = max(0, min(len(self.path)-1, len(self.path)-1 - dy / visual.HIERARCHY_SCRUB_STEP))
            self._preview = round(self._scrub_position)
            self._layout_counts()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and getattr(self, '_return_pressed', False):
            self._return_pressed = False
            if self.return_item and self.return_rect().contains(event.position()):
                self.navigate_requested.emit(self.return_item[0])
            event.accept()
            return
        if event.button() != Qt.LeftButton or self._press is None:
            return super().mouseReleaseEvent(event)
        target = self.path[self._preview if self._preview is not None else self._pressed_index][0]
        self._release_display=self._display_rows()
        self._press = self._preview = None
        self._scrub_position = None
        if target==self.path[-1][0] and self._dragged:
            self._from_display=self._release_display
            self._release_display=None
            self._old_path=self.path[:]
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(1.0)
            self.animation.start()
        self._layout_counts()
        self.navigate_requested.emit(target)


# Kept for callers of the original presentation component.
HierarchyRail = HierarchyLocationHeader


def sort_named(items, mode):
    """Temporary display order; SQLite's canonical order remains untouched."""
    return SortProjection.from_display(mode).project(items, name=lambda item: item['name'])


class AttachedTabRow(QWidget):
    """Continue the content boundary under the trailing projection control."""
    def __init__(self, parent=None):
        super().__init__(parent)
        visual.theme.changed.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(QColor(visual.colors()['border']), 1))
        painter.drawLine(0, self.height()-1, self.width(), self.height()-1)


class NavigationItem(QStyledItemDelegate):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self._indicator = QRectF()
        self._selection_motion = QVariantAnimation(self)
        self._selection_motion.setDuration(visual.MOTION.select)
        self._selection_motion.setEasingCurve(visual.MOTION.easing)
        self._selection_motion.valueChanged.connect(self._slide_indicator)
        self._selection_timer=QTimer(self);self._selection_timer.setSingleShot(True)
        self._selection_timer.timeout.connect(self._selection_changed)
        view.selectionModel().selectionChanged.connect(lambda *_:self._selection_timer.start(0))
        view.verticalScrollBar().valueChanged.connect(self._snap_indicator)
        visual.theme.changed.connect(view.viewport().update)
        visual.theme.accent_changed.connect(view.viewport().update)

    def _indicator_target(self):
        selected=[i for i in self.view.selectionModel().selectedIndexes() if i.column()==0]
        if len(selected)!=1:
            return QRectF()
        index=selected[0]
        rect=self.view.visualRect(index)
        depth,parent=0,index.parent()
        while parent.isValid():
            depth+=1;parent=parent.parent()
        return QRectF(10+min(depth*6,24),rect.top()+11,2,max(2,rect.height()-22))

    def _slide_indicator(self,value):
        self._indicator=value
        self.view.viewport().update()

    def _snap_indicator(self,*_):
        self._selection_motion.stop()
        self._indicator=self._indicator_target()
        self.view.viewport().update()

    def _selection_changed(self,*_):
        target=self._indicator_target()
        self._selection_motion.stop()
        if target.isEmpty() or self._indicator.isEmpty():
            self._indicator=target
        else:
            self._selection_motion.setStartValue(self._indicator)
            self._selection_motion.setEndValue(target)
            self._selection_motion.start()
        self.view.viewport().update()

    def _paint_indicator(self,painter,rect,selected):
        moving=self._selection_motion.state()==QVariantAnimation.Running or self._selection_timer.isActive()
        indicator=self._indicator if moving else self._indicator_target()
        if indicator.isEmpty() and selected:
            indicator=QRectF(rect.left()+6,rect.top()+8,2,rect.height()-16)
        painter.save();painter.setClipRect(rect)
        painter.setPen(Qt.NoPen);painter.setBrush(QColor(visual.accent()))
        painter.drawRoundedRect(indicator,1,1)
        painter.restore()

    def sizeHint(self, option, index):
        from fluent_ui.components.section_index import SectionHeader
        height = SectionHeader.HEIGHT if index.data(SectionHeader.ROLE) else max(34, self.view.iconSize().height()+16)
        return QSize(super().sizeHint(option, index).width(), height)

    def paint(self, painter, option, index):
        from fluent_ui.components.section_index import SectionHeader
        section = index.data(SectionHeader.ROLE)
        if section:
            if index.column() == 0:
                SectionHeader.paint(painter, option.rect.adjusted(8, 0, -8, 0), section)
            return
        if hasattr(self.view, 'chevron_rect'):
            if index.column() == 0:
                self._paint_category(painter, option, index)
            return
        c = visual.colors()
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        tree = hasattr(self.view, 'chevron_rect')
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(4, 3, -4, -3)
        if index.column() == 0:
            rect.setRight(self.view.viewport().width()-4)
            if selected or hovered:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(c['selected'] if selected else c['hover']))
                painter.drawRoundedRect(rect, 4, 4)
            self._paint_indicator(painter,rect,selected)
            if option.state & QStyle.State_HasFocus:
                painter.setPen(QPen(QColor(c['border']),1,Qt.DotLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect,6,6)
        if tree and index.column() == 2:
            item = self.view.itemFromIndex(index)
            if item.childCount():
                from PySide6.QtCore import QPointF
                from PySide6.QtGui import QPolygonF
                x,y=option.rect.center().x(),option.rect.center().y()
                points=[(x-3,y-2),(x,y+1),(x+3,y-2)] if item.isExpanded() else [(x-2,y-3),(x+1,y),(x-2,y+3)]
                painter.setPen(QPen(QColor(c['muted']),1.5))
                painter.drawPolyline(QPolygonF([QPointF(a,b) for a,b in points]))
            painter.restore()
            return
        text_rect=option.rect.adjusted(20 if index.column()==0 else 0,0,-8,0)
        icon=index.data(Qt.DecorationRole)
        if index.column()==0 and icon is not None:
            size=self.view.iconSize().width()
            icon.paint(painter,text_rect.left(),text_rect.center().y()-size//2,size,size)
            text_rect.setLeft(text_rect.left()+size+8)
        font=option.font
        font.setBold(selected and index.column()==0)
        painter.setFont(font)
        painter.setPen(QColor(c['text'] if index.column()==0 else c['muted']))
        text=painter.fontMetrics().elidedText(str(index.data(Qt.DisplayRole) or ''),Qt.ElideRight,max(0,text_rect.width()))
        painter.drawText(text_rect,Qt.AlignVCenter | (Qt.AlignRight if index.column() else Qt.AlignLeft),text)
        painter.restore()

    def _paint_category(self, painter, option, index):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF
        item = self.view.itemFromIndex(index)
        c = visual.colors()
        selected = bool(option.state & QStyle.State_Selected)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(4, 3, -4, -3)
        painter.setPen(Qt.NoPen)
        fill=QColor(c['selected'] if selected else c['hover'])
        fill.setAlpha(180 if selected else 255 if option.state & QStyle.State_MouseOver else 0)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 4, 4)
        self._paint_indicator(painter,rect,selected)
        if option.state & QStyle.State_HasFocus:
            painter.setPen(QPen(QColor(c['border']), 1, Qt.DotLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 4, 4)
        trailing = self.view.chevron_rect(item)
        right = trailing.left() if item.childCount() else rect.right()
        text_rect = option.rect.adjusted(14,0,0,0)
        text_rect.setRight(int(right-4))
        size = self.view.iconSize().width()
        item.icon(0).paint(painter, text_rect.left(), text_rect.center().y()-size//2, size, size)
        text_rect.setLeft(text_rect.left()+size+8)
        font = visual.font()
        font.setBold(selected)
        painter.setFont(font)
        painter.setPen(QColor(c['text']))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(item.text(0), Qt.ElideRight, max(0,text_rect.width())))
        if item.childCount():
            x,y = trailing.center().x(), trailing.center().y()
            points = [(x-3,y-2),(x,y+1),(x+3,y-2)] if item.isExpanded() else [(x-2,y-3),(x+1,y),(x-2,y+3)]
            painter.setPen(QPen(QColor(c['text_secondary']), 1.5))
            painter.drawPolyline(QPolygonF([QPointF(a,b) for a,b in points]))
        painter.restore()


class ContentPane(QWidget):
    """The open-top surface immediately below an attached TabStrip."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(visual.font())
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(1, 0, 1, 10)
        self.content_layout.setSpacing(0)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        # Clip children as well as the pane paint, keeping the open top intact.
        from PySide6.QtGui import QRegion
        radius=getattr(self,'corner_radius',12);w=self.width();h=self.height()
        path=QPainterPath();path.moveTo(0,0);path.lineTo(w,0);path.lineTo(w,h-radius)
        path.quadTo(w,h,w-radius,h);path.lineTo(radius,h);path.quadTo(0,h,0,h-radius);path.closeSubpath()
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def paintEvent(self, event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
        r=QRectF(self.rect()).adjusted(.5,0,-.5,-.5)
        radius=getattr(self,'corner_radius',12)
        path=QPainterPath();path.moveTo(r.left(),0);path.lineTo(r.right(),0)
        path.lineTo(r.right(),r.bottom()-radius);path.quadTo(r.right(),r.bottom(),r.right()-radius,r.bottom())
        path.lineTo(r.left()+radius,r.bottom());path.quadTo(r.left(),r.bottom(),r.left(),r.bottom()-radius);path.closeSubpath()
        p.fillPath(path,QColor(c['surface']))
        # Top boundary is owned by the attached tabs, never doubled here.
        path=QPainterPath();path.moveTo(r.left(),0);path.lineTo(r.left(),r.bottom()-radius)
        path.quadTo(r.left(),r.bottom(),r.left()+radius,r.bottom());path.lineTo(r.right()-radius,r.bottom())
        path.quadTo(r.right(),r.bottom(),r.right(),r.bottom()-radius);path.lineTo(r.right(),0)
        p.setPen(QPen(QColor(c['border_soft']),1));p.drawPath(path)


class TabStrip(QTabBar):
    """Notebook tabs: the pane's top boundary detours around the active tab."""
    def __init__(self, parent=None, *, location_divider=False):
        super().__init__(parent)
        self.location_divider = location_divider
        self.setFont(visual.font())
        self.setObjectName('NekoriTabStrip')
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.ElideRight)
        self.setFixedHeight(43)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._hovered_tab = -1
        self._line_rect = QRectF()
        self._line_motion = QVariantAnimation(self)
        self._line_motion.setDuration(visual.MOTION.select)
        self._line_motion.setEasingCurve(visual.MOTION.easing)
        self._line_motion.valueChanged.connect(self._move_line)
        self.currentChanged.connect(self._animate_line)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def _target_line(self):
        if self.currentIndex()<0:
            return QRectF()
        rect=self.content_tab_rect(self.currentIndex())
        width=min(38,max(18,rect.width()-32))
        return QRectF(rect.center().x()-width/2,9,width,3)

    def _move_line(self,value):
        self._line_rect=value
        self.update()

    def _animate_line(self,*_):
        target=self._target_line()
        self._line_motion.stop()
        if self._line_rect.isEmpty() or not self.isVisible():
            self._line_rect=target
        else:
            self._line_motion.setStartValue(self._line_rect)
            self._line_motion.setEndValue(target)
            self._line_motion.start()
        self.update()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._line_motion.stop()
        self._line_rect=self._target_line()

    def mouseMoveEvent(self, event):
        self._hovered_tab = self.tabAt(event.position().toPoint())
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_tab = -1
        self.update()
        super().leaveEvent(event)

    def tabSizeHint(self, index):
        gap = visual.TAB_LOCATION_GAP if self.location_divider and index == 0 and self.count() > 1 else 0
        return QSize(min(max(96, min(240, self.width()-48)), max(72, self.fontMetrics().horizontalAdvance(self.tabText(index))+36+(22 if not self.tabIcon(index).isNull() else 0)))+gap, 43)

    def content_tab_rect(self, index):
        rect = self.tabRect(index)
        if self.location_divider and index == 0 and self.count() > 1:
            rect.adjust(0, 0, -visual.TAB_LOCATION_GAP, 0)
        return rect

    def set_tabs(self, labels, current=0):
        if labels == [self.tabText(i) for i in range(self.count())]:
            self.blockSignals(True)
            self.setCurrentIndex(current)
            self.blockSignals(False)
            self._animate_line()
            return
        self.blockSignals(True)
        while self.count():
            self.removeTab(0)
        for label in labels:
            index = self.addTab(label)
            self.setTabToolTip(index, label)
        self.setCurrentIndex(current)
        self.blockSignals(False)
        self._animate_line()
        self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = visual.colors()
        y = self.height()-0.5
        selected = self.content_tab_rect(self.currentIndex()) if self.currentIndex() >= 0 else None
        # Neutral pane boundary, with a separate rounded active contour.
        painter.setPen(QPen(QColor(c['border']), 1))
        if selected:
            painter.drawLine(0, int(y), selected.left(), int(y))
            painter.drawLine(selected.right(), int(y), self.width(), int(y))
        else:
            painter.drawLine(0, int(y), self.width(), int(y))
        boundary = QPainterPath()
        if selected:
            left, right = selected.left()+0.5, selected.right()+0.5
            radius, top = 7, 5.5
            boundary.moveTo(max(0, left-radius), y)
            boundary.quadTo(left, y, left, y-radius)
            boundary.lineTo(left, top+radius)
            boundary.quadTo(left, top, left+radius, top)
            boundary.lineTo(right-radius, top)
            boundary.quadTo(right, top, right, top+radius)
            boundary.lineTo(right, y-radius)
            boundary.quadTo(right, y, min(self.width(), right+radius), y)
            fill = QPainterPath(boundary)
            fill.closeSubpath()
            painter.fillPath(fill, QColor(c['surface']))
        painter.setPen(QPen(QColor(c['border']), 1))
        painter.drawPath(boundary)
        if self.location_divider and self.count() > 1:
            x = self.tabRect(0).right()-visual.TAB_LOCATION_GAP//2
            painter.setPen(QPen(QColor(c['border']), visual.TAB_DIVIDER_WIDTH))
            painter.drawLine(x, 13, x, self.height()-9)
        for i in range(self.count()):
            rect = self.content_tab_rect(i)
            active = i == self.currentIndex()
            if not active and i == self._hovered_tab:
                painter.fillRect(rect.adjusted(3, 8, -3, -4), QColor(c['hover']))
            painter.setPen(QColor(c['text'] if active else c['muted']))
            font = self.font()
            font.setBold(active)
            painter.setFont(font)
            icon=self.tabIcon(i);text_rect=rect.adjusted(12,10,-12,-1)
            if not icon.isNull():
                # Keep the icon and label as a centred group. A fixed icon cell
                # must never be borrowed by the label's centring/elision.
                label_width=min(max(0,text_rect.width()-24),painter.fontMetrics().horizontalAdvance(self.tabText(i)))
                group_left=text_rect.center().x()-(label_width+24)//2
                icon.paint(painter,int(group_left),int(text_rect.center().y())-9,18,18)
                text_rect.setLeft(int(group_left)+24)
                text_rect.setWidth(label_width)
            painter.drawText(text_rect,Qt.AlignCenter,painter.fontMetrics().elidedText(self.tabText(i),Qt.ElideRight,max(0,text_rect.width())))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(c['accent']))
        painter.drawRoundedRect(self._line_rect if not self._line_rect.isEmpty() else self._target_line(),1.5,1.5)
        painter.end()
