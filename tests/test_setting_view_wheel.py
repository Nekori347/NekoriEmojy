import unittest

from PySide6.QtWidgets import QApplication, QWidget, QScrollBar
from PySide6.QtCore import Qt, QPointF, QPoint, QCoreApplication
from PySide6.QtGui import QWheelEvent, QKeyEvent
from qfluentwidgets import SpinBox, Slider, ComboBox

from services.config import ConfigService
from fluent_ui.views.setting_view import (
    SettingInterface,
    RangeRow,
    disable_wheel_scroll_adjustment,
)
from fluent_ui.views.exchange_view import ExchangeInterface
from fluent_ui.views.qq_scan_view import QQScanInterface
from fluent_ui.views.tg_sticker_view import TGStickerInterface


def _simulate_wheel(widget, angle_delta_y=-120):
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollUpdate,
        False,
    )
    event.ignore()
    widget.wheelEvent(event)
    return event.isAccepted()


class TestSettingWheelDisabled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def test_range_row_wheel_disabled(self):
        row = RangeRow("Test Title", "hint", "test_key", 50, 10, 100)
        self.assertEqual(row.spin.value(), 50)
        self.assertEqual(row.slider.value(), 50)

        accepted = _simulate_wheel(row.spin, angle_delta_y=-120)
        self.assertFalse(accepted, "SpinBox 不应接受滚轮事件")
        self.assertEqual(row.spin.value(), 50, "SpinBox 数值不应被滚轮改变")

        accepted = _simulate_wheel(row.slider, angle_delta_y=-120)
        self.assertFalse(accepted, "Slider 不应接受滚轮事件")
        self.assertEqual(row.slider.value(), 50, "Slider 数值不应被滚轮改变")

        # 键盘上下键仍可调节，说明只屏蔽了滚轮而非整体输入
        up_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
        QCoreApplication.sendEvent(row.spin, up_event)
        self.assertEqual(row.spin.value(), 51, "键盘上下键应依然能调节 SpinBox 数值")

    def test_setting_interface_all_inputs_wheel_disabled(self):
        interface = SettingInterface(ConfigService())

        from PySide6.QtWidgets import QAbstractSpinBox, QAbstractSlider, QComboBox
        target_types = (QAbstractSpinBox, QAbstractSlider, QComboBox, SpinBox, Slider, ComboBox)

        inputs = []
        for page in range(interface.nav.count()):
            interface._select_page(page)
            for tab in range(len(interface._tabs)):
                interface._show_tab(tab)
                inputs.extend(
                    child for child in interface.findChildren(QWidget)
                    if isinstance(child, target_types) and not isinstance(child, QScrollBar)
                )
        self.assertGreaterEqual(len(inputs), 16)

        for widget in inputs:
            old = (widget.value() if isinstance(widget, (SpinBox, Slider, QAbstractSpinBox, QAbstractSlider))
                   else widget.currentIndex())
            accepted = _simulate_wheel(widget, -120)
            self.assertFalse(accepted, f"{type(widget).__name__} 不应接受滚轮事件")
            new = (widget.value() if isinstance(widget, (SpinBox, Slider, QAbstractSpinBox, QAbstractSlider))
                   else widget.currentIndex())
            self.assertEqual(new, old, f"{type(widget).__name__} 数值不应被滚轮改变")

    def test_disable_wheel_scroll_adjustment_helper(self):
        container = QWidget()
        spin = SpinBox(container)
        spin.setRange(0, 10)
        spin.setValue(5)
        disable_wheel_scroll_adjustment(container)
        accepted = _simulate_wheel(spin, -120)
        self.assertFalse(accepted)
        self.assertEqual(spin.value(), 5)

    def test_secondary_setting_views_wheel_disabled(self):
        qq_view = QQScanInterface()
        tg_view = TGStickerInterface()
        exchange_view = ExchangeInterface()
        for view in [qq_view, tg_view, exchange_view]:
            from PySide6.QtWidgets import QAbstractSpinBox, QAbstractSlider, QComboBox
            target_types = (QAbstractSpinBox, QAbstractSlider, QComboBox, SpinBox, Slider, ComboBox)

            for child in view.findChildren(QWidget):
                if isinstance(child, target_types) and not isinstance(child, QScrollBar):
                    accepted = _simulate_wheel(child, -120)
                    self.assertFalse(accepted, f"{type(view).__name__} 中的 {type(child).__name__} 不应接受滚轮事件")


if __name__ == "__main__":
    unittest.main()
