"""Preview category text keeps mixed-tree order without a global image map."""
from unittest.mock import patch
from test_library_baseline import storage_at, image_file


def test_single_image_labels_follow_tree_order_and_edits(tmp_path):
    storage = storage_at(tmp_path)
    index = storage.index
    first = index.create_node('A/%')
    child = index.create_node('Child', first)
    second = index.create_node('Second')
    path, _ = storage.save_file(str(image_file(tmp_path / 'image.png', 'red')))
    rid = storage._resource_id(path)
    for node in (second, child, first):
        index.add_membership(rid, node)
    expected = storage.get_image_to_categories_map()[path]
    with patch.object(storage, 'get_image_to_categories_map', side_effect=AssertionError('whole-library scan')):
        assert storage.get_categories_by_image(path) == expected
        index.update_node(first, name='Renamed')
        assert storage.get_categories_by_image(path) == ['Renamed', 'Renamed / Child', 'Second']
        index.remove_membership(rid, first)
        assert storage.get_categories_by_image(path) == ['Renamed / Child', 'Second']
        index.remove_membership(rid, child)
        index.remove_membership(rid, second)
        assert storage.get_categories_by_image(path) == []
