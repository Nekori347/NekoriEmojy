"""Settings composition built around a glass navigation and one parameter sheet."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QListWidget,QScrollArea,QFrame,QStackedWidget
from fluent_ui import visual
from fluent_ui.icons import Icon
from fluent_ui.components.controls import TransparentToolButton
from fluent_ui.components.navigation import NavigationItem,TabStrip,ContentPane
from fluent_ui.components.feedback import FeedbackHost
from services.i18n import translated,bind_text
from .surfaces import Surface,RuleHeading


class DecisionBar(QWidget):
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'actions'):return
        margin=10;width=max(1,self.width()-2*margin)
        natural=sum(self.actions.layout().itemAt(i).sizeHint().width() for i in range(self.actions.layout().count()))+16
        preview=self.preview.sizeHint().width()
        stacked=width<natural+preview+16
        action_width=width if stacked else natural
        action_height=self.actions.layout().heightForWidth(action_width)
        y=48 if stacked else 10
        self.preview.setGeometry(margin,10 if stacked else y+(action_height-34)//2,preview,34)
        self.actions.setGeometry(margin if stacked else self.width()-margin-action_width,y,action_width,action_height)
        self.setFixedHeight(y+action_height+10)


def build_settings(c):
    root=QHBoxLayout(c);root.setContentsMargins(0,2,0,0);root.setSpacing(6)
    nav_surface=Surface('navigation',c,edge=False)
    nav_surface.setMinimumWidth(150);nav_surface.setMaximumWidth(180)
    navigation=QVBoxLayout(nav_surface);navigation.setContentsMargins(6,8,6,10);navigation.setSpacing(8)
    title=translated(QLabel,'设置',nav_surface);title.setObjectName('SettingsPageTitle')
    title.setProperty('role','title');navigation.addWidget(title)
    c.nav=QListWidget(nav_surface);c.nav.setObjectName('SettingsNav')
    c.nav.setItemDelegate(NavigationItem(c.nav));c.nav.setMouseTracking(True)
    c.nav.currentRowChanged.connect(c._select_page);navigation.addWidget(c.nav,1)
    c.btn_back=TransparentToolButton(Icon.LEFT_ARROW,nav_surface);c.btn_back.clicked.connect(c._go_back);c.btn_back.hide()
    lower=QHBoxLayout();lower.setContentsMargins(4,0,4,0)
    c.dirty_label=QLabel('',nav_surface);c.dirty_label.setObjectName('SettingsDirty')
    lower.addWidget(c.dirty_label,1)
    c.btn_tools=TransparentToolButton(Icon.MORE,nav_surface)
    bind_text(c.btn_tools,'导入 / 导出设置','setToolTip');c.btn_tools.clicked.connect(c._show_settings_tools)
    lower.addWidget(c.btn_tools);navigation.addLayout(lower);root.addWidget(nav_surface)
    foundation=Surface('base',c,radius=12)
    sheet=QVBoxLayout(foundation);sheet.setContentsMargins(6,6,6,6);sheet.setSpacing(0)
    c.tab_bar=TabStrip(foundation);c.tab_bar.currentChanged.connect(c._show_tab)
    sheet.addWidget(c.tab_bar)
    c.content_pane=ContentPane(foundation);sheet.addWidget(c.content_pane,1)
    pane=c.content_pane.content_layout
    c.scroll=QScrollArea(c.content_pane);c.scroll.setWidgetResizable(True);c.scroll.setFrameShape(QFrame.NoFrame)
    c.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    c.scroll.setStyleSheet('QScrollArea {border:none;background:transparent;}')
    c.scroll.verticalScrollBar().valueChanged.connect(c._update_sticky_header)
    c.body_widget=QWidget();c.body_widget.setObjectName('SettingsBody')
    c.scroll.viewport().setObjectName('SettingsViewport')
    c.body_layout=QVBoxLayout(c.body_widget);c.body_layout.setContentsMargins(10,12,10,10);c.body_layout.setSpacing(12)
    c.scroll.setWidget(c.body_widget)
    c.page_stack=QStackedWidget(c.content_pane);c.page_stack.addWidget(c.scroll);pane.addWidget(c.page_stack,1)
    c.sticky=QLabel('',c.scroll.viewport());c.sticky.setObjectName('SettingsSectionTitle');c.sticky.hide()
    pane.addWidget(c._build_footer())
    root.addWidget(foundation,1)
    c.feedback_host=FeedbackHost(c.content_pane,pane,before=c.page_stack)
    c._apply_style();c._set_dirty(False)
