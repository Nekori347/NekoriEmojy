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


def test_native_export_reports_written_and_omitted_resources(tmp_path, monkeypatch):
    import zipfile
    from services.nekori_package import NekoriPackageService
    root = tmp_path / 'library'
    root.mkdir()
    (root / 'good.bin').write_bytes(b'generated good data')
    (root / 'unreadable.bin').write_bytes(b'generated inaccessible data')
    entries = [dict(relative_path=n, package_path='images/'+n, display_name=n)
               for n in ('good.bin', 'missing.bin', 'unreadable.bin')]
    service = NekoriPackageService(SimpleNamespace(index=SimpleNamespace(root=root)))
    monkeypatch.setattr(service, 'build_manifest', lambda **_: dict(resources=entries, nodes=[]))
    original = zipfile.ZipFile.write
    def write(archive, filename, *args, **kwargs):
        if Path(filename).name == 'unreadable.bin':
            raise PermissionError('Generated read failure')
        return original(archive, filename, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, 'write', write)
    target = tmp_path / 'test.zip'
    result = service.export(target)
    assert result['resources'] == 1
    assert result['skipped'] == 2
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(json.loads(archive.read('nekori.json'))['resources']) == 3
        assert archive.read('images/good.bin') == b'generated good data'
    assert (root / 'good.bin').read_bytes() == b'generated good data'


@pytest.mark.parametrize('skipped', [0, 2])
def test_both_share_export_entries_show_same_omission_notice(tmp_path, monkeypatch, skipped):
    from fluent_ui.views.gallery_view import CategorySidebar, GalleryInterface
    from fluent_ui.components import feedback, exchange_task_dialog
    monkeypatch.setattr('fluent_ui.views.gallery_view.QFileDialog.getExistingDirectory', lambda *_: str(tmp_path))
    monkeypatch.setattr('fluent_ui.views.gallery_view.QFileDialog.getSaveFileName', lambda *_: (str(tmp_path/'result.zip'), ''))
    monkeypatch.setattr(exchange_task_dialog, 'run_exchange_task', lambda *_a, **_k: {'skipped': ['generated']*skipped})
    host = Mock()
    monkeypatch.setattr('services.exchange_export.ExchangeExportService', lambda **_: Mock())
    monkeypatch.setattr(feedback, 'feedback_for', lambda *_: host)
    storage = SimpleNamespace(node=lambda _: {'name':'Generated'}, category_labels=lambda: {'Generated':'node-id'})
    sidebar = SimpleNamespace(window=lambda: object(), storage=storage, gallery_view=Mock(), _error=Mock())
    gallery = SimpleNamespace(window=lambda: object(), storage=storage)
    for lang in LANGS:
        i18n_engine.load_language(lang)
        host.reset_mock()
        CategorySidebar.export_node(sidebar, 'node-id')
        if skipped:
            assert M['E2']['values'][lang].format(count=skipped) in host.notice.call_args.args[1]
        else:
            assert not host.notice.called
        host.reset_mock()
        GalleryInterface._export_exchange_package(gallery)
        call = host.notice.call_args if skipped else host.toast.call_args
        assert call
        if skipped:
            assert M['E2']['values'][lang].format(count=skipped) in call.args[1]
    i18n_engine.load_language('zh')


@pytest.mark.parametrize('skipped', [0, 2, 3])
def test_native_export_entry_distinguishes_incomplete(tmp_path, monkeypatch, skipped):
    from fluent_ui.views.settings_center import SettingsCenter
    from fluent_ui.components import feedback, exchange_task_dialog
    target = str(tmp_path / 'result.zip')
    monkeypatch.setattr('fluent_ui.views.settings_center.QFileDialog.getSaveFileName', lambda *_: (target, ''))
    monkeypatch.setattr('services.nekori_package.NekoriPackageService', lambda *_: Mock())
    monkeypatch.setattr(exchange_task_dialog, 'run_exchange_task', lambda *_a, **_k: dict(resources=3-skipped, nodes=1, skipped=skipped))
    host = Mock()
    monkeypatch.setattr(feedback, 'feedback_for', lambda *_: host)
    view = SimpleNamespace(storage=None, window=lambda:None, show_success=Mock(), show_error=Mock())
    for lang in LANGS:
        i18n_engine.load_language(lang)
        view.show_success.reset_mock();host.reset_mock()
        SettingsCenter.export_nekori_package(view)
        assert not view.show_error.called
        if skipped:
            assert not view.show_success.called
            assert host.notice.call_args.args == (M['E4-title']['values'][lang],
                M['E4-body']['values'][lang].format(written=3-skipped, skipped=skipped)+'\n'+target)
            assert host.notice.call_args.kwargs['warning'] is True
        else:
            assert target in view.show_success.call_args.args[1]
    i18n_engine.load_language('zh')


def test_share_import_summary_preserves_counts_and_raw_warnings(monkeypatch):
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui.components import exchange_task_dialog
    warning = 'Generated optional icon unavailable'
    monkeypatch.setattr('services.exchange_import.ExchangeImportService', lambda **_: SimpleNamespace(warnings=[warning]))
    monkeypatch.setattr('fluent_ui.views.gallery_view.QFileDialog.getOpenFileName', lambda *_: ('generated.zip', ''))
    monkeypatch.setattr(exchange_task_dialog, 'run_exchange_task', lambda *_: (2, 3))
    view = SimpleNamespace(window=lambda:None, import_thread=None, storage=Mock(), sidebar=Mock(),
        current_node='generated-id', on_images_changed=Mock(), show_success=Mock(), show_error=Mock())
    for lang in LANGS:
        i18n_engine.load_language(lang)
        GalleryInterface._import_exchange_package(view)
        assert view.show_success.call_args.args[1] == M['E1']['values'][lang].format(value_0=2, value_1=3)+'\n'+warning
        assert not view.show_error.called
    i18n_engine.load_language('zh')
