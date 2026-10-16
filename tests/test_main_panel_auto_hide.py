import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt

from fluent_ui.views.gallery_view import GalleryInterface


class MainPanelAutoHideTests(unittest.TestCase):
    def test_select_and_manage_clicks_do_not_start_send(self):
        cases = [('normal', Qt.NoModifier, 'select'), ('manage', Qt.NoModifier, 'send'),
                 ('normal', Qt.ControlModifier, 'send'), ('normal', Qt.ShiftModifier, 'send')]
        for mode, modifiers, click_action in cases:
            with self.subTest(mode=mode, modifiers=modifiers, click_action=click_action):
                config = Mock()
                config.get.side_effect = lambda key, default=None: click_action if key == 'gallery_click_action' else default
                view = SimpleNamespace(config=config, mode=mode, _shift_anchor='previous',
                    _shift_touched=set(), _last_clicked_key=None, _select_single=Mock(),
                    _toggle_selection=Mock(), _extend_shift_selection=Mock(), use_resource=Mock())
                GalleryInterface.on_image_clicked(view, 'emoji.gif', modifiers)
                view.use_resource.assert_not_called()

    def test_hide_preserves_position_and_cancels_preview(self):
        from fluent_ui.main_window import MainWindow
        window = SimpleNamespace(
            clear_transient_button_states=Mock(), gallery_interface=Mock(), hide=Mock()
        )
        MainWindow._hide_after_paste(window)
        window.gallery_interface.save_scroll_position.assert_called_once()
        window.gallery_interface.preview_controller.cancel.assert_called_once()
        window.hide.assert_called_once()

    def test_setting_waits_for_explicit_save(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import tempfile
        from PySide6.QtWidgets import QApplication
        from fluent_ui.views.setting_view import SettingInterface
        app = QApplication.instance() or QApplication([])
        values = {}
        config = Mock()
        config.get.side_effect = lambda key, default=None: values.get(key, default)
        config.set.side_effect = lambda key, value: values.update({key: value})
        config.config = values
        config.base_dir = tempfile.mkdtemp()
        with patch('fluent_ui.views.settings_center.AutostartService') as startup:
            startup.return_value.is_enabled.return_value = False
            view = SettingInterface(config)
            view._show_tab(0)  # Startup/window settings are built on demand.
            row = view._rows['hide_main_after_paste'][0]
            self.assertFalse(row.value())

            row.set_value(True)
            row.changed.emit()
            self.assertIn('hide_main_after_paste', view.pending)
            self.assertNotIn('hide_main_after_paste', values)
            view.save()
            self.assertTrue(values['hide_main_after_paste'])

            row.set_value(False)
            row.changed.emit()
            view.discard()
            self.assertEqual(view._rows['hide_main_after_paste'][0].value(), True)
            view.deleteLater()


if __name__ == '__main__':
    unittest.main()
