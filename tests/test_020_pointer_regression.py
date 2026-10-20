"""Pointer routing through the visible hit target, without desktop input."""
from unittest.mock import Mock
import sys
import os
import pytest
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from test_phase2_interaction import surface, settle, card


@pytest.fixture(autouse=True)
def passive_native_window(monkeypatch):
    if os.environ.get('NEKORI_POINTER_NATIVE') != '1':
        return
    from fluent_ui.views.gallery_view import GalleryInterface
    original = GalleryInterface.show
    def show(widget):
        widget.setAttribute(Qt.WA_ShowWithoutActivating)
        from PySide6.QtGui import QGuiApplication
        screens = QGuiApplication.screens()
        screen = next((s for s in screens if 'Mi' in s.name()), screens[-1])
        widget.move(screen.availableGeometry().topLeft())
        original(widget)
    monkeypatch.setattr(GalleryInterface, 'show', show)
    from fluent_ui.components.safe_round_menu import SafeRoundMenu
    original_menu = SafeRoundMenu._show_menu
    def show_menu(menu, *args, **kwargs):
        menu.setAttribute(Qt.WA_ShowWithoutActivating)
        return original_menu(menu, *args, **kwargs)
    monkeypatch.setattr(SafeRoundMenu, '_show_menu', show_menu)


@pytest.mark.parametrize('ocr_state', ['not_running', 'running', 'stopped', 'restarted'])
def test_pointer_send_select_and_context_menu(surface, monkeypatch, ocr_state):
    s = surface
    g = s.g
    c = card(s, s.paths[0])
    # A controlled worker holds an actual supplement queue in flight. This
    # isolates input routing from CPU throughput; inference is tested separately.
    started = threading.Event()
    release = threading.Event()
    class HeldProcess:
        def recognize(self, *args):
            started.set()
            release.wait(3)
            return {'text': '测试', 'raw_text': '测试'}
        def close(self):
            release.set()
    service = g.ocr
    if ocr_state != 'not_running':
        monkeypatch.setattr(type(service.component), 'installed', property(lambda _: True))
        service.process = HeldProcess()
        service.supplement()
        assert started.wait(2)
        if ocr_state == 'stopped':
            service.cancel()
        elif ocr_state == 'restarted':
            from services.ocr_service import OcrService
            service.close()
            service = OcrService(s.storage)
            assert not service.busy
    point = c.mapTo(g, c.rect().center())
    target = g.childAt(point)
    assert target is c, type(target).__name__
    send = Mock()
    monkeypatch.setattr(g, '_send_to_clipboard', send)
    s.config.set('gallery_click_action', 'send')
    QTest.mouseClick(target, Qt.LeftButton)
    send.assert_called_once_with(c.image_path)
    assert not g.selected_keys
    s.config.set('gallery_click_action', 'select')
    QTest.mouseClick(target, Qt.LeftButton)
    assert g.selected_keys == {c.image_path}
    # QtTest right-click does not synthesize the platform context-menu event.
    # Deliver that event to the hit target and observe the actual menu exec.
    from fluent_ui.views.gallery_view import RoundMenu
    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *args: errors.append(args))
    event = QContextMenuEvent(QContextMenuEvent.Mouse, c.rect().center(),
                             c.mapToGlobal(c.rect().center()))
    s.app.sendEvent(target, event)
    assert not errors, [str(e[1]) for e in errors]
    opened = [m for m in g.findChildren(RoundMenu) if m.isVisible()]
    assert opened, 'resource menu did not open from pointer event'
    assert any(a.text() == '查看与编辑文字' for a in opened[0].actions())
    for menu in opened:
        menu.hide()
    # A context click selects its target. That single selection must not turn
    # the configured fast-send mode into a silent select-only mode afterwards.
    s.config.set('gallery_click_action', 'send')
    send.reset_mock()
    QTest.mouseClick(target, Qt.LeftButton)
    send.assert_called_once_with(c.image_path)
    assert not g.selected_keys
    release.set()
    service.close()


@pytest.mark.skipif(os.environ.get('NEKORI_REAL_OCR') != '1', reason='explicit local component check')
def test_pointer_during_real_optional_worker(surface, monkeypatch):
    s = surface
    g = s.g
    service = g.ocr
    service.component.root = Path(__file__).resolve().parents[2] / 'DevData/ocr-integration/packages/ocr-package-stage'
    service.component.base.mkdir(parents=True, exist_ok=True)
    assert service.available
    send = Mock()
    monkeypatch.setattr(g, '_send_to_clipboard', send)
    s.config.set('gallery_click_action', 'send')
    ids = [s.storage.index.resource(p)['id'] for p in (s.paths[0], s.paths[1], s.paths[4])]
    service.enqueue(ids)
    started = time.monotonic()
    click_count = 0
    try:
        while service.busy and time.monotonic()-started < 45:
            c = card(s, s.paths[0])
            target = g.childAt(c.mapTo(g, c.rect().center()))
            assert target is c
            QTest.mouseClick(target, Qt.LeftButton)
            click_count += 1
            assert send.call_count == click_count
            QTest.qWait(100)
        assert not service.busy, service.summary
        assert service.summary.get('done') == 3, service.summary
        assert click_count > 2
        output = Path(__file__).resolve().parents[2] / 'DevData/020-regression'
        output.mkdir(exist_ok=True)
        g.grab().save(str(output / 'native-ocr-pointer.png'))
        import json
        (output / 'real-worker-pointer.json').write_text(json.dumps(dict(
            platform=s.app.platformName(), elapsed_seconds=time.monotonic()-started,
            pointer_send_count=click_count, summary=service.summary,
            desktop_input_injected=False), indent=2), encoding='utf-8')
    finally:
        service.close()
