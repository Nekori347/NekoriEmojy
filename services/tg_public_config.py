"""Read public upstream defaults on demand; never execute downloaded source."""
import ast
import re
import requests
from urllib.parse import urljoin

SOURCES = (
    'https://raw.githubusercontent.com/IxinorTyan/SuzuEmojy/main/services/tg_downloader.py',
    'https://raw.githubusercontent.com/Kiowx/tg_sticker_downloader/main/index.html',
)
MAX_SOURCE_BYTES = 256 * 1024
TOKEN_PATTERN = re.compile(r'[0-9]{5,15}:[A-Za-z0-9_-]{20,100}')


def valid_token(value):
    return isinstance(value, str) and TOKEN_PATTERN.fullmatch(value) is not None


def read_public_token(session, source):
    """Fixed HTTPS URLs, bounded redirects/body, one literal assignment only."""
    if source not in SOURCES:
        return None
    try:
        url = source
        for _ in range(3):
            with session.get(url, timeout=(4, 8), stream=True, allow_redirects=False) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get('Location', ''))
                    if url not in SOURCES:
                        return None
                    continue
                if response.status_code != 200 or response.url not in SOURCES:
                    return None
                if int(response.headers.get('Content-Length', '0')) > MAX_SOURCE_BYTES:
                    return None
                body = bytearray()
                for chunk in response.iter_content(16 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_SOURCE_BYTES:
                        return None
                text = body.decode('utf-8-sig')
            if url.endswith('.py'):
                values = [n.value.value for n in ast.parse(text).body
                          if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
                          and any(isinstance(t, ast.Name) and t.id == 'DEF_TOKEN' for t in n.targets)]
            else:
                values = re.findall(r'\bconst\s+DEF_TOKEN\s*=\s*["\']([0-9]+:[A-Za-z0-9_-]+)["\']\s*;', text)
            return values[0] if len(values) == 1 and valid_token(values[0]) else None
    except (requests.RequestException, ValueError, UnicodeError, SyntaxError, RecursionError, TypeError):
        # Upstream changes, network failures and invalid literals leave config intact.
        return None


def cached_public_token():
    from services.config import ConfigService
    token = ConfigService(defer_create=True).get('tg_public_token_cache')
    return token if valid_token(token) else None


def remember_public_token(token):
    from services.config import ConfigService
    # Read afresh so a download does not overwrite newer unrelated preferences.
    ConfigService(defer_create=True).set('tg_public_token_cache', token)
