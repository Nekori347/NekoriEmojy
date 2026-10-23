"""Real card feedback stays independent of selection when hit geometry changes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication, QWidget, QScrollArea
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from fluent_ui.components.emoji_card import EmojiCard
from fluent_ui.views.gallery_view import GalleryInterface


def test_geometry_hit_updates_only_old_and_new_hover(monkeypatch):
    app = QApplication.instance() or QApplication([])
    owner = QWidget()
    owner.scroll_area = QScrollArea(owner)
    content = QWidget()
    content.resize(300, 600)
    owner.scroll_area.setWidget(content)
    owner.feedback_host = SimpleNamespace(toasts=[], hint_label=SimpleNamespace(isVisible=lambda: False))
    owner.config = {'preview_delay': 100}
    owner.preview_controller = Mock()
    first = EmojiCard('first.png', parent=content, load_image=False)
    second = EmojiCard('second.png', parent=content, load_image=False)
    for card in (first, second):
        card.hover_started.connect(lambda path, card=card: GalleryInterface.on_hover_started(owner, card, path))
        card.hover_ended.connect(lambda card=card: GalleryInterface.on_hover_ended(owner, card))
    first.set_selected(True)
    first.set_hovered(True)
    monkeypatch.setattr(QApplication, 'widgetAt', lambda point: second)
    first._is_dragging = True
    GalleryInterface._sync_hover_card(owner)
    assert first._hovered and first.is_selected
    first._is_dragging = False
    GalleryInterface._sync_hover_card(owner)
    assert not first._hovered and first.is_selected
    assert second._hovered and not second.is_selected
    first.hover_ended.emit()  # A delayed leave must not cancel the new hit.
    assert owner._hover_card is second
    monkeypatch.setattr(QApplication, 'widgetAt', lambda point: content)
    GalleryInterface._sync_hover_card(owner)
    assert not second._hovered and first.is_selected
    assert owner._hover_card is None
    clicks, activations = [], []
    first.clicked.connect(lambda *args: clicks.append(args))
    first.activated.connect(activations.append)
    QTest.mouseClick(first, Qt.LeftButton)
    QTest.mouseDClick(first, Qt.LeftButton)
    assert clicks and activations == ['first.png'] and first.is_selected
    owner.deleteLater()
    app.processEvents()
