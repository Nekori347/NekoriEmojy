"""Data safety contracts use generated resources and isolated program/library trees."""
import json
from pathlib import Path
import sqlite3
import threading
import uuid

from PIL import Image
import pytest

from services.config import ConfigService
from services import library
from services.library import (LibraryBusy, LibraryContext, LibraryError, BootstrapStore,
                              create_library, open_library, copy_library, inspect_library, digest, read_db)
from services.storage import StorageService


def test_reconnect_copy_retains_state_without_hashing(tmp_path, monkeypatch):
    program = tmp_path / "program"
    program.mkdir()
    context = create_library(tmp_path / "图库 中文", program)
    session = open_library(context.root, program)
    storage = StorageService(session)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 24), "red").save(source)
    before = digest(source)
    saved, duplicate = storage.save_file(str(source))
    assert saved and not duplicate and digest(source) == before
    storage.add_category("分类")
    storage.add_category("空分类")
    storage.add_image_to_category(saved, "分类")
    storage.set_category_icon("分类", saved)
    storage.save_order([saved])
    storage.set_image_keywords(saved, "普通 Tag")
    storage.add_recent_image(saved)
    ConfigService(session).set("preview_size", 472)
    bootstrap = BootstrapStore(tmp_path / "bootstrap")
    bootstrap.remember(context)
    session.close()
    bootstrap.path.unlink()
    program.rmdir()  # Only a deliberately empty test program directory.
    monkeypatch.setattr(StorageService, "_repair_orphaned_resources", lambda *a: pytest.fail("unexpected repair"))
    monkeypatch.setattr("services.hasher.compute_sync_key", lambda *a: pytest.fail("unexpected hash scan"))
    original_hashes = {p.name: digest(p) for p in context.data_dir.glob("*.db")}
    session = open_library(context.root, program)
    assert original_hashes == {p.name: digest(p) for p in context.data_dir.glob("*.db")}
    copied = copy_library(session, tmp_path / "搬迁库 空格", program)
    session.close()
    with_source_name = Path(saved).name
    target = StorageService(copied)
    expected = str(copied.resource(with_source_name)).lower()
    assert [p.lower() for p in target.get_all_images()] == [expected]
    assert [p.lower() for p in target.get_images_by_category("分类")] == [expected]
    assert target.get_all_categories()["空分类"] == []
    assert target.get_image_keywords(expected) == "普通 Tag"
    assert target.get_category_icon("分类").lower() == expected
    assert target.get_recent_images()[0].lower() == expected
    assert ConfigService(copied).get("preview_size") == 472
    assert context.images_dir.is_dir() and Path(saved).exists()


def test_missing_future_and_program_nested_library_are_not_initialized(tmp_path):
    program = tmp_path / "app"
    program.mkdir()
    with pytest.raises(LibraryError):
        create_library(program / "data", program)
    missing = tmp_path / "missing"
    with pytest.raises(LibraryError):
        open_library(missing, program)
    assert not missing.exists()
    context = create_library(tmp_path / "future", program)
    for name in library.DATABASES:
        with sqlite3.connect(context.db(name)) as conn:
            conn.execute("PRAGMA user_version=999")
    before = {p.name: digest(p) for p in context.data_dir.glob("*.db")}
    with pytest.raises(LibraryError, match="较新"):
        open_library(context.root, program)
    assert before == {p.name: digest(p) for p in context.data_dir.glob("*.db")}


def test_json_is_not_a_runtime_fallback_or_write_target(tmp_path):
    context = create_library(tmp_path / "library")
    stale = context.data_dir / "categories.json"
    stale.write_text('{"stale":["missing.png"]}', encoding="utf-8")
    before = digest(stale)
    storage = StorageService(context)
    assert storage.get_all_categories() == {}
    storage.add_category("current")
    storage.force_reload()
    assert storage.get_all_categories() == {"current": []}
    assert digest(stale) == before
    assert not (context.data_dir / "config.json").exists()


def test_active_job_prevents_switch_and_old_session_cannot_write_new_library(tmp_path):
    first = create_library(tmp_path / "first")
    second = create_library(tmp_path / "second")
    session = open_library(first.root)
    old = StorageService(session)
    started, release = threading.Event(), threading.Event()
    def task():
        with session.task():
            started.set()
            release.wait(5)
            old.add_category("old task")
    worker = threading.Thread(target=task)
    worker.start()
    assert started.wait(2)
    with pytest.raises(LibraryBusy):
        copy_library(session, tmp_path / "blocked")
    with pytest.raises(LibraryBusy):
        session.close()
    assert not (tmp_path / "blocked").exists()
    release.set()
    worker.join(5)
    assert not worker.is_alive()
    session.close()
    with pytest.raises(LibraryBusy):
        old.add_category("late")
    assert StorageService(second).get_all_categories() == {}
    assert StorageService(first).get_all_categories() == {"old task": []}


def test_schema_upgrade_failure_rolls_back_and_retry_preserves_data(tmp_path, monkeypatch):
    root = tmp_path / "v1"
    (root / "data/images").mkdir(parents=True)
    context = LibraryContext(root, uuid.uuid4().hex)
    library._migrate(context, 0, target=1)
    library.atomic_json(root / "nekori-library.json", {"format": "NekoriEmojy", "version": 1, "library_id": context.library_id})
    with context.transaction() as conn:
        conn.execute("INSERT INTO categories.categories(name) VALUES ('preserve')")
        conn.execute("INSERT INTO preferences VALUES ('preview_size', '433')")
    real = library.MIGRATIONS[2]
    def fail(conn, library_id):
        real(conn, library_id)
        conn.execute("DELETE FROM categories.categories")
        raise RuntimeError("injected upgrade interruption")
    monkeypatch.setitem(library.MIGRATIONS, 2, fail)
    with pytest.raises(RuntimeError, match="interruption"):
        open_library(root)
    assert inspect_library(root)[1] == 1
    with read_db(context.db("categories")) as conn:
        assert conn.execute("SELECT name FROM categories").fetchall() == [("preserve",)]
    snapshots = list((context.data_dir / "snapshots").glob("schema-*/snapshot.json"))
    assert len(snapshots) == 1
    monkeypatch.setitem(library.MIGRATIONS, 2, real)
    session = open_library(root)
    assert inspect_library(root)[1] == library.SCHEMA_VERSION
    assert ConfigService(session).get("preview_size") == 433
    assert StorageService(session).get_all_categories() == {"preserve": []}
    session.close()


def test_copy_failure_keeps_source_and_does_not_activate_target(tmp_path, monkeypatch):
    context = create_library(tmp_path / "source")
    session = open_library(context.root)
    StorageService(session).add_category("kept")
    real_copy = library.shutil.copy2
    def fail(source, target, *args, **kwargs):
        if Path(source).name == "nekori-library.json":
            raise OSError("simulated full target disk")
        return real_copy(source, target, *args, **kwargs)
    monkeypatch.setattr(library.shutil, "copy2", fail)
    target = tmp_path / "target"
    with pytest.raises(OSError):
        copy_library(session, target)
    assert not target.exists()
    assert StorageService(session).get_all_categories() == {"kept": []}
    session.close()


def test_missing_runtime_db_is_not_recreated_by_a_write(tmp_path):
    context = create_library(tmp_path / "library")
    store = StorageService(context)
    context.db("order").unlink()
    with pytest.raises(sqlite3.OperationalError):
        store.save_order([])
    assert not context.db("order").exists()
    with pytest.raises(sqlite3.OperationalError):
        ConfigService(context).set("preview_size", 100)
    assert not context.db("order").exists()
