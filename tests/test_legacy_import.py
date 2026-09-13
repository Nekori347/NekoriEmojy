import json
from pathlib import Path
import sqlite3

from PIL import Image
import pytest

from services.library import LibraryError, read_db
from services.legacy_import import migrate_legacy, inventory, LegacyConflict
from services.storage import StorageService
from services.config import ConfigService


def make_source(tmp_path):
    root = tmp_path / "旧 data"
    (root / "images").mkdir(parents=True)
    Image.new("RGB", (16, 16), "red").save(root / "images/a.png")
    Image.new("RGB", (16, 16), "blue").save(root / "images/b.png")
    values = {"categories": {"分类": ["a.png", "b.png"], "空分类": []},
              "order": ["b.png", "a.png"], "metadata": {"a.png": "标签"},
              "category_icons": {"分类": "a.png"}, "recent": ["b.png", "a.png"],
              "config": {"preview_size": 451}}
    for name, value in values.items():
        (root / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return root


def test_json_only_migration_preserves_source_relations_order_and_settings(tmp_path):
    source = make_source(tmp_path)
    before = inventory(source)
    context, report = migrate_legacy(source, tmp_path / "new", source_closed=True)
    assert inventory(source) == before
    assert report["target_counts"] == {"images": 2, "categories": 2, "relations": 2, "order": 2,
                                        "metadata": 1, "settings": 1, "skipped": 0, "failed": 0}
    storage = StorageService(context)
    assert [Path(p).name for p in storage.get_all_images()] == ["b.png", "a.png"]
    assert storage.get_all_categories()["空分类"] == []
    assert storage.get_image_keywords(str(context.images_dir / "a.png")) == "标签"
    assert ConfigService(context).get("preview_size") == 451
    snapshots = list((context.data_dir / "snapshots").glob("suzu-*"))
    assert inventory(snapshots[0]) == before
    with pytest.raises(LibraryError):
        migrate_legacy(source, context.root, source_closed=True)
    assert inventory(source) == before


def test_empty_db_does_not_override_nonempty_json_without_choice(tmp_path):
    source = make_source(tmp_path)
    with sqlite3.connect(source / "categories.db") as conn:
        conn.execute("CREATE TABLE categories(id INTEGER PRIMARY KEY,name TEXT,icon_path TEXT,sort_order INTEGER)")
        conn.execute("CREATE TABLE category_images(category_name TEXT,image_path TEXT)")
    before = inventory(source)
    with pytest.raises(LegacyConflict) as caught:
        migrate_legacy(source, tmp_path / "new", source_closed=True)
    assert caught.value.report["source_counts"]["db"]["categories"] == 0
    assert caught.value.report["source_counts"]["json"]["categories"] == 2
    assert set(caught.value.report["conflicts"]) == {"categories", "icons"}
    assert not (tmp_path / "new").exists()
    context, report = migrate_legacy(source, tmp_path / "new", source_closed=True,
                                     choices={"categories": "json", "icons": "json"})
    assert report["target_counts"]["relations"] == 2
    assert inventory(source) == before


def test_unclosed_source_is_refused_before_creating_target(tmp_path):
    source = make_source(tmp_path)
    with pytest.raises(LibraryError, match="关闭"):
        migrate_legacy(source, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_old_drive_references_and_missing_relations_are_reported(tmp_path):
    source = make_source(tmp_path)
    (source / "categories.json").write_text(json.dumps({"kept": [
        r"D:\old program\bin\data\images\a.png", "missing.gif"]}), encoding="utf-8")
    (source / "order.json").write_text(json.dumps([r"D:\old program\bin\data\images\a.png", "b.png"]), encoding="utf-8")
    context, report = migrate_legacy(source, tmp_path / "new", source_closed=True)
    assert report["target_counts"]["relations"] == 1
    assert any(row["reference"] == "missing.gif" and row["reason"] == "missing_resource" for row in report["skipped"])
    store = StorageService(context)
    assert [Path(path).name for path in store.get_all_images()] == ["a.png", "b.png"]
    assert store.get_images_by_category("kept") == [store._to_abspath("a.png")]
