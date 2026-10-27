"""Bounded recovery reports real stages and respects the initiating task."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

import pytest
import requests

from services import tg_public_config as public
from test_tg_public_recovery import downloader, Reply, OLD, NEW, invalid, bot, success


def test_recovery_phases_precede_their_network_work(downloader, monkeypatch):
    stages=[];downloader.recovery_callback=stages.append
    def fetch(*_):
        assert stages==['start','fetch']
        return NEW
    monkeypatch.setattr(public,'read_public_token',fetch)
    monkeypatch.setattr(public,'remember_public_token',Mock())
    def request(url, **_):
        if OLD in url:return invalid()
        if url.endswith('/getMe'):
            assert stages[-1]=='verify';return bot()
        assert stages[-1]=='success';return success()
    downloader.session.get.side_effect=request
    assert downloader._request_api('getStickerSet')=={'value':'ok'}
    assert stages==['start','fetch','verify','success']


def test_unavailable_sources_end_in_explicit_failure(downloader, monkeypatch):
    stages=[];downloader.recovery_callback=stages.append
    fetch=Mock(return_value=None);monkeypatch.setattr(public,'read_public_token',fetch)
    downloader.session.get.return_value=invalid()
    with pytest.raises(RuntimeError,match='暂时无法恢复默认连接'):
        downloader._request_api('getStickerSet')
    assert stages==['start','fetch','failed'] and fetch.call_count==2


@pytest.mark.parametrize('at',['fetch','verify'])
def test_cancelled_recovery_does_not_verify_cache_or_retry(downloader, monkeypatch, at):
    stages=[];cancelled=[False]
    def stage(value):
        stages.append(value)
        if value==at:cancelled[0]=True
    downloader.recovery_callback=stage;downloader.cancel_check=lambda:cancelled[0]
    monkeypatch.setattr(public,'read_public_token',lambda *_:NEW)
    cache=Mock();monkeypatch.setattr(public,'remember_public_token',cache)
    downloader.session.get.return_value=invalid()
    with pytest.raises(InterruptedError):downloader._request_api('getMe')
    assert downloader.session.get.call_count==1 and downloader.bot_token==OLD
    assert stages[-1]==at and 'success' not in stages and 'failed' not in stages
    cache.assert_not_called()


def test_concurrent_download_workers_share_one_recovery_and_stage_stream(downloader, monkeypatch):
    stages=[];downloader.recovery_callback=stages.append
    fetch=Mock(return_value=NEW);monkeypatch.setattr(public,'read_public_token',fetch)
    monkeypatch.setattr(public,'remember_public_token',Mock())
    entered=Barrier(2)
    def request(url, **_):
        if OLD in url:entered.wait(timeout=2);return invalid()
        return bot() if url.endswith('/getMe') else success()
    downloader.session.get.side_effect=request
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(downloader._request_api,'getStickerSet') for _ in range(2)]
        assert all(j.result(timeout=3)=={'value':'ok'} for j in jobs)
    assert fetch.call_count==1 and stages==['start','fetch','verify','success']


def test_recovered_candidate_does_not_hide_original_request_failure(downloader, monkeypatch):
    stages=[];downloader.recovery_callback=stages.append
    monkeypatch.setattr(public,'read_public_token',lambda *_:NEW)
    monkeypatch.setattr(public,'remember_public_token',Mock())
    downloader.session.get.side_effect=[invalid(),bot(),requests.Timeout('timeout'),requests.Timeout('timeout')]
    with pytest.raises(RuntimeError):downloader._request_api('getStickerSet')
    assert stages[-1]=='success'  # Connection recovery only; the actual operation still failed.


def test_working_token_and_noncredential_errors_have_no_recovery_stages(downloader):
    stages=[];downloader.recovery_callback=stages.append
    downloader.session.get.return_value=success()
    downloader._request_api('getStickerSet')
    assert stages==[]
    for code in (429,400,404):
        downloader.session.get.return_value=Reply(code,dict(ok=False,error_code=code))
        with pytest.raises(RuntimeError):downloader._request_api('getStickerSet')
    downloader.session.get.side_effect=requests.Timeout()
    with pytest.raises(RuntimeError):downloader._request_api('getStickerSet')
    assert stages==[]


@pytest.mark.parametrize('cancel', [False, True])
def test_batch_pipeline_forwards_recovery_and_cancellation(downloader, monkeypatch, cancel):
    from threading import Event
    from services.tg_batch_export import TGPackageBatchRunner
    event=Event();updates=[]
    monkeypatch.setattr(public,'read_public_token',lambda *_:NEW)
    monkeypatch.setattr(public,'remember_public_token',Mock())
    downloader.session.get.side_effect=[invalid(),bot(),Reply(200,dict(ok=True,result=dict(name='Example',stickers=[])))]
    def progress(*args):
        updates.append(args)
        if cancel and args[1]=='recovery' and args[-1]=='fetch':event.set()
    process=Mock(return_value=dict(message='done'))
    result=TGPackageBatchRunner(['Example'],lambda:downloader,process,progress,event).run()
    stages=[args[-1] for args in updates if args[1]=='recovery']
    assert stages==(['start','fetch'] if cancel else ['start','fetch','verify','success'])
    assert result[0]['status']==('cancelled' if cancel else 'done')
    if cancel:process.assert_not_called()
