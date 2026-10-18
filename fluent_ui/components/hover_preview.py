import os
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QHBoxLayout, QFrame, QSizePolicy
from PySide6.QtCore import Qt, QSize, QByteArray, QBuffer, QRect, QRectF, QEvent
from PySide6.QtGui import QPixmap, QMovie, QImageReader, QPainter, QPainterPath, QColor, QPalette, QFont
from fluent_ui.icons import Icon
from qfluentwidgets import BodyLabel, CaptionLabel
import darkdetect
from services.i18n import t, i18n_engine
from fluent_ui import visual
from fluent_ui.components.tag_panel import TagFlow
from fluent_ui.components.tag_model import TagItem

class IconCaption(QLabel):
    def __init__(self,icon,text):
        super().__init__(text);self.icon=icon;self.setContentsMargins(20,0,0,0);self.setFont(visual.font('secondary'))
    def paintEvent(self,event):
        p=QPainter(self);p.setFont(self.font());p.setPen(self.palette().color(QPalette.WindowText))
        rect=self.contentsRect()
        p.drawText(rect,Qt.AlignLeft|Qt.AlignVCenter|Qt.TextSingleLine,self.fontMetrics().elidedText(self.text(),Qt.ElideRight,rect.width()))
        self.icon.render(p,QRect(0,(self.height()-13)//2,13,13),fill=visual.colors()['text_secondary'])


class PreviewTags(TagFlow):
    """The real tag-panel chip painter, bounded to two rows for a preview."""
    def _chip_width(self, item):
        return min(super()._chip_width(item),max(1,self.width()-8))

    def _relayout(self):
        super()._relayout()
        self.setFixedHeight(min(self._content_height,2*self.CHIP_HEIGHT+self.CHIP_GAP+2*self.PAD))

    def heightForWidth(self, width):
        return min(self._content_height,2*self.CHIP_HEIGHT+self.CHIP_GAP+2*self.PAD)

    def sizeHint(self):return QSize(0,self.heightForWidth(self.width()))
    def minimumSizeHint(self):return self.sizeHint()


class PreviewText(QLabel):
    """One metric-sized OCR line; normalization is presentation-only."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWordWrap(False)
        self.setMinimumWidth(0)
        self.setContentsMargins(0,2,0,2)
        self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        self._sync_height()

    def _sync_height(self):
        margins=self.contentsMargins()
        self.setFixedHeight(self.fontMetrics().height()+margins.top()+margins.bottom())

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.FontChange:self._sync_height()

    def setText(self,text):
        super().setText(' '.join(str(text).split()))

    def sizeHint(self):return QSize(0,self.height())
    def minimumSizeHint(self):return self.sizeHint()

    def paintEvent(self,event):
        painter=QPainter(self);painter.setFont(self.font());painter.setPen(self.palette().color(QPalette.WindowText))
        rect=self.contentsRect()
        painter.drawText(rect,Qt.AlignLeft|Qt.AlignVCenter|Qt.TextSingleLine,
                         self.fontMetrics().elidedText(self.text(),Qt.ElideRight,rect.width()))


class IdentityCaption(QLabel):
    def __init__(self,parent=None):
        super().__init__(parent);self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);self.setProperty('role','data')

    def sizeHint(self):return QSize(0,self.fontMetrics().height())
    def minimumSizeHint(self):return self.sizeHint()

    def paintEvent(self,event):
        painter=QPainter(self);painter.setFont(self.font());painter.setPen(self.palette().color(QPalette.WindowText))
        painter.drawText(self.rect(),Qt.AlignLeft|Qt.AlignVCenter,self.fontMetrics().elidedText(self.text(),Qt.ElideMiddle,self.width()))


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
        
        self.ocr_heading=QWidget(self.metadata_footer)
        heading_layout=QHBoxLayout(self.ocr_heading);heading_layout.setContentsMargins(0,2,0,5);heading_layout.setSpacing(7)
        self.ocr_marker=QFrame(self.ocr_heading);self.ocr_marker.setFixedWidth(2)
        self.ocr_label=PreviewText(self.ocr_heading)
        heading_layout.addWidget(self.ocr_marker,0,Qt.AlignVCenter);heading_layout.addWidget(self.ocr_label,1)
        self.category_label=IconCaption(Icon.FOLDER,'')
        self.category_label.setWordWrap(False)
        self.category_label.setMinimumWidth(0)
        self.category_label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        self.tags=PreviewTags(self.metadata_footer);self.tags.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.identity_rule=QFrame(self.metadata_footer);self.identity_rule.setFixedHeight(1)
        self.name_label=IdentityCaption(self.metadata_footer)
        self.path_label=IdentityCaption(self.metadata_footer)
        for widget in (self.ocr_heading,self.category_label,self.tags,self.identity_rule,self.name_label,self.path_label):
            self.meta_layout.addWidget(widget)
        self.ocr_heading.hide();self.tags.hide()

        self.layout.addWidget(self.metadata_footer)
        
        self.current_movie = None
        self.setObjectName("PreviewPopup")
        
        # 绑定语言切换信号
        i18n_engine.language_changed.connect(self.update_texts)

    def update_texts(self, lang):
        category=getattr(self,'current_category_str','')
        self.category_label.setText(t('分类')+': '+category if category else t('无分类'))

    def update_identity(self, info):
        """File identity as low-weight text under the image."""
        self.current_name_str = str(info.get('name') or '')
        self.current_path_str = str(info.get('path') or '')
        self.name_label.setText(self.current_name_str)
        self.path_label.setText(self.current_path_str)
        self.name_label.setToolTip(self.current_name_str);self.path_label.setToolTip(self.current_path_str)
        self.name_label.setVisible(bool(self.current_name_str));self.path_label.setVisible(bool(self.current_path_str))
        self.identity_rule.setVisible(bool(self.current_name_str or self.current_path_str))

    def update_theme(self):
        """The preview uses the same semantic surface in either presentation."""
        visual.apply_typography(self)
        palette = visual.colors()
        data_style = f"color: {palette['text_muted']};"
        self.name_label.setStyleSheet(data_style)
        self.path_label.setStyleSheet(data_style)
        text_style = f"color: {palette['text_primary']};"
        self.category_label.setStyleSheet(text_style)
        self.tags.refresh_theme()
        font=visual.font('body');font.setPixelSize(14);font.setWeight(QFont.Medium);self.ocr_label.setFont(font)
        self.ocr_label._sync_height()
        self.ocr_marker.setFixedHeight(self.ocr_label.height())
        self.category_label.setFixedHeight(max(13,self.category_label.fontMetrics().height())+4)
        self.ocr_label.setStyleSheet(text_style)
        self.ocr_marker.setStyleSheet('background:'+palette['accent']+';')
        self.identity_rule.setStyleSheet('background:'+palette['border_soft']+';')
        for label in (self.name_label,self.path_label):label.setFont(visual.font('secondary'))
        self.setStyleSheet(f"QWidget#PreviewPopup {{ {visual.surface_style('popover')} "
                           f"border: 1px solid {palette['border']}; "
                           f"border-radius: {visual.PANEL_RADIUS}px; }}")

    def show_preview(self, image_path, global_pos, size_config=320, category_str="",
                     keyword_str="", info=None, anchor_rect=None, container_rect=None):
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

        self.update_texts(i18n_engine.current_lang)
        self.category_label.setToolTip(category_str)
        from services.storage import StorageService
        tags=StorageService.parse_tags(keyword_str) if keyword_str else []
        self.tags.set_items([TagItem(name) for name in tags]);self.tags.setVisible(bool(tags));self.tags.setToolTip(keyword_str)
        ocr=str(info.get('ocr_text') or '').strip()
        self.ocr_label.setText(ocr);self.ocr_heading.setVisible(bool(ocr))
        self.path_label.setToolTip(os.path.abspath(image_path))

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
            margins=self.meta_layout.contentsMargins()
            self.tags.setFixedWidth(max(1,display_size-8-margins.left()-margins.right()))
            self.tags._relayout()
            rows=[self.meta_layout.itemAt(i).widget() for i in range(self.meta_layout.count())]
            rows=[row for row in rows if not row.isHidden()]
            metadata_height=(margins.top()+margins.bottom()+sum(row.sizeHint().height() for row in rows)
                             +self.meta_layout.spacing()*max(0,len(rows)-1))
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
