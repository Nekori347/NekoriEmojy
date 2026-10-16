"""Continuous navigation surface; mode/sort actions form a separate small row."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QSizePolicy
from fluent_ui import visual
from fluent_ui.icons import Icon as I
from fluent_ui.components.controls import TransparentToolButton
from fluent_ui.components.navigation import CompactTitleLabel,SortCycleButton
from fluent_ui.components.library_tree import LibraryTree
from fluent_ui.components.sidebar_icons import SidebarIcons
from fluent_ui.components.section_index import SectionNavigator,SortProjection
from services.library_index import ROOT
from services.i18n import bind_text,translated
from .surfaces import RuleHeading


def build_sidebar(s):
    layout=QVBoxLayout(s);layout.setContentsMargins(2,4,2,4);layout.setSpacing(2)
    header=QWidget(s);top=QHBoxLayout(header);top.setContentsMargins(2,0,2,2);top.setSpacing(2)
    s.btn_view_mode=TransparentToolButton(I.MENU,header);s.btn_view_mode.setFixedSize(24,24)
    s.btn_view_mode.clicked.connect(s.toggle_presentation);top.addWidget(s.btn_view_mode)
    s.btn_root=TransparentToolButton(header);s.btn_root.setCheckable(True);s.btn_root.setFixedHeight(36)
    s.btn_root.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
    root=QVBoxLayout(s.btn_root);root.setContentsMargins(6,2,2,2);root.setSpacing(0)
    s.root_label=translated(CompactTitleLabel,'全部资源',s.btn_root)
    s.root_count=QLabel('0',s.btn_root);s.root_count.setProperty('role','data')
    s.root_label.setFixedHeight(18)
    s.root_count.setProperty('typography','data_small');s.root_count.setFont(visual.font('data_small'));s.root_count.setFixedHeight(14)
    for label in (s.root_label,s.root_count):label.setAttribute(Qt.WA_TransparentForMouseEvents)
    root.addWidget(s.root_label);root.addWidget(s.root_count)
    s.btn_root.clicked.connect(lambda:s.gallery_view.set_node(ROOT));top.addWidget(s.btn_root,1)
    s.btn_new=TransparentToolButton(I.ADD,header);s.btn_new.setFixedSize(24,24)
    bind_text(s.btn_new,'在当前位置新建分类','setToolTip');s.btn_new.clicked.connect(lambda:s.create_node(s.gallery_view.current_node))
    s.btn_sort=SortCycleButton('分类显示排序',header);s.btn_sort.mode_changed.connect(lambda mode:s.set_display_sort(mode.display_mode))
    top.addWidget(s.btn_new);top.addWidget(s.btn_sort);layout.addWidget(header)
    body=QWidget(s);row=QHBoxLayout(body);row.setContentsMargins(0,2,0,0);row.setSpacing(0)
    views=QWidget(body);stack=QVBoxLayout(views);stack.setContentsMargins(0,0,0,0);stack.setSpacing(0)
    s.tree=LibraryTree(s.storage,s)
    mode=SortProjection.from_display(s.config.get('sidebar_sort','manual'))
    s.tree.display_sort=mode.display_mode;s.btn_sort.set_mode(mode)
    for signal,callback in [
        ('node_selected',s._on_node_selected),('node_reparented',s._on_node_reparented),
        ('resources_dropped',s._on_resources_dropped),('files_dropped',s._on_files_dropped),
        ('node_menu_requested',s._show_node_menu),('blank_menu_requested',s._show_root_menu),
        ('tags_dropped',s.gallery_view.apply_tags_to_category),('nodes_dropped',s._on_nodes_dropped)]:
        getattr(s.tree,signal).connect(callback)
    s.tree.set_icon_size(s.config.get('sidebar_icon_size',20))
    s.tree.setColumnHidden(1,True);s.tree.setColumnHidden(2,True)
    s.icons=SidebarIcons(s.tree,s.config,s)
    stack.addWidget(s.tree,1);stack.addWidget(s.icons,1)
    s.index_view=SectionNavigator(body);s.index_view.set_orientation(Qt.Vertical)
    s.index_view.section_requested.connect(s._jump_section)
    row.addWidget(views,1);row.addWidget(s.index_view,alignment=Qt.AlignTop)
    layout.addWidget(body,1)
    s.tree.currentItemChanged.connect(lambda *_:s.icons.canvas.update())
    s.apply_presentation();s.update_theme()
