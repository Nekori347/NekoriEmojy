"""Observe original storage and exchange behavior with generated test images."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import shutil
import sys
import zipfile

work = Path(os.environ["P0_WORK_DIR"]).resolve()
source = work / "p0-behavior-source"
assert source.is_dir() and not (source / "data").exists()
os.chdir(source)
sys.path.insert(0, str(source))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PIL import Image
from PySide6.QtWidgets import QApplication
from services.storage import StorageService
from services.exchange_export import ExchangeExportService
from services.exchange_import import ExchangeImportService

app = QApplication([])
inputs = work / "p0-generated-inputs-2"
assert not inputs.exists()
inputs.mkdir()
png = inputs / "测试 静态.png"
gif = inputs / "测试 动态.gif"
Image.new("RGB", (32, 24), "red").save(png)
Image.new("RGB", (24, 32), "blue").save(
    gif, save_all=True, append_images=[Image.new("RGB", (24, 32), "yellow")],
    duration=[100, 120], loop=0)
digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
before = {p.name: digest(p) for p in (png, gif)}
storage = StorageService()
assert storage.get_all_images() == []
png_saved, png_duplicate = storage.save_file(str(png))
gif_saved, gif_duplicate = storage.save_file(str(gif))
assert png_saved and gif_saved and not png_duplicate and not gif_duplicate
assert {p.name: digest(p) for p in (png, gif)} == before
assert all(Path(p).resolve().is_relative_to(source / "data") for p in (png_saved, gif_saved))
with Image.open(gif_saved) as image:
    assert image.n_frames == 2
duplicate_path, duplicate = storage.save_file(str(png))
assert duplicate and duplicate_path == png_saved
assert storage.add_category("分类 A")
assert storage.add_category("空分类")
assert storage.add_image_to_category(png_saved, "分类 A") == "success"
assert storage.add_image_to_category(gif_saved, "分类 A") == "success"
assert storage.rename_category("分类 A", "分类 已改名")
storage.save_order([gif_saved, png_saved])
assert storage.get_all_images() == [gif_saved, png_saved]
assert storage.get_images_by_category("分类 已改名") == [gif_saved, png_saved]
storage.set_image_keywords(png_saved, "alpha, 哈哈")
assert png_saved in storage.search_images("alpha")
storage.set_category_icon("分类 已改名", png_saved)
assert storage.get_category_icon("分类 已改名")
storage.add_recent_image(gif_saved)
assert gif_saved in storage.get_recent_images()
reopened = StorageService()
assert reopened.get_all_images() == [gif_saved, png_saved]
assert reopened.get_images_by_category("分类 已改名") == [gif_saved, png_saved]
assert reopened.get_image_keywords(png_saved) == "alpha, 哈哈"

package = work / "p0-generated-exchange.zip"
manifest = ExchangeExportService(str(source)).export_zip(str(package))
with zipfile.ZipFile(package) as archive:
    catalog = json.loads(archive.read("catalog.json"))
target = work / "p0-exchange-initialized-target"
assert not target.exists()
# The application creates StorageService before exposing exchange. Reuse the
# upstream isolated-storage fixture to establish that same schema prerequisite.
sys.path.insert(0, str(source / "tests"))
from test_storage_single_frame_gif import _make_storage
_make_storage(target)
imported, skipped = ExchangeImportService(target).import_zip(package)
assert (imported, skipped) == (2, 0)
with sqlite3.connect(target / "data" / "categories.db") as connection:
    categories = [row[0] for row in connection.execute("SELECT name FROM categories ORDER BY sort_order")]
    relation_count = connection.execute("SELECT COUNT(*) FROM category_images").fetchone()[0]
assert categories == ["分类 已改名"] and relation_count == 2
imported_again, skipped_again = ExchangeImportService(target).import_zip(package)
assert (imported_again, skipped_again) == (0, 2)

report = {
    "sample_origin": "Pillow-generated solid-color PNG and two-frame GIF; no user images",
    "original_source_files_unchanged": True,
    "png_and_animated_gif_copy_import": "passed",
    "duplicate_png": "passed",
    "category_add_rename_membership_icon": "passed",
    "manual_global_order_and_category_filter_order": "passed",
    "keywords_search_and_recent_history": "passed",
    "storage_reopen_retains_test_state": "passed",
    "exchange_first_import": {"imported": imported, "skipped": skipped, "relations": relation_count},
    "exchange_duplicate_import": {"imported": imported_again, "skipped": skipped_again},
    "exchange_empty_category": "declared on export; not created by original import (controlled reproduction)",
    "exchange_manual_order": "format has no manual-order field; not claimed as restored",
    "exchange_prerequisite": "database schema must be initialized by application storage before import",
    "scope": "service calls in isolated copies; does not validate native GUI interactions or a real user package",
}
(work / "p0-behavior.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
