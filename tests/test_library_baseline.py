"""Small behavior checks for the data boundaries changed in this baseline."""
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image
from services.config import ConfigService
from services.library_index import ROOT
from services.resource_import import ImportTarget
from services.storage import StorageService


def storage_at(tmp_path, name='library'):
    return StorageService(tmp_path / name, config=ConfigService(tmp_path / 'app'))


def image_file(path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGBA', (16, 16), color).save(path)
    return path


def test_nodes_memberships_mixed_order_survive_reconnect_and_library_move(tmp_path):
    storage = storage_at(tmp_path)
    index = storage.index
    first = index.create_node('First', icon='◇')
    second = index.create_node('Second')
    child = index.create_node('Child', first)
    a, _ = storage.save_file(str(image_file(tmp_path / 'a.png', 'red')))
    b, _ = storage.save_file(str(image_file(tmp_path / 'b.png', 'blue')))
    ra, rb = storage._resource_id(a), storage._resource_id(b)
    for node in (first, second):
        index.add_membership(ra, node)
        index.add_membership(rb, node)
    index.set_order(first, [('resource', rb), ('node', child), ('resource', ra)])
    assert storage.get_images_by_category('First') == [b, a]
    assert storage.get_images_by_category('Second') == [a, b]
    index.move_node(second, child)
    with pytest.raises(ValueError):
        index.move_node(first, second)
    assert index.remove_membership(ra, first)
    assert Path(a).is_file() and storage.get_images_by_category('First / Child / Second') == [a, b]
    moved = tmp_path / 'moved-library'
    index.root.rename(moved)
    reconnected = StorageService(moved, config=storage.config)
    assert reconnected.index.resource(ra)['id'] == ra
    assert reconnected.get_images_by_category('First') == [os.path.normcase(str(moved / 'images' / Path(b).name))]
    assert reconnected.index.content(first)[1]['id'] == child
    assert reconnected.get_category_icon('First') == '◇'


def test_batch_assignment_keeps_copy_move_and_mixed_order_semantics(tmp_path):
    storage = storage_at(tmp_path)
    source = storage.create_node('Source')
    target = storage.create_node('Target')
    child = storage.create_node('Child', target)
    paths = [storage.save_file(str(image_file(tmp_path / f'{i}.png', color)),
                               target=ImportTarget(source))[0]
             for i, color in enumerate(('red', 'green', 'blue'))]
    ids = [storage.index.resource(path)['id'] for path in paths]
    assert storage.move_resources_to(paths[:1], target, copy=True) == 1
    assert storage.move_resources_to(paths, target, copy=True, position=0) == 2
    assert [(entry['kind'], entry['id']) for entry in storage.index.content(target)] == [
        ('resource', ids[0]), ('resource', ids[1]), ('resource', ids[2]), ('node', child)]
    assert [entry['id'] for entry in storage.index.content(source)] == ids
    assert storage.move_resources_to(paths, target, copy=False, source_node=source) == 0
    assert not storage.index.content(source)
    assert [entry['id'] for entry in storage.index.content(target)[:3]] == ids
    assert len(storage.index.resources()) == 3


def test_missing_rebind_search_remove_and_recycle_semantics(tmp_path):
    storage = storage_at(tmp_path)
    node = storage.index.create_node('Memes')
    saved, _ = storage.save_file(str(image_file(tmp_path / 'source.png', 'green')), target=ImportTarget(node))
    resource_id = storage._resource_id(saved)
    storage.index.set_search_fields(resource_id, tags='标签', ocr_text='隐性文字')
    # Simulate Explorer moving an owned file to a different ordinary folder.
    rebound = storage.index.root / 'other' / 'renamed.png'
    rebound.parent.mkdir()
    Path(saved).rename(rebound)
    storage.cleanup_dead_links()
    assert storage.index.resource(resource_id)['status'] == 'missing'
    assert storage.get_images_by_category('Memes') == [saved]
    storage.rebind_resource(resource_id, rebound)
    assert storage.search_images('隐性文字') == [os.path.normcase(str(rebound))]
    assert storage.search_images('Memes') == [os.path.normcase(str(rebound))]
    assert storage.remove_image_from_category(str(rebound), 'Memes')
    assert rebound.is_file() and storage.get_image_keywords(str(rebound)) == '标签'
    with patch('services.recycle_bin.recycle_file', side_effect=OSError('cancelled')):
        assert storage.delete_images_batch([str(rebound)])['failed'] == 1
    assert rebound.is_file() and storage.index.resource(resource_id)
    if os.name == 'nt':
        assert storage.delete_image(str(rebound))
        assert not rebound.exists() and storage.index.resource(resource_id) is None


def test_recursive_folder_clipboard_and_sharing_use_the_live_catalog(tmp_path):
    from PySide6.QtGui import QImage, QColor
    from services.exchange_export import ExchangeExportService
    from services.exchange_import import ExchangeImportService
    storage = storage_at(tmp_path)
    node = storage.index.create_node('Target')
    image_file(tmp_path / 'Folder/a.png', 'orange')
    image_file(tmp_path / 'Folder/Nested/b.png', 'purple')
    result = storage.import_paths([tmp_path / 'Folder'], ImportTarget(node, 0))
    assert (result.imported, result.duplicates, result.errors) == (2, 0, {})
    assert len(storage.get_images_by_category('Target / Folder / Nested')) == 1
    assert storage.import_paths([tmp_path / 'Folder'], ImportTarget(node)).duplicates == 2
    qimage = QImage(16, 16, QImage.Format_RGBA8888)
    qimage.fill(QColor('cyan'))
    clipboard_path, _ = storage.save_image(qimage, ImportTarget(node))
    assert clipboard_path in storage.get_images_by_category('Target')
    archive = tmp_path / 'share.zip'
    ExchangeExportService(storage=storage).export_zip(str(archive))
    recipient = storage_at(tmp_path, 'recipient')
    assert ExchangeImportService(storage=recipient).import_zip(archive) == (3, 0)
    assert len(recipient.get_all_images()) == 3
    assert recipient.search_images('a.png')


def test_minimal_internal_adoption_preserves_missing_and_is_idempotent(tmp_path):
    root = tmp_path / 'library'
    image_file(root / 'images/kept.png', 'yellow')
    (root / 'categories.json').write_text(json.dumps({'Existing': ['kept.png', 'missing.png']}), encoding='utf-8')
    (root / 'metadata.json').write_text(json.dumps({'missing.png': 'saved tag'}), encoding='utf-8')
    (root / 'order.json').write_text(json.dumps(['missing.png', 'kept.png']), encoding='utf-8')
    storage = storage_at(tmp_path)
    assert len(storage.get_images_by_category('Existing')) == 2
    missing = storage.index.resource('missing.png')
    assert missing['status'] == 'missing' and missing['tags'] == 'saved tag'
    storage.remove_image_from_category('missing.png', 'Existing')
    reopened = storage_at(tmp_path)
    assert len(reopened.get_images_by_category('Existing')) == 1
    assert reopened.index.resource('missing.png')['id'] == missing['id']
