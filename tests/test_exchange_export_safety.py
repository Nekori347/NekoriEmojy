"""R0.1: output publication and destination safety, with synthetic libraries."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

from PIL import Image
import pytest

from services import exchange_export
from services.exchange_export import ExchangeExportService
from services.exchange_import import ExchangeImportService
from services.library import LibraryError, create_library
from services.storage import StorageService


def file_state(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


@pytest.fixture
def source(tmp_path):
    context = create_library(tmp_path / "library")
    originals = tmp_path / "originals"
    originals.mkdir()
    store = StorageService(context)
    for index, color in enumerate(("red", "blue")):
        path = originals / f"{index}.png"
        Image.new("RGB", (20, 30), color).save(path)
        saved, _ = store.save_file(str(path))
        store.add_image_to_category(saved, "category")
        store.set_image_keywords(saved, "完整关键词")
    return context, originals


def old_backup(target):
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("old-backup.txt", b"keep this previous backup")
    return target.read_bytes()


@pytest.mark.parametrize("existing", [False, True])
def test_success_publishes_valid_compatible_zip(source, tmp_path, existing):
    context, originals = source
    # Similar prefix to the library name must not be rejected as inside it.
    target = tmp_path / "library-backups" / "备份.zip"
    target.parent.mkdir()
    previous = old_backup(target) if existing else None
    before = file_state(context.root), file_state(originals)
    manifest = ExchangeExportService(context).export_zip(target)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read("manifest.json")) == manifest
        assert manifest["format_version"] == 1
        assert manifest["counts"]["assets"] == 2
        assert "old-backup.txt" not in archive.namelist()
    if existing:
        assert target.read_bytes() != previous
    # Exercise the existing reader instead of relying only on ZIP validity.
    destination = create_library(tmp_path / "imported")
    assert ExchangeImportService(destination).import_zip(target) == (2, 0)
    assert (file_state(context.root), file_state(originals)) == before
    assert list(target.parent.glob(".nekori-export-*.tmp")) == []


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", ["progress", "write", "validation", "flush", "replace"])
def test_failures_preserve_backup_library_and_originals(source, tmp_path, monkeypatch, existing, failure):
    context, originals = source
    target = tmp_path / "backup.zip"
    previous = old_backup(target) if existing else None
    before = file_state(context.root), file_state(originals)
    callback = None
    if failure == "progress":
        packed = 0
        def callback(current, total, message):
            nonlocal packed
            if message.startswith("正在打包表情"):
                packed += 1
                if packed == 2:
                    raise RuntimeError("injected progress failure after first asset")
    elif failure == "write":
        original_write = zipfile.ZipFile.writestr
        def fail_write(archive, name, data, *args, **kwargs):
            original_write(archive, name, data, *args, **kwargs)
            if str(name).startswith("assets/"):
                raise OSError("injected asset write failure")
        monkeypatch.setattr(zipfile.ZipFile, "writestr", fail_write)
    elif failure == "validation":
        monkeypatch.setattr(zipfile.ZipFile, "testzip", lambda archive: "injected-bad-member")
    else:
        def fail(*args, **kwargs):
            raise OSError(f"injected {failure} failure")
        monkeypatch.setattr(exchange_export.os, "fsync" if failure == "flush" else "replace", fail)
    with pytest.raises((RuntimeError, OSError, zipfile.BadZipFile)):
        ExchangeExportService(context).export_zip(target, progress_callback=callback)
    if existing:
        assert target.read_bytes() == previous
        with zipfile.ZipFile(target) as archive:
            assert archive.read("old-backup.txt") == b"keep this previous backup"
    else:
        assert not target.exists()
    assert (file_state(context.root), file_state(originals)) == before
    assert list(tmp_path.glob(".nekori-export-*.tmp")) == []


def test_rejects_all_library_destinations_before_any_writes(source, tmp_path, monkeypatch):
    context, originals = source
    before = file_state(context.root), file_state(originals)
    targets = [context.root, context.root / "nekori-library.json",
               *context.data_dir.glob("*.db"), *context.images_dir.iterdir(),
               context.root / "new-directory" / "backup.zip",
               tmp_path / "library" / "data" / ".." / "backup.zip"]
    monkeypatch.chdir(tmp_path)
    targets.append(Path("library/data/library.db"))
    if os.name == "nt":
        targets.append(Path(str(context.db("library")).upper()))
    for target in targets:
        with pytest.raises(LibraryError, match="资源库目录之外"):
            ExchangeExportService(context).export_zip(target)
    assert (file_state(context.root), file_state(originals)) == before
    assert not (context.root / "new-directory").exists()
    assert list(tmp_path.rglob(".nekori-export-*.tmp")) == []


def test_rejects_another_native_library(source, tmp_path):
    context, originals = source
    other = create_library(tmp_path / "other-library")
    before = file_state(other.root), file_state(context.root), file_state(originals)
    for target in (other.db("library"), other.root / "backup.zip"):
        with pytest.raises(LibraryError):
            ExchangeExportService(context).export_zip(target)
    assert (file_state(other.root), file_state(context.root), file_state(originals)) == before


def test_library_alias_cannot_bypass_protection(source, tmp_path):
    context, _ = source
    alias = tmp_path / "library-alias"
    try:
        alias.symlink_to(context.root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory symlink unavailable: {exc}")
    before = file_state(context.root)
    with pytest.raises(LibraryError):
        ExchangeExportService(context).export_zip(alias / "data" / "library.db")
    assert file_state(context.root) == before


def test_completion_notification_cannot_report_committed_export_as_failed(source, tmp_path):
    context, _ = source
    target = tmp_path / "backup.zip"
    old_backup(target)
    notified = []
    def callback(current, total, message):
        if message == "打包完成":
            # Completion is only reported once a usable final file exists.
            with zipfile.ZipFile(target) as archive:
                assert archive.testzip() is None
                assert "manifest.json" in archive.namelist()
            notified.append(message)
            raise RuntimeError("closed UI")
    ExchangeExportService(context).export_zip(target, progress_callback=callback)
    assert notified == ["打包完成"]
    with zipfile.ZipFile(target) as archive:
        assert "manifest.json" in archive.namelist()
    assert list(tmp_path.glob(".nekori-export-*.tmp")) == []
