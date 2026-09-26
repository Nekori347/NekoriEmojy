"""Pinned original Suzu -> read-only migration -> restart/copy -> original exchange importer.

All resources are generated. --work must be a new directory outside the checkout.
No installed Suzu process or real user data is accessed.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
BASELINE = 'c84e5b2c201fe5103e721fca062283cadf97ca0d'
sys.path.insert(0, str(REPO))
from services.library import create_library, open_library, copy_library, read_db
from services.legacy_import import inventory, migrate_legacy
from services.storage import StorageService
from services.config import ConfigService
from services.category_groups import CategoryGroups
from services.exchange_export import ExchangeExportService
from services.exchange_import import ExchangeImportService

parser = argparse.ArgumentParser()
parser.add_argument('--work', required=True, type=Path)
args = parser.parse_args()
work = args.work.resolve()
assert not work.is_relative_to(REPO), 'Use a separate test data directory'
work.mkdir(exist_ok=False)
code = work / 'pinned-suzu'
code.mkdir()
archive = subprocess.check_output(['git', '-C', str(REPO), 'archive', '--format=zip', BASELINE, 'services'])
with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
    for entry in zipped.infolist():
        if entry.is_dir() or not entry.filename.endswith('.py'):
            continue
        dest = code / entry.filename
        assert dest.resolve().is_relative_to(code)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zipped.read(entry))

def old(action, root, archive):
    subprocess.run([sys.executable, str(Path(__file__).with_name('legacy_side.py')),
                    action, str(code), str(root), str(archive)], check=True, timeout=60)
    return json.loads((work / (root.name + '.json')).read_text(encoding='utf-8'))

checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)

source = work / 'old-app'
old_zip = work / 'suzu-export.zip'
expected = old('prepare', source, old_zip)
before = inventory(source / 'data')
originals = inventory(work / 'original-images')
context, migration = migrate_legacy(source, work / '独立资源库 中文', source_closed=True)
check('source files unchanged byte for byte', inventory(source / 'data') == before)
check('migration no skipped or failed records', not migration['skipped'] and not migration['failed'])
store = StorageService(context)
check('images retained byte for byte', {p.name: inventory(context.images_dir)[p.name] for p in context.images_dir.iterdir()} == expected['images'])
check('manual image order retained', [Path(p).name for p in store.get_all_images()] == expected['order'])
check('categories and multiple memberships retained', {c: sorted(Path(p).name for p in ps) for c, ps in store.get_all_categories().items()} == expected['categories'])
check('manual category order retained', list(store.get_all_categories()) == list(expected['categories']))
check('ordinary tags retained as complete text', {Path(p).name: store.get_image_keywords(p) for p in store.get_all_images()} == expected['keywords'])
check('recent order retained', [Path(p).name for p in store.get_recent_images()] == expected['recent'])
check('settings retained', ConfigService(context).get('preview_size') == 451)
session = open_library(context.root)
groups = CategoryGroups(session)
group = groups.create('日常', '常用小分类')
paths = StorageService(session).get_all_images()
groups.add(group, paths[:2])
groups.set_collapsed(group, True)
check('groups do not duplicate images', inventory(context.images_dir) == expected['images'])
copy = copy_library(session, work / '复制到新位置')
session.close()
session = open_library(copy.root)
check('copy and reopen keep order', [Path(p).name for p in StorageService(session).get_all_images()] == expected['order'])
with read_db(copy.db('categories')) as conn:
    check('copy and reopen keep collapsed small group', conn.execute('SELECT name, collapsed FROM category_groups').fetchall() == [('常用小分类', 1)])
    check('copy and reopen keep group membership', conn.execute('SELECT COUNT(*) FROM group_images').fetchone()[0] == 2)
new_zip = work / 'nekori-export.zip'
manifest = ExchangeExportService(session).export_zip(str(new_zip))
check('exchange includes all baseline resources and relationships', manifest['counts'] == {'resources': 3, 'categories': 3, 'relations': 5, 'assets': 3})
session.close()
returned = old('import', work / 'rollback-suzu', new_zip)
check('original Suzu importer accepts Nekori archive', returned['images'] == expected['images'])
check('original importer keeps nonempty categories and relations', returned['categories'] == {k:v for k,v in expected['categories'].items() if v})
check('Nekori tags survive original Suzu importer', returned['keywords'] == expected['keywords'])
target = create_library(work / 'from-old-resource-pack')
check('Nekori accepts original Suzu archive', ExchangeImportService(target).import_zip(old_zip) == (3, 0))
check('old resource pack repeated import is idempotent', ExchangeImportService(target).import_zip(old_zip) == (0, 3))
check('external original images unchanged', inventory(work / 'original-images') == originals)
check('source unchanged after all downstream operations', inventory(source / 'data') == before)
result = {'baseline': BASELINE, 'checks': checks, 'migration_counts': migration['target_counts'],
          'exchange_counts': manifest['counts'], 'source_read_only': True,
          'limits': ['Synthetic source only; not a real user library.',
                     'Exchange v1 carries images, ordinary tags and large category relations, not manual order, recent, settings or small groups.',
                     'Original baseline Suzu importer drops empty categories.',
                     'Original baseline exporter may split keywords into characters; direct read-only migration preserves original text.']}
(work / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
