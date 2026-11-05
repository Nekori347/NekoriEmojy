"""Setting rows and collapsible sections in the Nekori visual language.

Rows expose key-bound values and never write the config directly: the Settings
Center collects pending values so Save / Discard stay meaningful.
"""
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QSize, QObject
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QVBoxLayout, QWidget, QGridLayout, QBoxLayout,
)
from fluent_ui.components.controls import ComboBox, PushButton, SwitchButton, TransparentToolButton
from fluent_ui.icons import Icon as FIF
from qfluentwidgets import SpinBox

from fluent_ui.visual import DATA_FONT, accent, colors
from services.i18n import t, bind_text, translated, i18n_engine
from fluent_ui import visual
from fluent_ui.components.number_box import CompactNumberBox
from fluent_ui.components.keycap_label import KeycapLabel
from fluent_ui.components.softframe import SoftframeSlider as Slider, paint_setting_surface
from fluent_ui.components.softframe import DisclosureButton, SectionHeading
from fluent_ui.components.interaction_controls import ModeSegment


def _ignore_wheel(widget):
    """Scrolling the page must never change a value the pointer happens to cross."""
    widget.wheelEvent = lambda event: event.ignore()
    return widget


class SettingRow(QWidget):
    """One labeled setting with its control on the trailing edge."""

    changed = Signal()

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        controls=getattr(self,'controls',None)
        return QSize(max(160,controls.minimumSize().width()+44 if controls else 160),86)

    def __init__(self, title, hint="", parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.setFont(visual.font())
        self.setMinimumHeight(86)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 20, 18)
        layout.setSpacing(14)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        self.title_label = translated(QLabel, title, self)
        self.title_label.setWordWrap(True)
        title_font = visual.font()
        title_font.setWeight(QFont.Medium)
        self.title_label.setFont(title_font)
        text_column.addWidget(self.title_label)
        self.hint_label = translated(KeycapLabel, hint, self)
        self.hint_label.setProperty("role", "hint")
        self.hint_label.setWordWrap(True)
        self.hint_label.setFont(visual.font('secondary'))
        self.hint_label.setVisible(bool(hint))
        text_column.addWidget(self.hint_label)
        layout.addLayout(text_column, stretch=1)

        self.controls = QHBoxLayout()
        self.controls.setContentsMargins(0, 0, 0, 0)
        self.controls.setSpacing(8)
        layout.addLayout(self.controls)

        self.rule = QFrame(self)
        self.rule.setFixedHeight(1)
        self.rule.setProperty("role", "rule")
        visual.theme.changed.connect(self.refresh_theme)
        self.refresh_theme()
        self.rule.setParent(self)
        self.rule.lower()
        self.rule.hide()

    def refresh_theme(self):
        self.rule.setStyleSheet(f"background: {colors()['border_soft']};")
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        from PySide6.QtCore import QRectF
        painter=QPainter(self)
        paint_setting_surface(painter,QRectF(self.rect()))
        if self.property('pending'):
            from PySide6.QtGui import QPen
            painter.setPen(QPen(QColor(visual.accent()),3))
            painter.drawLine(8,16,8,self.height()-16)

    def set_pending(self,pending):
        self.setProperty('pending',bool(pending));self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        text_width=340 if '\n' in self.hint_label.text() else 230
        direction = QBoxLayout.TopToBottom if self.width() < self.controls.minimumSize().width()+text_width else QBoxLayout.LeftToRight
        if self.layout().direction() != direction:
            self.layout().setDirection(direction)
            self.updateGeometry()
        self.rule.setGeometry(18, self.height() - 1, max(0,self.width()-32), 1)

    def add_control(self, widget):
        self.controls.addWidget(widget, 0, Qt.AlignRight | Qt.AlignVCenter)
        return widget

    def set_hint(self, text):
        self.hint_label.setText(text)
        self.hint_label.setVisible(bool(text))


