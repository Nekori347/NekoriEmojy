"""Main library view: node navigation, mixed node/resource grid, selection, drops.

The view works directly with stable node IDs and the interleaved content order
from the library index. Category nodes and resources share one grid and one
manual order; the left tree is a projection of the same node tree.
"""
from services.i18n import t, bind_text, translated
import json
import os

from PySide6.QtWidgets import (
    QWidget, QGridLayout, QApplication, QHBoxLayout, QVBoxLayout, QLabel,
    QFrame, QScrollArea, QSplitter, QFileDialog, QSizePolicy,
)
from PySide6.QtCore import Qt, QEvent, QTimer, QThread, Signal, QPoint, QRect, QSize
from PySide6.QtGui import QCursor, QIcon, QShortcut, QKeySequence

from qfluentwidgets import ScrollArea, InfoBar, InfoBarPosition, RoundMenu, Action, BodyLabel
from fluent_ui.components.controls import SplitPushButton
from fluent_ui.components.controls import PushButton, TransparentToolButton
from fluent_ui.icons import Icon as FIF

from fluent_ui.components.safe_round_menu import SafeRoundMenu as RoundMenu
from fluent_ui.components.emoji_card import EmojiCard
from fluent_ui.components.node_card import NodeCard, NODE_MIME, RESOURCE_MIME
from fluent_ui.components.library_tree import LibraryTree, ALL_RESOURCES
from fluent_ui.components.hover_preview import HoverPreviewPopup
from fluent_ui.components.hover_preview_controller import HoverPreviewController
from fluent_ui.components.keycap_label import KeycapLabel
from fluent_ui.components import dialogs
from fluent_ui.components.drop_contract import (
    APPLY_TAG, APPLY_TAG_TO_SUBTREE, APPEND, COPY, EdgeAutoScroller, DropFeedback, DropTarget, IMPORT,
    INSERT_AFTER, INSERT_BEFORE, INTO, INVALID, INVALID_TARGET, MOVE, TAG_MIME,
    axis_ratio, edge_placement, parse_list_payload, parse_node_payload,
    viewport_rect, tag_drop_target,
)
from fluent_ui.components.tag_model import TagModel
from fluent_ui.components.tag_panel import TagPanel
from fluent_ui.components.panel_host import PanelSplitter, TagPanelHost
from fluent_ui.components.sidebar_icons import SidebarIcons, SidebarPresentationMode
from fluent_ui.components.interaction_controls import IconDropDownButton, ResourceSortIcon, DropDownButton, FilterCheckboxFlyout
from fluent_ui.components.section_index import SectionIndexModel, SectionNavigator, SortProjection
from services.i18n import t, i18n_engine, bind_text, translated
from fluent_ui import visual
from fluent_ui.components.navigation import TabStrip, ContentPane, HierarchyLocationHeader, SortCycleButton, AttachedTabRow
from services.library_index import ROOT
from services.action_policy import ActionContext, ActionPolicy
from services.resource_sort import ResourceSort
from services.send_target import SendTargetService, SendResult

FAILED_RETENTION_DAYS = 7
CLEANUP_THROTTLE_HOURS = 1


class DownloadThread(QThread):
    finished = Signal(bool, str, str, str)  # success, temp_filepath, error_msg, url

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        import urllib.request
        import urllib.error
        import tempfile
        import os
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content_type = response.headers.get('Content-Type', '').lower()
                is_image = content_type.startswith('image/')

                if not is_image:
                    import urllib.parse
                    parsed_url = urllib.parse.urlparse(self.url)
                    _, ext = os.path.splitext(parsed_url.path)
                    if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                        is_image = True

                if not is_image:
                    self.finished.emit(False, "", t("该链接不是有效的表情"), self.url)
                    return

                content = response.read()

                fd, temp_path = tempfile.mkstemp(suffix=".tmp")
                with os.fdopen(fd, 'wb') as f:
                    f.write(content)

                self.finished.emit(True, temp_path, "", self.url)
        except Exception as e:
            self.finished.emit(False, "", str(e), self.url)


class ImportThread(QThread):
    """Background import. Every source keeps its own target node and position."""

    progress = Signal(int, int)
    finished = Signal(int, int, int)  # saved, skipped, failed

    def __init__(self, sources, storage, target_node, delete_after=False, parent=None,
                 insert_position=None):
        super().__init__(parent)
        self.sources = list(sources)
        self.storage = storage
        self.target_node = target_node or ALL_RESOURCES
        self.insert_position = insert_position
        self.delete_after = delete_after
        import threading
        self.cancel_event=threading.Event();self.job_id='';self.duplicate_resolver=None
        self.result_paths=[];self.errors=[];self.cancelled_count=0
        self.operation=None;self.result=None
        self.duplicate_batch_resolver=None;self.kept_count=0

    def cancel(self):self.cancel_event.set()

    def _handle_failed_import(self, filepath):
        import shutil
        from datetime import datetime
        if self.delete_after and os.path.exists(filepath):
            abs_filepath = os.path.normcase(os.path.abspath(filepath))
            abs_inbox = os.path.normcase(os.path.abspath(self.storage.inbox_dir))
            if abs_filepath.startswith(abs_inbox) and not abs_filepath.startswith(
                    os.path.normcase(os.path.abspath(self.storage.inbox_failed_dir))):
                try:
                    filename = os.path.basename(filepath)
                    target_path = os.path.join(self.storage.inbox_failed_dir, filename)
                    if os.path.exists(target_path):
                        name, ext = os.path.splitext(filename)
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        target_path = os.path.join(self.storage.inbox_failed_dir, f"{name}_{timestamp}{ext}")
                    shutil.move(filepath, target_path)
                except Exception as e:
                    print(f"[ERROR] 移动失败文件到 failed 目录失败: {e}")
            else:
                try:
                    os.remove(filepath)
                except Exception:
                    pass

    def run(self):
        from services.resource_import import ImportTarget
        from services.resource_import import ImportSkipped,ImportDeferred
        from PySide6.QtGui import QImage
        saved_count = skipped_count = failed_count = 0
        total = len(self.sources)
        context=self.storage.import_context
        context.job_id=self.job_id;context.duplicate_resolver=self.duplicate_resolver
        context.cancelled=self.cancel_event.is_set
        if self.operation is not None:
            self._run_operation(context)
            return
        pending=[];temporaries=[]
        context.deferred_duplicates=pending if self.duplicate_batch_resolver else None
        for i, source in enumerate(self.sources):
            if self.cancel_event.is_set():break
            temporary=None;pending_before=len(pending)
            try:
                target = ImportTarget(self.target_node, None if self.insert_position is None else self.insert_position+i)
                if isinstance(source,str) and source.startswith(('https://','http://')):
                    response=[];download=DownloadThread(source)
                    download.finished.connect(lambda *args:response.append(args));download.run()
                    if not response or not response[0][0]:raise RuntimeError(response[0][2] if response else 'Download failed')
                    temporary=source=response[0][1]
                if isinstance(source,QImage):
                    saved,duplicate=self.storage.save_image(source,target)
                    if not saved:raise RuntimeError('Image could not be saved')
                    self.result_paths.append(saved);skipped_count+=int(duplicate);saved_count+=int(not duplicate)
                else:
                    result = self.storage.import_paths([source], target)
                    self.result_paths.extend(result.paths)
                    self.cancelled_count+=result.cancelled
                    saved_count += result.imported;skipped_count += result.duplicates;failed_count += len(result.errors)
                    self.errors.extend(result.errors.values())
                    if result.errors:self._handle_failed_import(source)
                    elif self.delete_after and not result.cancelled and len(pending)==pending_before and os.path.isfile(source):os.remove(source)
            except ImportDeferred:pass
            except ImportSkipped:self.cancelled_count+=1
            except InterruptedError:break
            except Exception as exc:
                self.errors.append(str(exc))
                if isinstance(source,str):self._handle_failed_import(source)
                failed_count += 1
            finally:
                if temporary:
                    from pathlib import Path
                    temporaries.append(temporary)
                context.normalized=None
            self.progress.emit(i + 1, total+1)
        context.deferred_duplicates=None
        try:
            if pending and not self.cancel_event.is_set():
                self.staged_counts=(saved_count,skipped_count,failed_count)
                decisions=self.duplicate_batch_resolver(pending)
                for candidate,decision in zip(pending,decisions):
                    if self.cancel_event.is_set():break
                    if decision=='skip':self.cancelled_count+=1;continue
                    context.duplicate_resolver=lambda old,new,choice=decision:choice
                    try:
                        destination=candidate.target
                        if candidate.before is not None:
                            position=next((i for i,e in enumerate(self.storage.index.content(destination.parent_node))
                                           if (e['kind'],e['id'])==candidate.before),None)
                            destination=ImportTarget(destination.parent_node,position)
                        if decision=='reuse':
                            with self.storage.lock:
                                self.storage.importer._validate_target(destination)
                                if not self.storage.index.resource(candidate.existing):raise FileNotFoundError(candidate.existing)
                                saved,duplicate=self.storage.importer._accept(candidate.existing,True,os.path.basename(candidate.existing),destination)
                            self.storage.importer._notify(saved,True)
                        elif isinstance(candidate.source,QImage):saved,duplicate=self.storage.save_image(candidate.source,destination)
                        else:saved,duplicate=self.storage.save_file(candidate.source,strict=True,target=destination)
                        self.result_paths.append(saved);skipped_count+=int(duplicate);saved_count+=int(not duplicate)
                        self.kept_count+=int(decision=='keep' and not duplicate)
                        if self.delete_after and isinstance(candidate.source,str) and os.path.isfile(candidate.source):os.remove(candidate.source)
                    except InterruptedError:break
                    except Exception as exc:self.errors.append(str(exc));failed_count+=1
        finally:
            for temporary in temporaries:
                from pathlib import Path
                Path(temporary).unlink(missing_ok=True)
            context.job_id='';context.duplicate_resolver=None;context.cancelled=None;context.normalized=None
        self.finished.emit(saved_count, skipped_count, failed_count)

    def _run_operation(self,context):
        context.accepted=[];context.skipped=0
        before={r['id'] for r in self.storage.index.resources()}
        failed=0
        def progress(done,total,message=''):
            if self.cancel_event.is_set():raise InterruptedError()
            self.progress.emit(done,total)
        try:self.result=self.operation(progress)
        except InterruptedError:pass
        except Exception as exc:
            if not self.cancel_event.is_set():failed=1;self.errors.append(str(exc))
        finally:
            accepted=context.accepted;self.result_paths=list(dict.fromkeys(path for path,_ in accepted))
            self.cancelled_count=context.skipped
            saved=len({r['id'] for path in self.result_paths if (r:=self.storage.index.resource(path))}-before)
            duplicates=sum(int(duplicate) for _,duplicate in accepted)
            if isinstance(self.result,dict):
                failed+=self.result.get('skipped',0);self.errors.extend(self.result.get('errors',[]))
            context.job_id='';context.duplicate_resolver=None;context.cancelled=None;context.normalized=None;context.accepted=None;context.skipped=0
        self.finished.emit(saved,duplicates,failed)


class FilterState:
    """Unified resource filter state."""

    def __init__(self):
        self.no_tag = False
        self.unclassified = False
        self.is_gif = False
        self.is_static = False
        self.missing = False

    def is_active(self):
        return any((self.no_tag, self.unclassified, self.is_gif, self.is_static, self.missing))


class Placement:
    """Where a content-area action should land.

    `parent` is the container the point belongs to (the deepest visible inline
    node when the point is inside one), `position` is an index into that
    container's canonical content stream, and `anchor` / `after` keep the entry
    the point was measured against. `exact` is False when the visible order no
    longer matches the manual order, in which case callers must append instead
    of writing an index the user never chose.
    """

    __slots__ = ('parent', 'position', 'anchor', 'after', 'exact')

    def __init__(self, parent, position=None, anchor=None, after=False, exact=True):
        self.parent = parent
        self.position = position
        self.anchor = anchor
        self.after = after
        self.exact = exact

    @property
    def append(self):
        return not self.exact or self.position is None

    def resolved_position(self):
        """Canonical insertion index, or None to append."""
        return None if self.append else self.position


from fluent_ui.presentation.surfaces import Surface

