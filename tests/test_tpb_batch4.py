"""Fourth approved copy batch: synthetic results only, no external services."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication
from services.i18n import i18n_engine, t

DATA = json.loads((Path(__file__).parent / 'fixtures/tpb_batch4_copy.json').read_text(encoding='utf-8'))
M = {r['id']: r for r in DATA['records']}
LANGS = ('zh', 'zh_TW', 'en', 'ja')


@pytest.fixture
def similarity(tmp_path):
    from test_similarity_view import FakeGallery
    from fluent_ui.views.similarity_view import SimilarityDialog
    app = QApplication.instance() or QApplication([])
    gallery = FakeGallery(str(tmp_path))
    dialog = SimilarityDialog(gallery)
    yield dialog
    dialog.worker = None
    dialog.close()
    dialog.deleteLater()
    gallery.deleteLater()
    app.processEvents()
    i18n_engine.load_language('zh')


def test_similarity_cancel_has_cancelled_feedback(similarity):
    v = similarity
    v.failures = [('generated.png', 'Generated error')]
    v.worker = SimpleNamespace(error='', cancelled=True, deleteLater=Mock())
    v.feedback_host.finish = Mock()
    v.worker_finished()
    assert v.feedback_host.finish.call_args.kwargs['outcome'] == 'cancelled'
    assert v.status.text() == M['missing-13']['source']


def test_similarity_language_switch_keeps_live_status_count_and_page(similarity):
    v = similarity
    v.on_progress('匹配', 3, 8)
    v.selected = {str(n) for n in range(5)}
    v.page = 2
    v.update_selection()
    for lang in LANGS:
        i18n_engine.load_language(lang)
        assert v.status.text() == f"{t('匹配')}：3 / 8"
        assert v.delete_button.text() == str(t('删除所选')) + '（5）'
        assert len(v.selected) == 5 and v.page == 2


@pytest.mark.parametrize('failed', [0, 2])
def test_similarity_result_templates_and_refresh(similarity, failed):
    v = similarity
    v.worker = SimpleNamespace(error='', cancelled=False, features=[], groups=[],
        failures=[('generated.png', 'Generated error')] * failed, deleteLater=Mock())
    v.feedback_host.finish = Mock()
    v.worker_finished()
    for lang in LANGS:
        i18n_engine.load_language(lang)
        expected = M['R1']['values'][lang].format(groups=0, entries=0)
        if failed:
            expected += '\n' + M['R2']['values'][lang].format(failed=failed)
        assert v.status.text() == expected
    assert v.feedback_host.finish.call_args.kwargs['outcome'] == ('partial' if failed else 'success')


def test_similarity_failure_and_cancelling_refresh(similarity):
    v = similarity
    v.worker = SimpleNamespace(error='Generated error', cancelled=False, deleteLater=Mock())
    v.worker_finished()
    for lang in LANGS:
        i18n_engine.load_language(lang)
        assert v.status.text() == M['missing-11']['values'][lang] + 'Generated error'
    v.worker = Mock()
    v.cancel()
    for lang in LANGS:
        i18n_engine.load_language(lang)
        assert v.status.text() == M['missing-12']['values'][lang]


def test_approved_similarity_translations():
    from string import Formatter
    fields = lambda s: sorted(n for _, n, _, _ in Formatter().parse(s) if n is not None)
    for lang in LANGS:
        i18n_engine.load_language(lang)
        for r in DATA['records']:
            if not (r['id'].startswith('missing-') or r['id'] in ('R1', 'R2')):
                continue
            assert t(r['source']) == r['values'][lang], (r['id'], lang)
            assert fields(r['source']) == fields(r['values'][lang])
    i18n_engine.load_language('zh')