class SwitchRow(SettingRow):
    def __init__(self, title, hint, key, value, parent=None):
        super().__init__(title, hint, parent)
        self.key = key
        self.switch = SwitchButton(self)
        self.switch.setChecked(bool(value))
        self.switch.setOnText("")
        self.switch.setOffText("")
        self.switch.checkedChanged.connect(lambda _: self.changed.emit())
        self.add_control(self.switch)

    def value(self):
        return bool(self.switch.isChecked())

    def set_value(self, value):
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(value))
        self.switch.blockSignals(False)


class ChoiceRow(SettingRow):
    def __init__(self, title, hint, key, value, options, parent=None):
        super().__init__(title, hint, parent)
        self.key = key
        self.options = list(options)
        self.combo = _ignore_wheel(ComboBox(self))
        self.combo.setMinimumWidth(150)
        self.combo.setMaximumWidth(320)
        self.combo.addItems([label if key=='language' else t(label) for _, label in self.options])
        self.combo.setMinimumWidth(min(320,self.combo.sizeHint().width()))
        i18n_engine.language_changed.connect(self.refresh_texts)
        self.combo.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.add_control(self.combo)
        self.set_value(value)

    def value(self):
        index = self.combo.currentIndex()
        return self.options[index][0] if 0 <= index < len(self.options) else None

    def set_value(self, value):
        self.combo.blockSignals(True)
        for index, (option, _) in enumerate(self.options):
            if option == value:
                self.combo.setCurrentIndex(index)
                break
        self.combo.blockSignals(False)

    def refresh_texts(self, *_):
        for index, (_, label) in enumerate(self.options):
            self.combo.setItemText(index, label if self.key=='language' else t(label))
        self.combo.setMinimumWidth(min(320,self.combo.sizeHint().width()))


class AccentRow(SettingRow):
    def __init__(self, value, parent=None):
        from services.i18n import t
        super().__init__(t('主题强调色'), '', parent)
        self.key = 'accent_color'
        self.color = QColor(value)
        self.rgb=QLabel(self);self.rgb.setProperty('role','data');self.add_control(self.rgb)
        from fluent_ui.presentation.swatch import ColorSwatchButton
        self.button = ColorSwatchButton(self)
        self.button.setFixedSize(48, 32)
        from fluent_ui.components.dialogs import _button_style
        self.button.setStyleSheet(_button_style())
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(40)
        self._preview_timer.timeout.connect(self.changed.emit)
        i18n_engine.language_changed.connect(self.refresh_texts)
        self.button.clicked.connect(self.choose_color)
        self.add_control(self.button)
        self.set_value(value)

    def value(self):
        return self.color.name()

    def set_value(self, value):
        self.color = QColor(value)
        self.button.setToolTip(t('选择颜色') + '  ' + self.color.name().upper())
        self.button.setAccessibleName(self.button.toolTip())
        self.rgb.setText(self.color.name().upper())
        self.rgb.setToolTip(self.color.name().upper())
        self.button.color=self.color;self.button.update()

    def refresh_texts(self, *_):
        self.set_value(self.value())

    def choose_color(self):
        from fluent_ui.components.accent_picker import AccentColorPicker
        previous = self.value()
        dialog = AccentColorPicker(self.color, self.window())
        self.picker = dialog
        dialog.setWindowModality(Qt.WindowModal)
        def preview(*_):
            self.set_value(dialog.color.name())
            if not self._preview_timer.isActive():
                self._preview_timer.start()
        def finish(accepted):
            self._preview_timer.stop()
            if not accepted:
                self.set_value(previous)
            self.changed.emit()
        dialog.colorChanged.connect(preview)
        dialog.accepted.connect(lambda: finish(True))
        dialog.rejected.connect(lambda: finish(False))
        # Color dialog belongs to Settings and stays on the same screen.
        from fluent_ui.components.dialogs import center_on_owner, DialogTitleDrag
        if hasattr(dialog, 'titleLabel'):
            bind_text(dialog.titleLabel, '主题强调色')
            dialog._title_drag = DialogTitleDrag(dialog.titleLabel)
        dialog.show()
        center_on_owner(dialog, self.window())


