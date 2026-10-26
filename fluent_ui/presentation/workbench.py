"""New Softframe workbench composition; the gallery remains its controller.

Glass navigation | opaque workspace -> hierarchy -> attached tabs -> raised
resource sheet. The tag dock is an auxiliary surface inside the sheet. No
storage, selection, navigation or drag decisions are made here.
"""
from PySide6.QtCore import Qt,QTimer,QSize,QRectF
from PySide6.QtGui import QPainter,QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QBoxLayout,QLabel,QSizePolicy
from fluent_ui import visual
from services.i18n import t
from fluent_ui.icons import Icon as I
from fluent_ui.components.controls import TransparentToolButton,SplitPushButton,SearchLineEdit
from fluent_ui.components.navigation import HierarchyLocationHeader,TabStrip,ContentPane,AttachedTabRow,WorkspaceTools
from fluent_ui.components.interaction_controls import IconDropDownButton,ResourceSortIcon,FilterCheckboxFlyout
from fluent_ui.components.panel_host import PanelSplitter
from fluent_ui.components.safe_round_menu import SafeRoundMenu
from qfluentwidgets import Action, IconWidget
from services.i18n import bind_text,translated
from .surfaces import Surface,CommandWell


class HeadingBand(QWidget):
    """The location and current-view commands share one compact working band."""
    def paintEvent(self,event):
        layout=self.layout()
        if not layout or layout.count()<1:return
        rail=layout.itemAt(0).widget()
        if not rail or not rail.isVisible():return
        # The original grey rule remains in the header. Use the free band
        # immediately below it, without moving the title/search or growing it.
        width=max(0,rail.width()-rail.axis_left)*.618
        gap=width*.04
        segment=(width-2*gap)/3
        p=QPainter(self);p.setPen(Qt.NoPen)
        for index,color in enumerate(('#DF52AC','#FFF500','#00E5FF')):
            p.setBrush(QColor(color))
            p.drawRect(QRectF(rail.x()+rail.axis_left+index*(segment+gap),rail.y()+rail.height()+2,segment,2))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        layout=self.layout()
        if not layout or layout.count()<2:return
        rail=layout.itemAt(0).widget()
        narrow=self.width()<610
        layout.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        rail.setMaximumWidth(16777215 if narrow else 250)