class CategorySidebar(Surface):
    """Left navigation hosting the real category node tree."""

    def __init__(self, storage, parent=None):
        super().__init__('navigation', parent, radius=12, edge=False)
        self.storage, self.gallery_view = storage, parent
        self.config = parent.config
        self.setObjectName('CategorySidebar')
        self.setMinimumWidth(172)
        self.setMaximumWidth(420)
        from fluent_ui.presentation.sidebar import build_sidebar
        build_sidebar(self)

    # -- compatibility surface ----------------------------------------
    def refresh_list(self, select_category=None):
        node_id = self._as_node_id(select_category)
        self.tree.set_icon_size(self.config.get("sidebar_icon_size", 20) if self.config else 20)
        self.tree.refresh(select=node_id)
        if hasattr(self, 'icons'):
            self.icons.refresh()
            self._update_section_index()

    def update_theme(self):
        self.setStyleSheet(visual.sidebar_style())
        self.tree.viewport().setAutoFillBackground(False)
        self.tree.viewport().setStyleSheet('background:transparent;')
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        from PySide6.QtGui import QIcon
        from fluent_ui.components.node_card import render_node_icon
        rows=QTreeWidgetItemIterator(self.tree);updated={}
        while rows.value():
            item=rows.value();record=self.tree._node_records.get(item.data(0,Qt.UserRole))
            if record and not record.get('icon'):
                item.setIcon(0,QIcon(render_node_icon(None,record,self.tree.iconSize().width())))
            if record:updated[record['id']]=item.icon(0)
            rows+=1
        if hasattr(self,'icons'):
            self.icons.canvas.items=[(key,name,updated.get(key,icon),depth,group) for key,name,icon,depth,group in self.icons.canvas.items]
        self.tree.viewport().update()
        if hasattr(self, 'icons'):
            self.icons.canvas.update()

    def apply_presentation(self):
        mode = SidebarPresentationMode(self.config.get('sidebar_mode', 'tree'))
        self.btn_view_mode.setIcon(FIF.MENU if mode == SidebarPresentationMode.TREE else FIF.TILES)
        target = '分类树' if mode == SidebarPresentationMode.TREE else '分类图标'
        bind_text(self.btn_view_mode, target, 'setToolTip')
        bind_text(self.btn_view_mode, target, 'setAccessibleName')
        self.tree.set_icon_size(self.config.get('sidebar_icon_size', 20))
        self.icons.canvas.relayout()
        self.tree.setVisible(mode == SidebarPresentationMode.TREE)
        self.icons.setVisible(mode == SidebarPresentationMode.CATEGORIZED_ICONS)
        self._update_section_index()

    def toggle_presentation(self):
        mode = 'categorized_icons' if self.config.get('sidebar_mode', 'tree') == 'tree' else 'tree'
        self.set_presentation(mode)

    def set_presentation(self, mode):
        self.config.set('sidebar_mode', mode)
        center = getattr(self.window(), 'setting_interface', None)
        if center is not None:
            center.sync_external_preference('sidebar_mode', mode)
        self.apply_presentation()

    def sync_root(self, count=None):
        if count is not None:
            self.root_count.setText(str(count))
        self.btn_root.setChecked(self.gallery_view.current_node == ROOT)
        bind_text(self.btn_root, t('表情库全部表情 · {value_0} 项').format(value_0=self.root_count.text()), 'setToolTip')
        self.btn_root.setAccessibleName(self.btn_root.toolTip())

    def set_display_sort(self, mode):
        projection = SortProjection.from_display(mode)
        mode = projection.display_mode
        self.config.set('sidebar_sort', projection.value)
        self.tree.set_display_sort(mode)
        self.btn_sort.set_mode(mode)
        self.icons.refresh()
        self._update_section_index()

    def _update_section_index(self):
        if not hasattr(self, 'index_view'):
            return
        projection = self.tree.section_projection
        self.index_view.set_model(SectionIndexModel(projection))
        self.index_view.setVisible(bool(projection.sections))

    def _jump_section(self, section):
        item = self.tree.section_headers.get(section)
        if item is None:
            return
        if self.tree.isVisible():
            self.tree.scrollToItem(item, self.tree.ScrollHint.PositionAtTop)
        else:
            rect = self.icons.canvas.section_headers.get(section)
            if rect is not None:
                self.icons.verticalScrollBar().setValue(rect.top())

    def set_active_category(self, category):
        self.tree.select_node(self._as_node_id(category))

    def _as_node_id(self, value):
        if not value or value in ("全部表情", "全部资源"):
            return ALL_RESOURCES
        labels = self.storage.category_labels()
        if value in labels:
            return labels[value]
        return value

    # -- navigation ----------------------------------------------------
    def _on_node_selected(self, node_id):
        if self.gallery_view:
            self.gallery_view.set_node(node_id)

    def _on_node_reparented(self, node_id, parent_id, position):
        self._on_nodes_dropped([node_id], parent_id, position)

    def _on_nodes_dropped(self, node_ids, parent_id, position):
        old_parents = {self.tree._parent_of(node_id) for node_id in node_ids}
        try:
            self.storage.move_nodes(node_ids, parent_id, position)
        except (KeyError, ValueError) as exc:
            self._error(t('无法移动分类'), str(exc))
            return
        self.tree.patch_nodes(node_ids, parent_id)
        self.icons.refresh()
        self._update_section_index()
        self.gallery_view.refresh_content_incremental(reason='structure', parents=old_parents | {parent_id})

    def _on_resources_dropped(self, node_id, paths, global_pos):
        if self.gallery_view:
            self.gallery_view.request_resource_drop(paths, node_id, global_pos=global_pos)

    def _on_files_dropped(self, node_id, paths):
        if self.gallery_view:
            self.gallery_view.import_paths_to(paths, node_id)

    def _error(self, title, content):
        if self.gallery_view:
            self.gallery_view.show_error(title, content)

    # -- node operations ----------------------------------------------
    def create_node(self, parent_id, position=None):
        name, ok = dialogs.prompt_text(
            self.window(), t("新建分类"), t("分类名称"), "",
            hint=t("分类是逻辑关系，不会创建或移动磁盘目录。"), code="NODE/NEW")
        if not ok or not name.strip():
            return
        try:
            self.storage.create_node(name.strip(), parent_id or ALL_RESOURCES,
                                     position=position)
        except ValueError as exc:
            self._error("创建失败", str(exc))
            return
        self.refresh_list(self.tree.current_node_id)
        if self.gallery_view:
            self.gallery_view.refresh_content_incremental(reason='create_node')
            self.gallery_view.show_success(t("分类已创建"), name.strip(), quiet=True)

    def rename_node(self, node_id):
        node = self.storage.node(node_id)
        if not node or node_id == ROOT:
            return
        name, ok = dialogs.prompt_text(self.window(), t("重命名分类"), t("分类名称"), node["name"], ok_text=t('重命名'),code="NODE/RENAME")
        if not ok or not name.strip() or name.strip() == node["name"]:
            return
        try:
            self.storage.rename_node(node_id, name.strip())
        except ValueError as exc:
            self._error("重命名失败", str(exc))
            return
        self.refresh_list(self.tree.current_node_id)
        if self.gallery_view:
            self.gallery_view.refresh_content_incremental(reason='rename_node')

    def set_node_icon(self, node_id):
        if not self.storage.index.node(node_id):
            return
        menu = RoundMenu(parent=self)
        action_emoji = translated(Action, "使用 Emoji 图标", parent=menu)
        action_emoji.triggered.connect(lambda: self._set_emoji_icon(node_id))
        menu.addAction(action_emoji)
        action_image = translated(Action, "使用本地表情…", parent=menu)
        action_image.triggered.connect(lambda: self._set_image_icon(node_id))
        menu.addAction(action_image)
        menu.addSeparator()
        action_reset = translated(Action, "恢复默认图标", parent=menu)
        action_reset.triggered.connect(lambda: self._reset_icon(node_id))
        menu.addAction(action_reset)
        menu.exec(QCursor.pos())

    def _set_emoji_icon(self, node_id):
        current = (self.storage.node(node_id) or {}).get("icon", "")
        text, ok = dialogs.prompt_text(self.window(), t("分类图标"), t("输入一个 Emoji"), current, code="NODE/ICON")
        if ok:
            self.storage.set_node_icon(node_id, text.strip())
            self._refresh_node_icon(node_id)

    def _set_image_icon(self, node_id):
        path, _ = QFileDialog.getOpenFileName(
            self.window(), t("选择分类图标"), "", t("表情 (*.png *.jpg *.jpeg *.gif *.webp *.bmp)"))
        if not path:
            return
        self.storage.set_node_icon(node_id, path)
        self._refresh_node_icon(node_id)

    def _reset_icon(self, node_id):
        self.storage.set_node_icon(node_id, "")
        self._refresh_node_icon(node_id)

    def _refresh_node_icon(self, node_id):
        self.refresh_list(self.tree.current_node_id)
        if self.gallery_view:
            parent = (self.storage.node(node_id) or {}).get('parent_id') or ROOT
            self.gallery_view.refresh_content_incremental(reason='node_icon', parents={parent})

    def _parent_of(self, node_id):
        node = self.storage.node(node_id)
        return (node or {}).get('parent_id') or ALL_RESOURCES

    def _sibling_slot(self, node_id, mode):
        """Insertion index next to `node_id` among its siblings."""
        siblings = [entry['id'] for entry in self.storage.entries_of(self._parent_of(node_id))
                    if entry['kind'] == 'node']
        try:
            index = siblings.index(node_id)
        except ValueError:
            return None
        return index + (1 if mode == 'after' else 0)

    def import_folder_as_node(self, parent_id):
        directory = QFileDialog.getExistingDirectory(self.window(), t("选择要导入为分类的文件夹"), "")
        if not directory:
            return
        if self.gallery_view:
            self.gallery_view.import_paths_to([directory], parent_id or ALL_RESOURCES)

    def delete_node(self, node_id):
        node = self.storage.node(node_id)
        if not node:
            return
        stats = self.storage.node_counts().get(node_id, {"resources": 0, "children": 0})
        confirmed = dialogs.confirm(
            self.window(), t("删除分类"),
            t('删除分类“{value_0}”？').format(value_0=node['name']),
            ok_text=t("删除"), danger=True, code="NODE/DELETE",
            hint=(t('分类本身将被删除，表情文件不会删除。\n其下 {child_count} 个子分类将提升到上一级。\n直接属于该分类的 {emote_count} 张表情将移出分类。').format(child_count=stats['children'], emote_count=stats['resources'])))
        if not confirmed:
            return
        self.storage.delete_node(node_id)
        if self.gallery_view and self.gallery_view.current_node == node_id:
            self.gallery_view.set_node(ALL_RESOURCES)
        self.refresh_list(self.tree.current_node_id)
        if self.gallery_view:
            self.gallery_view.show_success(t("分类已删除"), quiet=True)

    def export_node(self, node_id):
        from services.exchange_export import ExchangeExportService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        node = self.storage.node(node_id)
        directory = QFileDialog.getExistingDirectory(self.window(), t('导出“{value_0}”到').format(value_0=node['name']), "")
        if not directory:
            return
        target = os.path.join(directory, node["name"] + ".zip")
        service = ExchangeExportService(storage=self.storage)
        try:
            labels = {v: k for k, v in self.storage.category_labels().items()}
            run_exchange_task(self.window(), "正在导出分类",
                              lambda progress: service.export_zip(target, [labels.get(node_id, node["name"])], progress))
            if self.gallery_view:
                self.gallery_view.show_success(t("导出完成"), target)
        except Exception as exc:
            self._error("导出失败", str(exc))

    def _show_node_menu(self, node_id, global_pos, mode='into'):
        menu = RoundMenu(parent=self)
        action_open = translated(Action, "打开", parent=menu)
        action_open.triggered.connect(lambda: (self.tree.select_node(node_id), self._on_node_selected(node_id)))
        menu.addAction(action_open)
        menu.addSeparator()

        if mode in ('before', 'after'):
            # Right-clicking the gap above or below a row means "a sibling
            # here", not "a child of this category".
            sibling = translated(
                Action, '在此新建同级分类' if mode == 'before' else '在下方新建同级分类',
                parent=menu)
            sibling.triggered.connect(
                lambda: self.create_node(self._parent_of(node_id), position=self._sibling_slot(node_id, mode)))
            menu.addAction(sibling)

        action_child = translated(Action, "新建子分类", parent=menu)
        action_child.triggered.connect(lambda: self.create_node(node_id))
        menu.addAction(action_child)

        action_rename = translated(Action, "重命名…", parent=menu)
        action_rename.triggered.connect(lambda: self.rename_node(node_id))
        menu.addAction(action_rename)

        action_icon = translated(Action, "设置分类图标…", parent=menu)
        action_icon.triggered.connect(lambda: self.set_node_icon(node_id))
        menu.addAction(action_icon)

        action_import = translated(Action, "导入文件夹到此处…", parent=menu)
        action_import.triggered.connect(lambda: self.import_folder_as_node(node_id))
        menu.addAction(action_import)

        menu.addSeparator()
        action_export = translated(Action, "导出此分类为表情合集…", parent=menu)
        action_export.triggered.connect(lambda: self.export_node(node_id))
        menu.addAction(action_export)

        menu.addSeparator()
        action_delete = translated(Action, "删除分类", parent=menu)
        action_delete.triggered.connect(lambda: self.delete_node(node_id))
        menu.addAction(action_delete)
        menu.exec(global_pos)

    def _show_root_menu(self, global_pos):
        menu = RoundMenu(parent=self)
        action_new = translated(Action, "新建根级分类", parent=menu)
        action_new.triggered.connect(lambda: self.create_node(ALL_RESOURCES))
        menu.addAction(action_new)
        action_import = translated(Action, "导入文件夹为分类…", parent=menu)
        action_import.triggered.connect(lambda: self.import_folder_as_node(ALL_RESOURCES))
        menu.addAction(action_import)
        menu.exec(global_pos)


