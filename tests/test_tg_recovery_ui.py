"""Real Qt signal/feedback checks with controlled network responses only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from threading import Event,get_ident
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from fluent_ui import visual
from fluent_ui.views.tg_sticker_view import TGStickerInterface,ParsePackThread
from services.config import ConfigService
from services.i18n import i18n_engine,t
from services import tg_public_config as public
from services.tg_downloader import TGStickerDownloader
from test_tg_public_recovery import OLD,NEW,Reply,invalid,bot


def wait(app, predicate):
    for _ in range(300):
        app.processEvents()
        if predicate():return
        QTest.qWait(5)
    raise AssertionError('controlled Qt operation did not reach expected state')


@pytest.fixture
def tool(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    config=ConfigService(tmp_path/'app');visual.theme.configure(config);i18n_engine.init(config)
    monkeypatch.setattr(public,'cached_public_token',lambda:OLD)
    monkeypatch.setattr(public,'remember_public_token',Mock())
    monkeypatch.setattr('services.tg_downloader.time.sleep',lambda _:None)
    view=TGStickerInterface();view.resize(980,700);view.show();app.processEvents()
    yield view,app
    view.shutdown();view.close();view.deleteLater();app.processEvents()


def configured(monkeypatch):
    downloader=TGStickerDownloader(timeout=1,retries=1);downloader.session=Mock()
    def request(url,**_):
        if OLD in url:return invalid()
        if url.endswith('/getMe'):return bot()
        return Reply(200,dict(ok=True,result=dict(name='Example',title='Example',stickers=[])))
    downloader.session.get.side_effect=request
    return downloader


@pytest.mark.parametrize('operation',['parse','connection'])
def test_recovery_is_visible_while_network_waits_and_ui_remains_responsive(tool,monkeypatch,operation):
    view,app=tool;downloader=configured(monkeypatch)
    release=Event()
    def fetch(*_):
        if not release.wait(3):raise AssertionError('test release missing')
        return NEW
    monkeypatch.setattr(public,'read_public_token',fetch)
    monkeypatch.setattr(view,'_get_configured_downloader',lambda:downloader)
    messages=[];threads=[];original=view.log
    def log(message):messages.append(message);threads.append(get_ident());original(message)
    monkeypatch.setattr(view,'log',log)
    heartbeat=[];QTimer.singleShot(0,lambda:heartbeat.append(True))
    try:
        if operation=='parse':view.urlInputEdit.setText('Example');view.startParsePack()
        else:view.testNetworkConnection()
        wait(app,lambda:t(public.RECOVERY_MESSAGES['fetch']) in messages)
        assert heartbeat and view._busy and view.tooltip.is_active()
        assert view.tooltip.host.content_label.text()==t(public.RECOVERY_MESSAGES['fetch'])
        assert view.tooltip.host.progress.maximum()==0
    finally:release.set()
    wait(app,lambda:not view._busy)
    stages=[m for m in messages if m in public.RECOVERY_MESSAGES.values()]
    assert stages==[public.RECOVERY_MESSAGES[s] for s in ('start','fetch','verify','success')]
    assert all(thread==get_ident() for thread in threads)
    assert not view.tooltip.is_active() and OLD not in '\n'.join(messages) and NEW not in '\n'.join(messages)


def test_cancel_and_retry_ignore_old_worker_feedback(tool,monkeypatch):
    view,app=tool;release=Event();downloader=configured(monkeypatch)
    monkeypatch.setattr(public,'read_public_token',lambda *_:NEW if release.wait(3) else None)
    monkeypatch.setattr(view,'_get_configured_downloader',lambda:downloader)
    view.urlInputEdit.setText('Example');view.startParsePack();old=view._parse_thread
    try:
        wait(app,lambda:t(public.RECOVERY_MESSAGES['fetch']) in view.log_history)
        view._on_tooltip_closed()
        assert not view._busy and not view.tooltip.is_active()
    finally:release.set()
    wait(app,lambda:not old.isRunning())
    replacement=configured(monkeypatch)
    monkeypatch.setattr(view,'_get_configured_downloader',lambda:replacement)
    view.startParsePack();wait(app,lambda:not view._busy)
    before=list(view.log_history);pack=view.current_pack
    old.recovery_status.emit('start');old.success.emit(SimpleNamespace(name='stale'))
    app.processEvents()
    assert view.log_history==before and view.current_pack is pack and not view.tooltip.is_active()


@pytest.mark.parametrize('outcome',['unavailable','retry_error'])
def test_failed_recovery_or_failed_original_request_ends_loading(tool,monkeypatch,outcome):
    view,app=tool;downloader=configured(monkeypatch)
    monkeypatch.setattr(public,'read_public_token',lambda *_:None if outcome=='unavailable' else NEW)
    if outcome=='retry_error':
        downloader.session.get.side_effect=[invalid(),bot(),requests.Timeout('network failed'),requests.Timeout('network failed')]
    monkeypatch.setattr(view,'_get_configured_downloader',lambda:downloader)
    view.urlInputEdit.setText('Example');view.startParsePack()
    wait(app,lambda:not view._busy)
    assert view.current_pack is None and not view.tooltip.is_active()
    expected=public.RECOVERY_MESSAGES['failed' if outcome=='unavailable' else 'success']
    assert expected in view.log_history
    assert any('解析表情合集失败' in line for line in view.log_history)


def test_four_languages_render_recovery_without_credentials(tool):
    view,app=tool
    worker=view._parse_thread=ParsePackThread(TGStickerDownloader(), 'Example', view)
    view._set_busy(True);view._watch_recovery(worker,foreground=True)
    for language in ('zh','en','ja','zh_TW'):
        i18n_engine.set_language(language)
        for key in public.RECOVERY_MESSAGES.values():
            assert t(key) and (language=='zh' or t(key)!=key)
        for stage,key in public.RECOVERY_MESSAGES.items():
            worker.recovery_status.emit(stage);app.processEvents()
            assert view.log_history[-1]==t(key)
            assert view.tooltip.host.content_label.text()==t(key)
    view._on_tooltip_closed();i18n_engine.set_language('zh')


@pytest.mark.parametrize('custom,proxy',[(False,None),(True,None),(True,'https://configured.invalid')])
def test_batch_preserves_default_vs_user_configuration_identity(tool,monkeypatch,custom,proxy):
    view,_=tool;downloader=TGStickerDownloader(bot_token=OLD if custom else None,cf_proxy=proxy)
    monkeypatch.setattr(view,'_get_configured_downloader',lambda:downloader)
    view.storage=Mock();captured=[]
    class Dialog:
        def __init__(self,parent,directory,config,*args):captured.append(config)
        def exec(self):pass
        def shutdown(self):pass
        def deleteLater(self):pass
    monkeypatch.setattr('fluent_ui.components.tg_batch_dialog.TGBatchPackageDialog',Dialog)
    view.exportBatchPackages()
    recreated=TGStickerDownloader(**captured[0])
    assert recreated._custom_token==custom and recreated._custom_cf_proxy==bool(proxy)
    if proxy:assert recreated.cf_proxy==proxy


def test_batch_table_uses_existing_row_and_ignores_cancelled_or_old_signals(tool,tmp_path):
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QTableWidget,QTableWidgetItem
    from fluent_ui.components.tg_batch_dialog import BatchPackageWorker,TGBatchPackageDialog
    class RowOwner(QObject):
        _progress=TGBatchPackageDialog._progress
    owner=RowOwner();owner.table=QTableWidget(1,4)
    for col in range(4):owner.table.setItem(0,col,QTableWidgetItem(''))
    worker=owner.worker=BatchPackageWorker(['Example'],tmp_path,{},Mock(),Mock())
    worker.progress.connect(owner._progress)
    worker.progress.emit(0,'recovery',0,0,'fetch')
    assert owner.table.item(0,1).text()==t('正在恢复连接')
    assert owner.table.item(0,2).text()=='…'
    assert owner.table.item(0,3).text()==t(public.RECOVERY_MESSAGES['fetch'])
    worker.cancel();worker.progress.emit(0,'cancelled',0,0,'')
    worker.progress.emit(0,'recovery',0,0,'verify')
    assert owner.table.item(0,1).text()==t('已取消')
    owner.worker=BatchPackageWorker(['New'],tmp_path,{},Mock(),Mock())
    worker.progress.emit(0,'failed',0,0,'stale')
    assert owner.table.item(0,1).text()==t('已取消')
    owner.table.close();owner.table.deleteLater()
