"""Approved tool feedback with synthetic counts/errors; no real tool work."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import subprocess
from string import Formatter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from services.i18n import i18n_engine, t

DATA = json.loads((Path(__file__).parent/'fixtures/tpb_batch3_copy.json').read_text(encoding='utf-8'))
M = {r['id']: r for r in DATA['records']}
LANGS = ('zh', 'zh_TW', 'en', 'ja')


def test_exact_approved_values_and_no_other_translation_changes():
    root=Path(__file__).resolve().parents[1]
    fields=lambda value: sorted(name for _,name,_,_ in Formatter().parse(value) if name is not None)
    for lang in LANGS:
        path=f'translations/{lang}.json'
        old=json.loads(subprocess.check_output(['git','show',f"{DATA['baseline']}:{path}"],cwd=root).decode('utf-8'))
        expected=dict(old)
        for r in DATA['records']:
            assert fields(r['source'])==fields(r['values'][lang]),(r['id'],lang)
            if r['id']=='qq-folder-naming':continue
            key=r['source']+('::'+r['context'] if r.get('context') else '')
            expected[key]=r['values'][lang]
        help=DATA['help_binding']
        expected[help['source']]=help['values'][lang]
        if lang!='zh':
            assert help['values'][lang].splitlines()[3]=='2. '+M['qq-folder-naming']['values'][lang]
            assert help['values'][lang].splitlines()[:3]+help['values'][lang].splitlines()[4:] == old[help['legacy_source']].splitlines()[:3]+old[help['legacy_source']].splitlines()[4:]
        # Exact whole-dictionary guard now also permits the locked fourth batch.
        fourth=json.loads((root/'tests/fixtures/tpb_batch4_copy.json').read_text(encoding='utf-8'))
        for r in fourth['records']:
            assert r['source'] not in {row['source'] for row in DATA['records']}
            expected[r['source']]=r['values'][lang]
        if lang=='zh_TW':
            expected[fourth['tw_correction']['source']]=fourth['tw_correction']['value']
        # Later approved notification/sorting mapping adds only these keys.
        notifications=json.loads((root/'tests/fixtures/notification_tooltip_copy.json').read_text(encoding='utf-8'))
        for row in notifications:expected[row['source']]=row['values'][lang]
        actual=json.loads((root/path).read_text(encoding='utf-8'))
        assert actual==expected,lang


def test_qq_log_uses_the_same_localized_terminal_result(monkeypatch):
    from fluent_ui.views.qq_scan_view import QQScanInterface
    explorer=Mock();monkeypatch.setattr('subprocess.Popen',explorer)
    for lang in LANGS:
        i18n_engine.load_language(lang)
        for count,cancelled,outcome in [(3,False,'success'),(2,False,'partial'),(0,False,'error'),(1,True,'cancelled')]:
            logs=[];explorer.reset_mock()
            v=SimpleNamespace(_current_worker=SimpleNamespace(file_paths=[1,2,3]),_set_busy=Mock(),log=logs.append,tooltip=Mock())
            QQScanInterface._on_export_finished(v,count,'generated-output',cancelled)
            title,body=v.tooltip.finish.call_args.args
            assert logs[0]==f'{title}: {body}'
            assert all('✅' not in text for text in logs)
            assert v.tooltip.finish.call_args.kwargs['outcome']==outcome
            assert explorer.call_count==(0 if cancelled else 1)
            if cancelled:assert body==M['key-11']['values'][lang].format(count=count)
    i18n_engine.load_language('zh')


def test_qq_help_keeps_privacy_and_other_existing_paragraphs(monkeypatch):
    from fluent_ui.views.qq_scan_view import QQScanInterface,NICKNAME_NOTICE
    notify=Mock();monkeypatch.setattr('fluent_ui.views.qq_scan_view.notify',notify)
    for lang in LANGS:
        i18n_engine.load_language(lang)
        QQScanInterface.showHelp(SimpleNamespace())
        content=notify.call_args.args[2]
        assert content==DATA['help_binding']['values'][lang]+'\n\n'+str(t(NICKNAME_NOTICE))
        assert M['qq-folder-naming']['values'][lang] in content
        assert '[MISSING:' not in content
    i18n_engine.load_language('zh')


def test_ocr_refresh_distinguishes_wait_complete_and_processed_count():
    from fluent_ui.components.ocr_controls import OcrSettings
    component=SimpleNamespace(installed=True,_sizes=dict(download=100,installed=200),release=lambda:{})
    summary=dict(state='waiting_source',done=2,failed=1,skipped=1,total=6,error='Generated source unavailable')
    service=SimpleNamespace(component=component,install_state='',installing=False,install_error='',summary=summary,
        available=True,library_busy=False,busy=False,storage=SimpleNamespace(index=SimpleNamespace(search_revision=1)))
    v=SimpleNamespace(service=service,_failure_revision=1,_has_failures=False)
    for name in ('component','component_info','size_info','install_button','remove_button','auto','task','task_info','supplement','retry','cancel_button','supplement_group','stop_group','retry_group'):
        setattr(v,name,Mock())
    v.retry.fontMetrics.return_value.horizontalAdvance.return_value=100
    for lang in LANGS:
        i18n_engine.load_language(lang)
        for state,id in [('waiting_source','ocr-096'),('completed','ocr-092')]:
            summary['state']=state
            OcrSettings.refresh(v)
            assert v.task.value_label.setText.call_args.args[0]==M[id]['values'][lang]
            assert v.task_info.setText.call_args.args[0]==M['ocr-097']['values'][lang].format(done=4,total=6,failed=1,skipped=1)+'\n'+M['ocr-098']['values'][lang]
    i18n_engine.load_language('zh')


def test_telegram_three_terminal_states(monkeypatch):
    from fluent_ui.views.tg_sticker_view import TGStickerInterface
    monkeypatch.setattr('subprocess.Popen', Mock())
    v = SimpleNamespace(_current_worker_signal=lambda *_: True, _set_busy=Mock(), log=Mock(), tooltip=Mock())
    for lang in LANGS:
        i18n_engine.load_language(lang)
        for success, failed, id, outcome in [(3,0,'051','success'), (2,1,'052','partial'), (0,3,'053','error')]:
            result = dict(success_count=success, fail_count=failed, output_dir='generated-output')
            TGStickerInterface._onDownloadFinished(v,result)
            title, body = v.tooltip.finish.call_args.args
            assert title == M[id+'-title']['values'][lang]
            assert body == M[id+'-body']['values'][lang].format(success=success,failed=failed)
            assert v.tooltip.finish.call_args.kwargs['outcome'] == outcome
    i18n_engine.load_language('zh')


def test_unknown_telegram_error_keeps_detail(monkeypatch):
    from fluent_ui.views.tg_sticker_view import TGStickerInterface
    monkeypatch.setattr('fluent_ui.views.tg_sticker_view.bind_text',Mock())
    v=SimpleNamespace(_current_worker_signal=lambda *_:True,_set_busy=Mock(),log=Mock(),tooltip=Mock(),previewTitleLabel=object())
    error='Generated network error <untrusted> & detail'
    for lang in LANGS:
        i18n_engine.load_language(lang)
        for method in (TGStickerInterface._onParseFailed,TGStickerInterface._onDownloadFailed,TGStickerInterface._onPackageFailed):
            if method.__name__=='_onPackageFailed':v.window=lambda:SimpleNamespace()
            method(v,error)
            assert v.tooltip.fail.call_args.args[1] == error
        TGStickerInterface._onConnectionResult(v,dict(bot_ok=False,error=error))
        assert error in v.tooltip.fail.call_args.args[1]
        assert '[MISSING:' not in v.tooltip.fail.call_args.args[1]
    i18n_engine.load_language('zh')


def test_batch_dynamic_message_stays_plain():
    from fluent_ui.components.tg_batch_dialog import TGBatchPackageDialog
    cells={}
    def item(row,col):return cells.setdefault((row,col),Mock())
    v=SimpleNamespace(sender=lambda:None,table=SimpleNamespace(item=item),worker=SimpleNamespace(links=['generated-link']))
    message='Generated result\noutput.zip\nA < B & failure'
    for lang in LANGS:
        i18n_engine.load_language(lang)
        TGBatchPackageDialog._progress(v,0,'done',1,1,message)
        assert cells[0,3].setToolTip.call_args.args[0] == message
        assert cells[0,3].setText.call_args.args[0] == message.replace('\n',' ')
    i18n_engine.load_language('zh')


def test_ocr_source_wait_is_a_real_display_state():
    from fluent_ui.components.ocr_controls import TASKS
    assert TASKS['waiting_source'] == M['ocr-096']['source']
    assert TASKS['completed'] == M['ocr-092']['source']


def test_scan_and_collection_metadata_bindings_do_not_claim_import(monkeypatch):
    from fluent_ui.views.qq_scan_view import QQScanInterface
    from fluent_ui.views.tg_sticker_view import TGStickerInterface
    monkeypatch.setattr('fluent_ui.views.tg_sticker_view.bind_text',Mock())
    qq=SimpleNamespace(sender=lambda:None,_discovery_closed=False,_set_busy=Mock(),_sync_result_actions=Mock(),
        log=Mock(),tooltip=Mock(),collapse_config=Mock(),loadMoreEmojis=Mock())
    tg=SimpleNamespace(_current_worker_signal=lambda *_:True,_set_busy=Mock(),previewTitleLabel=object(),
        log=Mock(),tooltip=Mock(),formatComboBox=Mock(),collapse_config=Mock(),loadMoreThumbnails=Mock())
    pack=SimpleNamespace(stickers=[1,2,3],title='Generated title',name='generated',total_count=3,
        type_desc='Generated type',is_animated=False,is_video=False)
    for lang in LANGS:
        i18n_engine.load_language(lang)
        for paths in ([],['generated-a','generated-b','generated-c']):
            QQScanInterface._on_scan_finished(qq,paths)
            assert qq.tooltip.finish.call_args.args[0]==M['key-03']['values'][lang]
            assert qq.tooltip.finish.call_args.args[1]==M['key-05' if paths else 'key-04']['values'][lang].format(count=len(paths))
        QQScanInterface._on_export_progress(qq,1,3,'generated-source','generated-output')
        assert qq.tooltip.update.call_args.args[0]==M['key-09']['values'][lang].format(done=1,total=3,percent=33)
        TGStickerInterface._onParseSuccess(tg,pack)
        assert tg.tooltip.finish.call_args.args[0]==M['key-16']['values'][lang]
        assert tg.tooltip.finish.call_args.args[1]==M['key-17']['values'][lang].format(title=pack.title,total=3)
        assert tg.all_stickers==pack.stickers
    i18n_engine.load_language('zh')