class RangeRow(SettingRow):
    def __init__(self, title, hint, key, value, minimum, maximum, step=1, parent=None, *, count_only=False, unit=""):
        super().__init__(title, hint, parent)
        self.key = key
        self.default_value = None
        self.control_group = QWidget(self)
        self.range_controls = QHBoxLayout(self.control_group)
        self.range_controls.setContentsMargins(0, 0, 0, 0)
        self.range_controls.setSpacing(8)
        self.reset_button = TransparentToolButton(FIF.RESTORE, self)
        self.reset_button.setFixedSize(32, 32)
        self.reset_button.setIconSize(QSize(24, 24))
        bind_text(self.reset_button, '恢复默认', 'setToolTip')
        bind_text(self.reset_button, '恢复默认', 'setAccessibleName')
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self.restore_default)
        self.range_controls.addWidget(self.reset_button)
        self.spin = CompactNumberBox(self)
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.slider = _ignore_wheel(Slider(Qt.Horizontal, self))
        self.slider.setRange(minimum, maximum)
        self.slider.setSingleStep(step)
        self.slider.setMinimumWidth(180)
        self.slider.setMaximumWidth(260)
        self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.range_controls.addWidget(self.slider, 1)
        self.slider.setVisible(not count_only)
        if unit:
            number = QWidget(self)
            number_layout = QHBoxLayout(number)
            number_layout.setContentsMargins(0, 0, 0, 0)
            number_layout.setSpacing(4)
            number_layout.addWidget(self.spin)
            self.unit_label = translated(QLabel, unit, self)
            self.unit_label.setFont(visual.font('secondary'))
            number_layout.addWidget(self.unit_label)
            self.range_controls.addWidget(number)
        else:
            self.range_controls.addWidget(self.spin)
        self.add_control(self.control_group)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(lambda _: self.changed.emit())
        self.spin.valueChanged.connect(self._sync_default)
        self.set_value(value)

    def set_default(self, value):
        self.default_value = int(value)
        self._sync_default()

    def _sync_default(self, *_):
        self.reset_button.setEnabled(self.default_value is not None and self.value() != self.default_value)

    def restore_default(self):
        if self.default_value is not None:
            self.spin.setValue(self.default_value)

    def value(self):
        return int(self.spin.value())

    def set_value(self, value):
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        self.spin.setValue(int(value))
        self.slider.setValue(int(value))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)
        self._sync_default()


class ModeRow(SettingRow):
    def __init__(self, title, hint, key, value, options, parent=None):
        super().__init__(title, hint, parent)
        self.key, self.options = key, list(options)
        self.segment = ModeSegment([(str(k), t(label)) for k, label in options], self)
        self.add_control(self.segment)
        self.set_value(value)
        self.segment.currentItemChanged.connect(lambda _: self.changed.emit())
        i18n_engine.language_changed.connect(self.refresh_texts)

    def value(self):
        return next((k for k, _ in self.options if str(k) == self.segment.currentRouteKey()), None)

    def set_value(self, value):
        self.segment.blockSignals(True)
        self.segment.setCurrentItem(str(value))
        self.segment.blockSignals(False)

    def refresh_texts(self, *_):
        for key, label in self.options:
            item = self.segment.items[str(key)]
            item.setText(t(label))
            item.setToolTip(t(label))
            item.updateGeometry()
        self.segment.layout().invalidate()
        self.segment.updateGeometry()


class SpatialRow(SettingRow):
    def __init__(self, title, hint, key, value, parent=None):
        super().__init__(title, hint, parent)
        self.key, self._value = key, value
        from fluent_ui.presentation.dock_picker import DockPositionPicker
        host=DockPositionPicker(self);self.buttons=host.buttons
        for name,label in [('top','顶部'),('left','左侧'),('right','右侧'),('bottom','底部')]:
            button=self.buttons[name]
            bind_text(button, label, 'setToolTip')
            bind_text(button, label, 'setAccessibleName')
            button.clicked.connect(lambda checked=False, name=name: self._choose(name))
        self.add_control(host)
        self.set_value(value)

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        for name, button in self.buttons.items():
            button.setChecked(name == value)

    def _choose(self, value):
        self.set_value(value)
        self.changed.emit()


