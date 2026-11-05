"""Regressions at the real drag-source and mixed-membership call sites."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPointF, QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from test_wpb_drop import gallery


def test_resource_drag_cannot_reenter_while_native_loop_dispatches_mouse_moves(tmp_path, monkeypatch):
    from fluent_ui.components.emoji_card import EmojiCard
    app = QApplication.instance() or QApplication([])
    card = EmojiCard(str(tmp_path/'sample.png'), load_image=False)
    card.drag_identity_provider = lambda paths: object()
    calls = []
    def move():
        return QMouseEvent(QMouseEvent.MouseMove, QPointF(40, 30), QPointF(40, 30),
                           Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    def execute(drag):
        calls.append(drag)
        if len(calls) == 1:
            # QueryContinueDrag calls processEvents in the native OLE loop.
            QApplication.sendEvent(card, move())
        return False
    monkeypatch.setattr('services.external_drag.execute_resource_drag', execute)
    card._drag_start_pos = QPoint(2, 2)
    QApplication.sendEvent(card, move())
    assert len(calls) == 1, 'one physical press must create exactly one OLE drag'
    assert card._drag_start_pos is None
    assert not card._is_dragging
    card.close()


def test_cross_source_drop_keeps_interleaved_payload_order(gallery):
    gallery, storage, _parent, _children, all_paths = gallery
    source_a = storage.create_node('source-a')
    source_b = storage.create_node('source-b')
    target = storage.create_node('target')
    paths = all_paths[:3]
    assert len(paths) == 3
    storage.move_resources_to([paths[0], paths[2]], source_a)
    storage.move_resources_to([paths[1]], source_b)
    sources = {paths[0]:source_a, paths[1]:source_b, paths[2]:source_a}
    gallery._apply_drop_action(paths, target, False, sources, 0)
    assert [e['path'] for e in storage.entries_of(target)] == paths
    assert storage.entries_of(source_a) == []
    assert storage.entries_of(source_b) == []


def test_node_boundaries_render_visible_insertion_feedback(gallery):
    from fluent_ui.components.drop_contract import INSERT_BEFORE, INSERT_AFTER, INTO
    from fluent_ui import visual
    from PySide6.QtGui import QColor
    gallery, storage, parent, children, paths = gallery
    for placement in (INSERT_BEFORE, INSERT_AFTER, INTO):
        index = next(i for i,e in enumerate(gallery._entries) if e['id']==children[0])
        rect = gallery.renderer.index.rects[index]
        if placement != INTO:
            rect = gallery._category_insertion_rect(index, placement, rect)
        gallery.drop_feedback.show_target(placement, rect)
        QApplication.processEvents()
        mark = gallery.drop_feedback.geometry()
        assert gallery.grid_container.rect().contains(mark), (placement, mark)
        if placement != INTO:
            picture = gallery.grid_container.grab().toImage()
            assert picture.pixelColor(mark.center()) == QColor(visual.accent()), (placement, mark)


def test_client_cursor_uses_child_and_override_instead_of_stale_resize(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PySide6.QtWidgets import QWidget
    from PySide6.QtGui import QCursor
    from fluent_ui.components import native_resize
    app = QApplication.instance() or QApplication([])
    host=QWidget();child=QWidget(host)
    user=SimpleNamespace(LoadCursorW=Mock(side_effect=lambda instance,identifier:identifier),SetCursor=Mock())
    monkeypatch.setattr(native_resize.ctypes,'windll',SimpleNamespace(user32=user))
    monkeypatch.setattr(QApplication,'widgetAt',lambda pos:child)
    monkeypatch.setattr(QApplication,'overrideCursor',lambda:None)
    for shape,identifier in ((Qt.PointingHandCursor,32649),(Qt.IBeamCursor,32513),(Qt.ArrowCursor,32512)):
        child.setCursor(shape)
        assert native_resize.restore_client_cursor(host)
        user.SetCursor.assert_called_with(identifier)
    monkeypatch.setattr(QApplication,'overrideCursor',lambda:QCursor(Qt.WaitCursor))
    assert native_resize.restore_client_cursor(host)
    user.SetCursor.assert_called_with(32514)
    monkeypatch.setattr(QApplication,'widgetAt',lambda pos:None)
    user.SetCursor.reset_mock()
    assert not native_resize.restore_client_cursor(host)
    user.SetCursor.assert_not_called()
    host.close()
