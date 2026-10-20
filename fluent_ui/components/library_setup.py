"""Shared first-use/recovery presentation; pickers never initialize a library."""
from PySide6.QtWidgets import (QFileDialog, QLabel, QHBoxLayout, QVBoxLayout,
                               QWidget, QSizePolicy, QApplication, QPlainTextEdit)
from PySide6.QtCore import Qt, QEvent, QRectF, QTimer
from PySide6.QtGui import QPainter, QColor, QKeySequence
from fluent_ui.components.dialogs import NekoriDialog
from fluent_ui.components.controls import PushButton, TransparentToolButton
from fluent_ui import visual
from fluent_ui.icons import Icon
from services.i18n import t
from services.library_setup import check_target, commit_library, LibraryLocationError


class LibraryPath(QWidget):
    """One-line display with a full-path copy action, never an editable input."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.full_path = ''
        self.setMinimumWidth(0)
        row = QHBoxLayout(self); row.setContentsMargins(12, 8, 8, 8); row.setSpacing(10)
        self.icon = QLabel(self); self.icon.setFixedSize(18, 18)
        self.label = QLabel(self); self.label.setMinimumWidth(0)
        self.label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.label.installEventFilter(self)
        self.copy_button = TransparentToolButton(Icon.COPY, self)
        self.copy_button.setFixedSize(28, 28)
        self.copy_button.setToolTip(t('复制完整路径'))
        self.copy_button.setAccessibleName(t('复制完整路径'))
        self.copy_button.clicked.connect(self.copy_path)
        row.addWidget(self.icon); row.addWidget(self.label, 1); row.addWidget(self.copy_button)
        self.refresh_theme()

    def set_path(self, path):
        self.full_path = str(path)
        self.setToolTip(self.full_path); self.label.setToolTip(self.full_path)
        self._elide()

    def _elide(self):
        self.label.setText(self.label.fontMetrics().elidedText(
            self.full_path, Qt.ElideMiddle, max(1, self.label.contentsRect().width())))

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.FontChange):
            self._elide()
        if event.type() == QEvent.KeyPress and event.matches(QKeySequence.Copy):
            self.copy_path(); return True
        return super().eventFilter(obj, event)

    def copy_path(self):
        QApplication.clipboard().setText(self.full_path)

    def refresh_theme(self):
        self.icon.setPixmap(Icon.FOLDER.icon(color=visual.colors()['text_secondary']).pixmap(18, 18))
        self.update()

    def paintEvent(self, event):
        c = visual.colors(); painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(c['border_soft'])); painter.setBrush(QColor(c['surface_alt']))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 8, 8)


class LibrarySetupDialog(NekoriDialog):
    def __init__(self, config, path, *, recovery=False):
        super().__init__(title='')
        self.config = config; self.storage = None; self.path = str(path)
        self.original_path = self.path; self.recovery = recovery
        self.mode = 'connect' if recovery else 'create'
        self._ready = not recovery; self._failed = False; self._custom = False
        self.setObjectName('LibrarySetupDialog')
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(500); self.resize(560, 320)
        self.header.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        while self.header_layout.count(): self.header_layout.takeAt(0)
        self.header_layout.setContentsMargins(22, 18, 16, 14); self.header_layout.setSpacing(12)
        self.status_icon = QLabel(self.header); self.status_icon.setFixedSize(24, 24)
        headings = QVBoxLayout(); headings.setSpacing(4)
        self.subtitle = QLabel(self.header); self.subtitle.setProperty('role', 'hint')
        headings.addWidget(self.title_label); headings.addWidget(self.subtitle)
        self.close_button = TransparentToolButton(Icon.CANCEL, self.header)
        self.close_button.setFixedSize(28, 28); self.close_button.setToolTip(t('退出'))
        self.close_button.setAccessibleName(t('退出')); self.close_button.clicked.connect(self.reject)
        self.header_layout.addWidget(self.status_icon)
        self.header_layout.addLayout(headings, 1); self.header_layout.addWidget(self.close_button, 0, Qt.AlignTop)
        self.subtitle.installEventFilter(self._title_drag)
        self.body.setContentsMargins(22, 14, 22, 16); self.body.setSpacing(10)
        self.description = self.add_hint('')
        self.path_heading = QLabel(self)
        self.path_box = LibraryPath(self)
        self.path_label = self.path_box.label  # retained for diagnostics
        path_header = QHBoxLayout(); path_header.setSpacing(8)
        self.choose_new = PushButton(self)
        self.choose_new.ghost = True
        self.choose_new.clicked.connect(lambda: self.choose('create'))
        path_header.addWidget(self.path_heading); path_header.addStretch()
        path_header.addWidget(self.choose_new)
        self.body.addLayout(path_header); self.body.addWidget(self.path_box)
        self.selected_heading = QLabel(t('所选位置'), self)
        self.selected_box = LibraryPath(self)
        self.body.addWidget(self.selected_heading); self.body.addWidget(self.selected_box)
        self.connection_button = PushButton(t('连接已有表情库…'), self)
        self.connection_button.ghost = True
        self.connection_button.clicked.connect(lambda: self.choose('connect'))
        self.body.addWidget(self.connection_button, 0, Qt.AlignLeft)
        self.error_label = self.add_hint(''); self.error_label.setProperty('role', 'error')
        self.details_button = PushButton(t('查看错误详情'), self)
        self.details_button.ghost = True; self.details_button.clicked.connect(self.toggle_details)
        self.body.addWidget(self.details_button, 0, Qt.AlignLeft)
        self.details = QPlainTextEdit(self); self.details.setReadOnly(True); self.details.setFixedHeight(90)
        self.body.addWidget(self.details)
        self.actions.setContentsMargins(22, 12, 22, 14); self.actions.setSpacing(10)
        self.exit_button = self.add_button('退出', on_click=self.reject)
        self.exit_button.ghost = True
        # Neutral shared button paint: no role=primary (which would fill neon accent).
        self.start_button = self.add_button('开始使用', on_click=self.begin)
        self.start_button.setMinimumWidth(112); self.start_button.setDefault(True)
        self.choose_existing = self.start_button if recovery else self.connection_button
        self.error_label.hide(); self.details_button.hide(); self.details.hide()
        self._render_state(); self.refresh_theme()

    def _render_state(self):
        failed = self._failed
        title = '无法使用所选位置' if failed else '无法找到表情库' if self.recovery else '设置表情库位置'
        self.title_label.setText(t(title)); self.setWindowTitle(t(title))
        self.subtitle.setText(t('首次使用 NekoriEmojy') if not self.recovery and not failed else t('表情库位置'))
        self.description.setText(t(
            '无法在所选位置创建或保存表情库。\n请检查写入权限，或选择其他文件夹。' if failed else
            '无法访问上次使用的表情库。\n请选择原有表情库的新位置，或创建新的表情库。' if self.recovery else
            '选择保存表情及管理数据的位置。\n以后可以在设置中重新连接表情库。'))
        self.path_heading.setText(t('所选位置' if failed or self._custom and not self.recovery else
                                    '原表情库位置' if self.recovery else '推荐位置'))
        self.path_box.set_path(self.path if failed or not self.recovery else self.original_path)
        self.choose_new.setText(t('创建新表情库…' if self.recovery else '选择其他位置…'))
        self.choose_new.setVisible(not failed)
        self.connection_button.setVisible(not self.recovery and not failed)
        selected = self.recovery and self._ready and not failed
        self.selected_heading.setVisible(selected); self.selected_box.setVisible(selected)
        self.selected_box.set_path(self.path)
        action = ('选择其他位置…' if failed else '重新定位表情库…' if self.recovery and not self._ready else
                  '连接并开始' if self.recovery and self.mode == 'connect' else
                  '创建并开始' if self.recovery else '开始使用')
        self.start_button.setText(t(action)); self.start_button.setEnabled(True)
        self._update_icon(); self._fit_content()

    def _update_icon(self):
        if not hasattr(self, 'status_icon'): return
        warning = self.recovery or self._failed
        c = visual.colors()
        self.status_icon.setPixmap((Icon.WARNING if warning else Icon.FOLDER).icon(
            color=c['warning'] if warning else c['text_secondary']).pixmap(24, 24))

    def _fit_content(self):
        self.root.invalidate(); self.root.activate()
        height = self.root.heightForWidth(self.width())
        self.resize(self.width(), max(self.root.minimumSize().height(), height if height >= 0 else self.root.sizeHint().height()))

    def refresh_theme(self):
        super().refresh_theme()
        self.setStyleSheet(self.styleSheet() + '\nQDialog#LibrarySetupDialog { background: transparent; border: none; }')
        if hasattr(self, 'path_box'):
            self.path_box.refresh_theme(); self.selected_box.refresh_theme(); self._update_icon()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        font = visual.font('body'); font.setPixelSize(18); font.setBold(True); self.title_label.setFont(font)
        self._fit_content()
        QTimer.singleShot(0, self._fit_content)
        if not self.parentWidget() and not getattr(self, '_centered', False):
            screen = self.screen(); area = screen.availableGeometry()
            self.move(area.center().x()-self.width()//2, area.center().y()-self.height()//2)
            self._centered = True

    def paintEvent(self, event):
        from fluent_ui.materials import shell_color, shell_radius
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        radius = shell_radius(self); c = visual.colors()
        p.setPen(QColor(c['border_soft'])); p.setBrush(shell_color(self))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), radius, radius)
        # Opaque paper/ink body over the single native acrylic shell.
        top = self.header.geometry().bottom()+1; bottom = self.footer_rule.geometry().top()
        p.setPen(Qt.NoPen); p.setBrush(QColor(c['content_base']))
        p.drawRect(QRectF(1, top, self.width()-2, max(0, bottom-top)))
        p.setBrush(QColor(visual.accent())); p.drawRoundedRect(QRectF(14, 2, self.width()-28, 2), 1, 1)

    def toggle_details(self):
        self.details.setVisible(self.details.isHidden())
        self.details_button.setText(t('收起错误详情' if self.details.isVisible() else '查看错误详情'))
        self._fit_content()

    def show_failure(self, error, *, target=None, initialization=False):
        if initialization or not isinstance(error, LibraryLocationError):
            self._failed = True; self._ready = False
            if target is not None: self.path = str(target)
            summary = '无法写入该文件夹。' if isinstance(error, PermissionError) else '无法准备表情库或保存设置。'
            self.error_label.setText(t(summary)); self.details.setPlainText(str(error))
            self.details_button.show(); self.details.hide(); self._render_state()
        else:
            self.error_label.setText(t(str(error)))
        self.error_label.show(); self._fit_content()

    def choose(self, mode):
        directory = QFileDialog.getExistingDirectory(self, t(
            '创建新表情库…' if mode == 'create' else '连接已有表情库…'), self.path)
        if not directory: return
        try: actual = check_target(directory, mode)
        except (OSError, ValueError) as error:
            self.show_failure(error, target=directory); return
        self.path = directory; self.mode = actual; self._ready = True; self._failed = False; self._custom = True
        self.error_label.hide(); self.details_button.hide(); self.details.hide()
        self._render_state()

    def begin(self):
        if self._failed:
            self.choose('create'); return
        if not self._ready:
            self.choose('connect'); return
        self.start_button.setEnabled(False)
        try: self.storage = commit_library(self.config, self.path, self.mode)
        except Exception as error:
            self.show_failure(error, initialization=True); return
        self.accept()


def open_startup_library(config):
    from services.library_setup import startup_location,prepare_library
    from services.i18n import i18n_engine
    from fluent_ui import visual
    i18n_engine.init(config);visual.theme.configure(config)
    path,needs_ui,recovery=startup_location(config)
    if not needs_ui:
        try:
            mode='connect' if path.exists() and any(path.iterdir()) else 'create'
            with prepare_library(path,mode,config) as storage:return storage
        except Exception:recovery=True
    dialog=LibrarySetupDialog(config,path,recovery=recovery)
    return dialog.storage if dialog.exec() else None
