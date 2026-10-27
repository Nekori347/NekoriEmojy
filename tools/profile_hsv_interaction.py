"""Finite HSV investigation using the existing isolated Qt fixtures.

No business changes or desktop input. Run from Source with the test environment.
Results omit private data and separate local dispatch from subsequent paints.
"""
import cProfile
import io
import json
import os
from pathlib import Path
import pstats
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from fluent_ui import visual
from test_phase2_interaction import surface, settle
from test_l1_l3_interaction import settings


def summary(values):
    ordered = sorted(values)
    return dict(p50_ms=round(statistics.median(values), 3),
                p95_ms=round(ordered[int((len(ordered)-1)*.95)], 3),
                max_ms=round(max(values), 3))


def main():
    output = ROOT.parent / 'DevData/host-regression/hsv'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temp:
        with pytest.MonkeyPatch.context() as patch:
            source = surface.__wrapped__(Path(temp), patch)
            scene = next(source)
            editor = settings.__wrapped__(scene, patch)
            center = next(editor)
            center._select_page(1)
            center._show_tab(0)
            settle(scene.app)
            row = center._rows['accent_color'][0]
            counts = {}
            calls = []

            def dispatch(key):
                counts[key] = counts.get(key, 0)+1
                start = time.perf_counter()
                if key == 'accent_preview':
                    visual.theme.preview_accent()
                elif key == 'accent_color':
                    visual.theme.refresh()
                calls.append((key, (time.perf_counter()-start)*1000))

            center.settings_changed.connect(dispatch)
            reports = []
            profiler = cProfile.Profile()
            profiler.enable()
            for enabled in (False, True):
                center.preview_switch.setChecked(enabled)
                for route in ('spectrum', 'hsv-slider', 'swatch-owner'):
                    counts.clear()
                    calls.clear()
                    local, feedback = [], []
                    row.choose_color()
                    picker = row.picker
                    settle(scene.app)
                    for i in range(72):
                        start = time.perf_counter()
                        if route == 'spectrum':
                            r = picker.spectrum.selection_rect()
                            picker.spectrum._pick(QPointF(r.left()+i*(r.width()-1)/71,
                                                         r.top()+r.height()*.35))
                        elif route == 'hsv-slider':
                            picker.hsv_sliders[0].setValue(round(i*359/71))
                        else:
                            # Existing owner-side swatch update, without HSV field sync.
                            row.set_value(QColor.fromHsv(round(i*359/71), 166, 255).name())
                            if not row._preview_timer.isActive():
                                row._preview_timer.start()
                        local.append((time.perf_counter()-start)*1000)
                        scene.app.processEvents()
                        feedback.append((time.perf_counter()-start)*1000)
                        QTest.qWait(8)
                    final = row.value()
                    picker.accept()
                    QTest.qWait(220)
                    assert center.pending.get('accent_color') == final
                    reports.append(dict(preview=enabled, route=route, local=summary(local),
                                        dispatch_and_paint=summary(feedback), signals=dict(counts),
                                        theme_dispatch=summary([ms for _, ms in calls]) if calls else None,
                                        final_color_preserved=True))
            profiler.disable()
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(28)
            (output/'profile.txt').write_text(stream.getvalue(), encoding='utf-8')
            # UI-A evidence only; this probe does not restyle the controls.
            sizes = dict(preview_height=center.preview_switch.height(),
                         more_height=center.btn_tools.height(),
                         preview_checked=center.preview_switch.isChecked())
            payload = dict(platform='offscreen', samples_per_route=72, editor_geometry=[880,680],
                           library='generated 5-resource fixture', results=reports, controls=sizes,
                           boundary='No physical HSV dragging, DWM timing or large-Library claim.')
            (output/'result.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(payload, ensure_ascii=False))
            center.settings_changed.disconnect(dispatch)
            next(editor, None)
            next(source, None)


if __name__ == '__main__':
    main()
