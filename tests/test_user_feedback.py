"""Feedback actions use generated metadata and never a Library or network task."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication,QWidget
from fluent_ui.components import user_feedback as feedback
from services.i18n import i18n_engine

COPY=json.loads((Path(__file__).parent/'fixtures/user_feedback_copy.json').read_text(encoding='utf-8'))

@pytest.fixture
def app():
    value=QApplication.instance() or QApplication([])
    yield value
    i18n_engine.load_language('zh')


def test_real_menu_and_about_share_url_and_refresh_all_languages(app,monkeypatch):
    from fluent_ui.views.about_view import AboutInformation
    from fluent_ui.views.gallery_view import GalleryInterface,RoundMenu
    opener=Mock(return_value=True)
    monkeypatch.setattr(feedback.QDesktopServices,'openUrl',opener)
    monkeypatch.setattr(feedback,'environment_text',Mock(side_effect=AssertionError('Opening feedback must not collect local info')))
    monkeypatch.setattr('services.ocr_service.ocr_service',lambda _:SimpleNamespace(library_busy=False))
    menus=[];monkeypatch.setattr(RoundMenu,'popup_at',lambda menu,*args,**kwargs:menus.append(menu))
    owner=QWidget();owner.storage=object();owner.btn_tools=QWidget(owner)
    for name in ('similarity_requested','qq_requested','tg_requested','about_requested'):
        setattr(owner,name,SimpleNamespace(emit=Mock()))
    about=AboutInformation(owner)
    GalleryInterface._show_tools_menu(owner)
    action=next(a for a in menus[-1].actions() if a.text()=='反馈与建议')
    app.clipboard().setText('Generated clipboard sentinel')
    for lang in ('zh','zh_TW','en','ja'):
        i18n_engine.load_language(lang)
        assert action.text()==COPY[0]['values'][lang]
        assert about.feedback_button.text()==COPY[0]['values'][lang]
        assert about.copy_environment_button.text()==COPY[1]['values'][lang]
        action.trigger();about.feedback_button.click()
        assert app.clipboard().text()=='Generated clipboard sentinel'
    assert opener.call_count==8
    assert {c.args[0].toString() for c in opener.call_args_list}=={feedback.FEEDBACK_URL}
    owner.deleteLater();app.processEvents()


def test_failed_browser_copies_only_public_link(app,monkeypatch):
    owner=QWidget();host=Mock()
    monkeypatch.setattr(feedback.QDesktopServices,'openUrl',lambda _:False)
    monkeypatch.setattr(feedback,'feedback_for',lambda _:host)
    monkeypatch.setattr(feedback,'environment_text',Mock(side_effect=AssertionError('No automatic environment copy')))
    assert feedback.open_feedback(owner) is False
    assert app.clipboard().text()==feedback.FEEDBACK_URL
    assert host.notice.call_args.kwargs=={'warning':True}
    assert host.notice.call_args.args[1]==COPY[3]['values']['zh']
    owner.deleteLater()


def test_environment_allowlist_and_click_feedback(app,monkeypatch,tmp_path):
    metadata={'version':'7.8.9','channel':'preview','library':'TEST_PRIVATE_LIBRARY','token':'GENERATED_SECRET_NOT_TO_COPY'}
    (tmp_path/'version.json').write_text(json.dumps(metadata),encoding='utf-8');(tmp_path/'.git').mkdir()
    monkeypatch.setattr(feedback,'install_root',lambda:tmp_path)
    monkeypatch.setattr(feedback,'version_info',lambda:{'commit':'abcdef12','token':metadata['token']})
    monkeypatch.setattr(feedback.platform,'release',lambda:'11')
    monkeypatch.setattr(feedback.platform,'version',lambda:'10.0.TEST')
    owner=QWidget();monkeypatch.setattr(owner,'devicePixelRatioF',lambda:1.5)
    host=Mock();monkeypatch.setattr(feedback,'feedback_for',lambda _:host)
    for lang in ('zh','zh_TW','en','ja'):
        i18n_engine.load_language(lang);feedback.copy_environment_info(owner)
        text=app.clipboard().text()
        assert set(text.splitlines())=={'NekoriEmojy: 7.8.9','Channel: preview','Windows: 11 (10.0.TEST)',
            'UI language: '+lang,'Display scale: 150%','Development commit: abcdef12'}
        assert metadata['library'] not in text and metadata['token'] not in text and str(tmp_path) not in text
        assert host.toast.call_args.args[0]==COPY[2]['values'][lang]
    owner.deleteLater()


def test_missing_optional_fields_are_omitted(app,monkeypatch,tmp_path):
    (tmp_path/'version.json').write_text('{"version":"7.8.9"}',encoding='utf-8')
    monkeypatch.setattr(feedback,'install_root',lambda:tmp_path)
    monkeypatch.setattr(feedback,'version_info',Mock(side_effect=AssertionError('Not a source checkout')))
    owner=QWidget();monkeypatch.setattr(owner,'devicePixelRatioF',lambda:float('nan'))
    text=feedback.environment_text(owner)
    assert 'Channel:' not in text and 'Development commit:' not in text and 'Display scale:' not in text
    (tmp_path/'version.json').unlink();(tmp_path/'.git').mkdir()
    monkeypatch.setattr(feedback,'version_info',Mock(side_effect=FileNotFoundError('Generated missing version metadata')))
    text=feedback.environment_text(owner)
    assert 'NekoriEmojy:' not in text and 'Channel:' not in text and 'Development commit:' not in text
    owner.deleteLater()


@pytest.mark.parametrize('name,required_id,count',[
    ('01-bug-report.yml','description',5),('02-feature-request.yml','suggestion',3)])
def test_issue_forms_valid_yaml_json_subset_and_required_fields(name,required_id,count):
    # JSON flow syntax is a YAML 1.2 subset; no parser/dependency installation.
    path=Path(__file__).resolve().parents[1]/'.github/ISSUE_TEMPLATE'/name
    form=json.loads(path.read_text(encoding='utf-8'))
    assert form['name'] and form['description'] and 'labels' not in form
    body=form['body'];assert len(body)==count and len({row['id'] for row in body})==count
    assert [row['id'] for row in body if row['validations']['required']]==[required_id]
    assert all(row['type']=='textarea' and ' / ' in row['attributes']['label'] for row in body)
