"""Bounded passive native-state evidence for an intermittent resize failure.

Enabled only by NEKORI_NATIVE_CHECK. No input, no repairs or periodic probes.
"""
import json
import os
import time
from pathlib import Path
import win32gui
from PySide6.QtCore import Qt


class NativeStateLog:
    LIMIT = 256

    def __init__(self):
        self.remaining = self.LIMIT
        self.last = None
        self.path = Path(os.environ['NEKORI_APP_DATA'])/'native-state.log'

    def record(self, window, event, hwnd, result=None):
        if not self.remaining or not hwnd or not win32gui.IsWindow(hwnd):
            return
        state = dict(event=event, hwnd=int(hwnd),
                     style=hex(win32gui.GetWindowLong(hwnd, -16) & 0xffffffff),
                     exstyle=hex(win32gui.GetWindowLong(hwnd, -20) & 0xffffffff),
                     owner=int(win32gui.GetWindow(hwnd, 4)),
                     resize_enabled=getattr(window, '_isResizeEnabled', None),
                     minimum=[window.minimumWidth(), window.minimumHeight()],
                     maximum=[window.maximumWidth(), window.maximumHeight()],
                     flags=window.windowFlags().value, state=window.windowState().value,
                     visible=window.isVisible(), result=result,
                     client=list(win32gui.GetClientRect(hwnd)),
                     translucent=window.testAttribute(Qt.WA_TranslucentBackground))
        # Hit-test stream is reduced to changes in result/native state, not
        # every mouse move. Geometry is included for lifecycle/resize bounds.
        signature = json.dumps({key: value for key, value in state.items() if key != 'client'}, sort_keys=True)
        if signature == self.last:
            return
        self.last = signature
        self.remaining -= 1
        state['time'] = time.time()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(state, ensure_ascii=False)+'\n')