def build_workbench(g):
    from fluent_ui.views.gallery_view import CategorySidebar
    g.main_layout=QHBoxLayout(g)
    g.main_layout.setContentsMargins(6,0,6,6);g.main_layout.setSpacing(0)
    g.splitter=PanelSplitter(Qt.Horizontal,g);g.splitter.setHandleWidth(6)
    g._apply_splitter_style()
    g.sidebar=CategorySidebar(g.storage,g)
    g.splitter.addWidget(g.sidebar)

    # The content foundation is a single rounded paper/ink plate. Its inset
    # exposes the glass edge of the window rather than piling up card borders.
    g.right_container=Surface('base',g,radius=visual.WINDOW_RADIUS-6)
    g.right_container.setObjectName('WorkspaceFoundation')
    g.right_layout=QVBoxLayout(g.right_container)
    g.right_layout.setContentsMargins(6,2,6,6);g.right_layout.setSpacing(0)
    g.top_bar=HeadingBand(g.right_container)
    g.top_bar_layout=QHBoxLayout(g.top_bar)
    g.top_bar_layout.setContentsMargins(2,0,2,0);g.top_bar_layout.setSpacing(6)
    g.location_rail=HierarchyLocationHeader(g.top_bar)
    g.location_rail.navigate_requested.connect(g.set_node)
    g.content_count=g.location_rail.count_label
    g.location_rail.setMinimumWidth(190)
    g.top_bar_layout.addWidget(g.location_rail,0,Qt.AlignTop)
    g.right_layout.addWidget(g.top_bar)

    g.tab_row=AttachedTabRow(g.right_container)
    tab_layout=QHBoxLayout(g.tab_row);tab_layout.setContentsMargins(0,0,0,0);tab_layout.setSpacing(0)
    g.category_tabs=TabStrip(g.tab_row,location_divider=True)
    g.category_tabs.currentChanged.connect(g._on_category_tab)
    tab_layout.addWidget(g.category_tabs,1)
    g.tab_row.setFixedHeight(g.category_tabs.height())
    g.right_layout.addWidget(g.tab_row)
    g.content_pane=ContentPane(g.right_container)
    g.content_pane.setProperty('gallery_workspace',True)
    g.content_pane.content_layout.setContentsMargins(1,0,1,1)
    g.right_layout.addWidget(g.content_pane,1)

    from fluent_ui.components.softframe import SoftframeSlider
    from fluent_ui.presentation.glyphs import ClipboardImportIcon,ToolboxIcon
    from services.resource_sort import ResourceSort
    g.search_surface=QWidget(g.top_bar)
    rows=QVBoxLayout(g.search_surface);rows.setContentsMargins(6,21,2,0);rows.setSpacing(8)
    search=QHBoxLayout();search.setSpacing(4)
    g.search_box=SearchLineEdit(g.search_surface)
    g.search_box.setFixedHeight(30)
    bind_text(g.search_box,'搜索名称、标签或关键词…','setPlaceholderText')
    bind_text(g.search_box,'支持文件名、标签、分类名称和已保存的表情文字。','setToolTip')
    g.search_box.setMinimumWidth(90);search.addWidget(g.search_box,1)
    g.btn_filter=TransparentToolButton(I.FILTER,g.search_surface);g.btn_filter.setFixedSize(24,24)
    bind_text(g.btn_filter,'筛选当前视图','setToolTip');g.btn_filter.clicked.connect(g._show_filter_menu)
    search.addWidget(g.btn_filter);rows.addLayout(search)
    g._search_timer=QTimer(g);g._search_timer.setSingleShot(True)
    g._search_timer.timeout.connect(g._execute_search);g.search_box.textChanged.connect(g.set_search_keyword)
    commands=QWidget(g.search_surface);commands.setFixedHeight(32);g.view_commands=commands;row=QHBoxLayout(commands)
    row.setContentsMargins(0,0,0,0);row.setSpacing(4);row.addStretch()
    g.btn_paste=SplitPushButton(ClipboardImportIcon(),'',commands)
    g.btn_paste.button.ghost=True;g.btn_paste.button.setFixedSize(32,32);g.btn_paste.button.setIconSize(QSize(18,18))
    g.btn_paste.dropButton.setIcon(I.IMPORT_MENU);g.btn_paste.dropButton.setFixedSize(32,32);g.btn_paste.dropButton.setIconSize(QSize(18,18));g.btn_paste.layout().setSpacing(4)
    bind_text(g.btn_paste.button,'从剪贴板粘贴表情 (Ctrl+V)','setToolTip')
    bind_text(g.btn_paste.dropButton,'导入表情','setToolTip')
    g.btn_paste.clicked.connect(g.handle_global_paste)
    g.import_menu=SafeRoundMenu(parent=g.btn_paste)
    for text,callback in [('导入文件…',g._pick_import_files),('导入文件夹为分类…',lambda:g.sidebar.import_folder_as_node(g.content_scope_node()))]:
        action=translated(Action,text,parent=g.import_menu);action.triggered.connect(callback);g.import_menu.addAction(action)
    g.btn_paste.setFlyout(g.import_menu);row.addWidget(g.btn_paste)
    g.btn_manage=TransparentToolButton(I.MANAGE,commands);g.btn_manage.setFixedSize(32,32);g.btn_manage.setIconSize(QSize(18,18));g.btn_manage.setCheckable(True)
    bind_text(g.btn_manage,'管理模式','setToolTip');g.btn_manage.clicked.connect(g.toggle_manage_mode);row.addWidget(g.btn_manage)
    g.btn_content_sort=TransparentToolButton(ResourceSortIcon(),commands);g.btn_content_sort.setFixedSize(32,32);g.btn_content_sort.setIconSize(QSize(18,18))
    def cycle_sort():
        modes=list(ResourceSort);g.set_content_sort(modes[(modes.index(ResourceSort(g.content_sort))+1)%len(modes)])
    g.btn_content_sort.clicked.connect(cycle_sort);g._update_resource_sort_label();row.addWidget(g.btn_content_sort)
    rows.addWidget(commands)
    g.filter_flyout=FilterCheckboxFlyout(g.btn_filter)
    g.filter_flyout.changed.connect(g._update_filter);g.filter_flyout.clear_requested.connect(g._clear_filter)
    g.top_bar_layout.addWidget(g.search_surface,1)
    size_host=WorkspaceTools(g.tab_row);size_host.setFixedHeight(38)
    size_row=QHBoxLayout(size_host);size_row.setContentsMargins(6,5,8,5);size_row.setSpacing(0);size_row.setAlignment(Qt.AlignVCenter)
    glyph=IconWidget(I.PHOTO,size_host);glyph.setFixedSize(16,16);bind_text(glyph,'缩略图大小','setToolTip');size_row.addWidget(glyph,0,Qt.AlignVCenter)
    visual.theme.changed.connect(glyph.update)
    g.size_slider=SoftframeSlider(Qt.Horizontal,size_host);g.size_slider.setFixedWidth(88)
    g.size_slider.setRange(60,300);g.size_slider.setSingleStep(10);g.size_slider.setPageStep(10)
    g.size_slider.setValue(g.config.get('thumbnail_size',120));bind_text(g.size_slider,'缩略图大小','setToolTip')
    def resize_tiles(value):
        value=max(60,min(300,round(value/10)*10))
        if g.size_slider.value()!=value:
            g.size_slider.blockSignals(True);g.size_slider.setValue(value);g.size_slider.blockSignals(False)
        if value==g.config.get('thumbnail_size',120):return
        g._commit_thumbnail_size(value)
    g.size_slider.valueChanged.connect(resize_tiles);size_row.addSpacing(8);size_row.addWidget(g.size_slider)
    g.category_tabs.tabBarClicked.connect(lambda index:g._on_category_tab(index) if getattr(g,'_recent_view',False) else None)
    g.btn_recent=TransparentToolButton(I.HISTORY,size_host);g.btn_recent.setFixedSize(26,26);g.btn_recent.setIconSize(QSize(18,18));g.btn_recent.setCheckable(True)
    bind_text(g.btn_recent,'最近使用','setToolTip');g.btn_recent.setAccessibleName(t('最近使用'))
    g.btn_recent.clicked.connect(g.toggle_recent_view)
    size_row.insertWidget(0,g.btn_recent,0,Qt.AlignVCenter);size_row.insertSpacing(1,5)
    tab_layout.addSpacing(8);tab_layout.addWidget(size_host,0,Qt.AlignRight|Qt.AlignBottom)
    g.tab_row.bind_structure(g.category_tabs,size_host)

    g.content_pane.corner_radius=10
    g.workspace=Surface('raised',g.content_pane,radius=9,edge=False)
    g.workspace_layout=QVBoxLayout(g.workspace)
    g.workspace_layout.setContentsMargins(0,0,0,0);g.workspace_layout.setSpacing(0)
    g._build_context_strip();g._build_grid();g._build_command_bar();g._build_tag_panel()
    from fluent_ui.components.feedback import FeedbackHost
    from fluent_ui.components.state_tool_tip_manager import StateToolTipManager
    g.feedback_host=FeedbackHost(g.workspace,g.workspace_layout,before=g.scroll_area,overlay_parent=g.scroll_area.viewport())
    g.feedback_host.dock_to_caption(g.window())
    g.workspace.feedback_host=g.feedback_host
    g.task_status=StateToolTipManager(g.workspace,closable=False)
    g.splitter.addWidget(g.right_container)
    g.splitter.setSizes([max(196,g.config.get('sidebar_width_list',220)),800])
    g.splitter.setCollapsible(0,False);g.splitter.setStretchFactor(0,0);g.splitter.setStretchFactor(1,1)
    g.main_layout.addWidget(g.splitter,1)
    g.splitter.splitterMoved.connect(g._on_splitter_moved)
    g.scroll_area.viewport().installEventFilter(g)
    g.scroll_area.verticalScrollBar().valueChanged.connect(g._on_scroll)
    g.btn_back_top=TransparentToolButton(I.UP,g.scroll_area.viewport());g.btn_back_top.setFixedSize(30,30)
    g.btn_back_top.setProperty('floating',True)
    bind_text(g.btn_back_top,'回到顶部（PgUp） · 到底部（PgDown）','setToolTip')
    g.btn_back_top.clicked.connect(lambda:g.scroll_area.verticalScrollBar().setValue(0));g.btn_back_top.hide()
    g.install_navigation_shortcuts()
    # The app menu is the footer of the navigation, in the same continuous face.
    footer=QWidget(g.sidebar);foot=QHBoxLayout(footer);foot.setContentsMargins(6,2,2,0);foot.setSpacing(2)
    from fluent_ui.presentation.glyphs import BrandLockup
    g.brand_lockup=BrandLockup(footer);foot.addWidget(g.brand_lockup,0,Qt.AlignBottom)
    from fluent_ui.components.update_center import UpdateBadge
    g.btn_update=UpdateBadge(footer)
    foot.addWidget(g.btn_update,0,Qt.AlignVCenter);g.btn_update.hide()
    g.btn_update.refresh()
    foot.addStretch()
    g.btn_settings=TransparentToolButton(I.SETTING,footer);g.btn_settings.setFixedSize(24,24)
    bind_text(g.btn_settings,'设置','setToolTip');g.btn_settings.clicked.connect(g.setting_requested);foot.addWidget(g.btn_settings,0,Qt.AlignBottom)
    g.btn_tools=TransparentToolButton(ToolboxIcon(),footer);g.btn_tools.setFixedSize(24,24)
    bind_text(g.btn_tools,'应用与工具','setToolTip');g.btn_tools.clicked.connect(g._show_tools_menu)
    foot.addWidget(g.btn_tools,0,Qt.AlignBottom);g.sidebar.layout().addWidget(footer)
