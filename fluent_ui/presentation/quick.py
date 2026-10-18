"""A compact glass command shelf over a stable, inset resource sheet."""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QWidget,QScrollArea
from fluent_ui.components.controls import SearchLineEdit,TransparentToolButton
from fluent_ui.icons import Icon
from services.i18n import t,i18n_engine,bind_text,translated
from fluent_ui import visual
from .surfaces import Surface


def build_quick(q):
    q.layout=QVBoxLayout(q);q.layout.setContentsMargins(6,8,6,6);q.layout.setSpacing(0)
    q.bg_widget=QWidget(q);q.bg_layout=QVBoxLayout(q.bg_widget)
    q.bg_layout.setContentsMargins(0,0,0,0);q.bg_layout.setSpacing(10);q.layout.addWidget(q.bg_widget)
    title=QWidget(q.bg_widget);row=QHBoxLayout(title);row.setContentsMargins(4,0,2,0)
    q.identity_icon=QLabel(title);q.identity_icon.setFixedSize(18,18);q.identity_icon.setPixmap(Icon.HISTORY.icon().pixmap(18,18))
    bind_text(q.identity_icon,'最近使用','setToolTip');q.identity_icon.setAccessibleName(t('最近使用'))
    visual.theme.changed.connect(lambda:q.identity_icon.setPixmap(Icon.HISTORY.icon().pixmap(18,18)))
    row.addWidget(q.identity_icon,0,Qt.AlignVCenter)
    name=QLabel('NekoriEmojy',title);name.setProperty('role','brand');name.setFont(visual.font('brand'))
    row.addWidget(name);row.addStretch()
    close=TransparentToolButton(Icon.CLOSE,title);close.setFixedSize(24,24)
    bind_text(close,'关闭','setToolTip');close.clicked.connect(q.hide_panel);row.addWidget(close)
    q.bg_layout.addWidget(title)
    q.search_box=SearchLineEdit(q.bg_widget);q.search_box.setObjectName('quickPanelSearchBox')
    bind_text(q.search_box,'搜索名称、标签或关键词…','setPlaceholderText');q.search_box.textChanged.connect(q._on_search_text_changed)
    bind_text(q.search_box,'支持文件名、标签、分类名称和已保存的表情文字。','setToolTip')
    q.bg_layout.addWidget(q.search_box)
    q.scroll_area=QScrollArea(q.bg_widget);q.scroll_area.setWidgetResizable(True);q.scroll_area.setFrameShape(QScrollArea.NoFrame)
    q.grid_container=QWidget();q.grid_layout=QGridLayout(q.grid_container)
    q.grid_layout.setSpacing(8);q.grid_layout.setContentsMargins(8,10,8,10)
    q.grid_layout.setAlignment(Qt.AlignTop|Qt.AlignHCenter)
    q.scroll_area.setWidget(q.grid_container)
    q.result_surface=Surface('base',q.bg_widget,radius=12)
    sheet=QVBoxLayout(q.result_surface);sheet.setContentsMargins(6,6,6,6)
    sheet.addWidget(q.scroll_area);q.bg_layout.addWidget(q.result_surface,1)
    q.empty_label=translated(QLabel,'暂无最近使用的表情',q.grid_container)
    q.empty_label.setAlignment(Qt.AlignCenter);q.empty_label.hide()
    i18n_engine.language_changed.connect(q._update_i18n_texts)
    q.scroll_area.viewport().installEventFilter(q)
    q.scroll_area.verticalScrollBar().valueChanged.connect(q._on_scroll)
    q._lazy_load_timer=QTimer(q);q._lazy_load_timer.setSingleShot(True);q._lazy_load_timer.timeout.connect(q._apply_lazy_loading)
