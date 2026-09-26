"""Subprocess half of transition_probe: execute pinned Suzu code on synthetic data."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['prepare', 'import'])
parser.add_argument('code', type=Path)
parser.add_argument('root', type=Path)
parser.add_argument('archive', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.code))
from PIL import Image
import services.storage as storage_module
import services.config as config_module
from services.exchange_export import ExchangeExportService
from services.exchange_import import ExchangeImportService

# Redirect only these legacy modules' implicit data roots; the code is unchanged.
args.root.mkdir(exist_ok=False)
storage_module.__file__ = str(args.root / 'services/storage.py')
config_module.__file__ = str(args.root / 'services/config.py')
store = storage_module.StorageService()
config = config_module.ConfigService()
if args.action == 'prepare':
    inputs = args.root.parent / 'original-images'
    inputs.mkdir()
    Image.new('RGB', (61, 47), 'red').save(inputs / '红.png')
    Image.new('RGB', (63, 49), 'blue').save(inputs / '蓝.png')
    frames = [Image.new('RGB', (65, 51), color) for color in ('green', 'yellow')]
    frames[0].save(inputs / '动态.gif', save_all=True, append_images=frames[1:], duration=120, loop=0)
    paths = [store.save_file(str(path))[0] for path in sorted(inputs.iterdir())]
    assert all(paths)
    store.save_categories({'收藏': [paths[0], paths[2]], '日常': paths, '空分类': []})
    store.save_order(paths[::-1])
    store.set_image_keywords(paths[0], '猫猫 开心')
    store.set_category_icon('收藏', paths[0])
    store.add_recent_image(paths[0])
    store.add_recent_image(paths[2])
    config.set('preview_size', 451)
    config.set('always_on_top', False)
    config.set('use_system_font', True)
    manifest = ExchangeExportService(str(args.root)).export_zip(str(args.archive))
else:
    count = ExchangeImportService(args.root).import_zip(args.archive)
    assert count == (3, 0), count
    store = storage_module.StorageService()
    manifest = {'imported': count[0], 'skipped': count[1]}

images = store.get_all_images()
state = {
    'order': [Path(path).name for path in images],
    'images': {Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in images},
    'categories': {cat: sorted(Path(path).name for path in paths) for cat, paths in store.get_all_categories().items()},
    'keywords': {Path(path).name: store.get_image_keywords(path) for path in images},
    'recent': [Path(path).name for path in store.get_recent_images()],
    'preview_size': config.get('preview_size'),
    'manifest': manifest,
}
(args.root.parent / (args.root.name + '.json')).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
