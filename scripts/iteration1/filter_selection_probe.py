"""Exercise existing gallery actions with generated resources, without native clicks."""
import argparse
import json
import os
from pathlib import Path
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from services.library import create_library, open_library
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from fluent_ui.views.gallery_view import GalleryInterface


parser = argparse.ArgumentParser()
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
work = args.work.resolve()
assert not work.is_relative_to(REPO), 'Use a separate generated-data directory'
work.mkdir(exist_ok=False)
app = QApplication([])
context = create_library(work / '测试资源库')
session = open_library(context.root)
gallery = None
checks = []
try:
    storage = StorageService(session)
    config = ConfigService(session)
    paths = []
    for color in ('red', 'green', 'blue'):
        source = work / (color + '.png')
        Image.new('RGB', (24, 24), color).save(source)
        path, _ = storage.save_file(source, target_category='日常')
        assert path
        paths.append(path)
    source = work / 'animated.gif'
    Image.new('RGB', (24, 24), 'black').save(
        source, save_all=True, append_images=[Image.new('RGB', (24, 24), 'white')],
        duration=100, loop=0)
    path, _ = storage.save_file(source)
    assert path
    paths.append(path)
    storage.set_image_keywords(paths[0], '测试标签')
    gallery = GalleryInterface(storage, ClipboardService(config), config)
    # These are synchronous action checks. No event loop or background jobs run.
    for timer in gallery.findChildren(QTimer):
        timer.stop()

    def check(name, actual, expected):
        assert set(actual) == set(expected), (name, actual, expected)
        checks.append({'check': name, 'unique_resources': len(set(actual))})

    gallery.on_images_changed()
    check('all generated resources', gallery._all_current_images, paths)
    for key, expected in (
        ('no_tag', paths[1:]), ('unclassified', paths[3:]),
        ('is_gif', paths[3:]), ('is_static', paths[:3]),
    ):
        gallery._clear_filter()
        gallery._update_filter(key, True)
        check(key, gallery._all_current_images, expected)
    gallery._clear_filter()
    gallery.set_selection_mode(True)
    gallery.select_all_cards()
    check('multi select all', gallery.selected_paths, paths)
    gallery.select_all_cards()
    check('multi select all toggles off', gallery.selected_paths, [])
finally:
    if gallery is not None:
        gallery.close()
    session.close()

report = {
    'scope': 'Source GalleryInterface actions, Qt offscreen; not a physical frozen popup-menu click.',
    'data': 'Four generated resources in a new isolated library; no real user library accessed.',
    'checks': checks,
}
args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
