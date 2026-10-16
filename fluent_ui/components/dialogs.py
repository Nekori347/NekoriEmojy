from services.i18n import t, i18n_engine, bind_text, translated
"""Unified Nekori business dialogs.

Only Nekori's own rename / edit / confirm / status surfaces use these. Real
Windows tools such as the file picker keep their native presentation.
"""
from PySide6.QtCore import Qt, QPoint, QObject, QEvent
from PySide6.QtGui import QFont, QGuiApplication, QPainter, QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from services.i18n import t, i18n_engine, bind_text, translated

from fluent_ui.visual import DATA_FONT, RADIUS, accent, colors, dialog_style
from fluent_ui.components.controls import PushButton as QPushButton, LineEdit as QLineEdit
from fluent_ui.components.softframe import SoftframeSlider as QSlider

BUTTON_STYLE = '''
QPushButton {{ background: {surface}; color: {text}; border: 1px solid {border};
    border-radius: {radius}px; padding: 6px 18px; }}
QPushButton:hover {{ border-color: {signal}; }}
QPushButton[role="primary"] {{ background: {signal}; color: {accent_text};
    border: 1px solid {signal}; font-weight: 600; }}
QPushButton[role="danger"] {{ color: {error}; border-color: {error}; }}
QPushButton[role="danger"]:hover {{ background: {error}; color: #FFFFFF; }}
QPushButton:disabled {{ color: {muted}; border-color: {border}; }}
QPushButton[role="primary"]:disabled {{ background: {surface}; color: {muted}; border-color: {border}; }}
'''


def _button_style():
    from fluent_ui.visual import control_style
    return control_style()


