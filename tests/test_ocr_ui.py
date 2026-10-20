import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from unittest.mock import Mock
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPlainTextEdit,QApplication
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings
from services.i18n import i18n_engine
from fluent_ui.components import dialogs
from fluent_ui.components.ocr_controls import edit_text,request_recognition
from fluent_ui.components.controls import PushButton
from fluent_ui.components.quick_panel import QuickPanel


def test_manual_dialog_and_both_search_scopes_use_ocr(surface,monkeypatch):
    s=surface;g=s.g;path=s.paths[0]
    rid=s.storage.index.resource(path)['id']
    def save_dialog():
        dialog=s.app.activeModalWidget()
        editor=dialog.findChild(QPlainTextEdit);editor.setPlainText('不要放棄 楽しい')
        next(b for b in dialog.findChildren(PushButton) if b.text()=='保存').click()
    QTimer.singleShot(0,save_dialog)
    edit_text(g,s.storage,path)
    assert s.storage.index.ocr_info(rid)['manual']
    assert path in s.storage.search_images('放弃')
    g.search_keyword='放弃'
    assert path in [r['path'] for r in g._collect_entries() if r['kind']=='resource']
    # No OCR installation is required to edit or search persisted text.
    assert not g.ocr.available
    quick=QuickPanel(s.storage,s.clipboard,s.config)
    quick.search_box.setText('放弃');quick._perform_search(force=True)
    assert path in quick._cached_results
    s.storage.index.edit_ocr_text(rid,'別の文字')
    quick._perform_search()
    assert path not in quick._cached_results
    quick.shutdown();quick.close();quick.deleteLater()


def test_manual_rerecognition_requires_explicit_overwrite(surface,monkeypatch):
    s=surface;g=s.g;path=s.paths[0];rid=s.storage.index.resource(path)['id']
    g.ocr.edit(rid,'manual')
    monkeypatch.setattr(type(g.ocr),'available',property(lambda _:True))
    enqueue=Mock();monkeypatch.setattr(g.ocr,'enqueue',enqueue)
    monkeypatch.setattr(dialogs,'confirm',lambda *args,**kwargs:False)
    request_recognition(g,s.storage,[path],True);enqueue.assert_not_called()
    monkeypatch.setattr(dialogs,'confirm',lambda *args,**kwargs:True)
    request_recognition(g,s.storage,[path],True)
    assert enqueue.call_args.kwargs==dict(force=True,overwrite=True)


def test_new_ocr_result_updates_active_gallery_without_rebuild(surface,monkeypatch):
    s=surface;g=s.g;path=s.paths[0];rid=s.storage.index.resource(path)['id']
    g.search_keyword='放弃';g.refresh_content(reason='search')
    assert not [r for r in g._entries if r['kind']=='resource']
    rebuild=Mock(wraps=g.refresh_content);monkeypatch.setattr(g,'refresh_content',rebuild)
    g.ocr.edit(rid,'放棄')
    QTest.qWait(750);settle(s.app)
    assert path in [r['path'] for r in g._entries if r['kind']=='resource']
    rebuild.assert_not_called()


@pytest.mark.parametrize('language',['zh','en','ja','zh_TW'])
def test_settings_ocr_tab_uses_existing_rows_and_no_missing_text(settings,language):
    s=settings;i18n_engine.set_language(language)
    c=s;c._select_page(3)
    i=next(i for i,(_,fn) in enumerate(c._tabs) if fn.__name__=='_page_ocr')
    c._show_tab(i);settle(QApplication.instance())
    o=c.ocr_controls
    assert not o.service.available and not o.remove_button.isEnabled()
    assert not o.supplement.isEnabled() and o.install_button.isEnabled()
    assert 'MISSING' not in o.component.hint_label.text()
    assert 'MISSING' not in o.task.hint_label.text()
    i18n_engine.set_language('zh')
