import os

from PySide6.QtWidgets import QLabel, QApplication, QMenu
from PySide6.QtGui import QCursor, QDrag, QPixmap, QImageReader, QPixmapCache
from PySide6.QtCore import (
    Qt, Signal, QMimeData, QPoint, QSize, QTimer, QEasingCurve, QUrl,
    QPropertyAnimation, QObject, QRunnable, QThreadPool
)
from PySide6.QtWidgets import QGraphicsOpacityEffect
from fluent_ui.components.controls import TransparentToolButton
from fluent_ui.icons import Icon as FluentIcon

try:
    from shiboken6 import isValid as _is_qt_object_valid
except ImportError:
    def _is_qt_object_valid(obj):
        return True


class _ThumbnailLoadSignals(QObject):
    finished = Signal(str, object, int, int)


class _ThumbnailLoadTask(QRunnable):
    """在线程池中解码缩略图，只传递 QImage，不在线程中创建 QPixmap。"""

    def __init__(self, image_path, target_size, request_id, frame=0, cache_file=None):
        super().__init__()
        self.image_path = image_path
        self.target_size = target_size
        self.request_id = request_id
        self.frame = int(frame or 0)
        self.cache_file = cache_file
        self._cancelled = False
        self.signals = _ThumbnailLoadSignals()

    def run(self):
        image = None
        try:
            if self._cancelled:
                return

            if self.cache_file and os.path.isfile(self.cache_file):
                cached = QImageReader(self.cache_file).read()
                if not cached.isNull():
                    self._emit_finished(self.image_path, cached, self.request_id, self.target_size)
                    return
            if self.frame:
                # A requested frame goes through the shared frame decoder:
                # QImageReader cannot step GIF frames here, so asking it for a
                # frame silently produced frame 0 every time.
                from services.image_frames import frame_at
                loaded = frame_at(self.image_path, self.frame)
                if loaded is not None and not loaded.isNull():
                    loaded = loaded.scaled(self.target_size, self.target_size,
                                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                reader = QImageReader(self.image_path)
                original_size = reader.size()

                if original_size.isValid():
                    original_size.scale(
                        self.target_size,
                        self.target_size,
                        Qt.KeepAspectRatio
                    )
                    reader.setScaledSize(original_size)

                loaded = reader.read()
            if self._cancelled:
                return
            if loaded and not loaded.isNull():
                image = loaded
                if self.cache_file:
                    temporary = self.cache_file + '.tmp'
                    if image.save(temporary, 'PNG'):
                        os.replace(temporary, self.cache_file)
        except Exception as e:
            print(
                f"[Error] Async thumbnail failed: "
                f"{self.image_path}, error: {e}"
            )

        if self._cancelled:
            return

        # The card can be gone by the time a decode finishes (shutdown, or a
        # category switch that dropped it), which deletes the signals object.
        self._emit_finished(
            self.image_path,
            image,
            self.request_id,
            self.target_size
        )

    def _emit_finished(self, *args):
        """Emit unless the receiving card already went away.

        A decode can outlive its card (shutdown, or a category switch that
        dropped it), and the signals object dies with the card.
        """
        try:
            self.signals.finished.emit(*args)
        except RuntimeError:
            pass


class ThumbnailCache:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._normal_limit_kb = 128 * 1024  # Bounded resource cache, independent of cards.
            self._idle_limit_kb = self._normal_limit_kb

            QPixmapCache.setCacheLimit(self._normal_limit_kb)

            # 空闲收缩定时器 (60秒)
            self._idle_timer = QTimer()
            self._idle_timer.setSingleShot(True)
            self._idle_timer.timeout.connect(self._on_idle_timeout)
            self._idle_timer.start(60000)

            self._initialized = True

    def reset_idle_timer(self):
        """由外部交互(滚动、切换分类等)调用，重置空闲状态"""
        if QPixmapCache.cacheLimit() != self._normal_limit_kb:
            QPixmapCache.setCacheLimit(self._normal_limit_kb)
        self._idle_timer.start(60000)

    def _on_idle_timeout(self):
        """Qt's LRU limit evicts on pressure; idle does not invalidate resources."""
        pass

    _library_identity = None
    _library_identity_source = None

    @classmethod
    def library_identity(cls):
        """Library root used in cache keys, resolved once per library.

        Resolving the path (a filesystem syscall) and re-reading the config on
        every key made each lookup cost more than the decode it exists to
        avoid, and produced unstable keys while the config was still unset.
        Kept as an explicit cache invalidated by the configured source instead.
        """
        from services.app_paths import selected_library
        from fluent_ui import visual
        config = visual.theme.config
        try:
            source = os.environ.get('NEKORI_LIBRARY') or (
                config.get('library_path') if config is not None else '') or ''
        except Exception:
            source = ''
        if cls._library_identity is None or source != cls._library_identity_source:
            cls._library_identity_source = source
            try:
                cls._library_identity = os.path.normcase(str(selected_library(config)))
            except Exception:
                cls._library_identity = ''
        return cls._library_identity

    @classmethod
    def cache_key(cls, image_path, target_size, frame=0):
        """Identity of one cached thumbnail.

        The library root is part of the key so switching libraries without
        restarting cannot hit another library's file under the same path.
        """
        return (f"{cls.library_identity()}|{image_path}"
                f"|{target_size}x{target_size}|{int(frame or 0)}")

    def get_thumbnail(self, image_path, target_size, frame=0):
        cache_key = self.cache_key(image_path, target_size, frame)

        pixmap = QPixmap()
        if QPixmapCache.find(cache_key, pixmap):
            return pixmap

        try:
            if frame:
                # Same reason as the async path: the shared decoder is the only
                # one that can actually reach a GIF frame here.
                from services.image_frames import frame_at
                image = frame_at(image_path, int(frame))
                if image is None or image.isNull():
                    return None
                pixmap = QPixmap.fromImage(image)
                if pixmap.width() > target_size or pixmap.height() > target_size:
                    pixmap = pixmap.scaled(target_size, target_size,
                                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
                QPixmapCache.insert(cache_key, pixmap)
                return pixmap

            reader = QImageReader(image_path)
            orig_size = reader.size()

            if orig_size.isValid():
                # 计算保持宽高比的缩放尺寸
                orig_size.scale(target_size, target_size, Qt.KeepAspectRatio)
                # 让图片直接解码为目标大小，大幅降低内存峰值和 CPU 开销
                reader.setScaledSize(orig_size)

            img = reader.read()
            if img and not img.isNull():
                pixmap = QPixmap.fromImage(img)

                # 确保最终尺寸不超过 target_size，并应用平滑缩放以保证画质
                if pixmap.width() > target_size or pixmap.height() > target_size:
                    pixmap = pixmap.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                QPixmapCache.insert(cache_key, pixmap)
                return pixmap
        except Exception as e:
            print(f"[Error] ThumbnailCache failed to load image: {image_path}, error: {e}")

        return None

_thumbnail_pool = QThreadPool()
# 缩略图解码通常受磁盘和图片解码器限制；降低并发可减少快速滚动时
# 同时存在的 QImage 峰值，避免线程池积压造成内存突增。
_thumbnail_pool.setMaxThreadCount(2)


class EmojiCard(QLabel):
    """
    Fluent风格的图片组件，用于在网格中展示缩略图并支持点击事件和拖拽排序
    """
    clicked = Signal(str, Qt.KeyboardModifiers)  # 点击信号，传递图片路径和键盘修饰键状态
    activated = Signal(str)
    delete_requested = Signal(object, str) # 请求删除的信号: (Widget实例, 路径)
    selection_changed = Signal(str, bool)  # 选中状态改变信号: (路径, 是否选中)

    hover_started = Signal(str) # 悬停进入
    hover_ended = Signal()      # 悬停离开

    def __init__(self, image_path, size=120, parent=None, load_image=True, frame=0, availability=None, status=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setFocusPolicy(Qt.StrongFocus)
        self._drag_start_pos = None
        self._is_dragging = False
        self.current_size = size
        self.frame = int(frame or 0)
        # Set by the gallery: returns every path that should travel with one drag.
        self.drag_payload_provider = None
        self._loaded_size = 0  # 记录当前实际加载的图片尺寸
        self._is_loaded = False
        self._is_loading = False
        self._loading_size = 0
        self._load_request_id = 0
        self._load_task = None

        # 入场动画资源。动画结束后会移除 opacity effect，避免长期增加绘制开销。
        self._appear_timer = None
        self._opacity_effect = None
        self._appear_animation = None
        self._animation_generation = 0

        self.is_selectable = False
        self.is_selected = False
        self._hovered = False

        self.setFixedSize(self.current_size, self.current_size)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.setAlignment(Qt.AlignCenter)

        self.setObjectName("EmojiCard")
        from fluent_ui import visual
        visual.theme.changed.connect(self.update_style)
        visual.theme.accent_changed.connect(self.update)
        import os
        exists = status!='missing' if status is not None else availability.exists(image_path) if availability is not None else os.path.isfile(image_path)
        self.setProperty("state", "normal" if exists else "missing")
        from services.i18n import t, bind_text
        # No tooltip on a healthy card: the hover preview already carries the
        # file identity, and a full path tooltip on top of it was pure noise.
        # A missing file still needs to say so, without repeating the path.
        if not exists:
            bind_text(self, t('表情文件缺失'), 'setToolTip')
        self.update_style()
        self.update_size(self.current_size, load_image=load_image)

    def set_selectable(self, selectable):
        self.is_selectable = selectable
        if not selectable:
            self.set_selected(False)

    def set_selected(self, selected):
        if self.is_selected == selected:
            return
        self.is_selected = selected
        self.update_style()
        self.selection_changed.emit(self.image_path, selected)

    def update_style(self):
        if not self.styleSheet():
            self.setStyleSheet('QLabel#EmojiCard {background:transparent;border:none;}')
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor
        from PySide6.QtCore import QRectF, QPointF
        from fluent_ui import visual
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform)
        c=visual.colors();r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        p.setPen(Qt.NoPen);p.setBrush(QColor(c['surface_alt']))
        p.drawRoundedRect(r,10,10)
        image=r.adjusted(2,2,-2,-2)
        movie=self.movie();pix=movie.currentPixmap() if movie else self.pixmap()
        if pix is not None and not pix.isNull():
            clip=QPainterPath();clip.addRoundedRect(image,6,6);p.save();p.setClipPath(clip)
            size=pix.size().toSizeF();size.scale(image.size(),Qt.KeepAspectRatio)
            target=QRectF(0,0,size.width(),size.height());target.moveCenter(image.center())
            p.drawPixmap(target,pix,QRectF(pix.rect()));p.restore()
        if self.property('state')=='missing':
            p.setPen(QPen(QColor(c['muted']),1))
            q=image.adjusted(18,18,-18,-28)
            p.drawLine(q.topLeft(),q.bottomRight());p.drawLine(q.topRight(),q.bottomLeft())
            p.setFont(visual.font('data'));p.drawText(image,Qt.AlignBottom|Qt.AlignHCenter,'MISSING')
        if self.is_selected or self._hovered:
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(c['accent']),1 if self.is_selected else 2))
            selection=r.adjusted(1,1,-1,-1)
            p.drawRoundedRect(selection,9,9)
            if self.is_selected:
                p.setPen(QPen(QColor(c['accent']),2))
                p.drawLine(QPointF(selection.left()+5,selection.top()+4),
                           QPointF(selection.right()-5,selection.top()+4))

    def needs_reload(self, target_size):
        target_img_size = max(10, target_size - 8)
        if self._is_loading and self._loading_size == target_img_size:
            return False
        return not self._is_loaded or self._loaded_size != target_size

    def set_frame(self, frame):
        self.frame = int(frame or 0)
        self._is_loaded = False
        self._loaded_size = 0
        if hasattr(self, 'gallery_reload'):
            self.gallery_reload(self.image_path)
            return
        self.update_size(self.current_size, load_image=True)

    def _stop_appear_animation(self):
        """停止入场动画并恢复正常绘制状态。"""
        self._animation_generation += 1

        timer = self._appear_timer
        self._appear_timer = None
        if timer is not None:
            try:
                if _is_qt_object_valid(timer):
                    timer.stop()
                    timer.deleteLater()
            except RuntimeError:
                pass

        animation = self._appear_animation
        self._appear_animation = None
        if animation is not None:
            try:
                if _is_qt_object_valid(animation):
                    animation.stop()
                    animation.deleteLater()
            except RuntimeError:
                pass

        effect = self._opacity_effect
        self._opacity_effect = None
        if effect is not None:
            try:
                if _is_qt_object_valid(effect) and self.graphicsEffect() is effect:
                    self.setGraphicsEffect(None)
            except RuntimeError:
                pass

    def _start_appear_animation(self, generation):
        if generation != self._animation_generation or not self.isVisible():
            return

        self._appear_timer = None
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.0)
        self._opacity_effect = effect
        self.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._appear_animation = animation

        def finish():
            if self._appear_animation is not animation:
                return

            self._appear_animation = None
            self._opacity_effect = None
            try:
                if _is_qt_object_valid(effect):
                    effect.setOpacity(1.0)
                    if self.graphicsEffect() is effect:
                        self.setGraphicsEffect(None)
                if _is_qt_object_valid(animation):
                    animation.deleteLater()
            except RuntimeError:
                pass

        animation.finished.connect(finish)
        animation.start()

    def animate_appear(self, delay=0):
        """以轻微淡入显示卡片；delay 用于批次内错峰，避免同时闪现。"""
        self._stop_appear_animation()
        generation = self._animation_generation

        if delay <= 0:
            self._start_appear_animation(generation)
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda: self._start_appear_animation(generation)
        )
        self._appear_timer = timer
        timer.start(delay)

    def _cancel_thumbnail_task(self):
        task = self._load_task
        self._load_task = None
        if task is not None:
            task._cancelled = True

    def clear_resources(self):
        """释放图片引用，但保留卡片控件和占位外观。"""
        self._stop_appear_animation()
        self._cancel_thumbnail_task()
        self._load_request_id += 1
        self._is_loading = False
        self._loading_size = 0
        self.clear()
        self._is_loaded = False
        self._loaded_size = 0
        self.setText("⋯")

    def _cache_key(self, target_img_size):
        # One key format for the whole app: the card and the shared cache must
        # agree, and the key carries the library identity.
        return ThumbnailCache.cache_key(self.image_path, target_img_size, self.frame)

    def _on_thumbnail_loaded(
        self, image_path, image, request_id, target_size
    ):
        if (
            request_id != self._load_request_id
            or image_path != self.image_path
            or target_size != max(10, self.current_size - 8)
        ):
            return

        self._load_task = None
        self._is_loading = False
        self._loading_size = 0
        if image is None or image.isNull():
            self._is_loaded = False
            self._loaded_size = 0
            import os
            self.setText("?" if not os.path.isfile(self.image_path) else " ")
            return

        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            self._is_loaded = False
            self._loaded_size = 0
            self.setText(" ")
            return

        target_img_size = max(10, self.current_size - 8)
        QPixmapCache.insert(self._cache_key(target_img_size), pixmap)
        self.setText("")
        self.setPixmap(pixmap.scaled(target_img_size, target_img_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._is_loaded = True
        self._loaded_size = self.current_size

    def _load_thumbnail_async(self, target_size):
        if self._is_loading and self._loading_size == target_size:
            return

        cache_key = self._cache_key(target_size)
        cached = QPixmap()
        if QPixmapCache.find(cache_key, cached):
            self.setText("")
            self.setPixmap(cached.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._is_loaded = True
            self._loaded_size = self.current_size
            return

        self._cancel_thumbnail_task()
        self._load_request_id += 1
        request_id = self._load_request_id
        self._is_loading = True
        self._loading_size = target_size

        task = _ThumbnailLoadTask(
            self.image_path,
            target_size,
            request_id,
            self.frame,
        )
        task.signals.finished.connect(self._on_thumbnail_loaded)
        self._load_task = task
        _thumbnail_pool.start(task)

    def update_size(self, new_size, load_image=True):
        target_img_size = max(10, new_size - 8)
        if (
            load_image
            and self._is_loading
            and self._loading_size == target_img_size
            and self.current_size == new_size
        ):
            return

        self.current_size = new_size
        self.setFixedSize(new_size, new_size)

        if not load_image:
            # 尺寸调整期间保留旧 pixmap，避免先清空造成闪烁；
            # 但新建卡片没有旧图时显示稳定的占位符。
            self._cancel_thumbnail_task()
            self._load_request_id += 1
            self._is_loading = False
            self._loading_size = 0
            if not self._is_loaded:
                pixmap = self.pixmap()
                if pixmap is None or pixmap.isNull():
                    self.setText("⋯")
            return

        target_img_size = max(10, new_size - 8)
        self._is_loaded = False
        self._loaded_size = 0
        self.setText("⋯")
        self._load_thumbnail_async(target_img_size)

    def closeEvent(self, event):
        """卡片销毁前取消异步任务并释放仍由 QLabel 持有的缩略图。"""
        self._stop_appear_animation()
        self._cancel_thumbnail_task()
        self._load_request_id += 1
        self.clear()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._is_dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            return super().mouseMoveEvent(event)

        if (event.pos() - self._drag_start_pos).manhattanLength() <= QApplication.startDragDistance():
            return super().mouseMoveEvent(event)

        self._is_dragging = True
        payload = [self.image_path]
        if self.drag_payload_provider is not None:
            resolved = self.drag_payload_provider(self.image_path)
            if resolved:
                payload = list(resolved)

        from fluent_ui.components.node_card import RESOURCE_MIME
        import json
        import os

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(RESOURCE_MIME, json.dumps(payload).encode('utf-8'))
        # File URLs make the same drag usable by Explorer (copy out) and by chat
        # clients that accept dropped files (send).
        urls = [QUrl.fromLocalFile(path) for path in payload if os.path.isfile(path)]
        if urls:
            mime_data.setUrls(urls)
            mime_data.setText(os.pathsep.join(payload))
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.setHotSpot(QPoint(30, 30))

        self.setCursor(QCursor(Qt.ClosedHandCursor))
        drag.exec(Qt.CopyAction | Qt.MoveAction, Qt.CopyAction if urls else Qt.MoveAction)
        self._is_dragging = False
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self._drag_start_pos = None

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._is_dragging:
                modifiers = QApplication.keyboardModifiers()
                if self.is_selectable and not modifiers:
                    self.set_selected(not self.is_selected)
                else:
                    self.clicked.emit(self.image_path, modifiers)

        self._drag_start_pos = None
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        self.hover_started.emit(self.image_path)
        super().enterEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.image_path)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.activated.emit(self.image_path)
            event.accept()
            return
        super().keyPressEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        self.hover_ended.emit()
        super().leaveEvent(event)

    def hideEvent(self,event):
        self._hovered=False
        super().hideEvent(event)
