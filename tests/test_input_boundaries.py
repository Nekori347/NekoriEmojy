"""Untrusted package and image inputs stay inside their existing import boundary."""
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from services.nekori_package import NekoriPackageService, NekoriPackageError
from test_storage_single_frame_gif import _make_storage


@pytest.mark.parametrize('relative', [False, True])
def test_native_manifest_cannot_import_an_outside_image(tmp_path, monkeypatch, relative):
    storage = _make_storage(tmp_path / 'target')
    private = tmp_path / 'private.png'
    Image.new('RGB', (10, 10), 'red').save(private)
    stage = tmp_path / 'stage'; stage.mkdir()
    monkeypatch.setattr('services.nekori_package.tempfile.mkdtemp', lambda **_: str(stage))
    package = tmp_path / 'input.zip'
    manifest = dict(format='nekori-package', version=1, nodes=[], resources=[
        dict(id='outside', package_path='../private.png' if relative else str(private))])
    with zipfile.ZipFile(package, 'w') as z:
        z.writestr('nekori.json', json.dumps(manifest))
    with pytest.raises(NekoriPackageError):
        NekoriPackageService(storage).import_package(package)
    assert storage.index.resources() == [] and private.is_file()


@pytest.mark.parametrize('name', ['../outside.png', '/outside.png', 'C:/outside.png', 'images/../../outside.png', '.. /outside.png', 'NUL'])
def test_native_archive_rejects_unsafe_members_before_restore(tmp_path, name):
    storage = _make_storage(tmp_path / 'target')
    package = tmp_path / 'input.zip'
    with zipfile.ZipFile(package, 'w') as z:
        z.writestr('nekori.json', json.dumps(dict(format='nekori-package', nodes=[], resources=[])))
        z.writestr(name, b'not an image')
    with pytest.raises(NekoriPackageError):
        NekoriPackageService(storage).import_package(package)


def test_native_icon_reference_cannot_retain_a_local_image_path(tmp_path):
    storage = _make_storage(tmp_path / 'target')
    private = tmp_path / 'private.png'
    Image.new('RGB', (10, 10), 'blue').save(private)
    package = tmp_path / 'input.zip'
    with zipfile.ZipFile(package, 'w') as z:
        z.writestr('nekori.json', json.dumps(dict(format='nekori-package', resources=[], nodes=[
            dict(id='node', name='Node', icon=str(private))])))
    with pytest.raises(NekoriPackageError):
        NekoriPackageService(storage).import_package(package)
    assert storage.index.nodes() == []


@pytest.mark.parametrize('limit', ['MAX_PACKAGE_BYTES', 'MAX_PACKAGE_FILES', 'MAX_MANIFEST_BYTES'])
def test_native_limits_reject_before_any_restore(tmp_path, monkeypatch, limit):
    import services.nekori_package as native
    monkeypatch.setattr(native, limit, 1)
    storage = _make_storage(tmp_path / 'target')
    package = tmp_path / 'input.zip'
    with zipfile.ZipFile(package, 'w') as z:
        z.writestr('./nekori.json', json.dumps(dict(format='nekori-package', nodes=[], resources=[])))
        z.writestr('images/empty.png', b'')
    with pytest.raises(NekoriPackageError):
        NekoriPackageService(storage).import_package(package)
    assert storage.index.resources() == [] and storage.index.nodes() == []


def test_exchange_text_icon_cannot_retain_a_local_image_path(tmp_path):
    from services.exchange_import import ExchangeImportService
    service = ExchangeImportService(storage=_make_storage(tmp_path / 'target'))
    catalog = {'categories': [dict(ref='node', name='Node',
                                   icon=dict(type='text', text=str(tmp_path / 'private.png')))]}
    assert service._parse_icons(catalog, tmp_path) == {} and service.warnings
    catalog['categories'][0]['icon']['text'] = '🙂'
    assert service._parse_icons(catalog, tmp_path) == {'node': '🙂'}


