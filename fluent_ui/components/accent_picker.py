"""HSV editor: local drawing is immediate; the owner throttles theme preview."""
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QGridLayout, QVBoxLayout
from fluent_ui.components.softframe import SoftframeSlider as Slider
from fluent_ui.components.dialogs import NekoriDialog
from fluent_ui.components.number_box import CompactNumberBox
from fluent_ui import visual
from services.i18n import t, translated


class HSSpectrum(QWidget):
    changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hue, self.saturation, self.value = 0, 1.0, 1.0
        self.setMinimumSize(260, 170)
        self.setMouseTracking(True)

    def selection_rect(self):
        return self.rect().adjusted(7, 7, -7, -7)

    def selection_point(self):
        rect = self.selection_rect()
        return QPointF(rect.left()+self.hue/359*(rect.width()-1),
                       rect.top()+(1-self.saturation)*(rect.height()-1))

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.selection_rect()
        hue = QLinearGradient(rect.topLeft(), rect.topRight())
        for index in range(7):
            hue.setColorAt(index/6,QColor.fromHsv((index*60)%360,255,round(self.value*255)))
        painter.fillRect(rect, hue)
        saturation = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gray = round(self.value*255)
        saturation.setColorAt(0,QColor(gray,gray,gray,0))
        saturation.setColorAt(1,QColor(gray,gray,gray,255))
        painter.fillRect(rect,saturation)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor('black'),3))
        painter.drawEllipse(self.selection_point(),5,5)
        painter.setPen(QPen(QColor('white'),1.5))
        painter.drawEllipse(self.selection_point(),5,5)

    def _pick(self, position):
        rect = self.selection_rect()
        self.hue = round(359*max(0.,min(1.,(position.x()-rect.left())/max(1,rect.width()-1))))
        self.saturation = 1-max(0.,min(1.,(position.y()-rect.top())/max(1,rect.height()-1)))
        self.update()
        self.changed.emit(self.hue,self.saturation)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pick(event.position())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._pick(event.position())


class ColorSwatch(QWidget):
    """A centered color surface with its entire border inside stable bounds."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor()
        self.setFixedSize(72,36)

    def set_color(self, color):
        self.color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(QColor(visual.colors()['border']),1))
        painter.setBrush(self.color)
        painter.drawRect(self.rect().adjusted(4,4,-5,-5))


class AccentColorPicker(NekoriDialog):
    colorChanged = Signal(QColor)

    def __init__(self, color, parent=None):
        super().__init__(parent, t('主题强调色'))
        self.setWindowModality(Qt.WindowModal)
        self.previous = QColor(color)
        self.color = QColor(color)
        self.spectrum = HSSpectrum(self)
        self.body.addWidget(self.spectrum)
        self.hex_editor = QLineEdit(self)
        self.hex_editor.setProperty('typography','data')
        self.hex_editor.setFont(visual.font('data'))
        self.hex_editor.setMaxLength(7)
        self.hex_editor.setPlaceholderText('#RRGGBB')
        self.hsv_sliders, self.hsv_numbers = [], []
        grid = QGridLayout()
        for index, (label, maximum) in enumerate((('H', 359), ('S', 100), ('V', 100))):
            caption=QLabel(label,self)
            caption.setProperty('typography','data')
            caption.setFont(visual.font('data'))
            grid.addWidget(caption, index, 0)
            slider = Slider(Qt.Horizontal, self)
            slider.setRange(0, maximum)
            slider.wheelEvent = lambda event: event.ignore()
            number = CompactNumberBox(self)
            number.setRange(0, maximum)
            grid.addWidget(slider, index, 1)
            grid.addWidget(number, index, 2)
            self.hsv_sliders.append(slider)
            self.hsv_numbers.append(number)
            slider.valueChanged.connect(lambda value, i=index: self._hsv_changed(i, value))
            number.valueChanged.connect(lambda value, i=index: self._hsv_changed(i, value))
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)
        hex_row = QHBoxLayout()
        hex_row.addWidget(QLabel('HEX',self))
        hex_row.addWidget(self.hex_editor,1)
        self.body.addLayout(hex_row)
        comparison = QHBoxLayout()
        self.previous_swatch = ColorSwatch(self)
        self.current_swatch = ColorSwatch(self)
        for label, swatch in (('原颜色',self.previous_swatch),('当前颜色',self.current_swatch)):
            group = QVBoxLayout()
            title = translated(QLabel,label,self)
            title.setAlignment(Qt.AlignCenter)
            group.addWidget(title,0,Qt.AlignHCenter)
            group.addWidget(swatch,0,Qt.AlignHCenter)
            comparison.addLayout(group,1)
        self.body.addLayout(comparison)
        self.setMinimumWidth(420)
        self.resize(520,500)

        self.spectrum.changed.connect(self._spectrum_changed)
        self.hex_editor.textEdited.connect(self._hex_changed)
        self.add_button('恢复默认', on_click=lambda: self.set_color(QColor(visual.DEFAULT_ACCENT)))
        self.add_button('取消', on_click=self.reject)
        self.add_button('确定', role='primary', on_click=self.accept)
        self.set_color(self.color, emit=False)

    def set_color(self, color, *, emit=True, hsv=None):
        if not color.isValid():
            return
        self.color = QColor(color)
        h, s, v, _ = color.getHsvF()
        values = hsv or (max(0, color.hsvHue()), round(s*100), round(v*100))
        self._hsv = list(values)
        for widgets in (self.hsv_sliders, self.hsv_numbers):
            for widget, value in zip(widgets, values):
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)
        self.spectrum.hue, self.spectrum.saturation, self.spectrum.value = values[0], values[1]/100, values[2]/100
        self.spectrum.update()
        self.hex_editor.setText(color.name().upper())
        self.previous_swatch.set_color(self.previous)
        self.current_swatch.set_color(color)
        if emit:
            self.colorChanged.emit(self.color)

    def _hsv_changed(self, index, value):
        values = list(self._hsv)
        values[index] = value
        self.set_color(QColor.fromHsv(values[0], round(values[1]*2.55), round(values[2]*2.55)), hsv=values)

    def _spectrum_changed(self, hue, saturation):
        values = [round(hue), round(saturation*100), self._hsv[2]]
        self.set_color(QColor.fromHsv(values[0], round(values[1]*2.55), round(values[2]*2.55)), hsv=values)

    def _hex_changed(self, text):
        if len(text.lstrip('#')) == 6:
            self.set_color(QColor('#'+text.lstrip('#')))
