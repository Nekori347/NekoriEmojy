"""Compatibility surface for the Settings Center.

The real implementation lives in ``settings_center``. This module keeps the
historical import path used by the main window and by tests.
"""
from fluent_ui.views.settings_center import PREVIEW_KEYS, SettingsCenter
from fluent_ui.components.setting_rows import RangeRow, SettingRow


class SettingInterface(SettingsCenter):
    """Settings page bound to the main window stack."""

    def __init__(self, config_service, parent=None, storage=None):
        # The main window historically passed (config, parent); the library
        # actions need the storage facade, which we take from the window.
        if storage is None and parent is not None:
            storage = getattr(parent, "storage", None)
        super().__init__(config_service, storage, parent)


def disable_wheel_scroll_adjustment(widget):
    """Kept for callers that neutralise wheel input on a whole subtree."""
    from PySide6.QtWidgets import QAbstractSlider, QAbstractSpinBox, QComboBox, QScrollBar

    targets = (QAbstractSpinBox, QAbstractSlider, QComboBox)
    if isinstance(widget, targets) and not isinstance(widget, QScrollBar):
        widget.wheelEvent = lambda event: event.ignore()
    for child in widget.findChildren(object):
        if isinstance(child, targets) and not isinstance(child, QScrollBar):
            child.wheelEvent = lambda event: event.ignore()


# Historical name for the sliders + spin box row.
SpinBoxRangeSettingCard = RangeRow

__all__ = ["SettingInterface", "SettingsCenter", "PREVIEW_KEYS",
           "RangeRow", "SettingRow", "SpinBoxRangeSettingCard",
           "disable_wheel_scroll_adjustment"]