class HotkeyEditor(QLineEdit):
    """Native text field; capture and validation remain in HotkeyRow."""
    pass


class HotkeyRow(SettingRow):
    def __init__(self, title, hint, key, value, parent=None):
        super().__init__(title, hint, parent)
        self.key = key
        self.editor = _ignore_wheel(HotkeyEditor(value or "", self))
        bind_text(self.editor, t("点击此处并按下快捷键"), 'setPlaceholderText')
        self.editor.setReadOnly(True)
        self.editor.setFixedSize(200,36)
        self.editor.setFont(visual.font('data'))
        self.editor.setProperty('typography', 'data')
        self.editor.installEventFilter(self)
        self.add_control(self.editor)
        clear = translated(PushButton, "清除", self)
        clear.clicked.connect(lambda: self._set(""))
        self.add_control(clear)
        self.status_label = KeycapLabel('', self)
        self.status_label.setProperty('role', 'hint')
        self.status_label.setWordWrap(True)
        self.status_label.setFont(visual.font('secondary'))
        self.layout().itemAt(0).layout().addWidget(self.status_label)
        self.status_label.hide()

    def set_status(self, text, *, error=False):
        """Registration feedback must not replace the permanent usage hint."""
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))
        self.status_label.setStyleSheet('color: '+visual.colors()['danger']+';' if error else '')

    def _set(self, value):
        self.editor.setText(value)
        self.changed.emit()

    def value(self):
        return self.editor.text().strip()

    def set_value(self, value):
        self.editor.setText(value or "")

    def eventFilter(self, obj, event):
        from PySide6.QtGui import QKeySequence
        if obj is self.editor and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                event.accept()
                return True
            if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta,
                       Qt.Key_Super_L, Qt.Key_Super_R):
                return True
            parts = []
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                parts.append("ctrl")
            if modifiers & Qt.AltModifier:
                parts.append("alt")
            if modifiers & Qt.ShiftModifier:
                parts.append("shift")
            if modifiers & Qt.MetaModifier:
                parts.append("win")
            text = QKeySequence(key).toString().lower()
            if text:
                parts.append(text)
                self._set("+".join(parts))
            return True
        return super().eventFilter(obj, event)


class ActionRow(SettingRow):
    def __init__(self, title, hint, actions, parent=None):
        super().__init__(title, hint, parent)
        from fluent_ui.components.dialogs import _button_style
        for item in actions:
            text, callback = item[:2]
            button = translated(PushButton, text, self)
            button.setMinimumWidth(100)
            button.setStyleSheet(_button_style())
            button.clicked.connect(callback)
            self.add_control(button)


class SuzuExportRow(ActionRow):
    """Keep both export actions together, below the copy only when needed."""
    def resizeEvent(self,event):
        QWidget.resizeEvent(self,event)
        layout=self.layout()
        text_width=max(self.title_label.fontMetrics().horizontalAdvance(self.title_label.text()),
                       *(self.hint_label.fontMetrics().horizontalAdvance(line) for line in self.hint_label.text().splitlines()))
        margins=layout.contentsMargins()
        threshold=text_width+self.controls.minimumSize().width()+layout.spacing()+margins.left()+margins.right()
        direction=QBoxLayout.TopToBottom if self.width()<threshold else QBoxLayout.LeftToRight
        self.controls.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        if layout.direction()!=direction:
            layout.setDirection(direction);layout.invalidate()
        height=layout.heightForWidth(self.width())
        self.setMinimumHeight(max(86,height))
        self.updateGeometry()


class FullPathRow(SettingRow):
    """Full-width selectable directory below its title, without elision."""
    def __init__(self,title,hint,value,parent=None):
        super().__init__(title,hint,parent)
        self.layout().setDirection(QBoxLayout.TopToBottom)
        self.value_label=QLabel(str(value),self);self.value_label.setWordWrap(True)
        self.value_label.setTextFormat(Qt.PlainText)
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.value_label.setFont(visual.font('data'))
        self.layout().addWidget(self.value_label)
    def set_value(self,value):self.value_label.setText(str(value))
    def value(self):return self.value_label.text()
    def resizeEvent(self,event):QWidget.resizeEvent(self,event)


