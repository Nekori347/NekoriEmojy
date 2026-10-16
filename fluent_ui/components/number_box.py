"""One numeric field with a vertical, independently hit-tested stepper."""
from PySide6.QtCore import Qt, Signal, QEvent, QSize
from PySide6.QtGui import QIntValidator, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLineEdit
from fluent_ui.components.controls import TransparentToolButton
from fluent_ui.icons import Icon as FIF
from fluent_ui import visual


class CompactNumberBox(QWidget):
    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum, self._maximum, self._step, self._value = 0, 100, 1, 0
        self.setFixedSize(92, 32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)
        self.editor = QLineEdit('0', self)
        self.editor.setAlignment(Qt.AlignRight)
        self.editor.setFont(visual.font('data'))
        self.editor.setProperty('typography', 'data')
        self.editor.setValidator(QIntValidator(0, 100, self))
        self.editor.setMinimumWidth(0)
        self.editor.installEventFilter(self)
        layout.addWidget(self.editor, 1)
        self.setFocusProxy(self.editor)
        self.setFocusPolicy(Qt.StrongFocus)
        steps = QVBoxLayout()
        steps.setContentsMargins(0, 4, 0, 4)
        steps.setSpacing(0)
        self.up_button = TransparentToolButton(FIF.UP, self)
        self.down_button = TransparentToolButton(FIF.DOWN, self)
        for button, delta in ((self.up_button, 1), (self.down_button, -1)):
            button.setFixedSize(18, 12)
            button.setIconSize(QSize(8, 8))
            button.setFocusPolicy(Qt.NoFocus)
            button.setAutoRepeat(True)
            button.clicked.connect(lambda checked=False, delta=delta: self.stepBy(delta))
            steps.addWidget(button)
        layout.addLayout(steps)
        self.editor.textEdited.connect(self._edited)
        self.editor.editingFinished.connect(self._commit)
        visual.theme.changed.connect(self.refresh_theme)
        self.refresh_theme()
        self._sync()

    def refresh_theme(self):
        c = visual.colors()
        self.setStyleSheet(f'QLineEdit {{ color: {c["text"]}; background: transparent; border: none; padding: 2px; font-family: "{visual.DATA_FONT}"; font-size: 12px; }} QToolButton {{ border: none; background: transparent; padding: 0; }}')
        self.update()

    def paintEvent(self, event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c=visual.colors()
        painter.setOpacity(1 if self.isEnabled() else .4)
        painter.setPen(QPen(QColor(c['accent'] if self.editor.hasFocus() else c['border']),1))
        for x,delta in ((1,4),(self.width()-2,-4)):
            painter.drawLine(x,4,x,self.height()-5)
            painter.drawLine(x,4,x+delta,4)
            painter.drawLine(x,self.height()-5,x+delta,self.height()-5)

    def setRange(self, minimum, maximum):
        self._minimum, self._maximum = int(minimum), int(maximum)
        self.editor.validator().setRange(self._minimum, self._maximum)
        self.setValue(self._value)

    def setSingleStep(self, step):
        self._step = max(1, int(step))

    def value(self):
        return self._value

    def minimum(self):
        return self._minimum

    def maximum(self):
        return self._maximum

    def setValue(self, value):
        value = max(self._minimum, min(self._maximum, int(value)))
        changed = value != self._value
        self._value = value
        self._sync()
        if changed:
            self.valueChanged.emit(value)

    def _sync(self):
        self.editor.setText(str(self._value))
        self.up_button.setEnabled(self._value < self._maximum)
        self.down_button.setEnabled(self._value > self._minimum)

    def _edited(self, text):
        if self.editor.hasAcceptableInput():
            value = int(text)
            if value != self._value:
                self._value = value
                self.up_button.setEnabled(value < self._maximum)
                self.down_button.setEnabled(value > self._minimum)
                self.valueChanged.emit(value)

    def _commit(self):
        try:
            self.setValue(int(self.editor.text()))
        except ValueError:
            self._sync()

    def stepBy(self, steps):
        self._commit()
        self.setValue(self._value + steps * self._step)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.FocusIn, QEvent.FocusOut):
            self.update()
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.stepBy(1 if event.key() == Qt.Key_Up else -1)
            return True
        if event.type() == QEvent.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.stepBy(1 if event.key() == Qt.Key_Up else -1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        event.ignore()