def center_on_owner(widget, owner):
    """Center a real dialog/window on its owner, staying within that screen."""
    owner = owner.window()
    center = owner.frameGeometry().center()
    screen = QGuiApplication.screenAt(center) or owner.screen()
    area = screen.availableGeometry()
    x = max(area.left(), min(center.x()-widget.width()//2, area.right()-widget.width()+1))
    y = max(area.top(), min(center.y()-widget.height()//2, area.bottom()-widget.height()+1))
    widget.move(QPoint(x, y))


class DialogTitleDrag(QObject):
    """Route title presses to the native move loop, including label hits."""

    def __init__(self, title):
        super().__init__(title)
        title.installEventFilter(self)
        for label in title.findChildren(QLabel):
            label.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            handle = obj.window().windowHandle()
            if handle and handle.startSystemMove():
                return True
        return super().eventFilter(obj, event)


class OwnerScrim(QWidget):
    def __init__(self,owner):
        super().__init__(owner)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        owner.installEventFilter(self)
        self.setGeometry(owner.rect())

    def eventFilter(self,obj,event):
        if event.type()==QEvent.Resize:
            self.setGeometry(obj.rect())
        return False

    def paintEvent(self,event):
        p=QPainter(self)
        p.fillRect(self.rect(),QColor(0,0,0,92))


class OwnerCenteredDialog(QDialog):
    """Keep legacy dialog content while sharing first-show owner positioning."""

    def __init__(self, parent=None):
        super().__init__(parent.window() if parent else None)
        self.setWindowModality(Qt.WindowModal)
        self._scrim = None

    def showEvent(self, event):
        from fluent_ui import visual
        visual.apply_typography(self)
        super().showEvent(event)
        from fluent_ui.materials import native_material,sync_native_clip
        native_material(self,overlay=True);sync_native_clip(self)
        if self.parentWidget() and self.windowModality()!=Qt.NonModal:
            if self._scrim is None:
                self._scrim=OwnerScrim(self.parentWidget())
                self.destroyed.connect(self._scrim.deleteLater)
            self._scrim.setGeometry(self.parentWidget().rect())
            self._scrim.show();self._scrim.raise_()
        if not getattr(self, '_positioned', False) and self.parentWidget():
            center_on_owner(self, self.parentWidget())
            self._positioned = True

    def hideEvent(self,event):
        if self._scrim:
            self._scrim.hide()
        super().hideEvent(event)


class NekoriDialog(OwnerCenteredDialog):
    """Frameless dialog with the Nekori header strip and a bottom rule of actions."""

    def __init__(self, parent=None, title="", code=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModal)
        self.setObjectName("NekoriDialog")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAutoFillBackground(True)
        self.setStyleSheet(dialog_style() + _button_style())
        from fluent_ui import visual
        visual.theme.changed.connect(self.refresh_theme)
        self._drag_offset = None

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        self.header = QWidget(self)
        self.header.setObjectName("DialogHeader")
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(16, 12, 16, 12)
        header_font = visual.font('page_title')
        header_font.setBold(True)
        self.title_label = translated(QLabel, title, self.header)
        self.title_label.setFont(header_font)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        if code:
            self.code_label = QLabel(code, self.header)
            mono = QFont(DATA_FONT.split(",")[0].strip())
            mono.setPixelSize(10)
            self.code_label.setFont(mono)
            self.code_label.setProperty("role", "data")
            self.header_layout.addWidget(self.code_label)
        self.root.addWidget(self.header)
        self._title_drag = DialogTitleDrag(self.header)

        rule = QFrame(self)
        rule.setFixedHeight(1)
        rule.setProperty("role", "rule")
        self.root.addWidget(rule)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(10)
        self.root.addLayout(self.body)

        self.footer_rule = QFrame(self)
        self.footer_rule.setFixedHeight(1)
        self.footer_rule.setProperty("role", "rule")
        self.root.addWidget(self.footer_rule)

        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(16, 12, 16, 12)
        self.actions.setSpacing(8)
        self.actions.addStretch()
        self.root.addLayout(self.actions)

    def refresh_theme(self):
        self.setStyleSheet(dialog_style() + _button_style())

    def add_button(self, text, role="", on_click=None, enabled=True):
        button = translated(QPushButton, text, self)
        if role:
            button.setProperty("role", role)
        button.setEnabled(enabled)
        button.setCursor(Qt.PointingHandCursor)
        if on_click is not None:
            button.clicked.connect(on_click)
        self.actions.addWidget(button)
        return button

    def add_hint(self, text):
        label = translated(QLabel, text, self)
        label.setWordWrap(True)
        label.setProperty("role", "hint")
        self.body.addWidget(label)
        return label

    def add_widget(self, widget):
        self.body.addWidget(widget)
        return widget

    # Frameless dragging is limited to the header strip.
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and \
                self.header.geometry().contains(event.position().toPoint()):
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


def prompt_text(parent, title, label, initial="", hint="", ok_text="确定", code=""):
    dialog = NekoriDialog(parent, title, code=code)
    dialog.add_widget(translated(QLabel, label, dialog))
    editor = QLineEdit(initial, dialog)
    editor.selectAll()
    dialog.add_widget(editor)
    if hint:
        dialog.add_hint(hint)
    result = {"value": None}

    def accept():
        result["value"] = editor.text()
        dialog.accept()

    dialog.add_button(t("取消"), on_click=dialog.reject)
    dialog.add_button(ok_text, role="primary", on_click=accept)
    editor.returnPressed.connect(accept)
    dialog.setMinimumWidth(360)
    editor.setFocus()
    accepted = dialog.exec() == QDialog.Accepted
    return (result["value"] if accepted else ""), accepted


def confirm(parent, title, message, ok_text="确定", danger=False, hint="", code=""):
    dialog = NekoriDialog(parent, title, code=code)
    label = translated(QLabel, message, dialog)
    label.setWordWrap(True)
    dialog.add_widget(label)
    if hint:
        dialog.add_hint(hint)
    dialog.add_button(t("取消"), on_click=dialog.reject)
    dialog.add_button(ok_text, role="danger" if danger else "primary", on_click=dialog.accept)
    dialog.setMinimumWidth(380)
    return dialog.exec() == QDialog.Accepted


def message(parent, title, text, code=""):
    dialog = NekoriDialog(parent, title, code=code)
    label = translated(QLabel, text, dialog)
    label.setWordWrap(True)
    dialog.add_widget(label)
    dialog.add_button(t("关闭"), role="primary", on_click=dialog.accept)
    dialog.setMinimumWidth(360)
    return dialog.exec()


def choose_item(parent, title, label, items, ok_text="确定", code="", *,
                searchable=False, paths=None):
    """items: list of (value, display). Returns (value, accepted).

    With searchable=True a filter box is added and every row carries its full
    path as a tooltip, so a deep tree stays usable without turning the picker
    into a very long flat list.
    """
    dialog = NekoriDialog(parent, title, code=code)
    dialog.add_widget(translated(QLabel, label, dialog))
    paths = paths or {}
    search = None
    if searchable:
        from fluent_ui.components.controls import SearchLineEdit
        search = SearchLineEdit(dialog)
        bind_text(search, t("搜索分类名或路径"), 'setPlaceholderText')
        dialog.add_widget(search)
    listing = QListWidget(dialog)
    listing.setMinimumHeight(240)
    listing.setMaximumHeight(360)
    for value, display in items:
        item = QListWidgetItem(display, listing)
        item.setData(Qt.UserRole, value)
        # Strip the indentation padding: the file already holds the hierarchy.
        item.setData(Qt.UserRole + 1, (paths.get(value) or display.strip()))
        item.setToolTip(paths.get(value) or display.strip())
    if listing.count():
        listing.setCurrentRow(0)
    dialog.add_widget(listing)

    empty = translated(QLabel, "没有匹配的分类", dialog)
    empty.setProperty("role", "data")
    empty.hide()
    dialog.add_widget(empty)

    def apply_filter(text):
        needle = (text or "").strip().casefold()
        first_visible = None
        for row in range(listing.count()):
            item = listing.item(row)
            haystack = f"{item.text()} {item.data(Qt.UserRole + 1)}".casefold()
            match = not needle or needle in haystack
            item.setHidden(not match)
            if match and first_visible is None:
                first_visible = item
        empty.setVisible(first_visible is None)
        if first_visible is not None:
            listing.setCurrentItem(first_visible)

    if search is not None:
        search.textChanged.connect(apply_filter)

    result = {"value": None}

    def accept():
        item = listing.currentItem()
        if item is None or item.isHidden():
            return
        result["value"] = item.data(Qt.UserRole)
        dialog.accept()

    dialog.add_button(t("取消"), on_click=dialog.reject)
    dialog.add_button(ok_text, role="primary", on_click=accept)
    listing.itemDoubleClicked.connect(lambda _: accept())
    dialog.setMinimumWidth(400 if not searchable else 460)
    accepted = dialog.exec() == QDialog.Accepted and result["value"] is not None
    return result["value"], accepted


class TagEditorDialog(NekoriDialog):
    """Add / remove / replace tags on one or many resources."""

    def __init__(self, parent, storage, paths):
        super().__init__(parent, "标签编辑", code=f"TAG/{len(paths)}")
        self.storage = storage
        self.paths = list(paths)
        self.add_hint(t('将以下标签应用到选中的 {value_0} 个资源。').format(value_0=len(paths)))

        self.mode_box = QComboBox(self)
        self.mode_box.addItem(t("追加标签"), "add")
        self.mode_box.addItem(t("移除标签"), "remove")
        self.mode_box.addItem(t("覆盖为"), "replace")
        self.add_widget(self.mode_box)
        i18n_engine.language_changed.connect(self.refresh_texts)

        self.editor = QLineEdit(self)
        bind_text(self.editor, t("多个标签用空格分隔"), 'setPlaceholderText')
        self.add_widget(self.editor)

        known = list(storage.all_tags())[:80]
        if known:
            self.add_hint(t("已有标签（点击追加）"))
            listing = QListWidget(self)
            listing.setMaximumHeight(130)
            listing.addItems(known)
            listing.itemClicked.connect(lambda item: self._append(item.text()))
            self.add_widget(listing)

        current = sorted({tag for path in self.paths
                          for tag in storage.parse_tags(storage.get_image_keywords(path))})
        if current:
            self.add_hint(t("当前标签：{tags}").format(tags=" / ".join(current)))

        self.add_button(t("取消"), on_click=self.reject)
        self.add_button(t("应用"), role="primary", on_click=self._apply)
        self.setMinimumWidth(430)

    def refresh_texts(self, *_):
        for i, label in enumerate(('追加标签', '移除标签', '覆盖为')):
            self.mode_box.setItemText(i, t(label))

    def _append(self, tag):
        existing = self.storage.parse_tags(self.editor.text())
        if tag not in existing:
            existing.append(tag)
        self.editor.setText(self.storage.serialize_tags(existing))

    def _apply(self):
        tags = self.storage.parse_tags(self.editor.text())
        mode = self.mode_box.currentData()
        if not tags and mode != "replace":
            self.reject()
            return
        self.storage.apply_tags(self.paths, tags, mode)
        self.accept()


class FramePickerDialog(NekoriDialog):
    """Choose which frame of a GIF / animated WebP represents it in the grid."""

    def __init__(self, parent, storage, path):
        super().__init__(parent, "选择缩略图帧", code="FRAME")
        # Needed by _apply / _reset: without it the confirm button raised
        # AttributeError, so the frame was never saved, the dialog never closed
        # and Windows played its invalid-operation sound.
        self.storage = storage
        self.path = path
        self.metadata = storage.resource_metadata(path)

        self.preview = QLabel(self)
        self.preview.setFixedSize(240, 240)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet(f"border: 1px solid {colors()['border']};")
        self.add_widget(self.preview)

        self.frame_count = self._count_frames()
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, max(0, self.frame_count - 1))
        self.slider.setValue(min(int(self.metadata.get("thumb_frame", 0) or 0), self.frame_count - 1))
        self.slider.valueChanged.connect(self._render)
        self.add_widget(self.slider)

        self.frame_label = QLabel(self)
        self.frame_label.setProperty("role", "data")
        self.add_widget(self.frame_label)

        self.add_button(t("取消"), on_click=self.reject)
        self.add_button(t("恢复自动"), on_click=self._reset)
        self.add_button(t("使用此帧"), role="primary", on_click=self._apply)
        self.setMinimumWidth(300)
        self._render(self.slider.value())

    def _count_frames(self):
        from services.image_frames import frame_count
        return frame_count(self.path)

    def _render(self, index):
        from PySide6.QtGui import QPixmap
        from services.image_frames import frame_at
        # QImageReader cannot step GIF frames in this build, so the frame comes
        # from the shared decoder; otherwise every index showed frame 0.
        image = frame_at(self.path, int(index))
        if image is None or image.isNull():
            bind_text(self.preview, t("无法读取该帧"), 'setText')
            self.frame_label.setText("")
            return
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.width() - 8, self.preview.height() - 8,
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pixmap)
        bind_text(self.frame_label, t('帧 {value_0} / {value_1}').format(value_0=int(index) + 1, value_1=self.frame_count), 'setText')

    def _apply(self):
        self.metadata["thumb_frame"] = int(self.slider.value())
        self.storage.set_resource_metadata(self.path, self.metadata)
        # The grid card re-attaches by itself: the thumbnail cache key carries
        # the frame, so the new frame is a cache miss and the old entry ages out.
        self.saved = True
        self.accept()

    def _reset(self):
        self.metadata.pop("thumb_frame", None)
        self.storage.set_resource_metadata(self.path, self.metadata)
        self.saved = True
        self.accept()
