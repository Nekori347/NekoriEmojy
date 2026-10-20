"""Destroyed views must stop consuming shared theme/task callbacks."""
import sys
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QWidget
from fluent_ui import visual
from fluent_ui.components.controls import PushButton
from test_phase2_interaction import surface, settle


def test_deleted_views_disconnect_shared_callbacks_and_owned_timers(surface, monkeypatch):
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui.components.quick_panel import QuickPanel
    errors=[]
    monkeypatch.setattr(sys,'excepthook',lambda *args:errors.append(args))
    s=surface
    gallery=GalleryInterface(s.storage,s.clipboard,s.config)
    gallery.focus_timer.stop()
    quick=QuickPanel(s.storage,s.clipboard,s.config)
    quick.shutdown()
    owner=QWidget();button=PushButton('test',owner)
    button._hover_settle_timer.start(0)
    for widget in (gallery,quick,owner):widget.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    visual.theme.changed.emit()
    s.g.ocr.changed.emit()
    s.g.imports.changed.emit('test')
    settle(s.app)
    assert not errors, [str(error[1]) for error in errors]