class GalleryInterface(QWidget):
    """Library view: left node tree + right mixed content grid."""

    setting_requested = Signal()
    exchange_requested = Signal()
    similarity_requested = Signal()
    qq_requested = Signal()
    tg_requested = Signal()
    about_requested = Signal()
    hide_after_paste_requested = Signal()
    send_finished = Signal(object)

    def __init__(self, storage_service, clipboard_service, config_service, parent=None, *, send_target_service=None):
        super().__init__(parent=parent)
        self.storage = storage_service
        self.clipboard = clipboard_service
        self.config = config_service
        self.send_target_service = send_target_service or SendTargetService(self)
        self.last_send_result = None
        self.setObjectName("GalleryInterface")

        self._view_state_key = os.path.normcase(os.path.abspath(self.storage.library_root))
        self._saved_view_state = self.config.get('library_view_states', {}).get(self._view_state_key, {})
        self._legacy_expanded_nodes = set(self._saved_view_state.get('inline_expanded', []))
        self._expanded_by_scope = {key: set(value) for key, value in self._saved_view_state.get('inline_expanded_by_scope', {}).items()}
        # Session position is restored from the saved working state; the
        # *transient* side of a session (search, filter, management mode,
        # selection) is deliberately not, and starts clean on every launch.
        self._initial_anchor = self._decode_anchor(self._saved_view_state.get('gallery_anchor'))
        self._live_anchor = self._initial_anchor
        self._location_anchors = dict(self._saved_view_state.get('gallery_anchors', {}))
        # The saved scroll is kept separately from the live one: the tree is
        # rebuilt during start-up and would otherwise overwrite it before the
        # window has a scroll range to restore it into.
        self._saved_sidebar_scroll = self._saved_view_state.get('sidebar_scroll')
        self._sidebar_scroll = self._saved_sidebar_scroll or 0
        self._selection_parents = {}
        self.return_child_hint = None  # transient, one-shot; never part of Session
        self.current_node = self._saved_view_state.get('location', ALL_RESOURCES)
        if not self.storage.index.node(self.current_node):
            self.current_node = ALL_RESOURCES
        self.active_view_node = self._saved_view_state.get('active_relative_view_node_id', self.current_node)
        if self.content_scope_node() != self.active_view_node:
            self.active_view_node = self.current_node
            self._initial_anchor = self._decode_anchor(self._location_anchors.get(self.current_node))
            self._live_anchor = self._initial_anchor
        self._activate_inline_scope()
        self.current_category = "全部表情"
        self.search_keyword = ""
        self.filter_state = FilterState()
        self.active_tags = set()
        self.mode = "normal"
        self.is_selection_mode = False
        self.selected_keys = set()
        self._last_clicked_key = None
        self._shift_anchor = None
        self._shift_touched = set()
        self._inbox_scanning = False
        self._last_cleanup_time = 0

        self._responsive_layout_timer = QTimer(self)
        self._responsive_layout_timer.setSingleShot(True)
        self._responsive_layout_timer.setInterval(0)
        self._responsive_layout_timer.timeout.connect(self._trigger_responsive_layout)

        from fluent_ui.components.gallery_model import GalleryEntryModel
        self.entry_model = GalleryEntryModel(self.storage)
        self.tag_model = TagModel(self.storage)
        self._entries = []
        # Signature of the view the current cards were built for; an incremental
        # update is only valid while it is unchanged.
        self._view_signature_at_build = None
        self._display_mode = "mixed"
        # Manual order is canonical; a display sort is temporary and never
        # writes back, so position-level actions must fall back to append.
        self.content_sort = ResourceSort(self.config.get('resource_sort', 'manual')).value
        self._loaded_count = 0
        self._is_loading = False
        self._target_load_count = 0
        self._all_card_widgets = []
        self._import_info_bar = None
        self.LAYOUT_TOP_MARGIN = 16
        self.LAYOUT_SPACING = 10

        self._init_ui()
        QApplication.clipboard().dataChanged.connect(self._refresh_paste_availability)
        QApplication.instance().applicationStateChanged.connect(self._on_application_state_changed)
        self._refresh_paste_availability()

        self.preview_popup = HoverPreviewPopup(self)
        self.preview_controller = HoverPreviewController(
            self, self.preview_popup, self.scroll_area.viewport(), parent=self)
        self.feedback_host.obstruction_changed.connect(self.preview_controller.cancel)
        self.apply_preview_position()
        self.preview_controller.set_delay(self.config.get("preview_delay", 500))

        self.focus_timer = QTimer(self)
        self.focus_timer.timeout.connect(self.track_active_window)
        self.focus_timer.start(500)

        self.download_threads = []
        self.import_thread = None
        self.setAcceptDrops(True)

        self._lazy_load_timer = QTimer(self)
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.timeout.connect(self._apply_lazy_loading)

        self._saved_scroll_position = 0
        self.sidebar.tree.itemExpanded.connect(lambda _: self._save_view_state())
        self.sidebar.tree.itemCollapsed.connect(lambda _: self._save_view_state())
        # Tracked in memory: writing the session file on every wheel tick would
        # turn scrolling the sidebar into a stream of disk writes.
        self.sidebar.tree.verticalScrollBar().valueChanged.connect(self._remember_sidebar_scroll)
        # Loading belongs to startup/mutations, never to palette refresh.
        self.sidebar.refresh_list(self.current_node)
        self.refresh_content()
        self.storage.availability.changed.connect(self._availability_changed)
        self.storage.recent_changed.connect(self._recent_changed)
        from services.ocr_service import ocr_service
        self.ocr=ocr_service(self.storage)
        self._ocr_paths=set()
        self._ocr_refresh_timer=QTimer(self)
        self._ocr_refresh_timer.setSingleShot(True);self._ocr_refresh_timer.setInterval(600)
        self._ocr_refresh_timer.timeout.connect(self._refresh_ocr_results)
        self.ocr.text_changed.connect(self._ocr_text_changed)
        from fluent_ui.components.import_queue import import_queue
        self.imports=import_queue(self.storage)
        self._task_refresh_timer=QTimer(self);self._task_refresh_timer.setSingleShot(True);self._task_refresh_timer.setInterval(80)
        self._task_refresh_timer.timeout.connect(self._sync_background_tasks)
        self.imports.changed.connect(self._schedule_task_refresh)
        self.ocr.changed.connect(self._schedule_task_refresh)
        self.imports.files_finished.connect(self._queued_files_finished)
        visual.theme.changed.connect(self.refresh_theme)
        i18n_engine.language_changed.connect(self.refresh_texts)

    # ==================================================================
    # UI construction
    # ==================================================================
    def _schedule_task_refresh(self, *_):
        self._task_refresh_timer.start()

    def _init_ui(self):
        from fluent_ui.presentation.workbench import build_workbench
        build_workbench(self)

    def _apply_splitter_style(self):
        """The sidebar divider keeps its 10px hit area; this only marks it.

        The width persistence, the stretch factors and the splitter itself are
        untouched -- a wider invisible handle with no feedback just reads as a
        dead gap between two panels.
        """
        sheet="QSplitter::handle { background: transparent; }"
        if self.splitter.styleSheet()!=sheet:self.splitter.setStyleSheet(sheet)


    def _refresh_paste_availability(self):
        self.btn_paste.button.setEnabled(bool(self.clipboard.has_importable_data(self.storage.SUPPORTED_FORMATS)))

    def _on_application_state_changed(self, state):
        if state == Qt.ApplicationActive:
            self._refresh_paste_availability()


    def _pick_import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, t("导入表情"), "", t("表情 (*.png *.apng *.jpg *.jpeg *.gif *.webp *.bmp *.tiff *.tgs *.webm)"))
        if paths:
            self.import_paths_to(paths, self.content_scope_node())

    def _build_context_strip(self):
        self.context_strip = QWidget(self.right_container)
        self.context_strip.setObjectName("ContextStrip")
        self.context_strip.setFixedHeight(32)
        self.context_strip.setStyleSheet(visual.strip_style())
        outer = QHBoxLayout(self.context_strip)
        outer.setContentsMargins(14, 3, 14, 3)
        outer.setSpacing(8)

        self.chip_area = QScrollArea(self.context_strip)
        self.chip_area.setWidgetResizable(True)
        self.chip_area.setFrameShape(QFrame.NoFrame)
        self.chip_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chip_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chip_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.chip_container = QWidget()
        self.chip_container.setStyleSheet("background: transparent;")
        self.chip_layout = QHBoxLayout(self.chip_container)
        self.chip_layout.setContentsMargins(0, 0, 0, 0)
        self.chip_layout.setSpacing(6)
        self.chip_area.setWidget(self.chip_container)
        outer.addWidget(self.chip_area, stretch=1)

        self.content_pane.content_layout.addWidget(self.context_strip)

    def _build_grid(self):
        self.scroll_area = QScrollArea(self.right_container)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Keep the narrow vertical gutter even when the content fits. A dock
        # animation can cross the overflow threshold; AsNeeded changes the
        # viewport width and shifts every centered resource row sideways.
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        self.grid_container = QWidget()
        self.grid_container.setAcceptDrops(True)
        self.grid_container.installEventFilter(self)
        self.grid_container.setObjectName("GalleryGrid")
        self.grid_container.setStyleSheet("QWidget#GalleryGrid { background: transparent; }")
        self.scroll_area.setWidget(self.grid_container)
        self.scroll_area.viewport().setAcceptDrops(True)

        # Empty content belongs to the visible resource area, not to the
        # scrollable card canvas. Its layout follows viewport/dock geometry
        # even when the Gallery widget itself receives no resize event.
        self.empty_state = QWidget(self.scroll_area.viewport())
        self.empty_state.setProperty("galleryDropSurface", True)
        self.empty_state.setAcceptDrops(True)
        self.empty_state.installEventFilter(self)
        viewport_layout = QVBoxLayout(self.scroll_area.viewport())
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.addWidget(self.empty_state)
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(24, 20, 24, 20)
        empty_layout.setSpacing(12)
        empty_layout.addStretch()
        self.placeholder = KeycapLabel("", self.empty_state)
        self.placeholder.setWordWrap(True)
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setProperty("role", "data")
        empty_layout.addWidget(self.placeholder)
        self.empty_import_button=translated(PushButton,'导入表情',self.empty_state)
        self.empty_import_button.setFixedHeight(32)
        self.empty_import_button.clicked.connect(lambda:self._pick_import_files())
        self.empty_import_button.hide()
        empty_layout.addWidget(self.empty_import_button, 0, Qt.AlignHCenter)
        empty_layout.addStretch()
        self.empty_state.hide()

        # Right-clicking the empty content area is the position-aware entry for
        # the level being viewed; cards keep their own menus.
        #
        # The handler is attached to the grid container as well as the viewport:
        # the grid fills the viewport, so it is the widget actually under the
        # cursor in the empty area, and its default context-menu policy does not
        # forward the event to the viewport. Without this the menu never opens.
        for surface in (self.scroll_area.viewport(), self.grid_container, self.empty_state):
            surface.setContextMenuPolicy(Qt.CustomContextMenu)
            surface.customContextMenuRequested.connect(
                lambda position, surface=surface: self.show_content_menu(position, surface))

        self.workspace_layout.addWidget(self.scroll_area, stretch=1)
        from fluent_ui.components.virtual_gallery import VirtualGallery
        self.renderer = VirtualGallery(self)
        # One indicator for the whole content area, owned here and only ever
        # moved: drawing the drop target never touches the real layout.
        self.drop_feedback = DropFeedback(self.grid_container)
        self.drop_scroller = EdgeAutoScroller(self.scroll_area)
        self._drop_target = INVALID_TARGET

    def _build_tag_panel(self):
        """The dock host wraps the gallery workspace, not the whole page.

        Hierarchy Header -> Attached Tabs -> Search -> Content Workspace, and
        all four TagPanel placements are relative to that workspace: TOP is
        Search -> TagPanel -> Gallery, BOTTOM is Search -> Gallery -> TagPanel,
        LEFT/RIGHT are Search -> [TagPanel | Gallery]. Search therefore stays
        outside the host in every placement, without a TOP special case.
        """
        self.tag_panel = TagPanel(self.tag_model, self.config, self.content_pane)
        self.tag_panel_host = TagPanelHost(self.workspace, self.tag_panel, self.config, self.content_pane)
        self.content_pane.content_layout.addWidget(self.tag_panel_host, 1)
        self.tag_panel.tags_changed.connect(self._on_tags_changed)
        self.tag_panel.filter_requested.connect(self._toggle_tag)
        self.tag_panel.apply_requested.connect(self.apply_tag_to_paths)
        self.tag_panel.message_requested.connect(self._on_tag_panel_message)
        flow = self.tag_panel.flow
        flow.manual_required.connect(lambda: self.feedback_host.hint(
            t('标签顺序')+'\n'+t('切换到手动顺序后可调整顺序'), self.tag_panel.btn_sort,
            owner=flow._drag_session))
        flow.drag_hint_cleared.connect(lambda owner: self.feedback_host.clear_hint(owner))

    def show_content_menu(self, position, source=None):
        """Position-aware menu for the empty content area.

        Right-clicking a specific spot means "do it here", so both actions take
        the same placement. Cards and nodes keep their own menus; only real
        gaps reach this one. `position` arrives in the emitting widget's
        coordinates, so it is converted once and used for both the placement and
        the popup location.
        """
        source = source if source is not None else self.scroll_area.viewport()
        position = source.mapTo(self, position)
        placement = self.placement_at(position)
        menu = RoundMenu(parent=self)
        paste = translated(Action, '粘贴到此处' if placement.exact else '粘贴到当前分类',
                           parent=menu)
        paste.setIcon(FIF.PASTE)
        paste.triggered.connect(lambda: self.paste_into(placement))
        menu.addAction(paste)

        node = translated(Action, '在此新建分类' if placement.exact else '在当前分类新建分类',
                          parent=menu)
        node.setIcon(FIF.ADD)
        node.triggered.connect(lambda: self.create_node_here(placement))
        menu.addAction(node)

        if not placement.exact:
            menu.addSeparator()
            hint = translated(Action, '当前为搜索或临时排序，将添加到分类末尾', parent=menu)
            hint.setEnabled(False)
            menu.addAction(hint)
        menu.exec(self.mapToGlobal(position))

    def _exact_placement_available(self):
        """Whether the visible order still maps onto the canonical manual order.

        Search results and a temporary display sort reorder what is on screen
        without touching content.position, so a point in that layout no longer
        names a manual insertion slot. Filters keep the canonical order, so
        they do not affect placement.
        """
        return not self.search_keyword.strip() and self.content_sort == 'manual'

    def placement_at(self, position):
        """Resolve a content-area point into an insertion placement.

        Measured from the rendered layout only -- the nearest visible card, its
        container and its canonical index -- so it costs nothing on a large
        library and naturally lands inside a nested inline node when the point
        is inside one.
        """
        exact = self._exact_placement_available()
        entry, after = self._nearest_entry(position)
        if entry is None or self._below_last_card(position):
            # The empty area under the last row reads as "at the end", not as
            # "next to whichever card happens to be closest".
            return Placement(self.content_scope_node(), None, entry, False, exact)
        return Placement(entry['_parent'] or self.content_scope_node(),
                         entry['position'] + bool(after), entry, after, exact)

    def _below_last_card(self, position):
        view_pos = self.grid_container.mapFrom(self, position)
        return bool(self.renderer.index.rects) and view_pos.y() > self.renderer.index.rects[-1].bottom()

    def create_node_here(self, placement=None):
        """Create a node at the placement; in ALL_RESOURCES that is a root node."""
        if placement is None:
            placement = Placement(self.content_scope_node(), None, None, False,
                                  self._exact_placement_available())
        self.sidebar.create_node(placement.parent or self.content_scope_node(),
                                 position=placement.position if placement.exact else None)

    def _build_command_bar(self):
        self.command_bar = QWidget(self.content_pane)
        self.command_bar.setObjectName("CommandBar")
        self.command_bar.setFixedHeight(50)
        self.command_bar.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.command_bar.setStyleSheet(visual.command_bar_style())
        layout = QHBoxLayout(self.command_bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(visual.COMPACT_CONTROLS.spacing)

        self.selected_count_label = BodyLabel(self.command_bar)
        self.selected_count_label.setObjectName("CommandCount")
        layout.addWidget(self.selected_count_label)

        layout.addStretch()

        self.btn_select_all = TransparentToolButton(FIF.ACCEPT, self.command_bar)
        bind_text(self.btn_select_all, t("全选"), 'setToolTip')
        self.btn_select_all.clicked.connect(self.select_all_cards)
        layout.addWidget(self.btn_select_all)

        self.btn_add_to = translated(PushButton, "加入分类…", self.command_bar)
        bind_text(self.btn_add_to, "加入分类…", 'setToolTip')
        self.btn_add_to.clicked.connect(lambda: self._batch_assign(copy=True))
        layout.addWidget(self.btn_add_to)

        self.btn_move_to = translated(PushButton, "移动到…", self.command_bar)
        bind_text(self.btn_move_to, "移动到…", 'setToolTip')
        self.btn_move_to.clicked.connect(lambda: self._batch_assign(copy=False))
        layout.addWidget(self.btn_move_to)

        self.btn_tags = translated(PushButton, "标签…", self.command_bar)
        bind_text(self.btn_tags, "标签…", 'setToolTip')
        self.btn_tags.clicked.connect(self._batch_tags)
        layout.addWidget(self.btn_tags)

        self.btn_arrange = DropDownButton(self.command_bar)
        bind_text(self.btn_arrange, '顺序', 'setText')
        self.arrange_menu = RoundMenu(parent=self.btn_arrange)
        for label, front in (('移到最前', True), ('移到最后', False)):
            action = translated(Action, label, parent=self.arrange_menu)
            action.triggered.connect(lambda checked=False, front=front: self._move_selection_extreme(front))
            self.arrange_menu.addAction(action)
        self.btn_arrange.setMenu(self.arrange_menu)
        layout.addWidget(self.btn_arrange)

        self.btn_more = TransparentToolButton(FIF.MORE, self.command_bar)
        bind_text(self.btn_more, t("更多"), 'setToolTip')
        self.btn_more.clicked.connect(self._show_more_menu)
        layout.addWidget(self.btn_more)

        self.btn_delete = translated(PushButton, FIF.DELETE, "删除", self.command_bar)
        self.btn_delete.clicked.connect(self._batch_delete)
        layout.addWidget(self.btn_delete)

        self.btn_exit_mode = translated(PushButton, "完成", self.command_bar)
        bind_text(self.btn_exit_mode, '完成', 'setToolTip')
        self.btn_exit_mode.clicked.connect(self.finish_selection)
        layout.addWidget(self.btn_exit_mode)

        self._organization_buttons = (self.btn_add_to, self.btn_move_to, self.btn_tags, self.btn_arrange)
        for button in (*self._organization_buttons, self.btn_delete, self.btn_exit_mode):
            button.setFixedHeight(visual.COMPACT_CONTROLS.action_extent)
        self._selection_overflow = False
        self.btn_delete.setProperty('role', 'danger')
        self.btn_delete.setStyleSheet(dialogs._button_style())
        self.content_pane.content_layout.addWidget(self.command_bar)
        self.command_bar.installEventFilter(self)
        self.command_bar.hide()

    def _layout_selection_actions(self):
        layout = self.command_bar.layout()
        required = (layout.contentsMargins().left() + layout.contentsMargins().right()
                    + sum(w.sizeHint().width() for w in
                          (self.selected_count_label, self.btn_select_all, *self._organization_buttons,
                           self.btn_more, self.btn_delete, self.btn_exit_mode))
                    + layout.spacing() * 8)
        self._selection_overflow = self.command_bar.width() < required
        for button in self._organization_buttons:
            button.setVisible(not self._selection_overflow)

    # ==================================================================
    # Library selection
    # ==================================================================
    def _choose_library(self):
        # Preserve the old entry without a second, immediate-write selection path.
        self.window().show_settings()
        center=self.window().settings_window.center
        center._select_page(3);center._show_tab(0);center._choose_library()

    # ==================================================================
    # Navigation and content pipeline
    # ==================================================================
    def content_scope_node(self):
        """The only content target: location itself or one valid direct child."""
        active = getattr(self, 'active_view_node', self.current_node)
        if active == self.current_node:
            return self.current_node
        node = self.storage.index.node(active)
        if self.current_node != ALL_RESOURCES and node and node.get('parent_id') == self.current_node:
            return active
        return self.current_node

    def _activate_inline_scope(self):
        # Each content projection owns its disclosure state. A relative tab
        # never opens the corresponding Node in its parent's projection.
        scope = self.content_scope_node()
        self._expanded_nodes = self._expanded_by_scope.setdefault(scope, set(self._legacy_expanded_nodes))

    def set_relative_view(self, node_id):
        if node_id not in self._tab_nodes or node_id == self.content_scope_node():
            return
        self._remember_location_anchor()
        self.active_view_node = node_id
        self._activate_inline_scope()
        self._initial_anchor = self._decode_anchor(self._location_anchors.get(node_id))
        self._live_anchor = self._initial_anchor
        self._search_timer.stop()
        self.finish_selection()
        self.refresh_content()
        self._save_view_state()

    def _view_state_is_default(self):
        """Whether search, filter, tags and display order are all untouched."""
        return (not self.search_keyword.strip()
                and not self.search_box.text().strip()
                and not self.filter_state.is_active()
                and not self.active_tags
                and self.content_sort == 'manual')

    def _drop_selection_only(self):
        """Clear the selection without rebuilding the grid."""
        self.selected_keys.clear()
        self._selection_parents.clear()
        self._last_clicked_key = self._shift_anchor = None
        self._shift_touched.clear()
        for card in self._all_card_widgets:
            if getattr(card, 'is_selected', False):
                card.set_selected(False)
        self._sync_command_bar()

    def set_node(self, node_id, force=False):
        """Explicit category navigation resets the relative view to its location.

        Re-entering the same place with the same view state does nothing: every
        data change already refreshes the view where it happens, so a repeat
        click on the current category must not rebuild cards, re-decode
        thumbnails or relayout the grid. `force=True` is for the paths that
        really do need a rebuild after an external change.
        """
        if getattr(self, '_recent_view', False):
            self.toggle_recent_view(False)
        node_id = node_id or ALL_RESOURCES
        if not self.storage.index.node(node_id):
            node_id = ALL_RESOURCES
        if not force and node_id == self.current_node and self.content_scope_node() == node_id and self._view_state_is_default():
            self.finish_selection()
            return
        self._remember_location_anchor()
        if node_id != self.current_node:
            ancestors = {n['id'] for n in self.storage.node_path(self.current_node)[:-1] if n['id'] != ROOT}
            self.return_child_hint = self.current_node if node_id in ancestors else None
        self.current_node = node_id
        self.active_view_node = node_id
        self._activate_inline_scope()
        self._initial_anchor = self._decode_anchor(self._location_anchors.get(node_id))
        self._live_anchor = self._initial_anchor
        self.sidebar.tree.select_node(node_id, reveal=True)
        self.finish_selection()
        self.search_keyword = ''
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self._search_timer.stop()
        self.filter_state = FilterState()
        self.active_tags.clear()
        self.refresh_content()
        self._save_view_state()

    def set_category(self, category_name):
        """Legacy entry point; accepts a node id, a breadcrumb label or a name."""
        if category_name in (None, "全部资源", "全部表情"):
            self.set_node(ALL_RESOURCES)
            return
        labels = self.storage.category_labels()
        self.set_node(labels.get(category_name, category_name))

    def set_search_keyword(self, keyword):
        self.search_keyword = keyword
        self._search_timer.start(280)

    def _execute_search(self):
        self.refresh_content()

    def _ocr_text_changed(self,rid):
        record=self.storage.index.resource_by_id(rid)
        if record and self.search_keyword.strip():
            self._ocr_paths.add(self.storage.index.absolute_path(record))
            if not self._ocr_refresh_timer.isActive():self._ocr_refresh_timer.start()

    def _refresh_ocr_results(self):
        paths=list(self._ocr_paths);self._ocr_paths.clear()
        if paths and self.search_keyword.strip():
            self.refresh_content_incremental(reason='ocr',paths=paths,parents=set())

    def _collect_entries(self):
        from services.search_text import normalize_search
        content_node = self.content_scope_node()
        keyword = normalize_search(self.search_keyword.strip())
        self._display_mode = 'search' if keyword else ('resources' if content_node == ROOT else 'mixed')
        texts = self.storage.get_search_metadata() if keyword else {}
        categories = self.storage.get_image_to_categories_map() if self.filter_state.unclassified else {}
        def matches(entry):
            tags = set(self.storage.parse_tags(entry['tags']))
            return (not keyword or keyword in texts.get(entry['path'], '').casefold()) and self.active_tags.issubset(tags) and self._matches_filter(entry, tags, categories)
        if getattr(self, '_recent_view', False):
            self._display_mode = 'recent'
            entries = {e['path']: e for e in self.entry_model.entries_of(ROOT) if e['kind'] == 'resource'}
            return [dict(entries[path], _parent=ROOT, _depth=0) for path in self.storage.get_recent_images()
                    if path in entries and matches(entries[path])]
        def collect(parent, depth):
            result = []
            for original in self.entry_model.entries_of(parent):
                entry = dict(original, _parent=parent, _depth=depth)
                if entry['kind'] == 'resource' and not matches(entry):
                    continue
                if parent == ROOT and entry['kind'] == 'node':
                    continue
                result.append(entry)
                if entry['kind'] == 'node' and entry['id'] in self._expanded_nodes:
                    result.extend(collect(entry['id'], depth+1))
            return result
        if not keyword:
            return self._apply_content_sort(collect(content_node, 0))
        scope = {n['id'] for n in self.storage.index.subtree(content_node)} | {content_node}
        memberships = {}
        for member in self.storage.index.memberships():
            if content_node == ROOT or member['node_id'] in scope:
                memberships.setdefault(member['resource_id'], []).append(member['node_id'])
        # One pass over the (small) node tree instead of a per-hit ancestor
        # walk, which opened a database connection for every result row.
        node_paths = {row['id']: row['path'] for row in self.storage.node_choice_rows()}
        result = []
        for original in self.entry_model.entries_of(ROOT):
            if original['kind'] != 'resource' or not matches(original):
                continue
            parents = memberships.get(original['id'], [])
            if content_node != ROOT and not parents:
                continue
            parent = ROOT if content_node == ROOT else (content_node if content_node in parents else parents[0])
            names = [node_paths[p] for p in parents if p in node_paths]
            source_label = ' · '.join(names) if names else t('全部表情')
            result.append(dict(original, _parent=parent, _depth=0, _source_label=source_label, _unclassified_source=not parents))
        return self._apply_content_sort(result)

    def _apply_content_sort(self, entries):
        """Apply the temporary display sort to what is rendered.

        Only resources are reordered, and only inside each contiguous run
        between two nodes: node entries are structural section breaks and keep
        their slots. Nothing is written back, so the manual order is intact
        when the user returns to it.
        """
        return ResourceSort(self.content_sort).project(entries)

    def _matches_filter(self, entry, tags, categories_map):
        state = self.filter_state
        if not state.is_active():
            return True
        if state.no_tag and tags:
            return False
        if state.unclassified and categories_map.get(entry["path"]):
            return False
        if state.missing:
            return entry["status"] == "missing"
        animated = self.storage.is_animated(entry["path"])
        if state.is_gif and not state.is_static and not animated:
            return False
        if state.is_static and not state.is_gif and animated:
            return False
        return True

    def _cards_by_key(self):
        """Existing renderers indexed by stable entry key."""
        result = {}
        for widget in self._all_card_widgets:
            entry = getattr(widget, 'content_entry', None)
            if entry is not None:
                result.setdefault(self._entry_key(entry), widget)
        return result

    def _view_signature(self):
        return (self.content_scope_node(), self.search_keyword.strip(), self.content_sort,
                tuple(vars(self.filter_state).values()), tuple(sorted(self.active_tags)),
                tuple(sorted(self._expanded_nodes)), getattr(self, '_recent_view', False))

    def toggle_recent_view(self, checked=None):
        active = getattr(self, '_recent_view', False)
        enabled = not active if checked is None else bool(checked)
        if enabled == active:return
        if enabled:
            self._save_view_state()
            self._before_recent_anchor = self.renderer.anchor()
            self._before_recent_scroll = self.scroll_area.verticalScrollBar().value()
            self._before_recent_controls = (self.search_keyword, self.filter_state, set(self.active_tags), self.content_sort)
            self.search_keyword = ''; self.filter_state = FilterState(); self.active_tags.clear(); self.content_sort = 'manual'
        else:
            self.search_keyword, self.filter_state, self.active_tags, self.content_sort = self._before_recent_controls
        self.search_box.blockSignals(True); self.search_box.setText(self.search_keyword); self.search_box.blockSignals(False)
        self._search_timer.stop()
        self.finish_selection()
        self._recent_view = enabled
        self.btn_recent.setChecked(enabled)
        self.entry_model.snapshots.clear()
        self._initial_anchor = None
        self.refresh_content(anchor=None if enabled else getattr(self, '_before_recent_anchor', None))
        if not enabled and not getattr(self, '_before_recent_anchor', None):
            self.scroll_area.verticalScrollBar().setValue(getattr(self, '_before_recent_scroll', 0))

    def _recent_changed(self):
        if getattr(self, '_recent_view', False):
            self.refresh_content_incremental(reason='recent',parents=set())

    def refresh_content_incremental(self, *, reason='', paths=(), parents=None):
        if self._view_signature_at_build != self._view_signature() or not self.storage.index.node(self.current_node):
            self.entry_model.invalidate()
            self.refresh_content(reason=reason)
            return
        anchor = self.renderer.anchor()
        old_scroll = self.scroll_area.verticalScrollBar().value()
        self.entry_model.sync(parents=parents, paths=paths)
        plain = not getattr(self,'_recent_view',False) and not self.search_keyword.strip() and not self.filter_state.is_active() and not self.active_tags and self.content_sort == 'manual'
        if plain:
            first = self.entry_model.patch_normal(self._entries, self.content_scope_node(), self._expanded_nodes)
        else:
            first = self.entry_model.patch(self._entries, self._collect_entries())
        self._reconcile_selection()
        if first < max(len(self._entries), len(self.renderer.index.rects)):
            self.renderer.relayout(first, anchor=anchor if old_scroll else None)
        else:
            self.renderer.sync()
        self._rebuild_context_strip()
        self._sync_command_bar()
        self._update_placeholder()

        self._update_back_top()

    def refresh_content(self, *, reason='', anchor=None, first_key=None):
        """Rebuild the entry list; `anchor` keeps one entry fixed on screen.

        `first_key` names the entry that changed: everything from its row on is
        relaid out, everything above it is reused.
        """
        if not self.storage.index.node(self.current_node):
            self.current_node = ROOT
            self.active_view_node = ROOT
            self._initial_anchor = self._live_anchor = None
            self._save_view_state()
        if self.active_view_node != self.content_scope_node():
            self.active_view_node = self.current_node
            self._initial_anchor = self._decode_anchor(self._location_anchors.get(self.current_node))
            self._live_anchor = self._initial_anchor
        self._activate_inline_scope()
        self.current_category = '全部表情' if self.current_node == ROOT else self.storage.node(self.current_node)['name']
        self.sidebar.tree.select_node(self.current_node)
        if hasattr(self, 'preview_controller'):
            self.preview_controller.cancel()
        signature = self._view_signature()
        old = self._view_signature_at_build
        if old is not None:
            self.entry_model.snapshots[old] = (list(self._entries), self.renderer.anchor())
            if len(self.entry_model.snapshots) > 24:
                del self.entry_model.snapshots[next(iter(self.entry_model.snapshots))]
        snapshot = self.entry_model.snapshots.get(signature)
        self._display_mode = 'search' if self.search_keyword.strip() else ('resources' if self.content_scope_node() == ROOT else 'mixed')
        cold_start = False
        if snapshot:
            self._entries, scroll = list(snapshot[0]), 0
            anchor = anchor or self._initial_anchor or snapshot[1]
        else:
            self._entries, scroll = self._collect_entries(), 0
            if self._initial_anchor is not None:
                if self._initial_anchor is not None:
                    # Cold start: put the gallery back on the entry the user was
                    # looking at. An occurrence id plus a pixel offset survives
                    # inserted or removed resources, which a raw scrollbar value
                    # would not.
                    anchor, cold_start = self._initial_anchor, True
                else:
                    self._initial_anchor = None
        projection_filter_changed = old is not None and (old[1] != signature[1] or old[3:5] != signature[3:5])
        self._reconcile_selection(resources_only=projection_filter_changed)
        self._view_signature_at_build = signature
        if anchor is not None:
            # Callers that changed something below the viewport (expanding a
            # node, for instance) restore by entry instead of laying out at 0
            # and jumping back a frame later.
            self.renderer.relayout(first=self._first_index(first_key), anchor=anchor)
        else:
            self.renderer.relayout(scroll=scroll)
        self._finish_position_layout(anchor)
        self._rebuild_context_strip()
        self._sync_command_bar()
        self._update_placeholder()

        self._update_back_top()

    def _first_index(self, key):
        """Row from which a relayout has to recompute; 0 when unknown."""
        if key is None:
            return 0
        for index, entry in enumerate(self._entries):
            if self._entry_key(entry) == key:
                return index
        return 0

    def _anchor_landed(self, anchor):
        """Whether the viewport really sits on the entry the anchor names.

        A scroll area has no scroll range until it has been laid out, so a
        restore attempted during construction is silently clamped to the top;
        the anchor is kept for the first layout that can honour it.
        """
        current = self.renderer.anchor()
        return bool(current) and current[0] == anchor[0]

    def _apply_initial_anchor(self):
        self._trigger_responsive_layout()

    def _finish_position_layout(self, anchor=None):
        if not self.scroll_area.viewport().isVisible():
            return
        if self._initial_anchor is not None:
            # Consume only after the actual visible viewport and scroll range
            # exist. Never replace a pending saved anchor with a clamped zero.
            target = self._initial_anchor
            self.renderer.restore(target)
            self._initial_anchor = None
        self._live_anchor = self.renderer.anchor()
        self._position_geometry = self.scroll_area.viewport().size()

    def _remember_location_anchor(self):
        if getattr(self,'_recent_view',False):return
        anchor = self._current_anchor()
        if anchor:
            self._location_anchors[self.content_scope_node()] = anchor

    def sync_content_after_reorder(self):
        self.refresh_content_incremental(reason='structure')

    def on_images_changed(self):
        self.entry_model.invalidate()
        self.renderer.loader.revisions.clear()
        self._view_signature_at_build = None
        self.refresh_content()

    def refresh_gallery(self):
        self.on_images_changed()

    def _entry_key(self, entry):
        return entry["path"] if entry["kind"] == "resource" else entry["id"]

    def _update_placeholder(self):
        if self._entries:
            self.empty_state.hide()
            return
        if getattr(self,'_recent_view',False):
            text = t('暂无最近使用的表情')
        elif self._display_mode == "search":
            text = t("没有匹配的表情")
        elif self.current_node == ALL_RESOURCES:
            text = t("表情库还是空的\n把表情、文件夹或截图拖进来，或按 Ctrl+V 粘贴")
        else:
            text = t("该分类还没有内容\n把表情拖到左侧分类或此区域即可加入")
        self.placeholder.setText(text)
        self.empty_import_button.setVisible(self.current_node==ALL_RESOURCES and self._display_mode!='search' and not getattr(self,'_recent_view',False))
        self.empty_state.show()
        self.empty_state.raise_()

    # ==================================================================
    # Location header and compact active filter context
    # ==================================================================
    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _rebuild_context_strip(self):
        self._clear_layout(self.chip_layout)
        path = ([dict(id=ROOT, name=t('全部表情'))] if self.current_node == ROOT
                else [n for n in self.storage.node_path(self.current_node) if n['id'] != ROOT])
        return_node = self.storage.index.node(self.return_child_hint) if self.return_child_hint else None
        if return_node and self.current_node not in {n['id'] for n in self.storage.node_path(self.return_child_hint)[:-1]}:
            return_node = None
        if not return_node:
            self.return_child_hint = None
        self.location_rail.set_path(path, return_node)
        location_entries = self.entry_model.entries_of(self.current_node)
        resources = sum(e['kind'] == 'resource' for e in location_entries)
        children = 0 if self.current_node == ROOT else sum(e['kind'] == 'node' for e in location_entries)
        self.location_rail.set_counts(t('{value_0} 项表情').format(value_0=resources) + '\n' +
                                   t('{value_0} 个子分类').format(value_0=children))
        if getattr(self,'_recent_view',False):
            self.location_rail.set_path([dict(id=self.current_node,name=t('最近使用'))],None)
            self.location_rail.set_counts(t('表情 {count} 张').format(count=len(self._entries)))
        for field, label in (('no_tag', '无标签'), ('unclassified', '未分类'),
                             ('is_gif', '动图'), ('is_static', '静态表情'), ('missing', '已失效的表情')):
            if getattr(self.filter_state, field):
                self.chip_layout.addWidget(self._make_chip(t(label), lambda f=field: self._update_filter(f, False), self.chip_container, active=True))
        self.context_strip.setVisible(self.filter_state.is_active())

        self._rebuild_category_tabs()
        self.chip_layout.addStretch()
        self._rebuild_tag_panel()

    def _rebuild_tag_panel(self):
        """Project the tags of the effective location onto the panel.

        A search or a filter changes what is effective, so the projection
        follows what is on screen; a plain location counts its whole subtree,
        so a collapsed child category still contributes its tags.
        """
        if not hasattr(self, 'tag_panel'):
            return
        if getattr(self,'_recent_view',False) or self.search_keyword.strip() or self.filter_state.is_active():
            # The result set already carries its tag text; counting it needs no
            # query at all.
            texts = [e['resource']['tags'] for e in self._entries
                     if e['kind'] == 'resource']
            items = self.tag_model.project(tag_texts=texts)
        else:
            items = self.tag_model.project(node_id=self.content_scope_node())
        # Active filters remain controllable even if another filter empties the
        # result set. Their chips disappear only when the tag/scope is removed.
        from fluent_ui.components.tag_model import TagItem
        shown={item.name for item in items}
        items += [TagItem(name,0) for name in sorted(self.active_tags-shown) if name in self.tag_model.names()]
        self.tag_panel.set_items(items, self.tag_panel.selected())
        self.tag_panel.set_active_filters(self.active_tags)

    def _on_tags_changed(self):
        """Tag identity or order changed: the gallery data did not."""
        self.active_tags.intersection_update(self.tag_model.names())
        self.refresh_content_incremental(reason='tag_panel', parents=set())

    def _on_tag_panel_message(self, title, content, is_error):
        if is_error:
            self.show_error(title, content)
        else:
            self.show_success(title, content)

    def apply_tag_to_paths(self, paths, tag):
        """A resource dropped onto a tag: add the relation, then refresh."""
        paths = self.apply_tags(paths, [tag])
        if not paths:
            return
        self.show_success(t('标签已更新'),
                          t('已为 {value_0} 项表情添加标签「{value_1}」').format(
                              value_0=len(paths), value_1=tag), quiet=True)

    def apply_tags(self, resource_ids, tag_ids):
        """One relation commit for either drag direction and selection blocks."""
        tags = [name for name in dict.fromkeys(tag_ids) if name in self.tag_model.names()]
        paths = []
        for value in dict.fromkeys(resource_ids):
            path = self.storage.resource_path(value) or value
            if self.storage.resource_of(path):
                paths.append(path)
        if paths and tags:
            self.storage.apply_tags(paths, tags, 'add')
            self.refresh_content_incremental(reason='apply_tag', paths=paths, parents=set())
        return paths if tags else []

    def apply_tags_to_category(self, node_id, tags):
        tags = list(dict.fromkeys(tag for tag in tags if tag in self.tag_model.names()))
        node = self.storage.node(node_id)
        if not tags or not node or node_id == ROOT:
            return
        # Scope/count is deliberately resolved only at commit, never dragMove.
        records = self.storage.resources_in_subtree(node_id)
        question = t('将 {tags} 个标签添加到「{category}」中的 {resources} 个表情？').format(
            tags=len(tags), category=node['name'], resources=len(records))
        if not dialogs.confirm(self.window(), t('添加标签到分类'), question,
                               hint=t('已存在的标签关系会跳过，不会修改或删除任何表情文件。')):
            return
        paths = [self.storage.index.absolute_path(record) for record in records]
        self.storage.apply_tags(paths, tags, 'add')
        self.refresh_content_incremental(reason='category_tags', paths=paths, parents=set())

    def _commit_tag_drop(self, target, tags):
        if target.effect == APPLY_TAG_TO_SUBTREE:
            self.apply_tags_to_category(target.container_id, tags)
            return
        entry = next((entry for entry in self._entries if entry['kind'] == 'resource' and entry['id'] == target.target_id), None)
        if entry is None:
            return
        paths = self.get_selected_paths() if self._entry_key(entry) in self.selected_keys else [entry['path']]
        self.apply_tags([resource['id'] for resource in
                         (self.storage.resource_of(path) for path in paths) if resource], tags)

    def _rebuild_category_tabs(self):
        self.tab_row.setVisible(True)
        self.category_tabs.setVisible(self.current_node != ROOT)
        self.content_pane.setProperty('standalone', self.current_node == ROOT)
        self.content_pane.update()
        children = self.storage.child_nodes(self.current_node) if self.current_node != ROOT else []
        self._tab_nodes = [self.current_node]+[node['id'] for node in children]
        title = t('全部表情') if self.current_node == ROOT else self.storage.node(self.current_node)['name']
        self.category_tabs.set_tabs([title]+[node['name'] for node in children], self._tab_nodes.index(self.content_scope_node()))

    def _on_category_tab(self, index):
        if 0 <= index < len(self._tab_nodes):
            if getattr(self,'_recent_view',False):self.toggle_recent_view(False)
            self.set_relative_view(self._tab_nodes[index])

    def refresh_texts(self, *_):
        self.sidebar.tree.refresh(select=self.current_node)
        self._rebuild_context_strip()
        self._sync_command_bar()
        self._update_placeholder()

    def refresh_theme(self):
        self.sidebar.update_theme()
        c=visual.colors()
        from PySide6.QtGui import QPalette,QColor
        for widget in (self.scroll_area.viewport(),self.grid_container):
            palette=widget.palette();palette.setColor(QPalette.Window,QColor(c['surface']));widget.setPalette(palette)
            widget.setAutoFillBackground(True)
        self._apply_splitter_style()
        self.context_strip.setStyleSheet(visual.strip_style())
        self.command_bar.setStyleSheet(visual.command_bar_style())
        if hasattr(self, 'tag_panel'):
            self.tag_panel.refresh_theme()
        for chip in self.chip_container.findChildren(QLabel):
            chip.setStyleSheet(self._chip_style(True))

    def _make_chip(self, text, on_click, parent, active=False):
        chip = QLabel(text, parent)
        chip.setProperty("role", "chip")
        chip.setCursor(Qt.PointingHandCursor)
        chip.setStyleSheet(self._chip_style(active))
        chip.mousePressEvent = lambda _e: on_click()
        return chip

    def _chip_style(self, active):
        c = visual.colors()
        return (f"QLabel {{ color: {c['text']}; border: 1px solid "
                f"{visual.accent() if active else c['border']}; border-radius: {visual.RADIUS}px;"
                f" padding: 2px 8px; background: {c['surface'] if active else 'transparent'}; }}")

    def _toggle_tag(self, tag):
        if tag in self.active_tags:
            self.active_tags.discard(tag)
        else:
            self.active_tags.add(tag)
        self.refresh_content()


    # ==================================================================
    # Modes and selection
    # ==================================================================
    def set_mode(self, mode):
        mode = "manage" if mode == "manage" else "normal"
        self.mode = mode
        self.is_selection_mode = (mode == "manage")
        self.btn_manage.setChecked(mode == "manage")
        if mode == "normal":
            self._drop_selection_only()
        elif hasattr(self, 'preview_controller'):
            self.preview_controller.cancel()
        self._sync_command_bar()

    def toggle_manage_mode(self):
        self.set_mode("normal" if self.mode == "manage" else "manage")

    def finish_selection(self):
        self.set_mode('normal')

    def keyPressEvent(self, event):
        # Let menus/popovers/editors consume Esc before it bubbles here.
        if event.key() == Qt.Key_Escape and self.consume_escape():
            event.accept()
            return
        super().keyPressEvent(event)

    def install_navigation_shortcuts(self):
        self._view_shortcuts={}
        for key in (Qt.Key_PageUp,Qt.Key_PageDown,Qt.Key_Return,Qt.Key_Enter):
            shortcut=QShortcut(QKeySequence(key),self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda k=key:self._view_key(k))
            self._view_shortcuts[key]=shortcut
        QApplication.instance().focusChanged.connect(self._sync_view_shortcuts)
        self._sync_view_shortcuts()

    def _sync_view_shortcuts(self,*_):
        from PySide6.QtWidgets import QLineEdit,QTextEdit,QPlainTextEdit,QAbstractSpinBox,QAbstractButton
        focus=QApplication.focusWidget()
        editing=isinstance(focus,(QLineEdit,QTextEdit,QPlainTextEdit,QAbstractSpinBox))
        in_content=focus is self or (focus is not None and self.scroll_area.isAncestorOf(focus))
        can_send=(in_content and self.mode=='normal' and self.config.get('gallery_click_action','select')=='select'
                  and len(self.selected_keys)==1 and len(self.get_selected_paths())==1)
        for key,shortcut in self._view_shortcuts.items():
            shortcut.setEnabled(not editing and (key not in (Qt.Key_Return,Qt.Key_Enter)
                                or (can_send and not isinstance(focus,QAbstractButton))))

    def _view_key(self,key):
        bar=self.scroll_area.verticalScrollBar()
        if key==Qt.Key_PageUp:bar.setValue(bar.minimum())
        elif key==Qt.Key_PageDown:bar.setValue(bar.maximum())
        elif self.mode=='normal' and self.config.get('gallery_click_action','select')=='select' and len(self.selected_keys)==1:
            paths=self.get_selected_paths()
            if len(paths)==1:self.use_resource(paths[0])

    def consume_escape(self):
        if self.mode == 'manage' or self.selected_keys or self.tag_panel.flow.selected():
            self.finish_selection()
            self.tag_panel.flow._set_selection([])
            return True
        return False

    def set_selection_mode(self, enabled):
        """Compatibility with callers that used the old boolean flag."""
        self.set_mode("manage" if enabled else "normal")

    def _sync_command_bar(self):
        if hasattr(self,'_view_shortcuts'):self._sync_view_shortcuts()
        self._selection_parents = {key: parent for key, parent in self._selection_parents.items()
                                   if key in self.selected_keys}
        resources = [e for e in self._selected_entries() if e['kind'] == 'resource']
        count = len(resources)
        contextual = self.mode == 'manage' or count >= 2
        self.command_bar.setVisible(contextual)
        bind_text(self.selected_count_label, t('已选 {value_0} 项').format(value_0=count), 'setText')
        direct = ({e['id'] for e in self.entry_model.entries_of(self.content_scope_node())
                   if e['kind'] == 'resource'} if resources else set())
        context = ActionContext.from_entries(resources, direct, self.content_scope_node())
        self.btn_add_to.setEnabled(ActionPolicy.enabled('category_membership', context))
        self.btn_tags.setEnabled(ActionPolicy.enabled('tag_edit', context))
        self.btn_delete.setEnabled(ActionPolicy.enabled('delete', context))
        bind_text(self.btn_delete, ActionPolicy.delete_label(context), 'setToolTip')
        self.btn_move_to.setEnabled(ActionPolicy.enabled('category_membership', context)
                                    and any(e['_parent'] != ROOT for e in resources))
        self.btn_arrange.setEnabled(bool(resources) and self._exact_placement_available())
        visible = self._visible_resource_keys()
        self.btn_select_all.setEnabled(bool(visible))
        bind_text(self.btn_select_all, '取消全选' if visible and visible <= self.selected_keys else '全选', 'setToolTip')
        self.btn_select_all.setAccessibleName(self.btn_select_all.toolTip())
        self.btn_exit_mode.setVisible(contextual)
        self.filter_flyout.sync(self.filter_state)
        if contextual:
            self._layout_selection_actions()

    def _visible_resource_keys(self):
        return {self._entry_key(e) for e in self._entries if e['kind'] == 'resource'}

    def _reconcile_selection(self, *, resources_only=False):
        visible = self._visible_resource_keys() if resources_only else {self._entry_key(e) for e in self._entries}
        self.selected_keys.intersection_update(visible)
        sources = {}
        for entry in self._entries:
            key = self._entry_key(entry)
            if key in self.selected_keys:
                sources.setdefault(key, []).append(entry['_parent'])
        self._selection_parents = {key: self._selection_parents.get(key)
                                   if self._selection_parents.get(key) in parents else parents[0]
                                   for key, parents in sources.items()}
        self._shift_touched.intersection_update(self.selected_keys)
        if hasattr(self, '_shift_base'):
            self._shift_base.intersection_update(self.selected_keys)
        if self._shift_anchor not in visible:
            self._shift_anchor = None
        if self._last_clicked_key not in visible:
            self._last_clicked_key = None

    def update_selection_count(self):
        self._sync_command_bar()

    def _selected_entries(self):
        result, seen = [], set()
        occurrences = {(self._entry_key(e), e['_parent']) for e in self._entries}
        for entry in self._entries:
            key = self._entry_key(entry)
            if key in self.selected_keys and key not in seen:
                parent = self._selection_parents.get(key)
                if parent and parent != entry['_parent'] and (key, parent) in occurrences:
                    continue
                result.append(entry)
                seen.add(key)
        return result

    def get_selected_paths(self):
        return [e["path"] for e in self._selected_entries() if e["kind"] == "resource"]

    def _drag_payload(self, path):
        """Everything that should travel with one drag gesture."""
        if path in self.selected_keys and len(self.selected_keys) > 1:
            paths = self.get_selected_paths()
            return paths or [path]
        return [path]

    def on_selection_changed(self, key, selected):
        if selected:
            self.selected_keys.add(key)
        else:
            self.selected_keys.discard(key)
        self._sync_command_bar()

    def _set_widget_selected(self, key, selected):
        for widget in self._all_card_widgets:
            widget_key = getattr(widget, "image_path", None) or getattr(widget, "node_id", None)
            if widget_key == key:
                widget.set_selected(selected)

    def select_all_cards(self):
        everything = self._visible_resource_keys()
        if everything and self.selected_keys >= everything:
            self.selected_keys.clear()
        else:
            self.selected_keys = set(everything)
        self._reconcile_selection(resources_only=True)
        from PySide6.QtCore import QSignalBlocker
        for widget in self._all_card_widgets:
            with QSignalBlocker(widget):
                widget.set_selected(self._entry_key(widget.content_entry) in self.selected_keys)
        self._sync_command_bar()

    # ==================================================================
    # Grid rendering
    # ==================================================================
    def clear_gallery(self):
        self.renderer._batch_timer.stop()
        self.renderer._pending.clear()
        for card in list(self.renderer.active.values()):
            self.renderer.retire(card)
        self.renderer.active.clear()
        self._all_card_widgets = []

    def _load_next_batch(self):
        self.renderer.sync()


    def _create_widget(self, entry, size):
        if entry['kind'] == 'node':
            card = NodeCard(entry, self.storage, size=size)
            card.set_expanded(entry['id'] in self._expanded_nodes)
            card.clicked.connect(lambda key, mods, w=card: self._entry_clicked(w.content_entry, mods))
            card.activated.connect(self.set_node)
            card.disclosure_toggled.connect(self.toggle_node_expansion)
            card.context_requested.connect(self.show_node_context_menu)
            # Every drag that ends inside the gallery is resolved by the view
            # against one contract, so a node card is a drag source and nothing
            # else -- it no longer decides placements or paints its own hint.
            card.drag_payload_provider = lambda node_id: self._drag_node_payload(node_id)
        else:
            frame = int(json.loads(entry.get('resource', {}).get('metadata_json') or '{}').get('thumb_frame', 0) or 0)
            card = EmojiCard(entry['path'], size=size, frame=frame, load_image=False,
                             availability=self.storage.availability,status=entry.get('status'))
            card.entry_id = entry['id']
            card.drag_payload_provider = lambda path, w=card: self._drag_from_entry(w.content_entry, path)
            card.customContextMenuRequested.connect(lambda pos, w=card: self.show_context_menu(w, pos))
            card.clicked.connect(lambda key, mods, w=card: self._entry_clicked(w.content_entry, mods))
            card.activated.connect(self.use_resource)
            card.hover_started.connect(lambda path, w=card: self.on_hover_started(w, path))
            card.hover_ended.connect(lambda w=card: self.on_hover_ended(w))
        card.content_entry = entry
        card.set_selectable(False)
        card.selection_changed.connect(self.on_selection_changed)
        if self._entry_key(entry) in self.selected_keys:
            card.set_selected(True)
        return card

    GRID_SIDE_MARGIN = 20

    def _columns_for_width(self):
        step = self.config.get("thumbnail_size", 120) + self.LAYOUT_SPACING
        return max(1, (self.scroll_area.viewport().width() - self.GRID_SIDE_MARGIN * 2) // step)



    def _rearrange_gallery(self, columns=None):
        self.renderer.relayout()

    def _trigger_responsive_layout(self, force=False):
        self._responsive_layout_timer.stop()
        if hasattr(self, 'renderer'):
            anchor = self._initial_anchor or self._live_anchor or self.renderer.anchor()
            self.renderer.relayout(anchor=anchor)
            self._finish_position_layout(anchor)
            self._update_back_top()

    def _schedule_responsive_layout(self):
        if not self._responsive_layout_timer.isActive():
            self._responsive_layout_timer.start(0)

    # Cards outside the viewport keep their pixmap for this many screens: the
    # process-wide thumbnail cache still holds the result, so a card that comes
    # back only has to re-attach, not re-decode, and scrolling up and down does
    # not flicker through empty cards.
    LAZY_PREFETCH_SCREENS = 2
    # Beyond this the widget is released, but only into the shared cache.
    LAZY_RELEASE_SCREENS = 6

    def _apply_lazy_loading(self):
        self.renderer.sync()

    def _on_scroll(self, value):
        if (not self.renderer.updating and self.scroll_area.viewport().isVisible()
                and self._initial_anchor is None
                and getattr(self, '_position_geometry', None) == self.scroll_area.viewport().size()
                and not self._responsive_layout_timer.isActive()):
            self._live_anchor = self.renderer.anchor()
        self.renderer.sync(scroll_only=True)
        self._update_back_top()

    def _update_back_top(self):
        if hasattr(self, 'btn_back_top'):
            bar = self.scroll_area.verticalScrollBar()
            viewport = self.scroll_area.viewport()
            visible = bar.maximum() > 0 and bar.value() > max(120, viewport.height())
            if visible:
                # NodeCard's whole row is clickable, including its rightmost
                # disclosure target. Use the existing flow index so a card
                # awaiting lazy construction cannot briefly sit under the
                # floating button.
                origin = self.grid_container.mapTo(viewport, QPoint())
                for index in self.renderer.index.between(bar.value(), bar.value()+viewport.height()):
                    if self._entries[index]['kind'] == 'node' and self.renderer.index.rects[index].translated(origin).intersects(self.btn_back_top.geometry()):
                        visible = False
                        break
            self.btn_back_top.setVisible(visible)

    def _refresh_visible_thumbnails(self):
        self.renderer.sync()

    def _apply_thumbnail_size(self, size):
        if hasattr(self,'size_slider'):
            self.size_slider.blockSignals(True);self.size_slider.setValue(size);self.size_slider.blockSignals(False)
        self._trigger_responsive_layout(force=True)

    def _commit_thumbnail_size(self, size):
        """Main-panel controls commit; Settings preview remains an unsaved overlay."""
        self.config.set('thumbnail_size', size)
        center = getattr(getattr(self.window(), 'settings_window', None), 'center', None)
        if center is not None:
            center.sync_external_preference('thumbnail_size', size)
        self._apply_thumbnail_size(size)

    def _on_splitter_moved(self, pos, index):
        sizes = self.splitter.sizes()
        if sizes:
            self.config.set("sidebar_width_list", sizes[0])
        self._schedule_responsive_layout()

    def _capture_scroll_anchor(self):
        return self.renderer.anchor()

    def _restore_scroll_anchor(self, anchor):
        self.renderer.restore(anchor)

    def save_scroll_position(self):
        if hasattr(self, 'scroll_area'):
            self._saved_scroll_position = self.scroll_area.verticalScrollBar().value()

    def restore_scroll_position(self):
        if hasattr(self, 'scroll_area'):
            self.scroll_area.verticalScrollBar().setValue(self._saved_scroll_position)

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_responsive_layout()
        # Session restore attributes belong to a fully constructed view; a
        # handler that can fire on a partially built one must not crash.
        if getattr(self, '_saved_sidebar_scroll', None) is not None:
            # The tree only has a scroll range once the viewport has a size.
            self._restore_sidebar_scroll()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_responsive_layout()

    def eventFilter(self, obj, event):
        if obj == getattr(self, 'command_bar', None) and event.type() in (QEvent.Resize, QEvent.Show):
            self._layout_selection_actions()
        if obj in (self.scroll_area.viewport(), self.grid_container) or obj.property("galleryDropSurface"):
            kind = event.type()
            if kind in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
                position = obj.mapTo(self, event.position().toPoint())
                if kind == QEvent.Drop:
                    self._complete_drop(event, position)
                elif kind == QEvent.DragEnter:
                    self._begin_drop(event, position)
                else:
                    self._track_drop(event, position)
                return True
            if kind == QEvent.DragLeave:
                self._clear_drop()
                return True
        if obj == self.scroll_area.viewport() and event.type() == event.Type.Resize:
            if hasattr(self, 'btn_back_top'):
                self.btn_back_top.move(max(0, obj.width()-42), max(0, obj.height()-42))
                self.btn_back_top.raise_()
            self._schedule_responsive_layout()
        if obj == self.scroll_area.viewport() and event.type() == event.Type.Wheel:
            if QApplication.keyboardModifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 10 if delta > 0 else -10
                current = self.config.get("thumbnail_size", 120)
                new_size = max(60, min(300, current + step))
                if new_size != current:
                    self._commit_thumbnail_size(new_size)
                return True
        return super().eventFilter(obj, event)

    # ==================================================================
    # Activation
    # ==================================================================
    def on_node_clicked(self, node_id, modifiers=Qt.NoModifier):
        if self.mode == 'manage' or modifiers & (Qt.ControlModifier | Qt.ShiftModifier):
            self._toggle_selection(node_id)
        else:
            self._select_single(node_id)

    def on_node_order_dropped(self, source_id, target_id, insert_after):
        """Single-node reorder next to a sibling; the shared drop path uses
        the same index rule, so a drag and this entry cannot disagree."""
        if not self._manual_order_available():
            return
        parent = self.storage.node(target_id)['parent_id'] or ROOT
        placement = INSERT_AFTER if insert_after else INSERT_BEFORE
        position = self._node_insert_index(parent, target_id, placement, {source_id})
        try:
            self.storage.move_node(source_id, parent, position)
        except (KeyError, ValueError) as error:
            self.show_error(t('无法移动分类'), str(error))
        self.sidebar.refresh_list(self.current_node)
        self.refresh_content_incremental(reason='node_order')

    def on_image_clicked(self, image_path, modifiers=Qt.NoModifier):
        self.setFocus(Qt.MouseFocusReason)
        if (self.mode != 'manage' and len(self.selected_keys) <= 1
                and modifiers == Qt.NoModifier
                and self.config.get('gallery_click_action', 'select') == 'send'):
            # A resource context menu selects its target. A leftover single
            # selection must not silently disable the configured send action.
            # Modifiers, management and multiple selections still select only.
            if self.selected_keys:
                self.selected_keys.clear()
                self._commit_selection_visuals()
            self._selection_parents.pop(image_path,None)
            self.use_resource(image_path)
            return
        if modifiers & Qt.ShiftModifier and self._shift_anchor:
            self._extend_shift_selection(image_path)
        elif self.mode == 'manage' or modifiers & Qt.ControlModifier:
            self._toggle_selection(image_path)
            self._shift_anchor = image_path
            self._shift_touched.clear()
        else:
            self._select_single(image_path)
            self._shift_anchor = image_path
            self._shift_touched.clear()
        self._last_clicked_key = image_path

    def _send_to_clipboard(self, image_path):
        self.send_target_service.send(image_path, self.clipboard, self.storage,
                                      self._on_send_finished, self.config.get('recent_limit', 30))

    def _on_send_finished(self, result):
        self.last_send_result = result
        self.send_finished.emit(result)
        if result == SendResult.COPY_FAILED:
            self.show_error(t("复制失败"), t("无法将表情写入剪贴板"))
        elif result == SendResult.SENT and self.config.get('hide_main_after_paste', False):
            self.hide_after_paste_requested.emit()
        elif result == SendResult.COPIED_ONLY:
            self.feedback_host.notice(t('表情已复制'),t('未找到可发送的聊天窗口，可手动粘贴。'))

    def _handle_missing_click(self, image_path):
        if dialogs.confirm(self.window(), t("表情已失效"),
                           t('该表情在磁盘上的位置已失效：\n{value_0}\n\n索引记录、分类关系、排序和标签 均已保留。').format(value_0=image_path),
                           ok_text=t("重新绑定文件…"), code="MISSING"):
            self.rebind_resource(image_path)

    def _toggle_selection(self, key):
        if key in self.selected_keys:
            self.selected_keys.discard(key)
        else:
            self.selected_keys.add(key)
        self._set_widget_selected(key, key in self.selected_keys)
        self._sync_command_bar()

    def _extend_shift_selection(self, end_key):
        keys = [self._entry_key(e) for e in self._entries]
        if self._shift_anchor not in keys or end_key not in keys:
            return
        start, end = keys.index(self._shift_anchor), keys.index(end_key)
        low, high = min(start, end), max(start, end)
        wanted = set(keys[low:high + 1])
        if not self._shift_touched:
            self._shift_base = set(self.selected_keys)
        self.selected_keys = getattr(self, '_shift_base', set()) | wanted
        self._shift_touched = wanted
        self._commit_selection_visuals()

    def _commit_selection_visuals(self):
        """One selection commit, bounded by the virtual renderer's active cards."""
        from PySide6.QtCore import QSignalBlocker
        self._reconcile_selection()
        for card in self._all_card_widgets:
            selected = self._entry_key(card.content_entry) in self.selected_keys
            if card.is_selected != selected:
                with QSignalBlocker(card):
                    card.set_selected(selected)
        self._sync_command_bar()


    # ==================================================================
    # Assignment and batch operations
    # ==================================================================
    def assign_resources(self, paths, node_id, copy=True, position=None, source_node=None):
        groups = {}
        visible_sources = {e['path']: e['_parent'] for e in self._selected_entries() if e['kind'] == 'resource'}
        for path in paths:
            parent = source_node or visible_sources.get(path, self._selection_parents.get(path, self.content_scope_node()))
            groups.setdefault(parent, []).append(path)
        added = 0
        for parent, subset in groups.items():
            added += self.storage.move_resources_to(subset, node_id, copy=copy,
                source_node=None if copy else parent, position=position)
        self.sidebar.refresh_list(self.current_node)
        self.refresh_content_incremental(reason='assign_resources', parents=set(groups)|{node_id})
        self.show_success(t('分类已更新'), t('{value_0} 项').format(value_0=added), quiet=True)

    def _drag_from_entry(self, entry, path):
        self._selection_parents[path] = entry['_parent']
        for selected in self._selected_entries():
            self._selection_parents[self._entry_key(selected)] = selected['_parent']
        return self._drag_payload(path)

    def _drag_node_payload(self, node_id):
        """A selected category drags as one block, in visible order."""
        self._selection_parents[node_id] = self.content_scope_node()
        block = [entry['id'] for entry in self._selected_entries()
                 if entry['kind'] == 'node']
        if node_id not in block:
            return [node_id]
        for entry in self._selected_entries():
            self._selection_parents[entry['id']] = entry['_parent']
        return block

    def _node_choice_items(self, exclude=None):
        return [item for item in self.storage.node_choices() if item[0] != exclude]

    def choose_target_node(self, title, copy, exclude=None):
        """Searchable, hierarchy-aware target picker; returns a node id or None."""
        rows = [row for row in self.storage.node_choice_rows() if row["id"] != exclude]
        if not rows:
            self.show_error(t("没有目标分类"), t("请先创建分类"))
            return None
        items = [(row["id"], "    " * row["depth"] + row["name"]) for row in rows]
        paths = {row["id"]: row["path"] for row in rows}
        node_id, ok = dialogs.choose_item(
            self.window(), title, t("选择目标分类"), items, code="MOVE/COPY",
            searchable=len(rows) > 8, paths=paths)
        return node_id if ok else None

    def _assign_to_chosen(self, paths, title, copy, source_parent):
        node_id = self.choose_target_node(t(title), copy, exclude=source_parent)
        if node_id is None:
            return
        self.assign_resources(paths, node_id, copy=copy, source_node=source_parent)

    def _batch_assign(self, copy):
        entries = [e for e in self._selected_entries() if e["kind"] == "resource"]
        if not entries:
            self.show_error(t("无法执行"), t("请先选择表情"))
            return
        node_id = self.choose_target_node(
            t("复制到分类") if copy else t("移动到分类"), copy,
            exclude=self.content_scope_node() if not copy else None)
        if node_id is None:
            return
        self.assign_resources([e["path"] for e in entries], node_id, copy=copy)

    def _batch_remove_membership(self):
        paths = self.get_selected_paths()
        if not ActionPolicy.enabled('remove_from_category', self._action_context(paths)):
            return
        if not dialogs.confirm(self.window(), t('移出分类'), t('移出选中表情的当前分类关系？'),
            ok_text=t('移出'), hint=t('只删除分类关系，表情文件仍保留在表情库中。')):
            return
        if not ActionPolicy.enabled('remove_from_category', self._action_context(paths)):
            return
        for path in paths:
            self.storage.remove_image_from_category(path, self.content_scope_node())
        self.sidebar.refresh_list(self.current_node)
        self.refresh_content_incremental(reason='remove_membership')

    def _batch_tags(self):
        entries = self._selected_entries()
        paths = [e["path"] for e in entries if e["kind"] == "resource"]
        if not ActionPolicy.enabled('tag_edit', self._action_context(paths)):
            self.show_error(t("无法执行"), t("请先选择表情"))
            return
        dialog = dialogs.TagEditorDialog(self.window(), self.storage, paths)
        if dialog.exec():
            self.refresh_content_incremental(reason="batch_tags", paths=paths, parents=set())
            self.show_success(t("标签已更新"), quiet=True)

    def _batch_delete(self):
        entries = [e for e in self._selected_entries() if e["kind"] == "resource"]
        if not entries:
            self.show_error(t("无法执行"), t("请选择要删除的表情"))
            return
        paths = [e["path"] for e in entries]
        context = self._action_context(paths, revalidate=True)
        if not ActionPolicy.enabled('delete', context):
            return
        missing_only = not context.existing
        hint = ('只删除索引记录，磁盘文件不会被改动。' if missing_only else
                '文件会进入 Windows 系统回收站，索引记录同时移除。' if len(context.existing) == len(paths) else
                '现有文件进入 Windows 回收站；失效表情只移除索引记录。')
        if not dialogs.confirm(self.window(), t(ActionPolicy.delete_label(context)),
                               t('删除选中的 {value_0} 个表情？').format(value_0=len(paths)),
                               ok_text=t('移除记录' if missing_only else '删除'), danger=True, code="DELETE",
                               hint=t(hint)):
            return
        result = self.storage.delete_images_batch(paths)
        self.sidebar.refresh_list(self.current_node)
        self.refresh_content_incremental(reason='delete_resources')
        if result['failed']:
            self.show_error(t("部分删除失败"), t('{value_0} 项未能移入回收站，记录已保留').format(value_0=result['failed']))
        self.show_success(t("删除完成"),
                          t('已删除 {value_0} 项，清理失效记录 {value_1} 项').format(value_0=result['deleted'], value_1=result['missing_cleaned']), quiet=True)

    def _show_more_menu(self):
        self._build_selection_more_menu().exec(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft()))

    def _build_selection_more_menu(self):
        menu = RoundMenu(parent=self)
        paths = self.get_selected_paths()
        self._add_ocr_actions(menu,paths)
        menu.addSeparator()
        context = self._action_context(paths, revalidate=True)
        def action(icon, label, callback, enabled):
            item = translated(Action, icon, label, parent=menu)
            item.setEnabled(enabled)
            item.triggered.connect(callback)
            menu.addAction(item)
            return item
        if self._selection_overflow:
            action(FIF.COPY, '加入分类…', lambda: self._batch_assign(copy=True), self.btn_add_to.isEnabled())
            action(FIF.MOVE, '移动到…', lambda: self._batch_assign(copy=False), self.btn_move_to.isEnabled())
            action(FIF.TAG, '标签…', self._batch_tags, self.btn_tags.isEnabled())
            order_menu = RoundMenu(title=t('顺序'), parent=menu)
            for label, front in (('移到最前', True), ('移到最后', False)):
                item = translated(Action, label, parent=order_menu)
                item.setEnabled(self.btn_arrange.isEnabled())
                item.triggered.connect(lambda checked=False, front=front: self._move_selection_extreme(front))
                order_menu.addAction(item)
            menu.addMenu(order_menu)
            menu.addSeparator()
        if context.active_view != ROOT:
            action(FIF.REMOVE, '移出当前分类', self._batch_remove_membership,
                   ActionPolicy.enabled('remove_from_category', context))
        export = translated(Action, FIF.SHARE, '导出选中项到文件夹…', parent=menu)
        export.setEnabled(ActionPolicy.enabled('export', context))
        export.triggered.connect(self._execute_batch_export)
        menu.addAction(export)
        copy = translated(Action, FIF.COPY, '复制文件路径', parent=menu)
        copy.setEnabled(ActionPolicy.enabled('copy_path', context))
        copy.triggered.connect(lambda: self._copy_paths(paths))
        menu.addAction(copy)
        if ActionPolicy.enabled('show_in_explorer', context):
            action(FIF.FOLDER, '在资源管理器中显示', lambda: self.reveal_in_explorer(paths[0]), True)
        return menu

    def _move_selection_extreme(self, front):
        if not self._manual_order_available():
            return
        grouped = {}
        for entry in self._selected_entries():
            if entry['kind'] != 'resource':
                continue
            grouped.setdefault(entry['_parent'], set()).add(entry['id'])
        for parent, ids in grouped.items():
            stream = self.storage.entries_of(parent)
            moving = [e for e in stream if e['id'] in ids]
            remaining = [e for e in stream if e['id'] not in ids]
            self.storage.set_content_order(parent, moving+remaining if front else remaining+moving)
        self.refresh_content_incremental(reason='move_extreme')

    def _write_entry_order(self, ordered_entries):
        try:
            if self._display_mode == "mixed":
                self.storage.set_content_order(self.content_scope_node(), ordered_entries)
            else:
                self.storage.reorder_resources(
                    self.content_scope_node(), [e["id"] for e in ordered_entries if e["kind"] == "resource"])
        except ValueError as exc:
            self.show_error(t("排序失败"), str(exc))
            return
        # Re-read the saved order so both existing widgets and unfinished
        # render batches follow the same mixed list after a manual reorder.
        self.refresh_content_incremental(reason='entry_order')

    def _filter_by_tag(self):
        tags = self.storage.all_tags()
        if not tags:
            self.show_error(t("没有标签"), t("表情库中还没有任何标签"))
            return
        choices = [(tag, f"{tag}  ({count})") for tag, count in tags.items()]
        tag, ok = dialogs.choose_item(self.window(), t("按标签筛选"), t("选择一个标签"), choices, code="TAG/FILTER")
        if ok:
            self.active_tags.add(tag)
            self.refresh_content()

    def _execute_batch_export(self):
        paths = self.get_selected_paths()
        if not ActionPolicy.enabled('export', self._action_context(paths, revalidate=True)):
            self.show_error(t("无法导出"), t("请先选择表情"))
            return
        import shutil
        directory = QFileDialog.getExistingDirectory(self, t("选择导出目标文件夹"), "")
        if not directory:
            return
        count = 0
        for path in dict.fromkeys(paths):
            if not self.storage.availability.exists(path, revalidate=True):
                continue
            record = self.storage.resource_of(path)
            original = record["display_name"] if record else os.path.basename(path)
            try:
                shutil.copy2(path, self._unique_path(directory, original))
                count += 1
            except OSError as exc:
                self.show_error(t("导出失败"), str(exc))
                return
        self.show_success(t("导出完成"), t('{value_0} 项 → {value_1}').format(value_0=count, value_1=directory))

    @staticmethod
    def _unique_path(directory, original_name):
        base, ext = os.path.splitext(original_name)
        target = os.path.join(directory, original_name)
        counter = 1
        while os.path.exists(target):
            target = os.path.join(directory, f"{base}({counter}){ext}")
            counter += 1
        return target

    # ==================================================================
    # Menus
    # ==================================================================
    def _show_filter_menu(self):
        self.filter_flyout.toggle(self.filter_state)

    def _update_filter(self, key, value):
        setattr(self.filter_state, key, value)
        self.refresh_content()

    def _clear_filter(self):
        self.filter_state = FilterState()
        self.active_tags.clear()
        self.search_keyword = ""
        self.search_box.blockSignals(True)
        self.search_box.setText("")
        self.search_box.blockSignals(False)
        self._search_timer.stop()
        self.refresh_content()

    def show_context_menu(self, widget, position):
        self.preview_controller.cancel()
        entry = widget.content_entry
        self._selection_parents[entry['path']] = entry['_parent']
        if entry['path'] not in self.selected_keys:
            self._select_single(entry['path'])
        self._build_resource_menu(widget).exec(widget.mapToGlobal(position))

    def show_node_context_menu(self, widget, position):
        self._build_node_context_menu(widget).exec(widget.mapToGlobal(position))

    def _build_node_context_menu(self, widget):
        menu = RoundMenu(parent=self)
        for icon, label, callback in (
            (FIF.FOLDER, '打开', lambda: self.set_node(widget.node_id)),
            (FIF.DOWN, '展开 / 折叠内容', lambda: self.toggle_node_expansion(widget.node_id)),
        ):
            item = translated(Action, icon, label, parent=menu)
            item.triggered.connect(callback)
            menu.addAction(item)
        return menu

    def _add_ocr_actions(self,menu,paths):
        from fluent_ui.components.ocr_controls import request_recognition,edit_text
        from services.ocr_service import ocr_service
        service=ocr_service(self.storage)
        for title,force in [('识别文字',False),('重新识别文字',True)]:
            item=translated(Action,FIF.SCAN_TEXT,title,parent=menu)
            item.setEnabled(bool(paths) and service.available)
            item.triggered.connect(lambda checked=False,force=force:request_recognition(self,self.storage,paths,force))
            menu.addAction(item)
        if len(paths)==1:
            item=translated(Action,FIF.DOCUMENT,'查看与编辑文字',parent=menu)
            item.triggered.connect(lambda:edit_text(self,self.storage,paths[0]));menu.addAction(item)

    def _build_resource_menu(self, widget):
        path = widget.image_path
        paths = self.get_selected_paths() if path in self.selected_keys else [path]
        paths = paths or [path]
        parent = widget.content_entry['_parent']
        menu = RoundMenu(parent=self)
        def action(icon, title, callback, enabled=True):
            item = translated(Action, icon, title, parent=menu)
            item.setEnabled(enabled)
            item.triggered.connect(callback)
            menu.addAction(item)
            return item
        single = len(paths) == 1
        context = self._action_context(paths, revalidate=True)
        if self.mode == 'normal' and ActionPolicy.enabled('send', context):
            action(FIF.SEND, '发送表情', lambda: self.use_resource(path))
            menu.addSeparator()
        from fluent_ui.components.category_menu import CategoryTargetMenu
        for copy, title, icon in ((True, '添加到分类', FIF.COPY), (False, '移动到分类', FIF.MOVE)):
            can_move = any(self._selection_parents.get(p, parent) != ROOT for p in paths)
            branch=CategoryTargetMenu(title,self.storage,lambda target,c=copy:self.assign_resources(paths,target,copy=c),menu)
            branch.setIcon(icon);menu.addMenu(branch)
            if not (ActionPolicy.enabled('category_membership', context) and (copy or can_move)):
                branch.menuItem.setFlags(branch.menuItem.flags()&~Qt.ItemIsEnabled)
        if context.active_view != ROOT:
            action(FIF.REMOVE, '移出当前分类', self._batch_remove_membership,
                   ActionPolicy.enabled('remove_from_category', context))
        action(FIF.TAG, '编辑标签', lambda: self._open_tag_editor(paths), ActionPolicy.enabled('tag_edit', context))
        self._add_ocr_actions(menu,paths)
        menu.addSeparator()
        # Revealing the file replaces the path tooltip the cards used to show.
        action(FIF.FOLDER, '在文件资源管理器中显示', lambda: self.reveal_in_explorer(path),
               ActionPolicy.enabled('show_in_explorer', context))
        action(FIF.COPY, '复制文件路径', lambda: self._copy_paths(paths), ActionPolicy.enabled('copy_path', context))
        action(FIF.SHARE, '导出所选表情', self._execute_batch_export, ActionPolicy.enabled('export', context))
        if ActionPolicy.enabled('thumbnail_frame', context) or (single and not context.existing):
            menu.addSeparator()
        if single and not context.existing:
            action(FIF.LINK, '重新绑定文件…', lambda: self.rebind_resource(path))
        if ActionPolicy.enabled('thumbnail_frame', context):
            action(FIF.PHOTO, '选择缩略图帧…', lambda: self._choose_thumbnail_frame(path))
        menu.addSeparator()
        action(FIF.FOLDER, '设为当前分类图标', lambda: self._set_category_icon(path, context.active_view),
               context.active_view != ROOT and ActionPolicy.enabled('set_icon', context))
        action(FIF.PHOTO, '设为软件图标', lambda: self._set_application_icon(path),
               ActionPolicy.enabled('set_icon', context))
        menu.addSeparator()
        action(FIF.DELETE, ActionPolicy.delete_label(context), self._batch_delete,
               ActionPolicy.enabled('delete', context))
        return menu

    # -- resource operations -------------------------------------------
    def _action_context(self, paths=None, *, revalidate=False):
        return ActionContext.build(self.storage, self.get_selected_paths() if paths is None else paths,
                                   self.content_scope_node(), revalidate=revalidate)

    def _availability_changed(self, path, status):
        self.renderer.loader.invalidate([path])
        self.refresh_content_incremental(reason='availability', paths=[path], parents=set())

    def _copy_paths(self, paths):
        if ActionPolicy.enabled('copy_path', self._action_context(paths)):
            QApplication.clipboard().setText('\n'.join(paths))
            self.feedback_host.toast(t('已复制文件路径'))

    def _quick_tag(self, path, tag):
        self.storage.apply_tags([path], [tag], "add")
        self.refresh_content_incremental(reason='quick_tag', paths=[path], parents=set())
        self.show_success(t("标签已更新"), tag, quiet=True)

    def _open_tag_editor(self, paths):
        if not ActionPolicy.enabled('tag_edit', self._action_context(paths)):
            return
        if dialogs.TagEditorDialog(self.window(), self.storage, paths).exec():
            self.refresh_content_incremental(reason='tag_editor', paths=paths, parents=set())

    def _reload_resource_thumbnail(self, path):
        self.renderer.loader.invalidate([path])
        self.refresh_content_incremental(reason='thumbnail', paths=[path], parents=set())

    def _choose_thumbnail_frame(self, path):
        if not ActionPolicy.enabled('thumbnail_frame', self._action_context([path], revalidate=True)):
            return
        if not dialogs.FramePickerDialog(self.window(), self.storage, path).exec():
            return
        frame = int(self.storage.resource_metadata(path).get("thumb_frame", 0) or 0)
        for widget in self._all_card_widgets:
            if getattr(widget, "image_path", None) == path and hasattr(widget, "set_frame"):
                widget.set_frame(frame)
        self.show_success(t("缩略图帧已更新"), quiet=True)

    def _set_category_icon(self, path, node_id):
        if not ActionPolicy.enabled('set_icon', self._action_context([path], revalidate=True)):
            return
        self.storage.set_node_icon(node_id, path)
        self.sidebar._refresh_node_icon(node_id)
        self.show_success(t("分类图标已更新"), quiet=True)

    def _remove_from_current(self, path):
        if not ActionPolicy.enabled('remove_from_category', self._action_context([path])):
            return
        if self.storage.remove_image_from_category(path, self.content_scope_node()):
            self.sidebar.refresh_list(self.current_node)
            self.refresh_content_incremental(reason='remove', parents={self.content_scope_node()})
            self.show_success(t("已移出分类"), quiet=True)

    def _delete_single(self, path):
        self._select_single(path)
        self._batch_delete()

    def _set_application_icon(self, path):
        if not ActionPolicy.enabled('set_icon', self._action_context([path], revalidate=True)):
            return
        if not dialogs.confirm(self.window(), t('设置软件图标'), t('将此表情设为 NekoriEmojy 软件图标？'), ok_text=t('确认')):
            return
        if not ActionPolicy.enabled('set_icon', self._action_context([path], revalidate=True)):
            return
        from services.app_icon import ApplicationIconService
        try:
            ApplicationIconService(self.config).set_from_image(path,frame=int(self.storage.resource_metadata(path).get("thumb_frame",0) or 0))
        except Exception as exc:
            self.show_error(t("设置软件图标失败"), str(exc))
            return
        self.reload_application_icon()
        self.show_success(t("软件图标已更新"), quiet=True)

    def reload_application_icon(self):
        window = self.window()
        if hasattr(window, "reload_application_icon"):
            window.reload_application_icon()

    # ==================================================================
    # Missing handling
    # ==================================================================
    def rebind_resource(self, path):
        record = self.storage.resource_of(path)
        if not record:
            self.show_error(t("重新绑定失败"), t("表情记录不存在"))
            return
        chosen, _ = QFileDialog.getOpenFileName(self.window(), t("重新绑定文件"), "", t("所有文件 (*.*)"))
        if not chosen:
            return
        try:
            target = self._ensure_inside_library(chosen)
            self.storage.rebind_resource(record["id"], target)
        except Exception as exc:
            self.show_error(t("重新绑定失败"), str(exc))
            return
        self.renderer.loader.invalidate([path, target])
        self.refresh_content_incremental(reason='rebind', paths=[target])
        self.show_success(t("重新绑定成功"), t("分类、排序、标签与已有元数据均已保留"), quiet=True)

    def _ensure_inside_library(self, path):
        """Rebinding accepts library files; outside files are imported first."""
        try:
            self.storage.index.relative_path(path)
            return path
        except ValueError:
            pass
        result = self.storage.import_paths([path])
        if not result.paths:
            raise RuntimeError("无法把该文件导入表情库")
        return result.paths[0]

    def forget_resource(self, path):
        if not ActionPolicy.enabled('forget', self._action_context([path], revalidate=True)):
            return
        record = self.storage.resource_of(path)
        if not record:
            return
        if not dialogs.confirm(self.window(), t("删除表情记录"), t("删除这条表情记录？"),
                               ok_text=t("删除记录"), danger=True, code="FORGET",
                               hint=t("只删除索引记录，磁盘文件不会被改动。")):
            return
        if not ActionPolicy.enabled('forget', self._action_context([path], revalidate=True)):
            return
        self.storage.forget_resource(record["id"])
        self.sidebar.refresh_list(self.current_node)
        self.refresh_content_incremental(reason="forget")
        self.show_success(t("记录已删除"), quiet=True)

    # ==================================================================
    # Import
    # ==================================================================
    def import_paths_to(self, paths, node_id, position=None):
        """Import into a category; without a placement the new items go first.

        An import with no explicit insertion point (clipboard paste, toolbar
        import, a folder dropped on the category as a whole) lands at the front
        of the canonical stream so the user immediately sees what arrived.
        Only a Placement Context or a precise drop point passes an index.
        """
        if not paths:
            return
        insert_position = 0 if position is None else position
        from services.resource_import import ImportTarget
        return self.imports.submit(paths,ImportTarget(node_id or ALL_RESOURCES,insert_position),self)

    def _queued_files_finished(self,request):
        self.renderer.loader.invalidate(request.paths)
        self.sidebar.refresh_list(self.current_node)
        parents={ROOT,request.target.parent_node}
        if request.operation:parents.update(n['id'] for n in self.storage.index.nodes())
        self.refresh_content_incremental(reason='queued_import',paths=set(request.paths),parents=parents)

    def _sync_background_tasks(self):
        host=self.feedback_host
        for key,request in tuple(self.imports.requests.items()):
            job=self.ocr.jobs.get(key,{})
            state=request.state;details='\n'.join(request.errors)
            summary=t('新增 {saved} 张，已处理重复 {duplicates} 张，跳过 {skipped} 张，失败 {failed} 张').format(
                saved=request.saved,duplicates=request.duplicates,skipped=request.skipped,failed=request.failed)
            if state=='waiting':title=t('等待导入表情');outcome='waiting';done=0;total=request.total
            elif state=='decision':
                title=t('等待处理重复表情（{count}）').format(count=request.conflicts)
                outcome='waiting';done=0;total=0
            elif state=='running':title=t('正在导入表情');outcome='running';done=request.done;total=request.total
            elif state=='recognizing':
                title=t('正在识别新表情文字');outcome='running'
                done=sum(job.get(k,0) for k in ('done','failed','skipped'));total=job.get('total',0)
            else:
                title=(t('导入部分完成') if request.failed else t('导入处理完成')) if state=='completed' else t('导入失败') if state=='failed' else t('导入处理已停止')
                outcome='error' if state=='failed' else 'cancelled' if state=='cancelled' else 'partial' if request.failed else 'success'
                done=request.done;total=request.total
            if getattr(request,'kept',0):summary+=' · '+t('其中保留独立条目 {count} 张').format(count=request.kept)
            if request.kind=='migration' and state not in {'recognizing','decision'}:
                title=t('等待 Suzu 迁移') if state=='waiting' else t('正在 Suzu 迁移') if state=='running' else (t('Suzu 迁移部分完成') if request.failed else t('Suzu 迁移完成')) if state=='completed' else t('Suzu 迁移失败') if state=='failed' else t('Suzu 迁移已停止')
                if state in {'waiting','running'}:
                    # The task title is the only persistent text bound to this
                    # job; the content stays as its tooltip/summary. Both are
                    # cleared by the normal terminal states below.
                    title=t('等待迁移，勿动数据') if state=='waiting' else t('迁移中，勿动源数据')
                    summary+='\n'+t('迁移期间请保持源数据可用，不要移动或删除源文件；Nekori 只读取源数据，不会修改它。')
            if job.get('failed'):
                summary+=' · '+t('文字识别失败 {count} 张').format(count=job['failed'])
                details+='\n'+job.get('error','')
                if outcome=='success':outcome='partial'
            host.upsert_task(key,title,current=done,total=total,state=outcome,content=summary,kind='import',
                cancel=lambda k=key:self.imports.cancel(k),details=details.strip())
        for key,job in tuple(self.ocr.jobs.items()):
            if key in self.imports.requests:continue
            done=sum(job.get(k,0) for k in ('done','failed','skipped'));state=job['state']
            outcome=state if state in {'cancelled','interrupted'} else 'running' if state=='running' else ('partial' if job.get('done') or job.get('skipped') else 'error') if job.get('failed') else 'success' if state=='completed' else state
            title=t('重新识别全部表情') if job.get('force') and job.get('origin')=='library' else t('补充识别') if job.get('origin')=='library' else t('识别表情文字')
            content=t('表情 {done}/{total} 张，失败 {failed} 张，跳过 {skipped} 张').format(done=done,total=job.get('total',0),failed=job.get('failed',0),skipped=job.get('skipped',0))
            if state in {'cancelled','interrupted'}:title=t('文字识别已停止')
            resume=(lambda k=key,f=job.get('force',False):self.ocr.supplement(force=f,job_id=k)) if job.get('origin')=='library' and state in {'cancelled','interrupted'} else None
            host.upsert_task(key,title,current=done,total=job.get('total',0),state=outcome,content=content,kind='ocr',
                cancel=lambda k=key:self.ocr.cancel(job_id=k),resume=resume,details=job.get('error',''))

    def _on_import_progress(self, current, total):
        self.task_status.update(t('正在处理: {value_0} / {value_1}').format(value_0=current, value_1=total), current=current, total=total)

    def _on_import_finished(self, saved_count, skipped_count, failed_count, silent=False, folder_stats=None):
        if self._import_info_bar:
            self._import_info_bar.close()
            self._import_info_bar = None
        # The sidebar only gains counts; the gallery inserts just the new cards
        # instead of reloading the page the user is looking at.
        self.sidebar.refresh_list(self.current_node)
        self.refresh_content_incremental(reason='import')
        parts = []
        if saved_count:
            parts.append(t("导入 {count} 项").format(count=saved_count))
        if skipped_count:
            parts.append(t("跳过重复 {count} 项").format(count=skipped_count))
        if failed_count:
            parts.append(t("失败 {count} 项").format(count=failed_count))
        self.task_status.finish(t('导入完成'), '，'.join(parts),
                                outcome=('partial' if saved_count or skipped_count else 'error') if failed_count else 'success')

    def _start_background_import(self, filepaths, delete_after=False, silent=False,
                                 target_category=None, folder_stats=None, file_categories=None):
        """Legacy signature kept for the inbox and clipboard paths."""
        node_id = ALL_RESOURCES
        if target_category and target_category not in ("全部表情", "未分类", "全部资源"):
            try:
                node_id = self.storage.resolve_category(target_category)
            except KeyError:
                node_id = ALL_RESOURCES
        from services.resource_import import ImportTarget
        return self.imports.submit(filepaths,ImportTarget(node_id),self,delete_after=delete_after)

    def _import_dropped_folders(self, folders, local_files):
        self._start_background_import([*folders, *local_files], target_category=self.content_scope_node())

    def handle_global_paste(self):
        """Ctrl+V: paste into the current category, appended."""
        self.paste_into(Placement(self.content_scope_node(), None, None, False,
                                  self._exact_placement_available()))

    def paste_into(self, placement):
        """Paste using a placement resolved from where the user clicked."""
        data_type, data = self.clipboard.get_data_from_clipboard()
        parent = placement.parent or self.content_scope_node()
        position = placement.resolved_position()
        if data_type == 'file':
            data=[p for p in data if p.lower().endswith(self.storage.SUPPORTED_FORMATS) or os.path.isdir(p)]
            if not data:
                self.feedback_host.toast(t('剪贴板中没有可导入的表情'));return
            self.import_paths_to(data, parent, position=position)
        elif data_type == 'image':
            from services.resource_import import ImportTarget
            self.imports.submit([data.copy()],ImportTarget(parent,position),self)
        elif data_type == 'network_url':
            # A download finishes later, so an index captured now could point
            # into a stream that changed meanwhile; it appends by design.
            from services.resource_import import ImportTarget
            self.imports.submit([data],ImportTarget(parent,position),self)
        else:
            self.feedback_host.toast(t('剪贴板中没有可导入的表情'))

    def _on_download_finished(self, success, temp_filepath, error_msg, url, target_node=None):
        for thread in self.download_threads[:]:
            if thread.url == url:
                self.download_threads.remove(thread)
                thread.deleteLater()
        if not success:
            self.task_status.fail(t("下载失败"), t('无法获取网络表情: {value_0}').format(value_0=error_msg))
            return
        self._start_background_import([temp_filepath], delete_after=True,
                                      target_category=target_node or self.content_scope_node())

    # ==================================================================
    # Exchange packages (Suzu share format, kept for compatibility)
    # ==================================================================
    def _import_exchange_package(self):
        from services.exchange_import import ExchangeImportService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        if self.import_thread is not None and self.import_thread.isRunning():
            self.show_error(t("导入中"), t("请等待当前导入任务完成"))
            return
        path, _ = QFileDialog.getOpenFileName(self.window(), t("导入表情合集"), "", t("表情合集 (*.zip)"))
        if not path:
            return
        service = ExchangeImportService(storage=self.storage)
        try:
            saved, skipped = run_exchange_task(
                self.window(), "正在导入表情合集", lambda progress: service.import_zip(path, progress))
            self.storage.force_reload()
            self.sidebar.refresh_list(self.current_node)
            self.on_images_changed()
            message = t('新增 {value_0} 个，跳过 {value_1} 个').format(value_0=saved, value_1=skipped)
            if service.warnings:
                message += "\n" + "\n".join(map(str, service.warnings))
            self.show_success(t("导入完成"), message)
        except Exception as exc:
            self.show_error(t("导入失败"), str(exc))

    def _export_all_exchange_package(self, owner=None):
        self._export_exchange_package(owner=owner)

    def _export_selected_categories_exchange_package(self, owner=None):
        owner = owner or self.window()
        from fluent_ui.components.feedback import feedback_for
        from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem
        categories = self.storage.get_all_categories()
        if not categories:
            feedback_for(owner).notice(t("无法导出"), t("请先创建分类"), error=True)
            return
        dialog = dialogs.NekoriDialog(owner, t("选择要导出的分类"))
        layout = dialog.body
        choices = QListWidget(dialog)
        for name in categories:
            item = QListWidgetItem(name, choices)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
        layout.addWidget(choices)
        dialog.add_button(t("取消"), on_click=dialog.reject)
        accept_button = dialog.add_button(t("确定"), role="primary", on_click=dialog.accept, enabled=False)
        choices.itemChanged.connect(lambda _: accept_button.setEnabled(
            any(choices.item(i).checkState() == Qt.Checked for i in range(choices.count()))))
        dialog.resize(360, 420)
        if dialog.exec() == QDialog.Accepted:
            selected = [choices.item(i).text() for i in range(choices.count())
                        if choices.item(i).checkState() == Qt.Checked]
            self._export_exchange_package(selected, owner=owner)

    def _export_exchange_package(self, selected_categories=None, owner=None):
        owner = owner or self.window()
        from fluent_ui.components.feedback import feedback_for
        from services.exchange_export import ExchangeExportService
        from fluent_ui.components.exchange_task_dialog import run_exchange_task
        path, _ = QFileDialog.getSaveFileName(
            owner, t("导出表情合集"), "SuzuEmojy.zip", t("表情合集 (*.zip)"))
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            service = ExchangeExportService(storage=self.storage)
            manifest = run_exchange_task(owner, "正在导出表情合集", lambda progress:
                service.export_zip(path, selected_categories, progress))
            message = t('表情合集已保存到\n{value_0}').format(value_0=path)
            if manifest.get("skipped"):
                message += "\n" + t("跳过 {count} 个不支持的文件").format(count=len(manifest['skipped']))
            feedback_for(owner).notice(t("导出完成"), message) if manifest.get("skipped") else feedback_for(owner).toast(t("导出完成"), message)
        except Exception as exc:
            feedback_for(owner).notice(t("导出失败"), str(exc), error=True)

    # ==================================================================
    # Drag & drop in the content area
    # ==================================================================
    def _over_content(self, position):
        """Whether a GalleryInterface point is inside the gallery itself.

        The sidebar, the tag panel and the context strip are siblings inside
        this widget: a drag that none of them accepts must not silently become
        a gallery drop measured from a point in another panel.
        """
        return viewport_rect(self.scroll_area, self).contains(position)

    def _dragged_kind(self, mime):
        """What is travelling, in the contract's terms."""
        for mime_type, effect in ((RESOURCE_MIME, MOVE), (NODE_MIME, MOVE),
                                  (TAG_MIME, None)):
            if mime.hasFormat(mime_type):
                return mime_type, effect
        if mime.hasUrls():
            return 'urls', IMPORT
        return None, None

    def _hit_test(self, position):
        """Nearest rendered entry, its index, its rect and which side was hit.

        Measured against the flow index, which already holds one rectangle per
        entry, instead of every realized card: it is both cheaper and complete,
        because the pointer can only be over a place the layout knows about.
        """
        point = self.grid_container.mapFrom(self, position)
        best, best_index, best_rect, distance, after = None, -1, None, float('inf'), False
        for index, rect in enumerate(self.renderer.index.rects):
            d = (max(rect.left()-point.x(), 0, point.x()-rect.right())
                 + max(rect.top()-point.y(), 0, point.y()-rect.bottom()))
            if d < distance:
                best, best_index, best_rect, distance = self._entries[index], index, rect, d
                after = (point.y() > rect.center().y() if best['kind'] == 'node'
                         else point.x() > rect.center().x())
        return best, best_index, best_rect, after

    def _nearest_entry(self, pos):
        entry, _index, _rect, after = self._hit_test(pos)
        return entry, after

    def _subtree_ids(self, node_id):
        return {node['id'] for node in self.storage.index.subtree(node_id)}

    def _node_insert_index(self, parent, target_node, placement, moving):
        """Canonical slot next to `target_node` once the moving block is out."""
        stream = [entry for entry in self.storage.entries_of(parent)
                  if entry['id'] not in moving]
        for index, entry in enumerate(stream):
            if entry['id'] == target_node:
                return index + (1 if placement == INSERT_AFTER else 0)
        return len(stream)

    def _resolve_drop(self, position, mime):
        """One contract for every drag that reaches the gallery.

        Returns `(target, rect, vertical)`; `rect` is what the shared indicator
        is measured from and `vertical` says whether the insertion runs between
        two cards in a row or between two full-width rows.
        """
        kind, effect = self._dragged_kind(mime)
        if kind == TAG_MIME:
            entry, _index, rect, _after = self._hit_test(position)
            point = self.grid_container.mapFrom(self, position)
            if entry is None or not rect.contains(point):
                return INVALID_TARGET, None, False
            return tag_drop_target(entry['id'], category=entry['kind'] == 'node'), rect, False
        if kind is None:
            # Tags reorder against tags; the gallery is not a tag target.
            return INVALID_TARGET, None, False
        plain_order = not self.search_keyword.strip() and self.content_sort == 'manual'
        if kind in (NODE_MIME, RESOURCE_MIME) and not plain_order:
            return INVALID_TARGET, None, False

        moving_nodes = set(parse_node_payload(mime.data(NODE_MIME))) if kind == NODE_MIME else set()
        entry, _index, rect, after = self._hit_test(position)
        if entry is None or self._below_last_card(position):
            # The empty area under the last row means "at the end of this
            # location", not "next to whichever card happens to be closest".
            last = self.renderer.index.rects[-1] if self.renderer.index.rects else None
            return (DropTarget(APPEND, effect, None, self.content_scope_node(),
                               len(self.storage.entries_of(self.content_scope_node()))), last, False)

        if entry['kind'] == 'node':
            if kind != NODE_MIME:
                # A resource can only ever go *into* a category, never between
                # two of them; there is no slot "next to" a category row.
                return DropTarget(INTO, effect, entry['id'], entry['id']), rect, False
            point = self.grid_container.mapFrom(self, position)
            placement = edge_placement(axis_ratio(rect, point, horizontal=False))
            if placement == INTO:
                if entry['id'] in moving_nodes or self._subtree_ids(entry['id']) & moving_nodes:
                    # Dropping a category into itself or its own subtree would
                    # make a cycle.
                    return INVALID_TARGET, None, False
                return DropTarget(INTO, effect, entry['id'], entry['id']), rect, False
            parent = entry['_parent']
            index = self._node_insert_index(parent, entry['id'], placement, moving_nodes)
            return DropTarget(placement, effect, entry['id'], parent, index), rect, False

        parent = entry['_parent']
        placement = INSERT_AFTER if after else INSERT_BEFORE
        return (DropTarget(placement, effect, entry['id'], parent,
                           entry['position']+bool(after)), rect, True)

    def _track_drop(self, event, position=None):
        position = position if position is not None else event.position().toPoint()
        target, rect, vertical = (INVALID_TARGET, None, False)
        if self._over_content(position):
            target, rect, vertical = self._resolve_drop(position, event.mimeData())
        self._drop_target = target
        if not target.valid:
            self.drop_feedback.clear()
            self.drop_scroller.stop()
            event.ignore()
            return None
        event.acceptProposedAction()
        self.drop_scroller.track(self.scroll_area.viewport().mapFrom(self, position))
        self.preview_controller.cancel()
        self.feedback_host.set_overlays_suppressed(True)
        self.drop_feedback.show_target(target.placement, rect, vertical=vertical)
        return target

    def _begin_drop(self, event, position=None):
        from fluent_ui.components.drop_contract import DragSession
        self._clear_drop()
        self._gallery_drag_session = DragSession(event.mimeData())
        if not self._gallery_drag_session.supported:
            event.ignore()
            return
        self._track_drop(event, position)
        # Accept the receive surface even over a gap: Qt will otherwise never
        # deliver the subsequent move onto the first resource card.
        event.acceptProposedAction()

    def dragEnterEvent(self, event):
        self._begin_drop(event)

    def _clear_drop(self):
        self._drop_target = INVALID_TARGET
        self._gallery_drag_session = None
        self.feedback_host.set_overlays_suppressed(False)
        self.drop_feedback.clear()
        self.drop_scroller.stop()

    def dragLeaveEvent(self, event):
        self._clear_drop()
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        self._track_drop(event)

    def dropEvent(self, event):
        self._complete_drop(event, event.position().toPoint())

    def _complete_drop(self, event, position):
        session=getattr(self, '_gallery_drag_session', None)
        try:
            target,_rect,_vertical=self._resolve_drop(position,event.mimeData())
            if session and self._over_content(position) and session.commit(target,
                    lambda resolved,block:self._commit_drop_payload(resolved,event.mimeData(),block)):
                event.acceptProposedAction()
            else:
                event.ignore()
        finally:
            self._clear_drop()

    def _commit_drop_payload(self, target, mime, block):
        if mime.hasFormat(TAG_MIME):
            self._commit_tag_drop(target, block)
        elif target.effect == IMPORT:
            self._import_urls(mime, target)
        elif mime.hasFormat(NODE_MIME):
            self._apply_node_drop(block, target)
        elif mime.hasFormat(RESOURCE_MIME):
            self._reorder_by_drop(block, target)

    def _apply_node_drop(self, node_ids, target):
        """Category blocks keep their internal order wherever they land."""
        if not node_ids:
            return
        parent = target.container_id
        self.sidebar._on_nodes_dropped(node_ids, parent, target.index)

    def _reorder_by_drop(self, paths, target):
        if not paths:
            return
        parent = target.container_id or self.content_scope_node()
        sources = self._resource_sources(paths)
        if any(source != parent for source in sources.values()):
            self.request_resource_drop(paths, parent, position=target.index)
            return
        with self.storage.lock:
            stream = self.storage.entries_of(parent)
            keys = set(paths)
            moving = [e for e in stream if e['kind'] == 'resource' and e['path'] in keys]
            if not moving:
                self.assign_resources(paths, parent, position=target.index)
                return
            # The worker may prepend imports while the user drags over a
            # still-visible card. Resolve against that card's stable ID, not
            # the old numeric slot captured by the viewport.
            anchor = next((i for i, e in enumerate(stream)
                           if e['kind'] == 'resource' and e['id'] == target.target_id), None)
            position = (anchor + (target.placement == INSERT_AFTER)) if anchor is not None else (
                target.index if target.index is not None else len(stream))
            before = stream[:position]
            position = sum(not(e['kind'] == 'resource' and e['path'] in keys) for e in before)
            remaining = [e for e in stream if not(e['kind'] == 'resource' and e['path'] in keys)]
            from services.manual_order import insert_block
            self.storage.set_content_order(parent, insert_block(remaining, moving, position))
        self.refresh_content_incremental(reason='drop_order', parents={parent})

    def _import_urls(self, mime, target):
        folders, files = [], []
        library = os.path.normcase(os.path.abspath(self.storage.images_dir))
        for url in mime.urls():
            if not url.isLocalFile():
                if url.scheme() in ("http", "https"):
                    from services.resource_import import ImportTarget
                    self.imports.submit([url.toString()],ImportTarget(target.container_id or self.content_scope_node(),target.index),self)
                continue
            local = url.toLocalFile()
            if os.path.isdir(local):
                folders.append(local)
            elif not os.path.normcase(os.path.abspath(local)).startswith(library):
                files.append(local)
        if not folders and not files:
            return
        self.import_paths_to([*folders, *files], target.container_id or self.content_scope_node(),
                             position=target.index)

    # ==================================================================
    # Hover preview, focus tracking, inbox
    # ==================================================================
    def on_hover_started(self, card, image_path):
        previous = getattr(self, '_hover_card', None)
        self._hover_card = card
        if previous is not None and previous is not card:
            previous.set_hovered(False)
        if self.feedback_host.toasts or self.feedback_host.hint_label.isVisible():
            return
        self.preview_controller.set_delay(self.config.get("preview_delay", 500))
        self.preview_controller.enter(card, image_path)

    def on_hover_ended(self, card):
        if getattr(self, '_hover_card', None) is card:
            self._hover_card = None
        self.preview_controller.leave(card)

    def _sync_hover_card(self):
        """Scrolling moves cards under a stationary pointer without Qt Leave."""
        previous = getattr(self, '_hover_card', None)
        if previous is not None and previous._is_dragging:
            return
        viewport = self.scroll_area.viewport()
        hit = QApplication.widgetAt(QCursor.pos())
        while hit is not None and hit is not viewport and not isinstance(hit, EmojiCard):
            hit = hit.parentWidget()
        if not isinstance(hit, EmojiCard) or not viewport.isAncestorOf(hit):
            hit = None
        if previous is not None and previous is not hit:
            previous.set_hovered(False)
        if hit is not None:
            hit.set_hovered(True)

    def get_preview_size(self):
        return self.config.get("preview_size", 320)

    def reveal_in_explorer(self, path):
        """Open the containing folder with this file selected."""
        import subprocess
        if not ActionPolicy.enabled('show_in_explorer', self._action_context([path], revalidate=True)):
            self.show_error(t('无法定位文件'), t('表情文件已不存在，可尝试重新绑定。'))
            return
        try:
            subprocess.Popen(['explorer', f'/select,{os.path.normpath(path)}'])
        except OSError as exc:
            self.show_error(t('无法定位文件'), str(exc))

    def get_preview_metadata(self, image_path):
        categories = self.storage.get_categories_by_image(image_path)
        keywords = self.storage.get_image_keywords(image_path)
        return ", ".join(categories), keywords or ""

    def get_preview_info(self, image_path):
        """File identity for the preview, shown there instead of as a tooltip."""
        try:
            relative = self.storage.index.relative_path(image_path)
        except ValueError:
            relative = os.path.basename(image_path)
        record=self.storage.index.resource(image_path) or {}
        return {'name': os.path.basename(image_path), 'path': relative,
                'ocr_text':record.get('ocr_text','')}

    def apply_preview_position(self):
        """Fixed preview overlays the gallery workspace; floating stays a tool window.

        The workspace, not the whole pane: the pane also holds Search and the
        docked TagPanel now, and a fixed preview must never sit on those.
        """
        fixed = str(self.config.get('preview_position', 'floating')) == 'fixed'
        self.preview_popup.apply_presentation(self.workspace if fixed else None)

    def track_active_window(self):
        self.send_target_service.capture_foreground()
        self._check_inbox()

    def _check_inbox(self):
        if self._inbox_scanning:
            return
        import time
        current_time = time.time()
        if current_time - self._last_cleanup_time > CLEANUP_THROTTLE_HOURS * 3600:
            self._last_cleanup_time = current_time
            self._cleanup_failed_inbox()
        if not os.path.exists(self.storage.inbox_dir):
            return
        self._inbox_scanning = True
        pending_files = []
        for filename in os.listdir(self.storage.inbox_dir):
            filepath = os.path.join(self.storage.inbox_dir, filename)
            if not os.path.isfile(filepath):
                continue
            if not filename.lower().endswith(self.storage.SUPPORTED_FORMATS):
                continue
            try:
                with open(filepath, 'a'):
                    pass
            except Exception:
                continue
            pending_files.append(filepath)
        if not pending_files:
            self._inbox_scanning = False
            return
        initial_sizes = {}
        for filepath in pending_files:
            try:
                initial_sizes[filepath] = os.path.getsize(filepath)
            except FileNotFoundError:
                pass
        QTimer.singleShot(1000, lambda: self._verify_and_import_inbox(initial_sizes))

    def _verify_and_import_inbox(self, initial_sizes):
        ready_files = []
        for filepath, size1 in initial_sizes.items():
            try:
                if os.path.getsize(filepath) == size1 and size1 > 0:
                    ready_files.append(filepath)
            except FileNotFoundError:
                pass
        if ready_files:
            self._start_background_import(ready_files, delete_after=True, silent=True)
        self._inbox_scanning = False

    def _cleanup_failed_inbox(self):
        if not os.path.exists(self.storage.inbox_failed_dir):
            return
        import time
        current_time = time.time()
        retention = FAILED_RETENTION_DAYS * 24 * 3600
        for filename in os.listdir(self.storage.inbox_failed_dir):
            filepath = os.path.join(self.storage.inbox_failed_dir, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                if current_time - os.path.getmtime(filepath) > retention:
                    os.remove(filepath)
            except Exception as exc:
                print(f"[ERROR] 清理失败文件 {filename} 报错: {exc}")

    # ==================================================================
    # Status surfaces and settings hooks
    # ==================================================================
    def show_success(self, title, content='',*,quiet=False):
        if not quiet:self.feedback_host.toast(title, content,kind='success')

    def show_error(self, title, content=''):
        details=str(content) if content and not hasattr(content,'source') else ''
        self.feedback_host.notice(title,t('操作未完成，请查看详情后重试。') if details else content,error=True,details=details)

    def force_refresh_sidebar_icons(self):
        self.sidebar.refresh_list(self.current_node)

    def on_settings_changed(self, key=""):
        if key in ('sidebar_icon_size', 'sidebar_show_labels', 'sidebar_mode'):
            self.sidebar.apply_presentation()
        elif key in ("appearance_mode", "light_theme_key", "dark_theme_key"):
            self.sidebar.update_theme()
            self.context_strip.setStyleSheet(visual.strip_style())
            self.command_bar.setStyleSheet(visual.command_bar_style())
            self._rebuild_context_strip()
            for card in self._all_card_widgets:
                if isinstance(card, EmojiCard):
                    card.update_style()
                elif isinstance(card, NodeCard):
                    card.refresh_icon()
        elif key == "preview_delay":
            self.preview_controller.set_delay(self.config.get("preview_delay", 500))
        elif key == "thumbnail_size":
            self._apply_thumbnail_size(self.config.get("thumbnail_size", 120))

    def _show_tools_menu(self):
        menu = RoundMenu(parent=self)
        from fluent_ui.components.ocr_controls import recognize_all,offer_install
        from services.ocr_service import ocr_service
        service=ocr_service(self.storage)
        ocr_menu=RoundMenu(t('文字识别'),menu);ocr_menu.setIcon(FIF.SCAN_TEXT)
        supplement=translated(Action,'补充识别',parent=ocr_menu)
        supplement.setEnabled(not service.library_busy)
        supplement.triggered.connect(lambda:service.supplement() if service.available else offer_install(self))
        ocr_menu.addAction(supplement)
        all_action=translated(Action,'重新识别全部表情…',parent=ocr_menu);all_action.setEnabled(not service.library_busy)
        all_action.triggered.connect(lambda:recognize_all(self,self.storage));ocr_menu.addAction(all_action)
        if service.library_busy:
            status=translated(Action,'正在识别',parent=ocr_menu);status.setEnabled(False);ocr_menu.addAction(status)
        menu.addMenu(ocr_menu)
        for icon, label, callback in (
            (FIF.SEARCH, '相似表情', self.similarity_requested.emit),
            (FIF.APPLICATION, 'QQ 导入', self.qq_requested.emit),
            (FIF.DOWNLOAD, 'Telegram 导入', self.tg_requested.emit),
            (FIF.INFO, '关于', self.about_requested.emit),
        ):
            action = translated(Action, icon, label, parent=menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        menu.popup_at(self.btn_tools,prefer_up=True)

    def _change_thumbnail(self, step):
        size = max(60, min(300, self.config.get('thumbnail_size', 120)+step))
        self._commit_thumbnail_size(size)



    def toggle_node_expansion(self, node_id):
        # Expanding a node only changes the content at and below it, so the
        # viewport is anchored to the entry it is already showing: laying the
        # grid out at scroll 0 and correcting it on the next frame is what made
        # expand / collapse flash a blank, jumpy layout.
        #
        # Everything after this node's own row shifts, and nothing before it
        # does, so the flow index resumes at that row instead of walking the
        # whole library again on every disclosure click.
        anchor = self.renderer.anchor()
        if node_id in self._expanded_nodes:
            self._expanded_nodes.remove(node_id)
        else:
            self._expanded_nodes.add(node_id)
        self.refresh_content(anchor=anchor, first_key=node_id)
        self._save_view_state()

    def _entry_clicked(self, entry, modifiers):
        key = self._entry_key(entry)
        self._selection_parents[key] = entry['_parent']
        if entry['kind'] == 'node':
            self.on_node_clicked(key, modifiers)
        else:
            self.on_image_clicked(key, modifiers)

    def _select_single(self, key):
        self.selected_keys = {key}
        from PySide6.QtCore import QSignalBlocker
        for widget in self._all_card_widgets:
            with QSignalBlocker(widget):
                widget.set_selected(self._entry_key(widget.content_entry) == key)
        self._last_clicked_key = key
        self._sync_command_bar()

    def use_resource(self, path):
        if self.mode == 'manage':
            return
        if not self.storage.availability.exists(path, revalidate=True):
            self._handle_missing_click(path)
        else:
            self._send_to_clipboard(path)

    def set_content_sort(self, mode):
        mode = ResourceSort(mode).value
        if mode == self.content_sort:
            self._update_resource_sort_label()
            return
        self.content_sort = mode
        self.config.set('resource_sort', mode)
        self._update_resource_sort_label()
        self.refresh_content()

    def _update_resource_sort_label(self):
        label = {ResourceSort.MANUAL: '自定义顺序', ResourceSort.RECENT_ADDED: '最近添加',
                 ResourceSort.OLDEST_ADDED: '最早添加'}[ResourceSort(self.content_sort)]
        self.btn_content_sort.setIcon({ResourceSort.MANUAL:FIF.SORT,ResourceSort.RECENT_ADDED:FIF.TIME_DESC,ResourceSort.OLDEST_ADDED:FIF.TIME_ASC}[ResourceSort(self.content_sort)])
        bind_text(self.btn_content_sort, t('表情显示排序') + ' · ' + t(label), 'setToolTip')
        self.btn_content_sort.setAccessibleName(self.btn_content_sort.toolTip())
        for mode, action in getattr(self, 'resource_sort_actions', {}).items():
            action.setChecked(mode == self.content_sort)

    def _build_resource_sort_menu(self):
        menu = RoundMenu(parent=self.btn_content_sort)
        self.resource_sort_actions = {}
        for mode, label in ((ResourceSort.MANUAL, '自定义顺序'),
                            (ResourceSort.RECENT_ADDED, '最近添加'),
                            (ResourceSort.OLDEST_ADDED, '最早添加')):
            action = translated(Action, label, parent=menu)
            action.setCheckable(True)
            action.setChecked(mode == self.content_sort)
            action.triggered.connect(lambda checked=False, mode=mode: self.set_content_sort(mode))
            menu.addAction(action)
            self.resource_sort_actions[mode.value] = action
        self.btn_content_sort.setMenu(menu)

    def _manual_order_available(self):
        if self.search_keyword.strip():
            self.feedback_host.hint(t('请先清空搜索再调整手动顺序'), self.btn_arrange)
            return False
        if self.content_sort != 'manual':
            self.feedback_host.hint(t('当前是临时显示排序，请先切回手动顺序'), self.btn_content_sort)
            return False
        return True

    def _apply_quick_tags(self, paths, tag):
        self.storage.apply_tags(paths, [tag], 'add')
        self.refresh_content_incremental(reason='apply_tags', paths=paths, parents=set())


    def navigate_up(self):
        if self.current_node != ROOT:
            self.set_node(self.storage.node(self.current_node).get('parent_id') or ROOT)

    # -- session working position --------------------------------------
    # What a session restores: where the user was, and how the surface was
    # arranged. What it never restores: search, filter, management mode and
    # selection -- those belong to one sitting, not to the library.
    @staticmethod
    def _decode_anchor(value):
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            return None
        entry_id, parent, offset = value
        try:
            return (str(entry_id), str(parent)), int(offset)
        except (TypeError, ValueError):
            return None

    def _current_anchor(self):
        anchor = self._initial_anchor or self._live_anchor
        if anchor is None and hasattr(self, 'renderer'):
            anchor = self.renderer.anchor()
        if not anchor:
            return None
        (entry_id, parent), offset = anchor
        return [entry_id, parent, offset]

    def _remember_sidebar_scroll(self, value):
        self._sidebar_scroll = int(value)

    def save_session_state(self):
        """Persist the working position; called when the window goes away."""
        self._save_view_state()

    def _save_view_state(self):
        if getattr(self,'_recent_view',False):return
        self._remember_location_anchor()
        states = dict(self.config.config.get('library_view_states', {}))
        state = {'location': self.current_node,
                 'sidebar_expanded': sorted(self.sidebar.tree._expanded_ids()-{ROOT}),
                 'inline_expanded_by_scope': {key: sorted(value) for key, value in self._expanded_by_scope.items()},
                 'active_relative_view_node_id': self.content_scope_node(),
                 'sidebar_scroll': int(self._sidebar_scroll or 0),
                 'gallery_anchor': self._current_anchor(),
                 'gallery_anchors': dict(self._location_anchors)}
        if states.get(self._view_state_key) != state:
            states[self._view_state_key] = state
            self.config.set('library_view_states', states)

    def _restore_sidebar_scroll(self):
        """Put the sidebar back where it was, once it has a scroll range."""
        if self._saved_sidebar_scroll is None:
            return
        self._saved_sidebar_scroll = None
        self.sidebar.tree.verticalScrollBar().setValue(int(self._sidebar_scroll or 0))

    def _resource_sources(self, paths):
        visible = {e['path']: e['_parent'] for e in self._selected_entries() if e['kind']=='resource'}
        return {path: visible.get(path, self._selection_parents.get(path, self.content_scope_node())) for path in paths}

    def request_resource_drop(self, paths, target, position=None, global_pos=None):
        """After dropping, ask for the membership action before writing data."""
        sources = self._resource_sources(paths)
        pos = global_pos if global_pos is not None else self.top_bar.mapToGlobal(self.top_bar.rect().center())
        def show_menu():
            menu = RoundMenu(parent=self)
            self._drop_action_menu = menu
            title = self.storage.node(target)['name'] if target != ROOT else t('全部表情')
            if target != ROOT:
                if any(parent != ROOT for parent in sources.values()):
                    move = Action(t('移动到「{name}」').format(name=title), parent=menu)
                    move.triggered.connect(lambda: self._apply_drop_action(paths, target, False, sources, position))
                    menu.addAction(move)
                    label = t('复制到「{name}」').format(name=title)
                else:
                    label = t('加入「{name}」').format(name=title)
                add = Action(label, parent=menu)
                add.triggered.connect(lambda: self._apply_drop_action(paths, target, True, sources, position))
                menu.addAction(add)
            else:
                info = translated(Action, '全部表情已包含这些表情', parent=menu)
                info.setEnabled(False)
                menu.addAction(info)
            cancel = translated(Action, '取消', parent=menu)
            cancel.triggered.connect(menu.close)
            menu.addAction(cancel)
            menu.exec(pos)
        QTimer.singleShot(0, self, show_menu)

    def _apply_drop_action(self, paths, target, copy, sources, position):
        groups = {}
        for path in paths:
            groups.setdefault(sources[path], []).append(path)
        for source, subset in groups.items():
            self.assign_resources(subset, target, copy=copy, position=position, source_node=source)
        if hasattr(self, '_drop_action_menu'):
            self._drop_action_menu.close()
