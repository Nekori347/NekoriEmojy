import json
import gc
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import sqlite3
from contextlib import closing

from PIL import Image

from fluent_ui.views.tg_sticker_view import ImportPackThread
from services.tg_downloader import StickerUnavailableError
from test_storage_single_frame_gif import _make_storage


class TGPackageExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        self.root = Path(self.temp.name)
        self.storage = _make_storage(self.root)
        self.output = self.root / "tg-001.zip"
        payload = BytesIO()
        Image.new("RGB", (12, 10), "red").save(payload, "BMP")
        self.downloader = SimpleNamespace(
            get_file_path=lambda _: "sticker.bmp",
            download_file_bytes=lambda _: payload.getvalue(),
        )

    def worker(self):
        worker = ImportPackThread(
            self.downloader, self.storage,
            [SimpleNamespace(index=i, file_id=str(i)) for i in range(2)],
            "tg-001", export_path=str(self.output),
            source_url="https://t.me/addstickers/Kei_Aris",
        )
        self.errors = []
        self.finished = []
        worker.failed.connect(self.errors.append)
        worker.finished_all.connect(lambda *args: self.finished.append(args))
        return worker

    def test_download_clean_deduplicate_and_export_named_category(self):
        self.storage.add_category("unrelated")
        self.worker().run()
        self.assertEqual(self.errors, [])
        self.assertEqual(len(self.finished), 1)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read("TG.txt").decode("utf-8"),
                             "https://t.me/addstickers/Kei_Aris\n")
            manifest = json.loads(archive.read("manifest.json"))
            catalog = json.loads(archive.read("catalog.json"))
            self.assertEqual(manifest["package_id"], "tg-001")
            self.assertEqual(manifest["export_scope"], "categories")
            self.assertEqual(catalog["categories"], [{"ref": 1, "name": "tg-001"}])
            self.assertEqual(len(catalog["resources"]), 1)
            resource = catalog["resources"][0]
            self.assertEqual(resource["format"], "PNG")
            self.assertEqual(resource["category_refs"], [1])
            self.assertTrue(archive.read(resource["asset_path"]).startswith(b"\x89PNG"))
        self.assertTrue(self.storage.get_images_by_category("tg-001"))

    def test_missing_source_is_skipped_and_remaining_sticker_exports(self):
        def get_file_path(file_id):
            if file_id == "0":
                raise StickerUnavailableError("Bad Request: file not found")
            return "sticker.bmp"

        self.downloader.get_file_path = get_file_path
        worker = self.worker()
        messages = []
        worker.progress.connect(lambda _, __, msg: messages.append(msg))
        worker.run()
        self.assertEqual(self.errors, [])
        self.assertEqual(self.finished, [(1, 0, 0, "tg-001")])
        self.assertEqual(worker.skipped_count, 1)
        self.assertTrue(any("贴纸 #1 获取失败" in msg for msg in messages))
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(json.loads(archive.read("manifest.json"))["counts"]["resources"], 1)
            self.assertIn("TG.txt", archive.namelist())

    def test_all_sources_missing_does_not_replace_existing_zip(self):
        self.output.write_bytes(b"existing")
        self.downloader.download_file_bytes = lambda _: (_ for _ in ()).throw(
            StickerUnavailableError("file not found"))
        worker = self.worker()
        worker.run()
        self.assertEqual(worker.skipped_count, 2)
        self.assertTrue(self.errors)
        self.assertIn("没有可导出的贴纸", self.errors[0])
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_all_network_failures_do_not_export_empty_package(self):
        self.downloader.download_file_bytes = lambda _: (_ for _ in ()).throw(
            TimeoutError("timeout"))
        worker = self.worker()
        worker.run()
        self.assertEqual(worker.skipped_count, 2)
        self.assertTrue(self.errors)
        self.assertFalse(self.output.exists())

    def test_partial_network_failure_exports_with_details(self):
        self.downloader.get_file_path = lambda file_id: (
            "sticker.bmp" if file_id == "1" else (_ for _ in ()).throw(TimeoutError("timeout"))
        )
        worker = self.worker()
        worker.run()
        self.assertEqual(self.errors, [])
        self.assertTrue(self.output.exists())
        self.assertEqual(worker.imported_count, 1)
        self.assertEqual(worker.skipped_count, 1)
        self.assertIn("#1", worker.skipped_details[0])
        self.assertIn("timeout", worker.skipped_details[0])

    def test_tg_source_file_is_compatible_with_package_import(self):
        from services.exchange_import import ExchangeImportService
        worker = self.worker()
        worker.source_url = "https://t.me/addemoji/TestEmoji"
        worker.run()
        self.assertEqual(self.errors, [])
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read("TG.txt"),
                             b"https://t.me/addemoji/TestEmoji" + bytes([10]))
        destination = self.root / "roundtrip"
        target = _make_storage(destination)
        ExchangeImportService(storage=target).import_zip(str(self.output))
        self.assertEqual(len(target.get_all_images()), 1)
    def test_failed_cleaning_preserves_existing_output(self):
        self.output.write_bytes(b"existing")
        self.storage.save_file = lambda _, **kwargs: (None, False)
        self.worker().run()
        self.assertTrue(self.errors)
        self.assertFalse(self.finished)
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_cancel_during_packaging_preserves_existing_output(self):
        self.output.write_bytes(b"existing")
        worker = self.worker()
        worker.progress.connect(lambda done, total, msg: worker.cancel() if "正在解析表情" in msg else None)
        worker.run()
        self.assertEqual(self.errors, [])
        self.assertFalse(self.finished)
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.assertEqual(list(self.root.glob("tg_package_*")), [])

    def test_transient_index_failure_is_repaired_on_retry(self):
        real_save = self.storage._save_hashes
        calls = []

        def flaky(strict=False):
            calls.append(strict)
            if len(calls) == 1:
                raise PermissionError("busy")
            return real_save(strict=strict)

        with patch.object(self.storage, "_save_hashes", side_effect=flaky):
            self.worker().run()
        self.assertTrue(self.errors)
        self.assertFalse(self.output.exists())
        self.assertEqual(len(list(Path(self.storage.images_dir).iterdir())), 1)

        # The orphaned file is repaired into a normal duplicate instead of being
        # written a second time.
        self.worker().run()
        self.assertEqual(self.errors, [])
        self.assertTrue(self.output.exists())
        self.assertEqual(len(list(Path(self.storage.images_dir).iterdir())), 1)
    def test_persistent_index_failure_then_retry_repairs_orphan(self):
        self.output.write_bytes(b"existing")
        with patch.object(self.storage, "_save_hashes", side_effect=PermissionError("busy")):
            self.worker().run()
        self.assertTrue(self.errors)
        self.assertIn("索引保存失败", self.errors[0])
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.assertEqual(len(list(Path(self.storage.images_dir).iterdir())), 1)
        self.assertFalse(self.storage.get_images_by_category("tg-001"))
        self.assertEqual(list(Path(self.storage.data_dir).glob("*.tmp")), [])

        self.worker().run()
        self.assertEqual(self.errors, [])
        self.assertEqual(len(self.storage.get_images_by_category("tg-001")), 1)
        with closing(sqlite3.connect(self.storage.features_db_path)) as conn:
            rows = conn.execute("SELECT md5, sync_key FROM image_features").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0][0])
        self.assertTrue(rows[0][1].startswith("p:"))
    def test_category_write_failure_is_not_success_and_retry_recovers(self):
        from services.library_index import ROOT
        real_add = self.storage.index.add_membership
        state = {"failed": False}

        def add(resource_id, node_id, position=None):
            # ROOT membership is the library registration and must keep working;
            # only the user category relation fails.
            if node_id != ROOT and not state["failed"]:
                state["failed"] = True
                raise OSError("category database unavailable")
            return real_add(resource_id, node_id, position)

        with patch.object(self.storage.index, "add_membership", side_effect=add):
            self.worker().run()
        self.assertTrue(self.errors)
        self.assertIn("加入收藏夹失败", self.errors[0])
        self.assertFalse(self.output.exists())

        self.worker().run()
        self.assertEqual(self.errors, [])
        self.assertEqual(len(self.storage.get_images_by_category("tg-001")), 1)
    def test_feature_db_initialization_does_not_migrate_live_json(self):
        from services.feature_db import FeatureDB
        with patch.object(FeatureDB, "check_and_migrate_from_json") as migrate:
            FeatureDB(self.storage.features_db_path)
        migrate.assert_not_called()

    def test_restart_recovers_static_and_animated_orphans(self):
        for animated in (False, True):
            with self.subTest(animated=animated):
                orphan_root = self.root / str(animated)
                storage = _make_storage(orphan_root)
                payload = BytesIO()
                first = Image.new("RGB", (8, 8), "red")
                if animated:
                    first.save(payload, "GIF", save_all=True,
                               append_images=[Image.new("RGB", (8, 8), "blue")], duration=100)
                else:
                    first.save(payload, "PNG")
                source = orphan_root / "source.dat"
                source.write_bytes(payload.getvalue())
                with patch.object(storage, "_save_hashes", side_effect=PermissionError("busy")):
                    with self.assertRaisesRegex(RuntimeError, "索引保存失败"):
                        storage.save_file(str(source), strict=True)
                storage = _make_storage(orphan_root)
                path, duplicate = storage.save_file(str(source), strict=True)
                self.assertTrue(duplicate)
                self.assertEqual(storage.add_image_to_category(path, "recovered", strict=True), "success")
                self.assertEqual(len(list(Path(storage.images_dir).iterdir())), 1)

    def test_actual_category_db_failure_propagates(self):
        source = self.root / "source.bmp"
        source.write_bytes(self.downloader.download_file_bytes(""))
        path, _ = self.storage.save_file(str(source), strict=True)

        def broken():
            raise sqlite3.OperationalError("locked")

        with patch.object(self.storage.index, "connect", side_effect=broken):
            with self.assertRaises(sqlite3.OperationalError):
                self.storage.add_image_to_category(path, "recovered")

        self.storage.add_image_to_category(path, "recovered")
        self.assertEqual(len(self.storage.get_images_by_category("recovered")), 1)
