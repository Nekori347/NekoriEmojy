import os
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QHBoxLayout
from PySide6.QtCore import Qt, QSize, QByteArray, QBuffer, QRect, QRectF
from PySide6.QtGui import QPixmap, QMovie, QImageReader, QPainter, QPainterPath, QColor
from fluent_ui.icons import Icon
from qfluentwidgets import BodyLabel, CaptionLabel
import darkdetect
from services.i18n import t, i18n_engine
from fluent_ui import visual

class IconCaption(QLabel):
    def __init__(self,icon,text):
        super().__init__(text);self.icon=icon;self.setContentsMargins(20,0,0,0);self.setFont(visual.font('secondary'))
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);self.icon.render(p,QRect(0,(self.height()-13)//2,13,13),fill=visual.colors()['text_secondary'])


class PreviewImage(QLabel):
    # QLabel's QMovie handler updates the unscaled frame rectangle. Our custom
    # painter scales to fit, so every frame must invalidate the whole surface.
    def setMovie(self, movie):
        self._movie = movie
        movie.frameChanged.connect(self.update_frame)
        self.update()

    def movie(self):
        return getattr(self, '_movie', None)

    def update_frame(self, *_):
        self.update()

    def clear(self):
        self._movie = None
        super().clear()
        self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform)
        r=QRectF(self.rect());path=QPainterPath();path.addRoundedRect(r,8,8);p.setClipPath(path)
        p.fillRect(r,QColor(visual.colors()['surface_alt']))
        movie=self.movie();pix=movie.currentPixmap() if movie else self.pixmap()
        if pix is not None and not pix.isNull():
            size=pix.size().toSizeF();size.scale(r.size(),Qt.KeepAspectRatio)
            target=QRectF(0,0,size.width(),size.height());target.moveCenter(r.center())
            p.drawPixmap(target,pix,QRectF(pix.rect()))


class HoverPreviewPopup(QWidget):
    """
    独立且无焦点的悬停预览浮窗组件，包含元数据展示

    两种呈现模式共用同一个组件：浮动时是靠近指针的工具窗，固定时挂到内容
    面板上成为角落 overlay——固定模式不会额外创建一个窗口。
    """

    FLOATING_FLAGS = (Qt.Tool
                      | Qt.FramelessWindowHint
                      | Qt.WindowStaysOnTopHint
                      | Qt.WindowDoesNotAcceptFocus
                      | Qt.WindowTransparentForInput)

    def apply_presentation(self, pane):
        """Attach to `pane` as an overlay, or detach back to a floating window."""
        fixed = pane is not None
        if fixed and self.parentWidget() is pane:
            return
        if not fixed and self.parentWidget() is None:
            return
        self.hide()
        if fixed:
            self.setParent(pane)
            self.setWindowFlags(Qt.Widget)
        else:
            self.setParent(None)
            self.setWindowFlags(self.FLOATING_FLAGS)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 使用无焦点的工具窗口，避免 Qt.ToolTip 在应用失去激活状态时自动隐藏。
        # 预览不接收鼠标事件，因此不会阻挡指针离开缩略图。
        # 固定模式下会被重新挂到内容面板上成为 overlay，那时这些标志会被清除。
        self.setWindowFlags(self.FLOATING_FLAGS)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # 核心布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4,4,4,4)
        self.layout.setSpacing(4)
        
        # 图像显示区域
        self.image_label = PreviewImage()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: none; background: transparent;")
        self.layout.addWidget(self.image_label)
        
        # 元数据区域 (分类和关键词)
        from fluent_ui.presentation.surfaces import Surface
        self.metadata_footer = Surface('raised',self,radius=8,edge=True)
        self.meta_layout = QVBoxLayout(self.metadata_footer)
        self.meta_layout.setContentsMargins(10,8,10,8)
        self.meta_layout.setSpacing(2)
        
        # The image stays the first information; the file identity lives here as
        # low-weight text instead of a separate path tooltip on the card.
        self.name_label = CaptionLabel("")
        self.name_label.setWordWrap(True)
        self.name_label.setProperty("role", "section")
        self.path_label = CaptionLabel("")
        self.path_label.setWordWrap(True)
        self.path_label.setProperty("role", "data")

        self.category_label = IconCaption(Icon.FOLDER,f"{t('无分类')}")

        self.keyword_label = IconCaption(Icon.TAG,f"{t('无标签')}")
        self.ocr_label = IconCaption(Icon.SEARCH,'')

        self.meta_layout.addWidget(self.name_label)
        self.meta_layout.addWidget(self.path_label)
        self.meta_layout.addWidget(self.category_label)
        self.meta_layout.addWidget(self.keyword_label)
        self.meta_layout.addWidget(self.ocr_label)
        self.ocr_label.hide()
        
        self.layout.addWidget(self.metadata_footer)
        
        self.current_movie = None
        self.setObjectName("PreviewPopup")
        
        # 绑定语言切换信号
        i18n_engine.language_changed.connect(self.update_texts)

    def update_texts(self, lang):
        """动态刷新界面文本"""
        # 只有在没有实际数据时才刷新默认文本
        if not hasattr(self, 'current_category_str') or not self.current_category_str:
            self.category_label.setText(f"{t('无分类')}")
            self.keyword_label.setText(f"{t('无标签')}")
        else:
            # 如果有数据，重新翻译并显示
            self.category_label.setText(f"{t('分类')}: {self.current_category_str}")
            self.keyword_label.setText(f"{t('标签')}: {self.current_keyword_str}")

    def update_identity(self, info):
        """File identity as low-weight text under the image."""
        self.current_name_str = str(info.get('name') or '')
        self.current_path_str = str(info.get('path') or '')
        self.name_label.setText(self.current_name_str)
        self.path_label.setText(self.current_path_str)

    def update_theme(self):
        """The preview uses the same semantic surface in either presentation."""
        visual.apply_typography(self)
        palette = visual.colors()
        data_style = f"color: {palette['text_muted']};"
        self.name_label.setStyleSheet(data_style)
        self.path_label.setStyleSheet(data_style)
        text_style = f"color: {palette['text_primary']};"
        self.category_label.setStyleSheet(text_style)
        self.keyword_label.setStyleSheet(text_style)
        self.ocr_label.setStyleSheet(text_style)
        self.setStyleSheet(f"QWidget#PreviewPopup {{ {visual.surface_style('popover')} "
                           f"border: 1px solid {palette['border']}; "
                           f"border-radius: {visual.PANEL_RADIUS}px; }}")

    def show_preview(self, image_path, global_pos, size_config=320, category_str="无",
                     keyword_str="无", info=None, anchor_rect=None, container_rect=None):
        """
        显示预览窗口，并更新元数据

        `info` 提供文件名 / 相对路径等低权重文字；`container_rect` 非空时按
        固定模式把预览放进内容面板的角落（右下，被占用则左下），不再跟随鼠标。
        """
        if not os.path.exists(image_path):
            return

        self.update_theme()
        info = info or {}
        self.update_identity(info)

        # 保存当前状态以便语言切换时刷新
        self.current_category_str = category_str
        self.current_keyword_str = keyword_str

        self.category_label.setText(f"{t('分类')}: {category_str}")
        self.keyword_label.setText(f"{t('标签')}: {keyword_str}")
        ocr=str(info.get('ocr_text') or '').strip()
        self.ocr_label.setText(t('表情文字')+': '+ocr)
        self.ocr_label.setVisible(bool(ocr))
        for label in (self.category_label,self.keyword_label,self.ocr_label):
            label.setWordWrap(True)

        # 1. 停止清理上一次的动图
        if self.current_movie:
            self.current_movie.stop()
            self.current_movie.setDevice(None)
            self.current_movie.deleteLater() 
            self.current_movie = None
            
        self.image_label.clear()
        
        # 根据当前屏幕可用空间限制预览尺寸，避免边缘位置放不下时窗口
        # 超出屏幕或覆盖指针，继而被悬停逻辑立即隐藏。
        screen = QApplication.screenAt(global_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()

        gap = 15
        max_popup_width = max(1, screen_rect.width() - gap * 2)
        display_size=min(int(size_config),max_popup_width)
        for _ in range(2):
            self.metadata_footer.setFixedWidth(max(1,display_size-8))
            metadata_height=max(1,self.meta_layout.heightForWidth(max(1,display_size-8)))
            display_size=min(display_size,max(1,screen_rect.height()-gap*2-metadata_height-24))
        self.metadata_footer.setFixedHeight(metadata_height)
        total_height = display_size + metadata_height + 4
        self.setFixedSize(display_size, total_height)
        
        # 只读取图片尺寸，不载入原图像素数据。
        reader = QImageReader(image_path)
        original_size = reader.size()
        
        target_size = self.calculate_scaled_size(original_size, max(1, display_size-8))
        
        self.image_label.setFixedSize(
            max(1, display_size - 8),
            max(1, display_size - 8),
        )
        self.image_label.setScaledContents(False)

        # 2. 智能计算位置，防止预览窗口落到屏幕外
        popup_width = self.width()
        popup_height = self.height()

        if container_rect is not None:
            # Fixed mode: a corner overlay inside the content pane. Bottom-right
            # by default; when the hovered card already occupies that corner the
            # overlay moves to the bottom-left so it never covers what the user
            # is pointing at.
            margin = 4
            right_x = container_rect.right() - popup_width - margin
            target_y = max(container_rect.top() + margin,
                           container_rect.bottom() - popup_height - margin)
            occupied = anchor_rect is not None and anchor_rect.intersects(
                QRect(right_x, target_y, popup_width, popup_height))
            target_x = container_rect.left() + margin if occupied else right_x
        else:
            # 优先放在指针右下方；空间不足时分别翻转到左侧/上方。
            candidate_positions = (
                (global_pos.x() + gap, global_pos.y() + gap),
                (global_pos.x() - popup_width - gap, global_pos.y() + gap),
                (global_pos.x() + gap, global_pos.y() - popup_height - gap),
                (global_pos.x() - popup_width - gap, global_pos.y() - popup_height - gap),
            )

            target_x, target_y = next(
                (
                    (x, y)
                    for x, y in candidate_positions
                    if (
                        x >= screen_rect.left()
                        and y >= screen_rect.top()
                        and x + popup_width <= screen_rect.right() + 1
                        and y + popup_height <= screen_rect.bottom() + 1
                    )
                ),
                (
                    # 四个方向都放不下时，夹紧到当前屏幕可用区域。
                    max(
                        screen_rect.left(),
                        min(global_pos.x() + gap, screen_rect.right() - popup_width + 1),
                    ),
                    max(
                        screen_rect.top(),
                        min(global_pos.y() + gap, screen_rect.bottom() - popup_height + 1),
                    ),
                ),
            )

        # 3. 移动并无焦点显示窗口
        self.move(target_x, target_y)

        # 4. 根据文件格式渲染
        if image_path.lower().endswith(('.gif', '.webp')):
            self.current_movie = QMovie(image_path, parent=self)
            # 预览动图时只保留当前/必要帧，避免 CacheAll 将整个动画
            # 解码后常驻内存。显示尺寸和动画行为保持不变。
            self.current_movie.setCacheMode(QMovie.CacheNone)
            
            self.current_movie.setScaledSize(target_size)
            
            self.image_label.setMovie(self.current_movie)
            self.current_movie.start()
        else:
            # 直接按预览尺寸解码，避免 QPixmap(image_path) 先把超大原图
            # 完整载入内存后再缩放。target_size 已按原图比例计算。
            reader = QImageReader(image_path)
            reader.setScaledSize(target_size)
            image = reader.read()

            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.image_label.setPixmap(pixmap)
        self.show()

    def hide_preview(self):
        """隐藏预览并清理资源释放文件锁"""
        if self.current_movie:
            self.current_movie.stop()
            self.current_movie.setDevice(None)
            self.current_movie.deleteLater()
            self.current_movie = None
            
        self.image_label.clear()
        # 显式替换 QLabel 内部的 pixmap 引用，避免静态预览在隐藏后
        # 继续占用一块较大的图像内存。
        self.image_label.setPixmap(QPixmap())
        self.hide()
        
    def calculate_scaled_size(self, original_size, target_square_size):
        """计算保持宽高比的 QSize"""
        if original_size.isEmpty():
            return QSize(target_square_size - 16, target_square_size - 16)
            
        width = original_size.width()
        height = original_size.height()
        target = target_square_size - 16 

        if width > height:
            return QSize(target, int(height * (target / width)))
        else:
            return QSize(int(width * (target / height)), target)
