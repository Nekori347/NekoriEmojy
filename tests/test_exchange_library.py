from pathlib import Path

from PIL import Image
import pytest

from services.exchange_export import ExchangeExportService
from services.exchange_import import ExchangeImportError, ExchangeImportService
from services.library import create_library, read_db
from services.storage import StorageService


def package(tmp_path):
    source = create_library(tmp_path / "source")
    image = tmp_path / "source.png"
    Image.new("RGB", (20, 30), "red").save(image)
    store = StorageService(source)
    saved, _ = store.save_file(str(image))
    store.add_category("category")
    store.add_category("empty")
    store.add_image_to_category(saved, "category")
    store.set_image_keywords(saved, "keyword")
    target = tmp_path / "exchange.zip"
    ExchangeExportService(source).export_zip(str(target))
    return target


def test_exchange_uses_selected_library_and_keeps_idempotence(tmp_path):
    archive = package(tmp_path)
    target = create_library(tmp_path / "target")
    importer = ExchangeImportService(target)
    assert importer.import_zip(archive) == (1, 0)
    assert importer.import_zip(archive) == (0, 1)
    store = StorageService(target)
    images = store.get_all_images()
    assert len(images) == 1
    assert store.get_images_by_category("category") == images
    assert store.get_image_keywords(images[0]) == "keyword"
    assert store.get_all_categories()["empty"] == []


def test_exchange_failure_rolls_back_all_databases_and_new_files(tmp_path, monkeypatch):
    archive = package(tmp_path)
    target = create_library(tmp_path / "target")
    importer = ExchangeImportService(target)
    def fail(*args):
        raise RuntimeError("injected during metadata insert")
    monkeypatch.setattr(importer, "_insert_metadata", fail)
    with pytest.raises(ExchangeImportError, match="injected"):
        importer.import_zip(archive)
    for database, table in (("features", "image_features"), ("metadata", "image_metadata"),
                            ("categories", "category_images"), ("order", "item_orders")):
        with read_db(target.db(database)) as conn:
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert list(target.images_dir.iterdir()) == []


def test_post_commit_notification_failure_does_not_delete_import(tmp_path):
    archive = package(tmp_path)
    target = create_library(tmp_path / "target")
    def callback(current, total, text):
        if text == "导入完成":
            raise RuntimeError("closed UI")
    assert ExchangeImportService(target).import_zip(archive, callback) == (1, 0)
    assert len(StorageService(target).get_all_images()) == 1
