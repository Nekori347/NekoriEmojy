"""R0.3: exercise real export worker/signals and visible Qt result notices."""
import hashlib
import json
from pathlib import Path
import time
import zipfile

from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from qfluentwidgets import InfoBar

from fluent_ui.views.exchange_view import ExchangeInterface
from fluent_ui.views.gallery_view import GalleryInterface, QFileDialog
from services.category_groups import CategoryGroups
from services.library import create_library
from services.storage import StorageService


class ExportHost(GalleryInterface):
    """Keep production export methods; omit unrelated clipboard/hotkey timers."""
    def __init__(self, storage):
        QWidget.__init__(self)
        self.storage = storage
        self.exchange_export_thread = None
        self._exchange_export_info_bar = None


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    # The Windows offscreen platform does not discover system fonts itself.
    for name in ("msyh.ttc", "segoeui.ttf"):
        font = Path("C:/Windows/Fonts") / name
        if font.exists():
            assert QFontDatabase.addApplicationFont(str(font)) >= 0
    return application


@pytest.fixture
def ui(tmp_path, app):
    context = create_library(tmp_path / "library")
    store = StorageService(context)
    window = QWidget()
    window.resize(860, 640)  # Match the application's default window size.
    layout = QVBoxLayout(window)
    stack = QStackedWidget(window)
    layout.addWidget(stack)
    gallery = ExportHost(store)
    exchange = ExchangeInterface()
    stack.addWidget(gallery)
    stack.addWidget(exchange)
    exchange.export_all_requested.connect(gallery._export_all_exchange_package)
    stack.setCurrentWidget(exchange)
    window.show()
    app.processEvents()
    assert exchange.isVisible() and not gallery.isVisible()
    yield context, store, window, gallery, exchange
    if gallery.exchange_export_thread:
        assert gallery.exchange_export_thread.wait(5000)
    window.close()
    window.deleteLater()
    app.processEvents()


def add_image(store, tmp_path, name, size=(4, 5), color="red"):
    source = tmp_path / name
    Image.new("RGBA", size, color).save(source)
    return Path(store.save_file(source, target_category="普通分类")[0])