class BackupStatusRow(ActionRow):
    """Existing card/buttons, with actions wrapping inside the same card."""
    def __init__(self,title,hint,actions,parent=None):
        super().__init__(title,hint,actions,parent)
        self.layout().setDirection(QBoxLayout.TopToBottom)
        self.buttons=[]
        while self.controls.count():
            widget=self.controls.takeAt(0).widget()
            if widget is not None:self.buttons.append(widget)
        self.action_host=QWidget(self);self.action_grid=QGridLayout(self.action_host)
        self.action_grid.setContentsMargins(0,0,0,0);self.action_grid.setSpacing(8)
        self.action_grid.setAlignment(Qt.AlignRight);self.controls.addWidget(self.action_host)
        self.columns=0;self._arrange()
        i18n_engine.language_changed.connect(self._arrange)
    def minimumSizeHint(self):return QSize(260,86)
    def _arrange(self):
        widths=[max(b.minimumWidth(),b.sizeHint().width()) for b in self.buttons]
        available=max(1,self.width()-44)
        columns=4 if sum(widths)+24<=available else 2 if 2*max(widths)+8<=available else 1
        if columns!=self.columns:
            while self.action_grid.count():self.action_grid.takeAt(0)
            for i,button in enumerate(self.buttons):
                button.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Preferred)
                self.action_grid.addWidget(button,i//columns,i%columns)
            self.columns=columns
        self.layout().invalidate();self.updateGeometry()
    def resizeEvent(self,event):
        QWidget.resizeEvent(self,event);self._arrange()


class BackupPathRow(FullPathRow):
    """Selectable full path and existing controls; stages one config key."""
    def __init__(self,title,hint,value,default_path,choose,parent=None):
        self.stored_path=str(value or '');self.default_path=str(default_path)
        super().__init__(title,hint,self.stored_path or self.default_path,parent)
        self.reset_button=TransparentToolButton(FIF.RESTORE,self)
        self.reset_button.setFixedSize(32,32);self.reset_button.setIconSize(QSize(24,24))
        bind_text(self.reset_button,'恢复默认','setToolTip')
        self.reset_button.clicked.connect(self._reset)
        self.choose_button=translated(PushButton,'选择文件夹…',self);self.choose_button.clicked.connect(choose)
        self.add_control(self.reset_button);self.add_control(self.choose_button)
        self.reset_button.setEnabled(bool(self.stored_path))
    def _reset(self):self.set_value('');self.changed.emit()
    def set_value(self,value):
        self.stored_path=str(value or '');super().set_value(self.stored_path or self.default_path)
        self.reset_button.setEnabled(bool(self.stored_path))
    def value(self):return self.stored_path


class _InfoValueLabel(QLabel):
    """Reserve space using the full value, even when its visible text is elided."""

    def __init__(self, value, parent):
        super().__init__(parent)
        self._full_value = str(value)
        self.setWordWrap(False)
        self.setMaximumWidth(260)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.set_value(value)

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(min(260, metrics.horizontalAdvance(self._full_value)), metrics.height())

    def minimumSizeHint(self):
        hint = self.sizeHint()
        hint.setWidth(min(150, hint.width()))
        return hint

    def set_value(self, value):
        self._full_value = str(value)
        self.setToolTip(self._full_value)
        self._elide()
        self.updateGeometry()

    def _elide(self):
        self.setText(self.fontMetrics().elidedText(self._full_value, Qt.ElideMiddle, self.contentsRect().width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


class InfoRow(SettingRow):
    """Read-only value display in the data typeface."""

    def __init__(self, title, hint, value="", parent=None):
        super().__init__(title, hint, parent)
        self.value_label = _InfoValueLabel(value, self)
        mono = QFont(DATA_FONT.split(",")[0].strip())
        mono.setPixelSize(11)
        self.value_label.setFont(mono)
        self.value_label.setProperty("role", "data")
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.add_control(self.value_label)

    def set_value(self, value):
        self.value_label.set_value(value)


class _SoundField(QObject):
    """Adapt either field of one card to SettingsCenter's existing key contract."""
    changed = Signal()

    def __init__(self, row, name):
        super().__init__(row)
        self.row, self.name, self.pending = row, name, False

    def value(self):
        return self.row.switch.isChecked() if self.name == 'enabled' else self.row.path

    def set_value(self, value):
        if self.name == 'enabled':
            self.row.switch.blockSignals(True)
            self.row.switch.setChecked(bool(value))
            self.row.switch.blockSignals(False)
        else:
            self.row.path = str(value or '')
            self.row.refresh_file()

    def set_pending(self, pending):
        self.pending = bool(pending)
        self.row.set_pending(self.row.enabled_field.pending or self.row.path_field.pending)


class _SoundSourceLabel(_InfoValueLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and self.clickable:
            self.clicked.emit()

    def keyPressEvent(self, event):
        if self.clickable and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class SoundEventRow(SettingRow):
    """Two related lines inside the existing Softframe setting surface."""

    def __init__(self, title, hint, enabled, path, choose, preview, restore, parent=None):
        super().__init__(title, hint, parent)
        self.path = str(path or '')
        self.previewing = False
        self.enabled_field = _SoundField(self, 'enabled')
        self.path_field = _SoundField(self, 'path')
        self.switch = SwitchButton(self)
        self.switch.setOnText(''); self.switch.setOffText('')
        self.switch.setChecked(bool(enabled))
        self.switch.checkedChanged.connect(lambda _: self.enabled_field.changed.emit())
        self.add_control(self.switch)

        outer = self.layout()
        text = outer.takeAt(0).layout()
        controls = outer.takeAt(0).layout()
        outer.setDirection(QBoxLayout.TopToBottom)
        outer.setSpacing(10)
        header = QHBoxLayout(); header.setSpacing(14)
        header.addLayout(text, 1); header.addLayout(controls)
        outer.addLayout(header)
        self.source_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.source_layout.setSpacing(8)
        self.file_label = _SoundSourceLabel('', self)
        self.file_label.setTextFormat(Qt.PlainText)
        self.file_label.setFont(visual.font('secondary'))
        self.file_label.setProperty('role', 'hint')
        self.file_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.file_label.setMaximumWidth(16777215)
        self.file_label.setMinimumWidth(0)
        self.file_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.file_label.clicked.connect(self._toggle_path)
        self.source_layout.addWidget(self.file_label, 1)
        action_host = QWidget(self)
        self.actions = QHBoxLayout(action_host)
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(8)
        self.choose_button = translated(PushButton, '选择文件…', self)
        self.choose_button.setMinimumWidth(100)
        self.choose_button.clicked.connect(choose)
        from fluent_ui.components.sound_preview_button import SoundPreviewButton
        self.preview_button = SoundPreviewButton(self)
        self.reset_button = TransparentToolButton(FIF.RESTORE, self)
        self.reset_button.setFixedSize(32,32);self.reset_button.setIconSize(QSize(24,24))
        self.actions.addWidget(self.reset_button)
        self.actions.addWidget(self.preview_button)
        self.actions.addWidget(self.choose_button)
        self.preview_button.clicked.connect(preview)
        self.reset_button.clicked.connect(restore)
        bind_text(self.reset_button, '恢复默认音效', 'setToolTip')
        bind_text(self.reset_button, '恢复默认音效', 'setAccessibleName')
        self.source_layout.addWidget(action_host, 0, Qt.AlignRight)
        outer.addLayout(self.source_layout)
        self.full_path_label = QLabel(self)
        self.full_path_label.setTextFormat(Qt.PlainText)
        self.full_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.full_path_label.setWordWrap(True)
        self.full_path_label.setFont(visual.font('data'))
        self.full_path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        outer.addWidget(self.full_path_label)
        self.full_path_label.hide()
        i18n_engine.language_changed.connect(self.refresh_file)
        self.set_previewing(False)
        self.refresh_file()

    def refresh_file(self, *_):
        import ntpath
        source = t('自定义：{name}').format(name=ntpath.basename(self.path)) if self.path else t('内置音效')
        self.file_label.set_value(source)
        self.file_label.setToolTip(self.path or t('内置音效'))
        self.file_label.setAccessibleName(source)
        self.file_label.setAccessibleDescription(t('查看路径') if self.path else '')
        self.file_label.clickable = bool(self.path)
        self.file_label.setCursor(Qt.PointingHandCursor if self.path else Qt.ArrowCursor)
        self.file_label.setFocusPolicy(Qt.StrongFocus if self.path else Qt.NoFocus)
        self.reset_button.setEnabled(bool(self.path))
        self.full_path_label.setText(self.path)
        if not self.path:
            self.full_path_label.hide()
        self.updateGeometry()

    def _toggle_path(self):
        self.full_path_label.setVisible(bool(self.path) and self.full_path_label.isHidden())
        self.updateGeometry()

    def set_previewing(self, playing):
        self.previewing = bool(playing)
        self.preview_button.set_playing(playing)
        label = '停止试听' if playing else '试听'
        bind_text(self.preview_button, label, 'setToolTip')
        bind_text(self.preview_button, label, 'setAccessibleName')

    def resizeEvent(self, event):
        QWidget.resizeEvent(self, event)
        margins = self.layout().contentsMargins()
        available = self.width()-margins.left()-margins.right()
        # Keep actions together; only stack the source above them when the
        # translated file button would otherwise leave no useful source text.
        direction = QBoxLayout.TopToBottom if available < self.actions.minimumSize().width()+100 else QBoxLayout.LeftToRight
        if self.source_layout.direction() != direction:
            self.source_layout.setDirection(direction)
            self.layout().invalidate()
        self.updateGeometry()


class SettingSection(QWidget):
    """A titled group of rows with an explicit collapse control."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsGroup")
        self.setAttribute(Qt.WA_StyledBackground)
        from PySide6.QtWidgets import QVBoxLayout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(4)

        self.header = SectionHeading(self)
        self.header.setObjectName("SettingsSectionHead")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 4, 0, 4)
        self.toggle = DisclosureButton(self.header)
        bind_text(self.toggle, title, 'setAccessibleName')
        self.toggle.clicked.connect(self.toggle_collapsed)
        self.title_label = translated(KeycapLabel, title, self.header)
        self.title_label.setObjectName("SettingsSectionTitle")
        self.title_label.setFont(visual.font('section_title'))
        self.title_label.setProperty('typography','section_title')
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle)
        outer.addWidget(self.header)

        self.body = QWidget(self)
        self.body.setObjectName('SettingsSectionBody')
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        outer.addWidget(self.body)
        self._collapsed = False
        self._motion = QPropertyAnimation(self.body,b'maximumHeight',self)
        self._motion.setDuration(visual.MOTION.expand)
        self._motion.setEasingCurve(visual.MOTION.easing)
        self._motion.finished.connect(self._finish_collapse)

    def add_row(self, row):
        self.body_layout.addWidget(row)
        return row

    def sections_key(self):
        return self.title_label.text()

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self._motion.stop()
        start = 0 if self.body.isHidden() else self.body.height()
        self.body.show()
        target = max(self.body_layout.sizeHint().height(),self.body_layout.heightForWidth(self.body.width()))
        self._motion.setStartValue(start)
        self._motion.setEndValue(0 if self._collapsed else target)
        visual.start_animation(self._motion, visual.MOTION.expand)
        self.toggle.set_expanded(not self._collapsed)

    def _finish_collapse(self):
        self.body.setVisible(not self._collapsed)
        if not self._collapsed:
            self.body.setMaximumHeight(16777215)

    def is_collapsed(self):
        return self._collapsed


def apply_row_theme(root):
    # Rows subscribe directly to UiTheme; no palette traversal is required.
    pass
