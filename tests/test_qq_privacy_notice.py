"""Disclosure at existing help/confirmation; nickname behavior stays intact."""
import json,time
from urllib.parse import urlsplit,parse_qs
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem
from test_qq_lifecycle import qq,wait


def test_help_and_existing_export_confirm_explain_query_before_it_runs(qq,tmp_path,monkeypatch):
    from fluent_ui.views import qq_scan_view as module
    from services.i18n import i18n_engine
    view,root,app=qq;wait(lambda:not view._discovery_workers)
    path=root/'800001/nt_qq/nt_data/Emoji/personal_emoji/Ori/fixture.png'
    from PIL import Image
    Image.new('RGB',(20,20),'blue').save(path)
    view.emoji_file_paths=[str(path)];item=QListWidgetItem('fixture');item.setData(Qt.UserRole,str(path))
    view.previewListWidget.addItem(item);item.setSelected(True)
    view.savePath=str(tmp_path)
    notices=[];confirms=[]
    monkeypatch.setattr(module,'notify',lambda _owner,_title,message,*a,**kw:notices.append(message))
    monkeypatch.setattr(module.dialogs,'confirm',lambda *a,**kw:confirms.append(kw) or False)
    def unexpected(*a):raise AssertionError('No nickname request before export confirmation')
    monkeypatch.setattr(module.QQExtractor,'get_display_name',unexpected)
    try:
        for lang in ('zh','zh_TW','en','ja'):
            i18n_engine.load_language(lang)
            view.showHelp();view.exportSelected();view.exportAll()
            text=module.t(module.NICKNAME_NOTICE)
            assert 'uapis.cn' in text and '24' in text and 'QQ' in text
            assert text in notices[-1] and all(c['hint']==text for c in confirms[-2:])
    finally:i18n_engine.load_language('zh')


def test_nickname_get_request_and_one_day_cache_are_preserved(tmp_path,monkeypatch):
    import urllib.request
    from services.qq_extractor import QQExtractor
    cache=tmp_path/'nicknames.json';calls=[]
    monkeypatch.setattr(QQExtractor,'get_nickname_cache_path',staticmethod(lambda:str(cache)))
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return json.dumps({'nickname':'Fixture nickname'}).encode()
    def request(req,timeout):
        calls.append(req)
        assert urlsplit(req.full_url).hostname=='uapis.cn'
        assert parse_qs(urlsplit(req.full_url).query)=={'qq':['800001']}
        assert req.get_method()=='GET' and req.data is None and timeout==3
        return Response()
    monkeypatch.setattr(urllib.request,'urlopen',request)
    before=int(time.time())
    assert QQExtractor.get_display_name('800001')=='Fixture nickname（800001）'
    assert QQExtractor.get_display_name('800001')=='Fixture nickname（800001）'
    assert len(calls)==1
    stored=json.loads(cache.read_text(encoding='utf-8'))['800001']
    assert before+86400<=stored['username_expire_time']<=int(time.time())+86400
