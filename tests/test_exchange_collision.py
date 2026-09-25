"""R0.2: a legacy compatibility key is not proof of identical file content."""
import hashlib
from io import BytesIO
import json
import zipfile

from PIL import Image
from PIL.PngImagePlugin import PngInfo
import pytest

from services.exchange_export import ExchangeExportService
from services.exchange_import import ExchangeImportService
from services.identity import inspect_bytes, put_identity
from services.library import create_library
from services.storage import StorageService


def png(size=(2, 6), color="red", note=None):
    output = BytesIO()
    metadata = PngInfo()
    if note is not None:
        metadata.add_text("Description", note)
    Image.new("RGBA", size, color).save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def gif(color="red"):
    output = BytesIO()
    Image.new("RGB", (4, 5), color).save(
        output, format="GIF", save_all=True,
        append_images=[Image.new("RGB", (4, 5), "green")], duration=80, loop=0,
    )
    return output.getvalue()


def seed_library(tmp_path, payloads):
    context = create_library(tmp_path / "library")
    originals = tmp_path / "originals"
    originals.mkdir()
    paths = []
    # Seed distinct stored records, including copies an ordinary import could
    # deduplicate. This models already-present / migrated library resources.
    for index, data in enumerate(payloads):
        identity = inspect_bytes(data)
        name = f"{index}.{identity.format.lower()}"
        (originals / name).write_bytes(data)
        path = context.images_dir / name
        path.write_bytes(data)
        with context.transaction() as connection:
            put_identity(connection, path, identity)
        paths.append(str(path))
    store = StorageService(context)
    store.save_order(paths)
    for index, path in enumerate(paths):
        store.add_image_to_category(path, f"category-{index}")
        store.set_image_keywords(path, f"keyword-{index}")
    assert len(store.get_all_images()) == len(payloads)
    return context, originals


def state(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def assert_refused_without_changes(context, originals, target, existing=True):
    if existing:
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("old-backup.txt", b"previous valid backup")
    before_target = target.read_bytes() if existing else None
    before = state(context.root), state(originals)
    messages = []
    with pytest.raises(ValueError, match="兼容导出已拒绝.*sync_key 冲突") as error:
        ExchangeExportService(context).export_zip(
            target, progress_callback=lambda current, total, message: messages.append(message),
        )
    for path in context.images_dir.iterdir():
        assert path.name in str(error.value)
    assert "未生成或替换资源包" in str(error.value)
    assert "打包完成" not in messages
    if existing:
        assert target.read_bytes() == before_target
    else:
        assert not target.exists()
    assert (state(context.root), state(originals)) == before
    assert list(target.parent.glob(".nekori-export-*.tmp")) == []


@pytest.mark.parametrize("existing", [False, True])
def test_known_dimension_collision_refuses_without_losing_either_resource(tmp_path, existing):
    first, second = png((2, 6)), png((3, 4))
    # The known Gate A fixture: equal flattened RGBA, different image shape.
    assert inspect_bytes(first).sync_key == inspect_bytes(second).sync_key
    context, originals = seed_library(tmp_path, [first, second])
    assert_refused_without_changes(context, originals, tmp_path / "backup.zip", existing)


@pytest.mark.parametrize("kind", ["PNG", "GIF"])
def test_same_dimensions_but_different_content_cannot_hide_behind_key(tmp_path, monkeypatch, kind):
    make = png if kind == "PNG" else gif
    context, originals = seed_library(tmp_path, [make(color="red"), make(color="blue")])
    # Force the compatibility digest to collide; no global identity code changes.
    monkeypatch.setattr(ExchangeExportService, "_md5_hex", staticmethod(lambda data: "0" * 32))
    assert_refused_without_changes(context, originals, tmp_path / "backup.zip")


def test_equal_pixels_with_distinct_embedded_metadata_are_explicitly_refused(tmp_path):
    first, second = png(note="first"), png(note="second")
    assert first != second
    assert inspect_bytes(first).sync_key == inspect_bytes(second).sync_key
    context, originals = seed_library(tmp_path, [first, second])
    assert_refused_without_changes(context, originals, tmp_path / "backup.zip")


@pytest.mark.parametrize("data", [png(), gif()], ids=["PNG", "GIF"])
def test_byte_identical_copies_still_merge_keywords_and_category_relations(tmp_path, data):
    context, originals = seed_library(tmp_path, [data, data])
    before = state(context.root), state(originals)
    target = tmp_path / "duplicates.zip"
    manifest = ExchangeExportService(context).export_zip(target)
    assert manifest["counts"] == dict(resources=1, categories=2, relations=2, assets=1)
    assert manifest.get("warnings", []) == []
    with zipfile.ZipFile(target) as archive:
        resource, = json.loads(archive.read("catalog.json"))["resources"]
        assert set(resource["keywords"]) == {"keyword-0", "keyword-1"}
        assert len(resource["category_refs"]) == 2
        assert archive.read(resource["asset_path"]) == data
    imported = create_library(tmp_path / "imported")
    assert ExchangeImportService(imported).import_zip(target) == (1, 0)
    store = StorageService(imported)
    for name in ("category-0", "category-1"):
        assert store.get_images_by_category(name) == store.get_all_images()
    assert (state(context.root), state(originals)) == before


def test_normal_png_gif_export_keeps_v1_keys_assets_and_idempotent_import(tmp_path):
    payloads = [png(), gif()]
    context, originals = seed_library(tmp_path, payloads)
    before = state(context.root), state(originals)
    target = tmp_path / "normal.zip"
    manifest = ExchangeExportService(context).export_zip(target)
    assert manifest["format_version"] == 1
    assert manifest["hash_rules"] == {"static": "p:md5(RGBA bytes)", "animated": "f:md5(file bytes)"}
    assert manifest["counts"]["assets"] == 2
    assert manifest.get("warnings", []) == []
    assert manifest["skipped"] == []
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        resources = json.loads(archive.read("catalog.json"))["resources"]
        by_name = {item["display_name"]: item for item in resources}
        for index, data in enumerate(payloads):
            identity = inspect_bytes(data)
            item = by_name[f"{index}.{identity.format.lower()}"]
            assert item["sync_key"] == identity.sync_key
            assert item["asset_path"] == f"assets/{identity.sync_key.replace(':', '-')}.{identity.format.lower()}"
            assert archive.read(item["asset_path"]) == data
    imported = create_library(tmp_path / "imported")
    importer = ExchangeImportService(imported)
    assert importer.import_zip(target) == (2, 0)
    assert importer.import_zip(target) == (0, 2)
    assert (state(context.root), state(originals)) == before


@pytest.mark.parametrize("selected", [0, 1])
def test_collision_outside_selected_categories_does_not_block_export(tmp_path, selected):
    context, originals = seed_library(tmp_path, [png((2, 6)), png((3, 4))])
    before = state(context.root), state(originals)
    target = tmp_path / "selected.zip"
    manifest = ExchangeExportService(context).export_zip(target, selected_categories=[f"category-{selected}"])
    assert manifest["counts"] == dict(resources=1, categories=1, relations=1, assets=1)
    with zipfile.ZipFile(target) as archive:
        item, = json.loads(archive.read("catalog.json"))["resources"]
        assert item["display_name"] == f"{selected}.png"
    assert (state(context.root), state(originals)) == before
