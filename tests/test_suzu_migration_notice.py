"""Suzu migration notices stay bound to the real migration task."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace

from test_phase2_interaction import surface, settle


class FakeMigrationService:
    def discover_instances(self):
        return [{'title': 'SuzuEmojy', 'pid': 4242,
                 'executable': r'C:\Suzu\SuzuEmojy.exe',
                 'data_dir': r'C:\Suzu\data', 'error': ''}]

    def preview_data(self, directory):
        return {'data_dir': directory, 'resources': 12, 'nodes': 3, 'tags': 4,
                'icons': 1, 'ordered': 5, 'missing': [], 'categories': ['A', 'B', 'C']}


def request(**values):
    base = dict(state='running', errors=[], saved=0, duplicates=0, skipped=0,
                failed=0, total=10, done=3, kind='migration', paths=[])
    base.update(values)
    return SimpleNamespace(**base)


def test_instance_dialog_explains_keep_source_available(surface):
    from fluent_ui.components.keycap_label import KeycapLabel
    from fluent_ui.components.suzu_instance_dialog import SuzuInstanceDialog
    from services.i18n import i18n_engine, t
    source = '迁移完成前请不要关闭 Suzu，也不要移动或删除源文件。Nekori 只读取源数据，不会修改它。'
    try:
        for language in ('zh', 'zh_TW', 'en', 'ja'):
            i18n_engine.load_language(language)
            dialog = SuzuInstanceDialog(surface.g, FakeMigrationService())
            dialog.show()
            settle(surface.app)
            hints = [label.text() for label in dialog.findChildren(KeycapLabel)]
            assert str(t(source)) in hints
            assert all('[MISSING:' not in text for text in hints)
            assert dialog.import_button.isEnabled() and dialog.selected_data_dir == r'C:\Suzu\data'
            footer_top = dialog.footer_rule.geometry().top()
            for label in dialog.findChildren(KeycapLabel):
                assert label.mapTo(dialog, label.rect().bottomLeft()).y() < footer_top
            dialog.close()
    finally:
        i18n_engine.load_language('zh')


def test_running_migration_task_carries_notice_and_terminal_state_clears_it(surface):
    from PySide6.QtGui import QFontMetrics
    from fluent_ui import visual
    gallery = surface.g
    host = gallery.feedback_host
    gallery.imports.requests['mig'] = request()
    gallery._sync_background_tasks()
    settle(surface.app)
    job = host.named_tasks['mig']
    assert job['title'] == '迁移中，勿动源数据'
    assert '只读取源数据' in job['content']
    # The caption title column is 112 DIP; this title must not be elided.
    assert QFontMetrics(visual.font('secondary')).horizontalAdvance(job['title']) <= 112

    gallery.imports.requests['mig'] = request(done=5)
    gallery._sync_background_tasks()
    assert host.named_tasks['mig']['title'] == '迁移中，勿动源数据'
    assert len(host.named_tasks) == 1

    gallery.imports.requests['mig'] = request(state='waiting', done=0)
    gallery._sync_background_tasks()
    assert host.named_tasks['mig']['title'] == '等待迁移，勿动数据'

    gallery.imports.requests['mig'] = request(state='completed', done=10)
    gallery._sync_background_tasks()
    job = host.named_tasks['mig']
    assert job['title'] == 'Suzu 迁移完成'
    assert '请保持源数据可用' not in job['title'] + job['content']

    gallery.imports.requests['mig'] = request(state='failed', done=2, failed=1,
                                              errors=['isolated failure'])
    gallery._sync_background_tasks()
    job = host.named_tasks['mig']
    assert job['title'] == 'Suzu 迁移失败'
    assert '请保持源数据可用' not in job['title'] + job['content']

    gallery.imports.requests['imp'] = request(kind='import', state='running')
    gallery._sync_background_tasks()
    job = host.named_tasks['imp']
    assert 'Suzu' not in job['title'] and '源数据' not in job['content']
    host.remove_task('mig')
    host.remove_task('imp')