def test_native_export_carries_icon_asset_without_original_absolute_path(tmp_path):
    storage = _make_storage(tmp_path / 'target')
    source = tmp_path / 'legacy-icon.png'
    Image.new('RGB', (10, 10), 'blue').save(source)
    node = storage.index.create_node('Node')
    storage.index.update_node(node, icon=str(source))
    package = tmp_path / 'output.zip'
    NekoriPackageService(storage).export(package)
    with zipfile.ZipFile(package) as z:
        data = json.loads(z.read('nekori.json'))
        exported = data['nodes'][0]
        assert exported['icon'] == '' and 'icon_asset' in exported
        assert z.read(exported['icon_asset']) == source.read_bytes()
        assert str(source) not in json.dumps(data, ensure_ascii=False)


def test_native_shared_and_same_named_icons_export_without_duplicate_members(tmp_path):
    storage = _make_storage(tmp_path / 'target')
    first = tmp_path / 'one' / 'icon.png'; first.parent.mkdir()
    second = tmp_path / 'two' / 'icon.png'; second.parent.mkdir()
    Image.new('RGB', (10, 10), 'blue').save(first)
    Image.new('RGB', (10, 10), 'green').save(second)
    for name, source in [('First',first),('Shared',first),('Other',second)]:
        node = storage.index.create_node(name); storage.index.update_node(node, icon=str(source))
    package = tmp_path / 'output.zip'
    NekoriPackageService(storage).export(package)
    with zipfile.ZipFile(package) as z:
        assert len(z.namelist()) == len(set(z.namelist()))
        nodes = {n['name']:n for n in json.loads(z.read('nekori.json'))['nodes']}
        assert nodes['First']['icon_asset'] == nodes['Shared']['icon_asset']
        assert z.read(nodes['First']['icon_asset']) == first.read_bytes()
        assert z.read(nodes['Other']['icon_asset']) == second.read_bytes()
    recipient = _make_storage(tmp_path / 'recipient')
    assert NekoriPackageService(recipient).import_package(package)['nodes'] == 3


@pytest.mark.parametrize('same', [True, False])
def test_legacy_repeated_icons_require_identical_bytes(tmp_path, same):
    import warnings
    storage = _make_storage(tmp_path / 'target')
    package = tmp_path / 'legacy.zip'
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(package, 'w') as z:
            z.writestr('nekori.json', json.dumps(dict(format='nekori-package', nodes=[], resources=[])))
            z.writestr('icons/shared.png', b'same bytes')
            z.writestr('icons/shared.png', b'same bytes' if same else b'other data')
    if same:
        assert NekoriPackageService(storage).import_package(package)['resources'] == 0
    else:
        with pytest.raises(NekoriPackageError):NekoriPackageService(storage).import_package(package)


@pytest.mark.parametrize('declared', [False, True])
def test_image_url_download_is_bounded_and_cleans_partial_file(tmp_path, monkeypatch, declared):
    from unittest.mock import Mock
    from fluent_ui.views.gallery_view import DownloadThread
    import fluent_ui.views.gallery_view as gallery
    monkeypatch.setattr(gallery, 'MAX_IMAGE_DOWNLOAD_BYTES', 3)
    response = Mock(headers={'Content-Type': 'image/gif', 'Content-Length': '4' if declared else '0'})
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.side_effect = [b'1234', b'']
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **kw: response)
    import tempfile
    original = tempfile.mkstemp
    created = []
    def allocate(**kw):
        fd, name = original(dir=tmp_path, **kw); created.append(name); return fd, name
    monkeypatch.setattr(tempfile, 'mkstemp', allocate)
    thread = DownloadThread('https://example.invalid/image.gif')
    results = []; thread.finished.connect(lambda *args: results.append(args))
    thread.run()
    assert results and results[0][0] is False
    assert all(not Path(p).exists() for p in created)
    if not declared:response.read.assert_called_with(64 * 1024)


def test_image_url_stream_preserves_original_bytes(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from fluent_ui.views.gallery_view import DownloadThread
    response = Mock(headers={'Content-Type': 'image/gif'})
    response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
    response.read.side_effect = [b'GIF89a', b'original', b'']
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **kw: response)
    thread = DownloadThread('https://example.invalid/image.gif')
    results = []; thread.finished.connect(lambda *args: results.append(args)); thread.run()
    assert results[0][0] is True
    saved = Path(results[0][1])
    try:assert saved.read_bytes() == b'GIF89aoriginal'
    finally:saved.unlink()
