from services.i18n import t
import os
import ctypes
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QApplication
from PySide6.QtCore import Qt, QTimer, QEvent, QPoint, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from fluent_ui.components.controls import SearchLineEdit
from qfluentwidgets import ScrollArea, isDarkTheme, BodyLabel

from fluent_ui.components.emoji_card import EmojiCard
from fluent_ui.components.hover_preview import HoverPreviewPopup
from fluent_ui.components.hover_preview_controller import HoverPreviewController
from services.send_target import SendTargetService, SendResult

user32 = ctypes.windll.user32

class QuickPanel(QWidget):
    resources_imported = Signal()
    send_finished = Signal(object)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.config.get('esc_hide_quick', False):
            self.hide_panel()
            event.accept()
            return
        super().keyPressEvent(event)

    def __init__(self, storage_service, clipboard_service, config_service, parent=None, *, send_target_service=None):
        super().__init__(parent)
        self.storage = storage_service
        self.clipboard = clipboard_service
        self.config = config_service
        self.send_target_service = send_target_service or SendTargetService(self)
        self.last_send_result = None
        
        # 设置为 Tool 窗口，无边框，置顶
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 初始化时读取一次尺寸（后续 show_at_cursor 会再次读取最新值）
        w = self.config.get("quick_panel_width", 360)
        h = self.config.get("quick_panel_height", 480)
        self.resize(w, h)
            
        self._all_card_widgets = []
        self._current_columns = 0
        self._cached_query = None
        self._cached_results = None
        self._activation_guard = False
        # When the panel hides itself because it lost focus, remember when: a
        # tray click makes it lose focus, so the click that follows is the
        # "close" half of a toggle rather than a request to open it again.
        self._auto_hidden_at = 0.0
        self._activation_guard_timer = QTimer(self)
        self._activation_guard_timer.setSingleShot(True)
        self._activation_guard_timer.timeout.connect(self._end_activation_guard)
        
        # 布局常量
        self.LAYOUT_TOP_MARGIN = 10
        self.LAYOUT_SPACING = 8
        
        self._init_ui()
        from fluent_ui.components.feedback import FeedbackHost
        from fluent_ui.components.drop_contract import DropFeedback
        self.feedback_host = FeedbackHost(self.bg_widget, self.bg_layout, before=self.scroll_area,
                                          overlay_parent=self.scroll_area.viewport())
        self.bg_widget.feedback_host = self.feedback_host
        self.drop_feedback = DropFeedback(self.bg_widget)
        self._drop_payload = None
        self.import_thread = self.download_thread = None
        for surface in (self, self.bg_widget, self.scroll_area.viewport()):
            surface.setAcceptDrops(True)
            surface.installEventFilter(self)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        from services.ocr_service import ocr_service
        self._ocr_search_timer=QTimer(self)
        self._ocr_search_timer.setSingleShot(True);self._ocr_search_timer.setInterval(600)
        self._ocr_search_timer.timeout.connect(lambda:self._perform_search(force=True))
        ocr_service(self.storage).text_changed.connect(self._ocr_text_changed)
        from fluent_ui.components.import_queue import import_queue
        self.imports=import_queue(self.storage)
        self.imports.files_finished.connect(self._queued_import_finished)
        
        # 悬停预览组件
        self.preview_popup = HoverPreviewPopup(self)
        # 实例级修改 flag，避免抢占焦点导致 QuickPanel 隐藏
        self.preview_popup.setWindowFlags(
            self.preview_popup.windowFlags() | 
            Qt.WindowTransparentForInput | 
            Qt.WindowDoesNotAcceptFocus
        )
        
        self.preview_controller = HoverPreviewController(
            self,
            self.preview_popup,
            self.scroll_area.viewport(),
            parent=self,
        )
        self.preview_controller.set_delay(self.config.get("preview_delay", 500))
        
        # 搜索防抖
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        
        self.update_theme()
        self.storage.availability.changed.connect(self._availability_changed)
        self.storage.recent_changed.connect(self._recent_changed)

    def _recent_changed(self):
        self._cached_query = None
        if self.isVisible() and not self.search_box.text().strip():self._perform_search(force=True)

    def _init_ui(self):
        from fluent_ui.presentation.quick import build_quick
        build_quick(self)

    def _on_scroll(self, value):
        self._lazy_load_timer.start(32)
        
        from fluent_ui.components.emoji_card import ThumbnailCache
        ThumbnailCache().reset_idle_timer()

    def _apply_lazy_loading(self):
        if not hasattr(self, '_all_card_widgets') or not self._all_card_widgets:
            return
            
        scrollbar = self.scroll_area.verticalScrollBar()
        scroll_y = scrollbar.value()
        viewport_height = self.scroll_area.viewport().height()
        
        visible_top = scroll_y
        visible_bottom = scroll_y + viewport_height
        
        columns = getattr(self, '_current_columns', max(1, self.scroll_area.viewport().width() // (self.config.get("quick_panel_thumbnail_size", 72) + self.LAYOUT_SPACING)))
        current_size = self.config.get("quick_panel_thumbnail_size", 72)
        
        for index, widget in enumerate(self._all_card_widgets):
            row = index // columns
            
            card_y = self.LAYOUT_TOP_MARGIN + row * (current_size + self.LAYOUT_SPACING)
            card_bottom = card_y + current_size
            
            is_far_above = card_bottom < visible_top - 500
            is_far_below = card_y > visible_bottom + 500
            is_near = (card_bottom >= visible_top - 200) and (card_y <= visible_bottom + 200)
            
            if is_far_above or is_far_below:
                if getattr(widget, '_is_loaded', True):
                    widget.clear_resources()
            elif is_near:
                if widget.needs_reload(current_size):
                    widget.update_size(current_size, load_image=True)

    def set_target_hwnd(self, hwnd):
        self.send_target_service.remember(hwnd)

    def _availability_changed(self, path, status):
        self._cached_query = self._cached_results = None
        for card in self._all_card_widgets:
            if card.image_path == path:
                card.setProperty('state', status)
                from services.i18n import t
                card.setToolTip(t('表情文件缺失') if status == 'missing' else '')
                card.update_style()

    def showEvent(self,event):
        super().showEvent(event)
        from fluent_ui.materials import native_material,sync_native_clip
        native_material(self);sync_native_clip(self)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen
        from PySide6.QtCore import QRectF
        from fluent_ui import visual
        c=visual.colors();p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        from fluent_ui.materials import shell_color,shell_radius
        p.setCompositionMode(QPainter.CompositionMode_Source);p.fillRect(self.rect(),Qt.transparent);p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setBrush(shell_color(self));p.setPen(QPen(QColor(c['border']),1))
        radius=shell_radius(self)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),radius,radius)
        p.setPen(Qt.NoPen);p.setBrush(QColor(c['accent']))
        p.drawRoundedRect(QRectF(10,3,max(0,self.width()-20),3),1.5,1.5)

    def update_theme(self):
        from fluent_ui import visual
        visual.theme.material(self)
        from fluent_ui import visual
        c=visual.colors()
        visual.apply_typography(self)
        self.setStyleSheet(visual.control_style())
        self.search_box.setStyleSheet(f"SearchLineEdit {{ color: {c['text']}; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }} SearchLineEdit:focus {{ border-color: {c['accent']}; }}")
        self.scroll_area.setStyleSheet('QScrollArea { background: transparent; border: none; }')
        self.scroll_area.viewport().setAutoFillBackground(False)
        self.scroll_area.viewport().setStyleSheet('background: transparent;')
        self.grid_container.setAutoFillBackground(False)
        self.grid_container.setStyleSheet('background: transparent;')
        self.empty_label.setStyleSheet(f"color: {c['muted']}; background: transparent;")
        self.update()

    def _ocr_text_changed(self,rid):
        if self.isVisible() and self.search_box.text().strip() and not self._ocr_search_timer.isActive():
            self._ocr_search_timer.start()

    def _on_search_text_changed(self, text):
        self.search_timer.start(150)

    def _update_i18n_texts(self, lang):
        from services.i18n import t
        if hasattr(self, 'search_box'):
            self.search_box.setPlaceholderText(t('搜索名称、标签或关键词…'))
        keyword = self.search_box.text().strip() if hasattr(self, 'search_box') else ""
        if hasattr(self, 'empty_label'):
            self.empty_label.setText(t("没有找到匹配的表情") if keyword else t("暂无最近使用的表情"))

    def _perform_search(self, force=False):
        from services.i18n import t
        keyword = self.search_box.text().strip()
        limit = self.config.get("recent_limit", 30)
        query_key = (keyword, limit, self.storage.index.search_revision)
        
        if not force and query_key == self._cached_query and self._cached_results is not None:
            return
        
        if not keyword:
            # 初始状态或清空搜索框时，显示最近使用
            results = self.storage.get_recent_images()
            results = results[:limit]
        else:
            results = self.storage.search_images(keyword, "全部表情")
            # 限制结果数量，保证性能
            results = results[:30]
        
        self._cached_query = query_key
        self._cached_results = tuple(results)
        
        # 清理旧结果
        self.preview_controller.cancel()
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.empty_label:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
                
        self._all_card_widgets.clear()
                
        if not results:
            self.empty_label.setText(t("没有找到匹配的表情") if keyword else t("暂无最近使用的表情"))
            self.empty_label.show()
            self.grid_layout.addWidget(self.empty_label, 0, 0)
            return
            
        self.empty_label.hide()
                
        card_size = self.config.get("quick_panel_thumbnail_size", 72)
        
        # 填充新结果
        for path in results:
            # 初始化时不加载图片，交给懒加载处理
            card = EmojiCard(path, size=card_size, parent=self.grid_container,
                             availability=self.storage.availability)
            card.update_size(card_size, load_image=False)
            card._is_loaded = False
            
            card.clicked.connect(self._on_card_clicked)
            card.hover_started.connect(
                lambda path, card=card: self._on_card_hover_started(card, path)
            )
            card.hover_ended.connect(
                lambda card=card: self._on_card_hover_ended(card)
            )
            self._all_card_widgets.append(card)
            
        # 如果窗口已经可见（用户在搜索框中输入），则立即触发布局
        # 如果窗口不可见（刚唤醒），则等待 show_at_cursor 中的延迟触发
        if self.isVisible():
            self._trigger_responsive_layout(force=True)

    def _trigger_responsive_layout(self, force=False):
        if not self._all_card_widgets:
            return
            
        card_size = self.config.get("quick_panel_thumbnail_size", 72)
        available_width = self.scroll_area.viewport().width() - 16
        columns = max(1, available_width // (card_size + self.LAYOUT_SPACING))
        
        if self._current_columns != columns or force:
            self._current_columns = columns
            self._rearrange_gallery(columns)

    def _rearrange_gallery(self, columns):
        self.grid_container.setUpdatesEnabled(False)
        
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            # 不删除 widget，只是从 layout 中移除
            
        for index, widget in enumerate(self._all_card_widgets):
            row = index // columns
            col = index % columns
            self.grid_layout.addWidget(widget, row, col)
            widget.show()
            
        self.grid_container.setUpdatesEnabled(True)
        self.grid_container.update()
        
        # 重排后触发懒加载
        self._apply_lazy_loading()

    def _apply_thumbnail_size(self, size):
        # 第一阶段：仅更新尺寸，不判断可见性
        for widget in self._all_card_widgets:
            widget.update_size(size, load_image=False)
                
        self._trigger_responsive_layout(force=True)
        
        # 第二阶段：等待 layout 完成后，异步刷新可见区域
        QTimer.singleShot(0, self._refresh_visible_thumbnails)

    def _refresh_visible_thumbnails(self):
        if not hasattr(self, '_all_card_widgets') or not self._all_card_widgets:
            return
            
        scrollbar = self.scroll_area.verticalScrollBar()
        scroll_y = scrollbar.value()
        viewport_height = self.scroll_area.viewport().height()
        
        visible_top = scroll_y - 100
        visible_bottom = scroll_y + viewport_height + 100
        
        columns = getattr(self, '_current_columns', max(1, self.scroll_area.viewport().width() // (self.config.get("quick_panel_thumbnail_size", 72) + self.LAYOUT_SPACING)))
        current_size = self.config.get("quick_panel_thumbnail_size", 72)
        
        for index, widget in enumerate(self._all_card_widgets):
            row = index // columns
            card_y = self.LAYOUT_TOP_MARGIN + row * (current_size + self.LAYOUT_SPACING)
            card_bottom = card_y + current_size
            
            if card_bottom >= visible_top and card_y <= visible_bottom:
                if widget.needs_reload(current_size):
                    widget.update_size(current_size, load_image=True)

    def _track_external_drop(self, event):
        from services.clipboard import ClipboardService
        from fluent_ui.components.drop_contract import INTO, RESOURCE_MIME, TAG_MIME, NODE_MIME
        mime = event.mimeData()
        self._drop_payload = (None, None) if any(mime.hasFormat(k) for k in (RESOURCE_MIME, TAG_MIME, NODE_MIME)) else ClipboardService.importable_payload(mime, self.storage.SUPPORTED_FORMATS)
        if self._drop_payload[0]:
            self._activation_guard = True
            self._activation_guard_timer.stop()
            self.preview_controller.cancel()
            self.drop_feedback.show_target(INTO, self.bg_widget.rect().adjusted(5,5,-5,-5))
            event.acceptProposedAction()
        else:
            self.drop_feedback.clear()
            self.feedback_host.hint(t('无法导入此内容'), event.position().toPoint() + self.mapToGlobal(QPoint()))
            event.ignore()

    def _start_external_import(self, paths, *, temporary=False):
        from fluent_ui.views.gallery_view import ImportThread
        from services.library_index import ROOT
        self.import_thread = ImportThread(paths, self.storage, ROOT, delete_after=temporary, parent=self)
        self.import_thread.progress.connect(lambda current,total: self.feedback_host.update_task(current,total))
        self.import_thread.finished.connect(self._external_import_finished)
        self.import_thread.start()

    def _external_import_finished(self, saved, skipped, failed):
        self._cached_query = self._cached_results = None
        self.resources_imported.emit()
        self._perform_search(force=True)
        self.feedback_host.finish(t('导入完成'), t('新增 {saved} 项，重复 {skipped} 项，失败 {failed} 项').format(
            saved=saved,skipped=skipped,failed=failed),
            outcome=('partial' if saved or skipped else 'error') if failed else 'success')
        self._activation_guard_timer.start(180)

    def _external_download_finished(self, success, path, error, url):
        if success:
            self._start_external_import([path], temporary=True)
        else:
            self.feedback_host.finish(t('下载失败'), error, outcome='error')
            self._activation_guard_timer.start(180)

    def _import_external_payload(self, payload):
        kind, data = payload
        from services.resource_import import ImportTarget
        try:
            if kind == 'file':
                self.imports.submit(data,ImportTarget(),self)
            elif kind == 'image':
                self.imports.submit([data.copy()],ImportTarget(),self)
            else:
                self.imports.submit([data],ImportTarget(),self)
        except Exception as error:
            self.feedback_host.finish(t('导入失败'), str(error), outcome='error')
            self._activation_guard_timer.start(180)

    def _queued_import_finished(self,request):
        self._cached_query=self._cached_results=None
        if request.owner is self:
            self._perform_search(force=True);self._activation_guard_timer.start(180)

    def shutdown(self):
        for worker in (self.import_thread, self.download_thread):
            if worker and worker.isRunning():
                worker.wait()

    def eventFilter(self, obj, event):
        if obj in (self, getattr(self,'bg_widget',None), getattr(self,'scroll_area',None).viewport() if hasattr(self,'scroll_area') else None):
            if event.type() in (QEvent.DragEnter, QEvent.DragMove):
                self._track_external_drop(event)
                return True
            if event.type() == QEvent.DragLeave:
                self.drop_feedback.clear()
                self._activation_guard_timer.start(180)
                return True
            if event.type() == QEvent.Drop:
                self._track_external_drop(event)
                self.drop_feedback.clear()
                if event.isAccepted():
                    self._import_external_payload(self._drop_payload)
                return True
        if obj == self.scroll_area.viewport() and event.type() == event.Type.Wheel:
            if QApplication.keyboardModifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                step = 6 if delta > 0 else -6
                
                current_size = self.config.get("quick_panel_thumbnail_size", 72)
                new_size = max(40, min(200, current_size + step))
                
                if new_size != current_size:
                    self.config.set("quick_panel_thumbnail_size", new_size)
                    self._apply_thumbnail_size(new_size)
                    
                return True
        return super().eventFilter(obj, event)

    def _on_card_clicked(self, path, modifiers=None):
        # Ignore acquisition-induced focus loss until the send result is known.
        self._activation_guard = True
        self._activation_guard_timer.stop()
        self.send_target_service.send(path, self.clipboard, self.storage,
                                      self._on_send_finished, self.config.get('recent_limit', 30))

    def _on_send_finished(self, result):
        from fluent_ui.components.feedback import feedback_for
        local = feedback_for(self.bg_widget)
        self.feedback_host = local
        self.last_send_result = result
        self.send_finished.emit(result)
        if result != SendResult.COPY_FAILED:
            self._cached_query = self._cached_results = None
        if result == SendResult.SENT:
            local.dismiss()
            self.hide_panel()
        else:
            self._activation_guard_timer.start(180)
            if result == SendResult.COPIED_ONLY:
                local.notice(t('表情已复制'),t('未找到可发送的聊天窗口，可手动粘贴。'))
            else:
                local.notice(t('复制失败'), t('无法将表情写入剪贴板'), error=True)

    def _on_card_hover_started(self, card, path):
        self.preview_controller.set_delay(self.config.get("preview_delay", 500))
        self.preview_controller.enter(card, path)

    def _on_card_hover_ended(self, card):
        self.preview_controller.leave(card)

    def get_preview_size(self):
        return self.config.get("preview_size", 320)

    def get_preview_metadata(self, path):
        cats = self.storage.get_categories_by_image(path)
        cat_str = ", ".join(cats)
        kw_str = self.storage.get_image_keywords(path) or ""
        return cat_str, kw_str

    def _end_activation_guard(self):
        self._activation_guard = False

    def show_at_cursor(self):
        self.send_target_service.capture_foreground()
        # 每次唤醒时读取最新的宽高配置
        w = self.config.get("quick_panel_width", 360)
        h = self.config.get("quick_panel_height", 480)
        if self.width() != w or self.height() != h:
            self.resize(w, h)
            
        self._update_i18n_texts(None)
        self.update_theme()
        if self.search_box.text():
            self.search_box.clear()
        else:
            self._perform_search()
        
        # 计算位置
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if not screen:
            screen = QGuiApplication.primaryScreen()
            
        avail_geo = screen.availableGeometry()
        
        x = cursor_pos.x() + 10
        y = cursor_pos.y() + 10
        
        if x + self.width() > avail_geo.right():
            x = cursor_pos.x() - self.width() - 10
            
        if y + self.height() > avail_geo.bottom():
            y = cursor_pos.y() - self.height() - 10
            
        self.move(x, y)
        # show() 到 Windows 完成激活之间可能产生一次伪失焦事件，暂时忽略它。
        self._activation_guard = True
        self._activation_guard_timer.start(180)
        self.show()
        
        # 延迟触发布局计算，确保窗口已经显示且 viewport 宽度准确
        QTimer.singleShot(0, lambda: self._trigger_responsive_layout(force=True))
        
        # 恢复强制系统级前台和聚焦
        user32.SetForegroundWindow(int(self.winId()))
        self.activateWindow()
        self.search_box.setFocus()

    def hide_panel(self, auto=False):
        self.preview_controller.cancel()
        if auto:
            import time
            self._auto_hidden_at = time.monotonic()
        self.hide()

    def hidden_by_focus_loss_within(self, seconds=0.6):
        """Whether the panel just hid itself because it lost focus."""
        import time
        return bool(self._auto_hidden_at) and time.monotonic() - self._auto_hidden_at < seconds
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        from fluent_ui.materials import sync_native_clip
        sync_native_clip(self)
        # 窗口大小改变时，重新计算列数并重排
        if self.isVisible():
            self._trigger_responsive_layout()

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if not self.isActiveWindow() and not self._activation_guard:
                self.hide_panel(auto=True)
        super().changeEvent(event)
