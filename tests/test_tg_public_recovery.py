"""Public defaults recover only from authoritative credential failure."""
import json
from unittest.mock import Mock

import pytest
import requests

from services import tg_public_config as public
from services.tg_downloader import TGStickerDownloader, TG_DIRECT_API

OLD = '111111111:' + 'a' * 35
NEW = '222222222:' + 'b' * 35


class Reply:
    def __init__(self, status=200, data=None, *, body=None, url=TG_DIRECT_API, headers=None):
        self.status_code = status; self.data = data; self.url = url
        self.headers = headers or {}
        self.body = body if body is not None else json.dumps(data).encode()
    def json(self):return self.data
    def close(self):pass
    @property
    def content(self):return self.body
    def raise_for_status(self):
        if self.status_code >= 400:raise requests.HTTPError('request failed')
    def __enter__(self):return self
    def __exit__(self, *_):self.close()
    def iter_content(self, size):
        for i in range(0, len(self.body), size):yield self.body[i:i+size]


@pytest.fixture
def downloader(monkeypatch):
    monkeypatch.setattr(public, 'cached_public_token', lambda: OLD)
    monkeypatch.setattr('services.tg_downloader.time.sleep', lambda _: None)
    d = TGStickerDownloader(retries=1); d.session = Mock()
    return d


def invalid():return Reply(401, dict(ok=False, error_code=401, description='Unauthorized'))
def bot():return Reply(200, dict(ok=True, result=dict(is_bot=True, id=1)))
def success():return Reply(200, dict(ok=True, result=dict(value='ok')))


@pytest.mark.parametrize('secondary', [False, True])
def test_official_auth_failure_recovers_once_in_source_order(downloader, monkeypatch, secondary):
    fetch = Mock(side_effect=[None, NEW] if secondary else [NEW])
    cache = Mock();monkeypatch.setattr(public, 'read_public_token', fetch)
    monkeypatch.setattr(public, 'remember_public_token', cache)
    downloader.session.get.side_effect = [invalid(), bot(), success(), success()]
    assert downloader._request_api('getStickerSet') == {'value':'ok'}
    assert downloader.bot_token == NEW
    cache.assert_called_once_with(NEW)
    assert [c.args[1] for c in fetch.call_args_list] == list(public.SOURCES[:2 if secondary else 1])
    assert downloader._request_api('getStickerSet') == {'value':'ok'}
    assert fetch.call_count == (2 if secondary else 1)


@pytest.mark.parametrize('failure', ['timeout', 'dns', '429', '400', '404', 'proxy401'])
def test_other_failures_never_fetch_or_rotate(downloader, monkeypatch, failure):
    fetch = Mock();monkeypatch.setattr(public, 'read_public_token', fetch)
    if failure in ('timeout','dns'):
        downloader.session.get.side_effect = requests.Timeout() if failure=='timeout' else requests.ConnectionError()
    elif failure=='proxy401':
        downloader.prefer_direct=False
        downloader.session.get.side_effect=[invalid(), requests.Timeout()]
    else:
        code=int(failure)
        downloader.session.get.return_value=Reply(code,dict(ok=False,error_code=code,description='Unavailable'))
    with pytest.raises(RuntimeError):downloader._request_api('getStickerSet')
    fetch.assert_not_called();assert downloader.bot_token==OLD


def test_custom_token_has_priority_and_no_implicit_worker(monkeypatch):
    fetch=Mock();monkeypatch.setattr(public,'read_public_token',fetch)
    d=TGStickerDownloader(bot_token=OLD,retries=1);d.session=Mock()
    d.session.get.return_value=invalid()
    with pytest.raises(RuntimeError):d._request_api('getMe')
    fetch.assert_not_called();assert d.bot_token==OLD and d.candidate_bases==[TG_DIRECT_API]
    configured=TGStickerDownloader(bot_token=OLD,cf_proxy='http://custom.invalid')
    assert 'http://custom.invalid' in configured.candidate_bases


def test_failed_candidates_are_bounded_and_do_not_change_cache(downloader, monkeypatch):
    fetch=Mock(return_value=NEW);cache=Mock()
    monkeypatch.setattr(public,'read_public_token',fetch);monkeypatch.setattr(public,'remember_public_token',cache)
    downloader.session.get.return_value=invalid()
    for _ in range(2):
        with pytest.raises(RuntimeError):downloader._request_api('getMe')
    assert fetch.call_count==2 and downloader.bot_token==OLD
    cache.assert_not_called()


def test_network_errors_cannot_expose_token_or_proxy_credentials(downloader):
    downloader.session.get.side_effect=requests.ConnectionError('https://user:password@example.invalid/bot'+OLD+'/getMe')
    result=downloader.test_connection()
    assert not result['bot_ok']
    assert OLD not in result['error'] and 'password' not in result['error']


def test_candidate_rate_limit_stops_recovery_without_trying_another_bot(downloader, monkeypatch):
    fetch=Mock(return_value=NEW);monkeypatch.setattr(public,'read_public_token',fetch)
    downloader.session.get.side_effect=[invalid(),Reply(429,dict(ok=False,error_code=429))]
    with pytest.raises(RuntimeError):downloader._request_api('getMe')
    assert fetch.call_count==1 and downloader.bot_token==OLD


def test_file_download_can_recover_public_credentials_once(downloader, monkeypatch):
    monkeypatch.setattr(public,'read_public_token',lambda *_:NEW)
    monkeypatch.setattr(public,'remember_public_token',Mock())
    downloader.session.get.side_effect=[invalid(),bot(),Reply(body=b'original gif bytes')]
    assert downloader.download_file_bytes('stickers/file.gif')==b'original gif bytes'
    assert downloader.bot_token==NEW


def test_public_cache_uses_existing_config_and_survives_recreation(tmp_path, monkeypatch):
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    public.remember_public_token(NEW)
    assert public.cached_public_token()==NEW
    assert TGStickerDownloader().bot_token==NEW


@pytest.mark.parametrize('source', public.SOURCES)
def test_fixed_source_extracts_literal_without_executing_it(source, tmp_path):
    marker=tmp_path/'must-not-exist'
    text=(f'from pathlib import Path\nPath({str(marker)!r}).touch()\nDEF_TOKEN = {NEW!r}'
          if source.endswith('.py') else f'<script>const DEF_TOKEN = "{NEW}";</script>')
    session=Mock();session.get.return_value=Reply(body=text.encode(),url=source)
    assert public.read_public_token(session,source)==NEW
    assert not marker.exists()


@pytest.mark.parametrize('case',['http_redirect','other_host','oversize','malformed'])
def test_public_source_rejects_unsafe_or_unbounded_response(case):
    source=public.SOURCES[0];session=Mock()
    if case=='http_redirect':reply=Reply(302,url=source,headers={'Location':'http://raw.githubusercontent.com/x'})
    elif case=='other_host':reply=Reply(url='https://other.invalid',body=b'')
    elif case=='oversize':reply=Reply(url=source,body=b'x'*(public.MAX_SOURCE_BYTES+1))
    else:reply=Reply(url=source,body=b'DEF_TOKEN = unknown_call()')
    session.get.return_value=reply
    assert public.read_public_token(session,source) is None
    assert session.get.call_count==1