def library_state(context):
    return {str(p.relative_to(context.root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in context.root.rglob("*") if p.is_file()}


def export_from_page(ui, tmp_path, app, monkeypatch):
    context, store, window, gallery, exchange = ui
    target = tmp_path / "compatibility.zip"
    captions = []
    def choose(parent, caption, *args):
        captions.append(caption)
        return str(target), ""
    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    # Real page signal -> Gallery export entry -> QThread -> result slot.
    exchange.exportAllCard.button.click()
    assert gallery.exchange_export_thread is not None
    assert captions and "非完整备份" in captions[0]
    deadline = time.monotonic() + 10
    while gallery._exchange_export_info_bar is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert gallery._exchange_export_info_bar is None, "Export did not deliver its result"
    assert gallery.exchange_export_thread.wait(5000)
    QTest.qWait(300)  # Let the existing InfoBar entry animation finish.
    bars = [bar for bar in window.findChildren(InfoBar) if bar.isVisible()]
    assert len(bars) == 1
    assert bars[0].parentWidget() is window
    assert bars[0].geometry().left() >= 0
    assert bars[0].geometry().right() <= window.width()
    assert bars[0].geometry().bottom() <= window.height()
    assert QApplication.activeModalWidget() is None
    assert window.grab().save(str(tmp_path / "export-result.png"))
    return target, bars[0]


def test_capability_notice_is_visible_before_export_and_survives_text_refresh(ui, app):
    _, _, _, _, exchange = ui
    for refresh in (False, True):
        if refresh:
            exchange.update_texts("zh")
            app.processEvents()
        assert exchange.compatibilityNotice.isVisible()
        text = exchange.compatibilityNotice.text()
        for term in ("Suzu v1.11.6", "不是完整备份", "Native Full 尚未实现", "分类节点",
                     "分类图标", "手工图片排序", "原生身份", "标签与元数据", "设置", "最近记录", "空分类"):
            assert term in text
        assert "完整导出" not in exchange.exportAllCard.contentLabel.text()


def test_native_organization_is_explicitly_excluded_in_success_notice(ui, tmp_path, app, monkeypatch):
    context, store, _, _, _ = ui
    path = add_image(store, tmp_path, "first.png")
    second = add_image(store, tmp_path, "second.png", color="blue")
    store.save_order([str(second), str(path)])
    groups = CategoryGroups(context)
    group = groups.create("普通分类", "节点")
    groups.add(group, [str(path)])
    groups.set_collapsed(group, True)
    with context.transaction() as conn:
        conn.execute("UPDATE categories.categories SET icon_path=?", (path.name,))
        conn.execute("UPDATE metadata.image_metadata SET tags='额外标签'")
        conn.execute("INSERT INTO preferences VALUES ('test-setting', 'true')")
    before = library_state(context)
    target, bar = export_from_page(ui, tmp_path, app, monkeypatch)
    assert "非完整备份" in bar.title
    for term in ("不保留分类节点", "分类图标", "手工图片排序", "标签与元数据", "设置"):
        assert term in bar.content
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format_version"] == 1 and manifest["counts"]["resources"] == 2
    assert library_state(context) == before


def test_existing_category_warning_and_format_skip_are_visible(ui, tmp_path, app, monkeypatch):
    context, store, _, _, _ = ui
    path = add_image(store, tmp_path, "source.png")
    store.add_image_to_category(str(path), "é")
    store.add_image_to_category(str(path), "e\u0301")
    # Ordinary import converts static WebP to PNG; use a retained animated WebP.
    original = tmp_path / "unsupported.webp"
    Image.new("RGB", (4, 5), "blue").save(
        original, format="WEBP", save_all=True,
        append_images=[Image.new("RGB", (4, 5), "green")], duration=80, lossless=True,
    )
    saved, _ = store.save_file(original, target_category="普通分类")
    assert Path(saved).suffix == ".webp"
    before = library_state(context)
    target, bar = export_from_page(ui, tmp_path, app, monkeypatch)
    assert "有警告或跳过" in bar.title
    assert "分类名称合并" in bar.content and "未导出" in bar.content
    assert "unsupported" in bar.content and "1 项警告、1 项跳过" in bar.content
    assert "manifest.json" in bar.content and bar.duration == -1
    with zipfile.ZipFile(target) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["warnings"][0]["type"] == "category_name_collision"
        assert len(manifest["skipped"]) == 1
    assert library_state(context) == before


def test_collision_reaches_visible_error_when_gallery_page_is_hidden(ui, tmp_path, app, monkeypatch):
    context, store, _, gallery, _ = ui
    first = add_image(store, tmp_path, "first.png", size=(2, 6))
    second = add_image(store, tmp_path, "second.png", size=(3, 4))
    before = library_state(context)
    target, bar = export_from_page(ui, tmp_path, app, monkeypatch)
    assert not gallery.isVisible() and bar.isVisible()
    assert "失败" in bar.title and "sync_key 冲突" in bar.content
    assert first.name in bar.content and second.name in bar.content
    assert "未生成或替换资源包" in bar.content and bar.duration == -1
    assert "Traceback" not in bar.content and not target.exists()
    assert library_state(context) == before


def test_many_skips_use_bounded_notice_with_full_manifest_details(ui, tmp_path, app, monkeypatch):
    context, store, _, _, _ = ui
    add_image(store, tmp_path, "source.png")
    for index in range(5):
        (context.images_dir / f"unsupported-{index}.txt").write_text("not an image")
    target, bar = export_from_page(ui, tmp_path, app, monkeypatch)
    assert bar.content.count("未导出 ") == 3
    assert "5 项跳过" in bar.content and "完整明细" in bar.content
    with zipfile.ZipFile(target) as archive:
        assert len(json.loads(archive.read("manifest.json"))["skipped"]) == 5
