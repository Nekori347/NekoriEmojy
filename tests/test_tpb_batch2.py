"""Approved settings copy, partial-language boundaries and real Qt bindings."""
import ast
import json
import subprocess
from pathlib import Path

from services.i18n import i18n_engine, t
from test_phase2_interaction import surface, settle
from test_l1_l3_interaction import settings

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'tests/fixtures/tpb_batch2_copy.json').read_text(encoding='utf-8'))
RECORDS = DATA['records']


def test_exact_mapping_and_unapproved_values_unchanged():
    assert len(RECORDS) == 16
    assert len({r['id'] for r in RECORDS}) == 14
    assert sum(len(r['values']) for r in RECORDS) == 51
    for lang in ('zh', 'zh_TW', 'en', 'ja'):
        path = f'translations/{lang}.json'
        old = json.loads(subprocess.check_output(['git', 'show', f"{DATA['baseline']}:{path}"], cwd=ROOT).decode('utf-8'))
        actual = json.loads((ROOT / path).read_text(encoding='utf-8'))
        expected = dict(old)
        for row in RECORDS:
            if lang in row['values']:
                expected[row['source']] = row['values'][lang]
        # Later approved batches may add keys; this batch's locked values stay exact.
        assert all(actual.get(key) == value for key, value in expected.items()), lang


def test_settings_logic_identical_except_approved_literals():
    path = 'fluent_ui/views/settings_center.py'
    old = ast.parse(subprocess.check_output(['git', 'show', f"{DATA['baseline']}:{path}"], cwd=ROOT).decode('utf-8'))
    changes = {r['previous']: r['source'] for r in RECORDS}
    class Approved(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                node.value = changes.get(node.value, node.value)
            return node
    actual = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    assert ast.dump(Approved().visit(old)) == ast.dump(actual)


def test_live_settings_language_and_conflict_states(surface, settings):
    c = settings
    for lang in ('zh', 'zh_TW', 'en', 'ja'):
        i18n_engine.load_language(lang)
        for page, (_, tabs) in enumerate(c._icon_pages()):
            if page == 4:
                continue
            c._select_page(page)
            for tab in range(len(tabs)):
                # Avoid unrelated OCR/library/network tool pages.
                if page == 3 and tab != 2:
                    continue
                c._show_tab(tab)
                settle(surface.app)
        for key, id in [('hide_main_after_paste', '119'), ('global_hotkey', '149'), ('quick_panel_hotkey', '150')]:
            row = c._all_rows[key][0]
            expected = next(r['source'] for r in RECORDS if r['id'] == id and r['role'] == 'name')
            assert row.title_label.text() == t(expected)
        warning = next(r['source'] for r in RECORDS if r['id'] == '186')
        assert not c._hotkeys_valid({'global_hotkey': 'ctrl+alt+a', 'quick_panel_hotkey': 'ctrl+alt+a', 'clipboard_import_enabled': False})
        assert c._all_rows['global_hotkey'][0].hint_label.text() == t(warning)
        warning = next(r['source'] for r in RECORDS if r['id'] == '187')
        assert not c._hotkeys_valid({'global_hotkey': 'ctrl+alt+a', 'quick_panel_hotkey': 'ctrl+alt+b', 'clipboard_import_enabled': True, 'clipboard_import_hotkey': 'ctrl+alt+a'})
        assert c._all_rows['clipboard_import_hotkey'][0].hint_label.text() == t(warning)
        c._set_dirty(True)
        assert c.export_hint.hint_label.text() == t('未保存修改不会包含在导出文件中。')
        c._set_dirty(False)
        assert c.export_hint.hint_label.text() == ''
    i18n_engine.load_language('zh')
