"""Real Qt layouts for the approved text; no real import/export/update task."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import importlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QDialog
from qfluentwidgets import Theme, setTheme
from services.config import ConfigService
from services.i18n import i18n_engine
from fluent_ui import visual


def test_category_scope_and_diagnostic_copy_real_layout(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'unused-library'))
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('No network')))
    root = Path(__file__).resolve().parents[1]
    # Real Windows widgets use committed hosts, not the seven protected experiments.
    if os.environ.get('QT_QPA_PLATFORM') == 'windows':
        for short in ('materials', 'window_shell'):
            module = importlib.import_module('fluent_ui.'+short)
            source = subprocess.check_output(['git','show',f'HEAD:fluent_ui/{short}.py'],cwd=root).decode('utf-8')
            exec(compile(source,str(root/'fluent_ui'/f'{short}.py'),'exec'),module.__dict__)
    from fluent_ui.components import dialogs
    from fluent_ui.views.settings_center import SettingsCenter
    from fluent_ui.views.gallery_view import GalleryInterface
    monkeypatch.setattr('fluent_ui.views.settings_center.AutostartService.is_enabled', lambda _:False)
    config = ConfigService()
    i18n_engine.init(config);visual.theme.configure(config)
    data = json.loads((root/'tests/fixtures/tpb_batch4_copy.json').read_text(encoding='utf-8'))
    m = {r['id']:r for r in data['records']}
    center = SettingsCenter(config, None)
    center.resize(780, 700)
    center.show()
    measurements = []
    for lang in ('zh', 'zh_TW', 'en', 'ja'):
        i18n_engine.load_language(lang)
        for theme in (Theme.LIGHT, Theme.DARK):
            setTheme(theme);visual.theme.refresh()
            center._select_page(4)
            QTest.qWait(30)
            label = center.diagnostics_row.hint_label
            assert label.text() == m['D1']['values'][lang]
            assert label.height() >= label.heightForWidth(label.contentsRect().width()), (lang, label.size())
            assert label.isVisible()
            measurements.append((lang, theme.value, 'diagnostic', label.width(), label.height()))
            view = SimpleNamespace(window=lambda:center, storage=SimpleNamespace(get_all_categories=lambda:['Generated category']),
                                   _export_exchange_package=Mock())
            observed = [];errors = []
            def inspect():
                dialog = next((w for w in QApplication.topLevelWidgets() if isinstance(w, dialogs.NekoriDialog) and w.isVisible()), None)
                try:
                    assert dialog is not None and dialog.isVisible()
                    hint = next(l for l in dialog.findChildren(QLabel) if l.text() == m['E3']['values'][lang])
                    needed = hint.heightForWidth(hint.contentsRect().width())
                    assert hint.height() >= needed, (lang, hint.size(), needed)
                    assert hint.geometry().bottom() < dialog.footer_rule.y()
                    assert not dialog.grab().isNull()
                    observed.append((lang, theme.value, 'scope', hint.width(), hint.height()))
                    if os.environ.get('QT_QPA_PLATFORM') == 'windows' and lang in ('en', 'ja'):
                        evidence = root.parent/'DevData/ui-refresh'
                        evidence.mkdir(exist_ok=True)
                        dialog.grab().save(str(evidence/f'tpb4-scope-{lang}-{theme.value}.png'))
                        center.grab().save(str(evidence/f'tpb4-diagnostic-{lang}-{theme.value}.png'))
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    if dialog:dialog.reject()
            QTimer.singleShot(80, inspect)
            GalleryInterface._export_selected_categories_exchange_package(view)
            assert not errors, errors
            assert len(observed) == 1
            assert not view._export_exchange_package.called
            measurements.extend(observed)
    assert not center.grab().isNull()
    center.close();center.deleteLater();app.processEvents()
    i18n_engine.load_language('zh')
    print('TPB4_QT_LAYOUT', json.dumps(measurements))
