from PySide6.QtCore import QPoint, QRect, Qt, QSize
from qfluentwidgets import RoundMenu, MenuAnimationType
from qfluentwidgets.common.screen import getCurrentScreenGeometry
from qfluentwidgets.components.widgets.menu import SubMenuItemWidget


class _BranchHit(SubMenuItemWidget):
    def paintEvent(self,event):
        from PySide6.QtGui import QPainter
        from PySide6.QtCore import QRectF
        from fluent_ui.icons import Icon
        from fluent_ui import visual
        p=QPainter(self)
        Icon.CHEVRON_RIGHT.render(p,QRectF(self.width()-14,(self.height()-12)/2,12,12),fill=visual.colors()['text_secondary'])


class SafeRoundMenu(RoundMenu):
    """修复次级菜单在屏幕左侧展开时鼠标穿越导致的误收起。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from fluent_ui.components.controls import _own_presentation
        _own_presentation(self);_own_presentation(self.view)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet('QMenu { background: transparent; border: none; }')
        # PySide6 can cache QMenu.exec on the instance, shadowing RoundMenu's
        # Python method. Bind explicitly to show the custom action view.
        self.exec = self._show_menu
        from fluent_ui.visual import menu_style
        self.view.setStyleSheet(menu_style())
        self.setMaxVisibleItems(-1)
        from fluent_ui.presentation.menu import MenuDelegate
        self.view.setItemDelegate(MenuDelegate(self.view))
        from fluent_ui import visual
        self.view.setFont(visual.font())
        visual.theme.changed.connect(self.refresh_theme)

    def _show_menu(self, pos, ani=True, aniType=MenuAnimationType.DROP_DOWN):
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(pos) or self.screen()
        area = screen.availableGeometry()
        # Upstream animation managers resolve the cursor's screen separately
        # from `pos`. Position once from the actual trigger, including submenus.
        self.view.setFixedHeight(min(self.view.itemsHeight()+4, max(40, area.height()-24)))
        self.view.setFixedWidth(min(self.view.width(),max(80,area.width()-48)))
        self.adjustSize()
        x = max(area.left(), min(pos.x(), area.right()-self.width()+1))
        y = max(area.top(), min(pos.y(), area.bottom()-self.height()+1))
        self.move(QPoint(x, y))
        self.show()
        if self.isSubMenu:
            self.menuItem.setSelected(True)

    def popup_at(self, trigger, *, prefer_up=False):
        from PySide6.QtGui import QGuiApplication
        anchor = QRect(trigger.mapToGlobal(QPoint()), trigger.size())
        area = (QGuiApplication.screenAt(anchor.center()) or trigger.screen()).availableGeometry()
        self.view.setFixedHeight(min(self.view.itemsHeight()+4, max(40, area.height()-24)))
        self.adjustSize()
        self.layout().activate()
        inset=self.layout().contentsMargins()
        up = anchor.top()-self.height()+inset.bottom()-4
        down = anchor.bottom()+1-inset.top()+4
        y = up if prefer_up and up >= area.top() else down
        if y+self.height()>area.bottom()+1 and up>=area.top():y=up
        self._show_menu(QPoint(anchor.left()-inset.left(), y))

    def _adjustItemText(self,item,action):
        from fluent_ui import visual
        from PySide6.QtGui import QFontMetrics
        fm=QFontMetrics(visual.font())
        shortcut=action.shortcut().toString()
        width=fm.horizontalAdvance(action.text())+64+(fm.horizontalAdvance(shortcut)+36 if shortcut else 0)
        item.setText(action.text());item.setSizeHint(QSize(width,32))
        return width

    def _createSubMenuItem(self,menu):
        item,old=super()._createSubMenuItem(menu)
        hit=_BranchHit(menu,item,self);hit.showMenuSig.connect(self._showSubMenu);hit.resize(item.sizeHint())
        old.hide();old.deleteLater()
        return item,hit

    def refresh_theme(self):
        from fluent_ui.visual import menu_style
        self.setStyleSheet('QMenu { background: transparent; border: none; }')
        self.view.setStyleSheet(menu_style())

    def showEvent(self,event):
        super().showEvent(event)
        from fluent_ui import visual
        from PySide6.QtWidgets import QApplication
        if QApplication.platformName() != 'offscreen':
            from PySide6.QtCore import QPropertyAnimation,QEasingCurve
            if not hasattr(self,'_reveal'):
                self._reveal=QPropertyAnimation(self,b'windowOpacity',self)
            self._reveal.stop();self._reveal.setDuration(visual.MOTION.window)
            self._reveal.setEasingCurve(QEasingCurve.OutCubic)
            self._reveal.setStartValue(.92);self._reveal.setEndValue(1.)
            visual.start_animation(self._reveal, visual.MOTION.window)

    def _onShowMenuTimeOut(self):
        """定位次级菜单，避免左侧展开时与一级菜单产生异常间隔。"""
        if (
            self.lastHoverSubMenuItem is None
            or self.lastHoverItem is not self.lastHoverSubMenuItem
        ):
            return

        widget = self.view.itemWidget(self.lastHoverSubMenuItem)
        if widget is None or widget.menu.parentMenu.isHidden():
            return
        prepare=getattr(widget.menu,'prepare',None)
        if prepare:prepare()

        item_rect = QRect(
            widget.mapToGlobal(widget.rect().topLeft()),
            widget.size(),
        )
        submenu_size = widget.menu.sizeHint()
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(item_rect.center()) or self.screen()
        screen_rect = screen.availableGeometry()

        # 默认从右侧展开，并与一级菜单项保持很小的间距。
        x = item_rect.right() + 5
        y = item_rect.y() - 5

        # 屏幕右侧空间不足时改为从左侧展开。
        # 使用 +1 贴合父菜单项，避免默认的额外偏移在边缘修正后
        # 被放大成明显的空白区域。
        if x + submenu_size.width() > screen_rect.right():
            x = item_rect.left() - submenu_size.width() + 1

            # 只有真正超出屏幕左边界时才进行边界修正。
            if x < screen_rect.left():
                x = screen_rect.left()

        if y + submenu_size.height() > screen_rect.bottom():
            y = screen_rect.bottom() - submenu_size.height()

        y = max(y, screen_rect.top())
        widget.menu.exec(QPoint(x, y))

    def mouseMoveEvent(self, event):
        if not self.isSubMenu or self.parentMenu is None:
            return super().mouseMoveEvent(event)

        pos = event.globalPos()
        parent_menu = self.parentMenu
        view = parent_menu.view

        # 与 RoundMenu 原始实现保持一致，取得父菜单中的当前菜单项区域。
        margin = view.viewportMargins()
        item_rect = view.visualItemRect(self.menuItem).translated(
            view.mapToGlobal(QPoint())
        )
        item_rect = item_rect.translated(margin.left(), margin.top() + 2)

        # 鼠标位于当前菜单项、子菜单，或二者之间的横向间隙时，
        # 不执行原始的收起逻辑。该区域同时兼容右侧和左侧展开。
        submenu_rect = self.geometry()
        if item_rect.contains(pos) or submenu_rect.contains(pos):
            return

        gap_left = min(item_rect.right(), submenu_rect.right())
        gap_right = max(item_rect.left(), submenu_rect.left())
        gap_top = min(item_rect.top(), submenu_rect.top())
        gap_bottom = max(item_rect.bottom(), submenu_rect.bottom())
        bridge_rect = QRect(
            QPoint(gap_left, gap_top),
            QPoint(gap_right, gap_bottom),
        )
        if bridge_rect.contains(pos):
            return

        # 其他情况必须保留 RoundMenu 的默认行为，例如移动到父菜单的
        # 其他项目时收起当前子菜单。
        super().mouseMoveEvent(event)
