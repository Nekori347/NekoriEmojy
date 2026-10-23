"""Exercise the real MIME conversion boundary, not the advertised drop action."""
import json
import os
from pathlib import Path

from services.external_drag import ResourceDragMimeData
from fluent_ui.components.drop_contract import RESOURCE_MIME, DragSession


def test_external_file_is_independent_and_internal_payload_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    source=tmp_path/'library'/'image.gif';source.parent.mkdir();source.write_bytes(b'GIF89a-sample')
    mime=ResourceDragMimeData([str(source)])
    assert mime.hasUrls() and mime.hasText()
    assert DragSession(mime).payload == (str(source),)
    assert not (tmp_path/'app').exists()  # internal receiver does not export files
    export=Path(mime.urls()[0].toLocalFile())
    assert export != source and export.read_bytes()==source.read_bytes()
    assert export.stat().st_ino != source.stat().st_ino  # no hard link
    assert mime.text()==str(export) and str(source) not in mime.text()
    assert json.loads(bytes(mime.data(RESOURCE_MIME))) == [str(source)]
    export.unlink()  # a destructive target can only remove its independent copy
    assert source.read_bytes()==b'GIF89a-sample'


def test_export_survives_mime_lifetime_and_preserves_duplicate_names(tmp_path,monkeypatch):
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    sources=[]
    for i in range(2):
        path=tmp_path/str(i)/'face.png';path.parent.mkdir();path.write_bytes(bytes([i]));sources.append(str(path))
    mime=ResourceDragMimeData(sources)
    urls=[Path(url.toLocalFile()) for url in mime.urls()]
    assert len(set(urls))==2 and all(path.name=='face.png' for path in urls)
    del mime
    assert [path.read_bytes() for path in urls]==[b'\x00',b'\x01']


def test_copy_failure_never_exposes_source_or_partial_batch(tmp_path,monkeypatch):
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    source=tmp_path/'face.png';source.write_bytes(b'original')
    mime=ResourceDragMimeData([str(source),str(source)])
    import shutil
    copy=shutil.copyfile;calls=[]
    def fail(*args):
        calls.append(args)
        if len(calls)==2:raise OSError('disk full')
        return copy(*args)
    monkeypatch.setattr('services.external_drag.shutil.copyfile',fail)
    assert mime.urls()==[] and mime.text()=='' and mime.error is not None
    assert source.read_bytes()==b'original'


def test_old_exports_reclaimed_without_removing_recent_deliveries(tmp_path,monkeypatch):
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    root=tmp_path/'app/cache/external_drag';root.mkdir(parents=True)
    old=root/'drag-old';old.mkdir();(old/'file').write_bytes(b'old');os.utime(old,(1,1))
    recent=root/'drag-recent';recent.mkdir();(recent/'file').write_bytes(b'recent')
    source=tmp_path/'face.png';source.write_bytes(b'original')
    assert ResourceDragMimeData([str(source)]).urls()
    assert not old.exists() and (recent/'file').is_file()
