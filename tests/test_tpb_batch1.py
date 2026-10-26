"""Locked first-batch copy and real Qt binding checks on generated data only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
from string import Formatter
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from services.i18n import i18n_engine,t
from services.action_policy import ActionPolicy
from test_phase2_interaction import surface,settle

DATA=json.loads((Path(__file__).parent/'fixtures/tpb_batch1_copy.json').read_text(encoding='utf-8'))
M=DATA['approved']
LANGS=('zh','zh_TW','en','ja')


def pieces(id,lang):
    lines=M[id][lang].splitlines()
    if id=='141':
        prefixes={'zh':('名称：','副描述：'),'zh_TW':('名稱：','副描述：'),
                  'en':('Name: ','Description: '),'ja':('名前：','説明：')}[lang]
        return [line.removeprefix(prefix) for line,prefix in zip(lines,prefixes)]
    return lines


def test_all_approved_language_values_and_placeholders_are_exact():
    root=Path(__file__).resolve().parents[1]
    fields=lambda text:sorted(name for _,name,_,_ in Formatter().parse(text) if name is not None)
    for lang in LANGS:
        actual=json.loads((root/'translations'/f'{lang}.json').read_text(encoding='utf-8'))
        for id in M:
            sources=pieces(id,'zh') if id in ('141','222') else [M[id]['zh']]
            expected=pieces(id,lang) if id in ('141','222') else [M[id][lang]]
            for source,value in zip(sources,expected):
                assert actual[source]==value,(id,lang)
                assert fields(source)==fields(value),(id,lang)
        if lang=='zh_TW':
            for value in DATA['partial'].values():assert actual[value['source']]==value['zh_TW']


def test_sort_refresh_and_language_switch_do_not_translate_composed_text(surface):
    g=surface.g
    before=surface.storage.entries_of(surface.parent)
    for lang in LANGS:
        i18n_engine.load_language(lang);settle(surface.app)
        for mode,label in [('manual','自定义顺序'),('recent_added','最近添加'),('oldest_added','最早添加')]:
            g.set_content_sort(mode);g._update_resource_sort_label()
            assert g.btn_content_sort.toolTip()==str(t('表情显示排序'))+' · '+str(t(label))
            assert '[MISSING:' not in g.btn_content_sort.toolTip()
        assert surface.storage.entries_of(surface.parent)==before
    i18n_engine.load_language('zh')


def test_management_sources_survive_refresh_and_disabled_reasons_win(surface):
    g=surface.g;g.set_mode('manage')
    for lang in LANGS:
        i18n_engine.load_language(lang)
        g._select_single(surface.paths[0]);g._sync_command_bar()
        for button,id in [(g.btn_add_to,'062'),(g.btn_move_to,'063'),(g.btn_tags,'064'),(g.btn_arrange,'065')]:
            assert button.toolTip()==M[id][lang]
        for paths in ([surface.paths[0]],[surface.paths[2]],[surface.paths[0],surface.paths[2]]):
            g.selected_keys=set(paths);g._sync_command_bar()
            expected=str(t(ActionPolicy.delete_label(g._action_context(paths))))
            assert g.btn_delete.toolTip()==expected
            menu=g._build_resource_menu(SimpleNamespace(image_path=paths[0],content_entry={'_parent':surface.parent}))
            assert expected in [a.text() for a in menu.actions()]
            menu.deleteLater()
        g.selected_keys={surface.child};g._sync_command_bar()
        for button in (g.btn_add_to,g.btn_tags,g.btn_delete,g.btn_more):
            assert not button.isEnabled() and button.toolTip()==M['058'][lang]
        assert g.btn_move_to.isEnabled() and g.btn_move_to.toolTip()==t('移动到分类')
        g.selected_keys={surface.child,surface.paths[0]};g._sync_command_bar()
        assert not g.btn_move_to.isEnabled() and g.btn_move_to.toolTip()==M['059'][lang]
        assert g.selected_count_label.text()==M['061'][lang].format(value_0=2,value_1=1,value_2=1)
    i18n_engine.load_language('zh')


@pytest.mark.parametrize('lang',LANGS)
def test_telegram_menu_progress_and_failure_copy(surface,monkeypatch,lang):
    from fluent_ui.views.tg_sticker_view import TGStickerInterface
    from fluent_ui.components import dialogs
    monkeypatch.setattr('requests.sessions.Session.request',Mock(side_effect=AssertionError('No network in copy tests')))
    i18n_engine.load_language(lang)
    view=TGStickerInterface();view.storage=surface.storage
    view.current_pack=SimpleNamespace(title='Generated collection',source_url='');view.all_stickers=[SimpleNamespace(index=0)]
    view.resize(980,700);view.show();settle(surface.app)
    try:
        assert view.exportPackageButton.text()==M['220'][lang]
        from fluent_ui.components.safe_round_menu import SafeRoundMenu
        menus=[]
        monkeypatch.setattr(SafeRoundMenu,'_show_menu',lambda menu,*_:menus.append([a.text() for a in menu.actions()]))
        view.presentation.show_exports()
        assert M['220'][lang] in menus[-1]
        i18n_engine.load_language('zh' if lang!='zh' else 'en');settle(surface.app)
        assert view.exportPackageButton.text()==M['220'][i18n_engine.current_lang]
        i18n_engine.load_language(lang)
        # Keep file/network/import work outside this UI copy check.
        prompt=Mock(return_value=('Generated collection',True))
        monkeypatch.setattr(dialogs,'prompt_text',prompt)
        monkeypatch.setattr('fluent_ui.views.tg_sticker_view.QFileDialog.getExistingDirectory',lambda *_:str(surface.tmp))
        worker=Mock();factory=Mock(return_value=worker)
        monkeypatch.setattr('fluent_ui.views.tg_sticker_view.ImportPackThread',factory)
        progress=Mock();view.tooltip.show=progress
        view.exportPackage()
        progress.assert_called_once_with(t('正在导出表情合集'),M['225'][lang])
        worker.start.assert_called_once()
        errors=Mock();view.tooltip.fail=errors
        view._onPackageFailed('Generated detailed reason')
        assert errors.call_args.args[0]==M['229'][lang]
        assert 'Generated detailed reason' in errors.call_args.args[1]
    finally:
        view._import_thread=None
        view.shutdown();view.close();view.deleteLater();settle(surface.app)
        i18n_engine.load_language('zh')


def test_telegram_partial_import_keeps_specific_reason_in_locked_error(surface):
    from fluent_ui.views.tg_sticker_view import ImportPackThread
    storage=SimpleNamespace(add_category=Mock(),save_file=Mock(side_effect=ValueError('Generated failure')))
    for lang in LANGS:
        i18n_engine.load_language(lang)
        worker=ImportPackThread(SimpleNamespace(),storage,[SimpleNamespace(index=0)],'Generated collection',
                                export_path='unused.zip',prepared_sources={0:'unused'})
        worker._export_resource_package=Mock()
        errors=[];worker.failed.connect(errors.append);worker.run()
        assert errors and errors[0].startswith(M['226'][lang]+'\n')
        assert 'Generated failure' in errors[0]
        worker._export_resource_package.assert_not_called()
    i18n_engine.load_language('zh')
