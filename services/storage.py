"""Desktop storage facade over the Nekori catalog and Suzu's mature codecs."""
import os
import uuid
import json
import hashlib
import io
import sqlite3
import time
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QObject, Signal
from services.library_index import LibraryIndex, ROOT
from services.resource_import import ResourceImporter, ImportTarget
from services.exchange_icons import IMAGE_SUFFIXES, resolve_icon_path, portable_icon_path


def _storage_locked(method):
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return locked


class RecentEvents(QObject):
    changed = Signal()


class StorageService:
    SUPPORTED_FORMATS = ('.png', '.apng', '.jpg', '.jpeg', '.gif', '.webp', '.webm', '.tgs', '.bmp', '.tiff')

    def __init__(self, library_path=None, config=None):
        from services.app_paths import selected_library
        from services.config import ConfigService
        from services.feature_db import FeatureDB
        self.lock = threading.RLock()
        self.config = config if config is not None else ConfigService()
        root = Path(library_path) if library_path is not None else selected_library(self.config)
        if library_path is None and self.config.get('library_path') and not root.is_dir():
            raise FileNotFoundError(f'已选择的资源库无法连接：{root}。请恢复路径或在应用配置中重新指定 library_path。')
        self.index = LibraryIndex(root)
        from services.resource_availability import ResourceAvailability
        self.availability = ResourceAvailability(self.index)
        self.library_root = str(self.index.root)
        # base_dir continues to mean program files, never the selected library.
        self.base_dir = str(Path(__file__).resolve().parent.parent)
        self.data_dir = self.library_root
        self.images_dir = str(self.index.root / 'images')
        self.inbox_dir = str(self.index.root / 'inbox')
        self.inbox_failed_dir = str(self.index.root / 'inbox/failed')
        for directory in (self.images_dir, self.inbox_dir, self.inbox_failed_dir):
            Path(directory).mkdir(parents=True, exist_ok=True)
        self.features_db_path = str(self.index.path)
        FeatureDB(self.features_db_path)
        self._hashes_cache = self._load_hashes()
        self._images_dirty = self._categories_dirty = self._metadata_dirty = True
        self._recent_cache = None
        self._recent_events = RecentEvents()
        self.recent_changed = self._recent_events.changed
        self._sync_key_index = None
        self._sync_index_lock = threading.RLock()
        self._sync_index_event = threading.Event()
        self._sync_index_event.set()
        self._sync_index_building = False
        self.import_listeners = []
        self.import_context = threading.local()
        self.importer = ResourceImporter(self)
        self._adopt_internal_data()

    def _adopt_internal_data(self):
        """One-time adoption of data already inside this selected library.

        Never reads the old Nekori Repo or a separate Suzu installation.
        A transaction marker makes retries idempotent; source data is kept.
        """
        with self.index.connect() as db:
            adopted = db.execute("SELECT 1 FROM library_meta WHERE key='internal_adopted'").fetchone()
        if adopted:
            return
        # A Suzu-shaped directory explicitly selected as the library is a real
        # compatibility object; use its databases first, JSON only if absent.
        def read_records(db_name, sql, json_name, default):
            path = self.index.root / db_name
            if path.exists():
                from contextlib import closing
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                    return db.execute(sql).fetchall()
            path = self.index.root / json_name
            return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

        order = read_records('order.db', 'SELECT image_path FROM item_orders ORDER BY sort_order', 'order.json', [])
        order = [row[0] if isinstance(row, (tuple, list)) else row for row in order]
        categories = read_records('categories.db', 'SELECT name FROM categories ORDER BY sort_order,id', 'categories.json', {})
        if isinstance(categories, list):
            names = [row[0] for row in categories]
            relations = read_records('categories.db', 'SELECT category_name,image_path FROM category_images', 'categories.json', {})
            categories = {name: [r[1] for r in relations if r[0] == name] for name in names}
        metadata = read_records('metadata.db', 'SELECT image_path,keywords FROM image_metadata', 'metadata.json', {})
        metadata = dict(metadata)
        icons = read_records('categories.db', 'SELECT name,icon_path FROM categories WHERE icon_path IS NOT NULL', 'category_icons.json', {})
        icons = dict(icons)
        referenced = set(order) | set(metadata)
        for paths in categories.values():
            referenced.update(paths)
        referenced.update(p.name for p in Path(self.images_dir).iterdir() if p.is_file() and p.suffix.lower() in self.SUPPORTED_FORMATS)
        # Missing references from source records must also survive adoption.
        for filename in sorted(referenced):
            self.index.register(Path(self.images_dir) / Path(filename).name)
        if order:
            paths = [self._to_abspath(p) for p in order]
            paths += [p for p in self.get_all_images() if p not in paths]
            self.save_order(paths)
        for name, paths in categories.items():
            if name not in ('全部表情', '未分类', '新建分类'):
                self.add_category(name)
                self.add_images_to_category(paths, name)
        self.save_metadata(metadata)
        self.save_category_icons(icons)
        self.index.refresh_status()
        with self.index.connect() as db:
            db.execute("INSERT INTO library_meta VALUES ('internal_adopted','1')")

    def _to_filename(self, filepath):
        resource = self.index.resource(filepath)
        return resource['filename'] if resource else os.path.basename(filepath)

    def _to_abspath(self, filename):
        resource = self.index.resource(filename)
        if resource:
            return self.index.absolute_path(resource)
        return os.path.normcase(os.path.abspath(filename if os.path.isabs(filename) else os.path.join(self.images_dir, filename)))

    def get_all_images(self):
        return [self.index.absolute_path(r) for r in self.index.resources()]

    def category_labels(self):
        """Temporary breadcrumb projection for the existing flat Suzu sidebar."""
        nodes = {n['id']: n for n in self.index.nodes()}
        labels = {}
        def visit(parent, prefix):
            for entry in self.index.content(parent):
                if entry['kind'] == 'node':
                    node = nodes[entry['id']]
                    segment = node['name'].replace('%', '%25').replace('/', '%2F')
                    label = prefix + segment
                    labels[label] = node['id']
                    visit(node['id'], label + ' / ')
        visit(ROOT, '')
        return labels

    def resolve_category(self, category):
        if category is None or category in ('全部表情', '未分类', ROOT):
            return ROOT
        labels = self.category_labels()
        if category in labels:
            return labels[category]
        if category in labels.values():
            return category
        for node in self.index.nodes():
            if node['parent_id'] == ROOT and node['name'] == category:
                return node['id']
        raise KeyError(category)

    def get_all_categories(self):
        resources = {r['id']: self.index.absolute_path(r) for r in self.index.resources()}
        return {label: [resources[e['id']] for e in self.index.content(node) if e['kind'] == 'resource']
                for label, node in self.category_labels().items()}

    def get_exportable_categories(self):
        return list(self.category_labels())

    def get_images_by_category(self, category_name):
        if category_name in (None, '全部表情', ROOT):
            return self.get_all_images()
        if category_name == '未分类':
            reverse = self.get_image_to_categories_map()
            return [p for p in self.get_all_images() if not reverse.get(p)]
        node = self.resolve_category(category_name)
        resources = {r['id']: self.index.absolute_path(r) for r in self.index.resources()}
        return [resources[e['id']] for e in self.index.content(node) if e['kind'] == 'resource']

    def get_categories_by_image(self, filepath):
        return self.get_image_to_categories_map().get(self._to_abspath(filepath), [])

    def get_image_to_categories_map(self):
        result = {}
        for name, paths in self.get_all_categories().items():
            for path in paths:
                result.setdefault(path, []).append(name)
        return result

    def _resource_id(self, path):
        resource = self.index.resource(path)
        if not resource:
            raise KeyError(path)
        return resource['id']

    def save_order(self, filepaths, category_name=None):
        """Order resources within this view without moving interleaved child nodes."""
        node = self.resolve_category(category_name)
        entries = self.index.content(node)
        resources = [self._resource_id(p) for p in filepaths]
        current = [e['id'] for e in entries if e['kind'] == 'resource']
        if len(resources) != len(current) or set(resources) != set(current):
            raise ValueError('Resource order must contain the current category resources exactly once')
        sequence = iter(resources)
        for entry in entries:
            if entry['kind'] == 'resource':
                entry['id'] = next(sequence)
        self.index.set_order(node, entries)

    def add_category(self, category_name):
        if not category_name or category_name in ('全部表情', '未分类', '新建分类'):
            return False
        try:
            self.resolve_category(category_name)
            return False
        except KeyError:
            pass
        self.index.create_node(category_name)
        return True

    def rename_category(self, old_name, new_name):
        if not new_name or new_name in ('全部表情', '未分类', '新建分类'):
            return False
        try:
            self.index.update_node(self.resolve_category(old_name), name=new_name)
            return True
        except (KeyError, ValueError, sqlite3.IntegrityError):
            return False

    def remove_category(self, category_name):
        return self.index.delete_node(self.resolve_category(category_name))

    @_storage_locked
    def save_categories(self, categories_data, strict=False):
        """Existing sidebar reorder consumer; never reconstruct or flatten nodes."""
        labels = self.category_labels()
        for name in categories_data:
            if name not in labels:
                self.add_category(name)
        labels = self.category_labels()
        with self.index.connect() as db:
            for name, paths in categories_data.items():
                node = labels[name]
                resources = list(dict.fromkeys(self._resource_id(p) for p in paths))
                entries = self.index._entries(db, node)
                # Preserve existing mixed positions; append new relationships.
                kept = [(k, i) for k, i in entries if k == 'node' or i in resources]
                current_resources = iter(resources)
                kept = [(k, next(current_resources)) if k == 'resource' else (k, i) for k, i in kept]
                kept.extend(('resource', i) for i in current_resources)
                self.index._write_order(db, node, kept)
            # Sidebar drag order changes siblings only, with child/resource slots intact.
            rank = {labels[n]: i for i, n in enumerate(categories_data)}
            for parent in [ROOT, *labels.values()]:
                entries = self.index._entries(db, parent)
                ordered = iter(sorted([e for e in entries if e[0] == 'node'], key=lambda e: rank.get(e[1], len(rank))))
                self.index._write_order(db, parent, [next(ordered) if k == 'node' else (k, i) for k, i in entries])

    def add_image_to_category(self, filepath, category_name, strict=False):
        if category_name not in self.category_labels():
            self.add_category(category_name)
        added = self.index.add_membership(self._resource_id(filepath), self.resolve_category(category_name))
        return 'success' if added else 'already_exists'

    def remove_image_from_category(self, filepath, category_name):
        return self.index.remove_membership(self._resource_id(filepath), self.resolve_category(category_name))

    def add_images_to_category(self, filepaths, category_name):
        return sum(self.add_image_to_category(p, category_name) == 'success' for p in filepaths)

    def remove_images_from_category(self, filepaths, category_name):
        return sum(self.remove_image_from_category(p, category_name) for p in filepaths)

    # ------------------------------------------------------------------
    # Node-level navigation: the UI works with stable node IDs and the real
    # interleaved content order instead of projecting the tree into labels.
    # ------------------------------------------------------------------

    def node(self, node_id):
        return self.index.node(node_id or ROOT) or {"id": ROOT, "name": "Library", "icon": "", "parent_id": None}

    def node_path(self, node_id):
        """Breadcrumb from the root down to this node; the virtual root is included."""
        return self.index.node_path(node_id or ROOT)

    def child_nodes(self, node_id):
        return self.index.child_nodes(node_id or ROOT)

    def entries_of(self, node_id):
        """Mixed direct content: resources and child nodes in the user's manual order."""
        node_id = node_id or ROOT
        counts = self.node_counts()
        result = []
        for position, entry in enumerate(self.index.entries(node_id)):
            record = entry["record"]
            if entry["kind"] == "resource":
                result.append({
                    "kind": "resource", "id": record["id"], "position": entry["position"],
                    "name": record["display_name"], "path": self.index.absolute_path(record),
                    "status": record["status"], "tags": record["tags"],
                    "resource": record,
                })
            else:
                node_id_value = record["id"]
                stats = counts.get(node_id_value, {"resources": 0, "children": 0})
                result.append({
                    "kind": "node", "id": node_id_value, "position": entry["position"],
                    "name": record["name"], "icon": record["icon"],
                    "children": stats["children"], "total": stats["resources"],
                    "node": record,
                })
        return result

    def node_choices(self):
        """Every node as (id, indented display path), for target pickers."""
        return [(row["id"], "    " * row["depth"] + row["name"])
                for row in self.node_choice_rows()]

    def node_choice_rows(self):
        """Every node with its depth and full path, for searchable target pickers.

        Kept alongside node_choices because a flat indented label is not enough
        once the tree is deep: search and the path line need the actual
        structure rather than padding.
        """
        nodes = {n["id"]: n for n in self.index.nodes()}
        result = []

        def visit(parent, depth, trail):
            for entry in self.index.content(parent):
                if entry["kind"] != "node":
                    continue
                node = nodes.get(entry["id"])
                if node is None:
                    continue
                path = trail + [node["name"]]
                result.append({"id": node["id"], "name": node["name"], "depth": depth,
                               "path": " / ".join(path)})
                visit(node["id"], depth + 1, path)

        visit(ROOT, 0, [])
        return result

    def node_counts(self):
        """resource / child totals per node, computed in one pass."""
        stats = {}
        with self.index.connect() as db:
            for parent_id, resource_count, child_count in db.execute(
                    "SELECT parent_id, SUM(resource_id IS NOT NULL), SUM(node_id IS NOT NULL) "
                    "FROM content GROUP BY parent_id"):
                stats[parent_id] = {"resources": resource_count or 0, "children": child_count or 0}
        return stats

    def create_node(self, name, parent_id=ROOT, icon="", position=None):
        return self.index.create_node(name, parent_id or ROOT, icon, position)

    def rename_node(self, node_id, name):
        self.index.update_node(node_id, name=name)

    def delete_node(self, node_id):
        return self.index.delete_node(node_id)

    def move_node(self, node_id, parent_id, position=None):
        self.index.move_node(node_id, parent_id, position)

    def move_nodes(self, node_ids, parent_id, position=None):
        self.index.move_nodes(node_ids, parent_id, position)

    def set_content_order(self, node_id, entries):
        """entries: [{'kind': 'resource'|'node', 'id': ...}] in the wanted order."""
        with self.lock:
            self.index.set_order(node_id or ROOT, [(e["kind"], e["id"]) for e in entries])

    def reorder_resources(self, node_id, resource_ids):
        self.index.reorder_resources(node_id or ROOT, resource_ids)

    def resource_path(self, resource_id):
        record = self.index.resource_by_id(resource_id)
        return self.index.absolute_path(record) if record else None

    def resource_of(self, filepath):
        return self.index.resource(filepath)

    def set_node_icon(self, node_id, value):
        """value is either an emoji/text or a local image path (copied into the library)."""
        if value and Path(value).suffix.lower() in IMAGE_SUFFIXES and Path(value).is_file():
            value = self._store_node_icon_file(value)
        self.index.update_node(node_id, icon=value or "")

    def _store_node_icon_file(self, source):
        import shutil
        target_dir = Path(self.data_dir) / "category_icons"
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(source).suffix.lower()
        filename = hashlib.md5(Path(source).read_bytes()).hexdigest() + suffix
        target = target_dir / filename
        if not target.exists():
            shutil.copy2(source, target)
        return "category_icons/" + filename

    def node_icon_path(self, node_id):
        """Absolute path of an image node icon, or None when the icon is text/empty."""
        record = self.index.node(node_id)
        if not record:
            return None
        value = record.get("icon") or ""
        if Path(value).suffix.lower() not in IMAGE_SUFFIXES:
            return None
        path = resolve_icon_path(self.data_dir, value)
        return str(path) if Path(path).is_file() else None

    def move_resources_to(self, filepaths, target_node, copy=True, source_node=None, position=None):
        """Copy adds the target relation; Move also drops the source relation."""
        with self.lock:
            ids = self.index.resource_ids(filepaths)
            return self.index.assign_memberships(ids, target_node or ROOT, copy=copy,
                                                 source=source_node, position=position)

    def resource_metadata(self, filepath):
        record = self.index.resource(filepath)
        return self.index.resource_metadata(record["id"]) if record else {}

    def set_resource_metadata(self, filepath, values):
        record = self.index.resource(filepath)
        if record:
            self.index.set_resource_metadata(record["id"], values)

    def all_tags(self):
        """Tag to usage count, used by the quick filter strip."""
        counts = {}
        for record in self.index.resources():
            for tag in self.parse_tags(record["tags"]):
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())))

    # -- Tag as a global library metadatum -----------------------------
    # A tag is not owned by a category: resources carry tags, and the single
    # manual tag order belongs to the library. These four methods are the only
    # place tag *identity* changes; the panel only projects them.
    TAG_ORDER_KEY = 'tag_order'

    def tag_order(self):
        """The one global manual tag order for this library."""
        raw = self.index.meta(self.TAG_ORDER_KEY, '[]')
        try:
            names = json.loads(raw or '[]')
        except ValueError:
            return []
        return [str(name) for name in names] if isinstance(names, list) else []

    def set_tag_order(self, names):
        ordered = [str(name) for name in names]
        self.index.set_meta(self.TAG_ORDER_KEY,
                            json.dumps(list(dict.fromkeys(ordered)), ensure_ascii=False))

    def tag_usage(self, node_id=None, resource_ids=None):
        """Tag → resource count for the effective scope of one location.

        `resource_ids` is the explicit set a search or filter is actually
        showing; `node_id` is a category and counts its whole subtree, so a
        collapsed child still contributes its tags. Without either, the whole
        library is counted -- that is the library-wide view, not a location.
        """
        return self.count_tags(self.index.tag_strings(node_id=node_id,
                                                      resource_ids=resource_ids))

    def resources_in_subtree(self, node_id):
        """Unique resources for a committed category operation, one query."""
        with self.index.connect() as db:
            rows = db.execute(
                "WITH RECURSIVE tree(id) AS (SELECT ? UNION ALL "
                "SELECT n.id FROM nodes n JOIN tree t ON n.parent_id=t.id) "
                "SELECT DISTINCT r.* FROM resources r JOIN content c ON c.resource_id=r.id "
                "JOIN tree t ON c.parent_id=t.id", (node_id,)).fetchall()
        return [dict(row) for row in rows]

    def count_tags(self, tag_texts):
        counts = {}
        for text in tag_texts:
            for tag in self.parse_tags(text):
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def rename_tag(self, old, new):
        """Rename one tag on every resource that carries it; files untouched."""
        new = (new or '').strip()
        if not old or not new or old == new or any(ch.isspace() for ch in new):
            return 0
        changed = 0
        for record in self.index.resources():
            tags = self.parse_tags(record['tags'])
            if old not in tags:
                continue
            renamed = list(dict.fromkeys(new if tag == old else tag for tag in tags))
            self.index.set_search_fields(record['id'], tags=self.serialize_tags(renamed))
            changed += 1
        return changed

    def delete_tags(self, names):
        """Drop the tag relation everywhere; no resource is removed."""
        wanted = {str(name) for name in names}
        if not wanted:
            return 0
        changed = 0
        for record in self.index.resources():
            tags = self.parse_tags(record['tags'])
            if not wanted.intersection(tags):
                continue
            kept = [tag for tag in tags if tag not in wanted]
            self.index.set_search_fields(record['id'], tags=self.serialize_tags(kept))
            changed += 1
        return changed

    def apply_tags(self, filepaths, tags, mode="add"):
        """mode: add appends, remove deletes, replace overwrites."""
        for path in filepaths:
            existing = self.get_image_keywords(path)
            if mode == "add":
                result = self.merge_tags(existing, self.serialize_tags(tags))
            elif mode == "remove":
                result = self.remove_tags(existing, self.serialize_tags(tags))
            else:
                result = self.serialize_tags(tags)
            self.set_image_keywords(path, result)

    def get_all_category_icons(self):
        nodes = {n['id']: n for n in self.index.nodes()}
        return {label: str(resolve_icon_path(self.data_dir, nodes[node]['icon']))
                if Path(nodes[node]['icon']).suffix.lower() in IMAGE_SUFFIXES else nodes[node]['icon']
                for label, node in self.category_labels().items() if nodes[node]['icon']}

    def save_category_icons(self, icons_data):
        for label, node in self.category_labels().items():
            value = icons_data.get(label, '') or ''
            if Path(value).suffix.lower() in IMAGE_SUFFIXES:
                value = portable_icon_path(self.data_dir, value)
            self.index.update_node(node, icon=value)

    def set_category_icon(self, category_name, filepath):
        """Accepts a library image, an external file, or an emoji string."""
        self.set_node_icon(self.resolve_category(category_name), filepath)

    def get_category_icon(self, category_name):
        return self.get_all_category_icons().get(category_name)

    def get_all_metadata(self):
        return {self.index.absolute_path(r): r['tags'] for r in self.index.resources()}

    def save_metadata(self, metadata):
        with self.index.connect() as db:
            for path, tags in metadata.items():
                resource = self.index.resource(path)
                if resource:
                    db.execute('UPDATE resources SET tags=? WHERE id=?', (str(tags or ''), resource['id']))

    def get_image_keywords(self, filepath):
        resource = self.index.resource(filepath)
        return resource['tags'] if resource else ''

    def set_image_keywords(self, filepath, keywords_str):
        self.index.set_search_fields(self._resource_id(filepath), tags=keywords_str)

    def get_search_metadata(self):
        revision=self.index.search_revision
        cached=getattr(self,'_search_metadata_snapshot',None)
        if cached is not None and cached[0]==revision:return cached[1]
        texts = self.index.search_texts()
        result={self.index.absolute_path(r): texts.get(r['id'],'') for r in self.index.resources()}
        if self.index.search_revision==revision:self._search_metadata_snapshot=(revision,result)
        return result

    def search_images(self, keyword, category_name='全部表情'):
        from services.search_text import normalize_search
        images = self.get_images_by_category(category_name)
        keyword = normalize_search(keyword.strip())
        if not keyword:
            return images
        texts = self.get_search_metadata()
        return [p for p in images if keyword in texts.get(p, '')]

    def _get_recent_limit(self):
        return int(self.config.get('recent_limit', 30))

    def get_recent_images(self, limit=None):
        with self.index.connect() as db:
            rows = db.execute('SELECT r.* FROM recent h JOIN resources r ON h.resource_id=r.id ORDER BY h.used_at DESC LIMIT ?',
                              (limit if limit is not None else self._get_recent_limit(),)).fetchall()
            return [self.index.absolute_path(r) for r in rows if Path(self.index.absolute_path(r)).is_file()]

    def add_recent_image(self, filepath, limit=None):
        resource_id = self._resource_id(filepath)
        with self.index.connect() as db:
            db.execute('INSERT INTO recent VALUES (?,?) ON CONFLICT(resource_id) DO UPDATE SET used_at=excluded.used_at',
                       (resource_id, time.time_ns()))
            db.execute('DELETE FROM recent WHERE resource_id NOT IN (SELECT resource_id FROM recent ORDER BY used_at DESC LIMIT ?)',
                       (limit if limit is not None else self._get_recent_limit(),))
        self.recent_changed.emit()

    def _load_hashes(self):
        with self.index.connect() as db:
            return {r[0]: r[1] for r in db.execute('SELECT md5,image_path FROM image_features WHERE md5 IS NOT NULL')}

    def _save_hashes(self, strict=False):
        with self.index.connect() as db:
            db.executemany('INSERT INTO image_features(image_path,md5) VALUES (?,?) ON CONFLICT(image_path) DO UPDATE SET md5=excluded.md5',
                           [(filename, md5) for md5, filename in self._hashes_cache.items()])

    def save_file(self, source_path, strict=False, target=None, *, library_added_seq=None):
        return self.importer.file(source_path, target or ImportTarget(), strict, library_added_seq=library_added_seq)

    def replace_normalized(self,existing,normalized):
        """Keep catalog identity. Stage bytes before atomic replacement and roll back on failure."""
        import shutil
        data,ext,digest=normalized
        with self.lock:
            record=self.index.resource(existing)
            if not record:raise FileNotFoundError(existing)
            old=Path(self.index.absolute_path(record))
            if old.read_bytes()==data:return str(old)
            target=old.with_suffix(ext)
            if target!=old and target.exists():target=old.with_name(uuid.uuid4().hex+ext)
            stage=old.with_name('.'+uuid.uuid4().hex+'.new')
            backup=old.with_name('.'+uuid.uuid4().hex+'.old')
            replaced=False;restored=False
            try:
                with stage.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
                if target==old:shutil.copy2(old,backup)
                os.replace(stage,target);replaced=True
                state=self.index._ocr_state(record)
                state.update(source=None,revision=state.get('revision',0)+1)
                if not state.get('manual'):state.update(status='unrecognized',error='')
                metadata=json.loads(record.get('metadata_json') or '{}');metadata.pop('thumb_frame',None)
                with self.index.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('UPDATE resources SET relative_path=?,status=\'normal\',ocr_text=?,ocr_state_json=?,metadata_json=? WHERE id=?',
                        (self.index.relative_path(target),record['ocr_text'] if state.get('manual') else '',json.dumps(state,ensure_ascii=False),json.dumps(metadata,ensure_ascii=False),record['id']))
                    db.execute('DELETE FROM image_features WHERE image_path=?',(self._to_filename(str(old)),))
                    db.execute('INSERT INTO image_features(image_path,md5) VALUES (?,?) ON CONFLICT(image_path) DO UPDATE SET md5=excluded.md5',
                        (self._to_filename(str(target)),digest))
                restored=True
                if target!=old:old.unlink()
                old_name=self._to_filename(str(old))
                self._hashes_cache={k:v for k,v in self._hashes_cache.items() if v!=old_name}
                self._hashes_cache[digest]=self._to_filename(str(target))
                self._sync_key_index=None;self._images_dirty=True
                return str(target)
            except Exception:
                if replaced and not restored:
                    if target==old:os.replace(backup,old)
                    else:target.unlink(missing_ok=True)
                raise
            finally:
                stage.unlink(missing_ok=True)
                if restored or not replaced:backup.unlink(missing_ok=True)

    def save_image(self, qimage, target=None):
        return self.importer.image(qimage, target or ImportTarget())

    def import_paths(self, paths, target=None, progress=None):
        return self.importer.paths(paths, target or ImportTarget(), progress)

    def force_reload(self):
        self._hashes_cache = self._load_hashes()
        self._sync_key_index = None
        self.availability.refresh()

    def cleanup_dead_links(self):
        """Missing is an indexed state, never a reason to erase user metadata."""
        self.availability.refresh()

    def rebind_resource(self, resource_id, path):
        resource = self.index.resource(resource_id)
        if not resource:
            raise KeyError(resource_id)
        self.index.rebind(resource_id, path)
        self._remove_feature_record(resource['filename'])
        self._hashes_cache = self._load_hashes()
        self._sync_key_index = None

    def forget_resource(self, resource_id):
        resource = self.index.resource(resource_id)
        if not resource:
            return False
        self._remove_feature_record(resource['filename'])
        removed = self.index.forget_resource(resource_id)
        self._hashes_cache = self._load_hashes()
        self._sync_key_index = None
        return removed

    def delete_images_batch(self, filepaths, progress_callback=None, cancel_check=None):
        from services.recycle_bin import recycle_file
        paths = list(dict.fromkeys(filepaths))
        result = dict(requested=len(paths), deleted=0, missing_cleaned=0, failed=0,
                      cancelled=0, unprocessed=0, failure_details={})
        for i, path in enumerate(paths):
            if cancel_check and cancel_check():
                result['cancelled'] = result['unprocessed'] = len(paths) - i
                break
            try:
                with self.lock:
                    resource = self.index.resource(path)
                    if not resource:
                        raise ValueError('Resource is not owned by this library')
                    absolute = self.index.absolute_path(resource)
                    if self.availability.exists(resource['id'], revalidate=True):
                        recycle_file(absolute, self.library_root)
                        # Retain a Missing record if DB removal fails after recycling.
                        result['deleted'] += 1
                    else:
                        result['missing_cleaned'] += 1
                    self.forget_resource(resource['id'])
            except Exception as exc:
                result['failed'] += 1
                result['failure_details'][path] = str(exc)
            if progress_callback:
                progress_callback(i + 1, len(paths))
        return result

    def delete_image(self, filepath):
        result = self.delete_images_batch([filepath])
        return result['failed'] == 0 and result['deleted'] + result['missing_cleaned'] == 1


    def _persist_sync_key(self, filename, sync_key, file_size, mtime_ns, md5_val=None, strict=False):
        """持久化 sync_key 及其文件状态校验字段到 SQLite features.db"""
        try:
            with self.index.connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO image_features (image_path, sync_key, file_size, mtime_ns, md5)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(image_path) DO UPDATE SET
                        sync_key = excluded.sync_key,
                        file_size = excluded.file_size,
                        mtime_ns = excluded.mtime_ns,
                        md5 = COALESCE(excluded.md5, image_features.md5)
                """, (os.path.basename(filename), sync_key, file_size, mtime_ns, md5_val))
                conn.commit()
        except Exception as e:
            print(f"[WARNING] 持久化 sync_key 失败: {e}")
            if strict:
                raise

    def _remove_feature_record(self, filename):
        """从 features.db 移除失效文件的特征记录"""
        try:
            with self.index.connect() as conn:
                conn.execute("DELETE FROM image_features WHERE image_path = ?", (os.path.basename(filename),))
                conn.commit()
        except Exception as e:
            print(f"[WARNING] 从 features.db 移除记录失败: {e}")

    def _get_sync_key_index(self):
        """
        线程安全、Single-Flight、持久化与增量维护的 sync_key 索引获取函数
        - 仅允许单任务构建，并发线程等待同一结果
        - 全程使用局部字典构建完成后原子发布，禁止暴露半成品
        - 优先从 features.db 批量读取持久化数据，校验 size+mtime_ns，避免全库重复解码
        """
        # 1. 快速检查内存缓存 / 状态同步
        with self._sync_index_lock:
            if self._sync_key_index is not None:
                return self._sync_key_index

            if self._sync_index_building:
                event_to_wait = self._sync_index_event
            else:
                self._sync_index_building = True
                self._sync_index_event.clear()
                event_to_wait = None

        # 并发线程等待构建完成
        if event_to_wait is not None:
            event_to_wait.wait()
            with self._sync_index_lock:
                return self._sync_key_index if self._sync_key_index is not None else {}

        # 2. 当前构建者在局部字典中装配
        local_index = {}
        try:
            if not os.path.exists(self.images_dir):
                with self._sync_index_lock:
                    self._sync_key_index = local_index
                return self._sync_key_index

            from services.hasher import compute_sync_key

            # A. 批量从 features.db 读取持久化数据
            db_records = {}
            try:
                with self.index.connect() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT image_path, sync_key, file_size, mtime_ns FROM image_features WHERE sync_key IS NOT NULL")
                    for row in cursor.fetchall():
                        db_records[row[0]] = (row[1], row[2], row[3])
            except Exception as e:
                print(f"[WARNING] 从 features.db 批量读取 sync_key 失败: {e}")

            # Files already written by an interrupted import are not registered
            # yet; scanning them too lets a retry recognise the orphan as a
            # duplicate instead of writing the same picture a second time.
            known = {r['filename'] for r in self.index.resources()}
            try:
                on_disk = {p.name for p in Path(self.images_dir).iterdir()
                           if p.is_file() and p.suffix.lower().endswith(self.SUPPORTED_FORMATS)}
            except OSError:
                on_disk = set()
            filenames = sorted(known | on_disk)
            missing_or_dirty = []

            for filename in filenames:
                if not filename.lower().endswith(self.SUPPORTED_FORMATS):
                    continue
                # These names come from the selected library's images/ folder.
                # _to_abspath() queries the catalog for each name; rebuilding
                # this index must not issue one SQLite lookup per resource.
                abspath = os.path.join(self.images_dir, filename)
                try:
                    stat_res = os.stat(abspath)
                    cur_size = stat_res.st_size
                    cur_mtime_ns = getattr(stat_res, 'st_mtime_ns', int(stat_res.st_mtime * 1e9))
                except Exception:
                    continue

                cached = db_records.get(filename)
                # 状态校验: size 与 mtime_ns 均一致时安全命中持久化数据
                if cached and cached[0] and cached[1] == cur_size and cached[2] == cur_mtime_ns:
                    local_index.setdefault(cached[0], filename)
                else:
                    missing_or_dirty.append((filename, abspath, cur_size, cur_mtime_ns))

            # B. 对缺失或外部修改的文件增量计算并回填数据库
            if missing_or_dirty:
                records_to_update = []
                for filename, abspath, cur_size, cur_mtime_ns in missing_or_dirty:
                    skey = compute_sync_key(abspath)
                    if skey:
                        local_index.setdefault(skey, filename)
                        records_to_update.append((filename, skey, cur_size, cur_mtime_ns))

                if records_to_update:
                    try:
                        with self.index.connect() as conn:
                            cursor = conn.cursor()
                            cursor.executemany("""
                                INSERT INTO image_features (image_path, sync_key, file_size, mtime_ns)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(image_path) DO UPDATE SET
                                    sync_key = excluded.sync_key,
                                    file_size = excluded.file_size,
                                    mtime_ns = excluded.mtime_ns
                            """, records_to_update)
                            conn.commit()
                    except Exception as e:
                        print(f"[WARNING] 批量回填 sync_key 到 DB 失败: {e}")

        except Exception as e:
            print(f"[ERROR] 构建 sync_key 索引失败: {e}")
        finally:
            with self._sync_index_lock:
                self._sync_key_index = local_index
                self._sync_index_building = False
                self._sync_index_event.set()

        return self._sync_key_index

    @_storage_locked
    def _atomic_save_json(self, target_file, data, indent=4):
        """原子写入 JSON，防止文件写入损坏"""
        temp_file = f"{target_file}.{uuid.uuid4()}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            for attempt in range(5):
                try:
                    os.replace(temp_file, target_file)
                    break
                except OSError as exc:
                    if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 4:
                        raise
                    time.sleep(0.05 * (2 ** attempt))
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def _calculate_pixel_hash(self, img):
        """计算图片纯像素数据的 MD5 哈希值，用于精准去重"""
        try:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            return hashlib.md5(img.tobytes()).hexdigest()
        except Exception as e:
            print(f"[WARNING] 计算像素哈希失败: {e}")
            return None

    def _calculate_bytes_hash(self, data_bytes):
        """计算二进制数据的 MD5 哈希值"""
        return hashlib.md5(data_bytes).hexdigest()

    def is_animated(self, filepath):
        """判断图片是否为动图格式"""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in ['.gif', '.webp']

    @staticmethod
    def parse_tags(tags_str):
        if not tags_str: return []
        tags = []
        for t in tags_str.split(' '):
            if t and t not in tags:
                tags.append(t)
        return tags

    @staticmethod
    def serialize_tags(tags_list):
        return " ".join(tags_list)

    @staticmethod
    def merge_tags(existing_tags_str, new_tags_str):
        existing_list = StorageService.parse_tags(existing_tags_str)
        new_list = StorageService.parse_tags(new_tags_str)
        for tag in new_list:
            if tag not in existing_list:
                existing_list.append(tag)
        return StorageService.serialize_tags(existing_list)

    @staticmethod
    def remove_tags(existing_tags_str, remove_tags_str):
        existing_list = StorageService.parse_tags(existing_tags_str)
        remove_list = StorageService.parse_tags(remove_tags_str)
        final_list = [tag for tag in existing_list if tag not in remove_list]
        return StorageService.serialize_tags(final_list)

    def generate_new_filename(self, extension=".png"):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"{timestamp}{extension}"

    @staticmethod
    def detect_format_magic(data_bytes: bytes) -> str:
        """
        根据文件魔数识别真实格式
        返回值: 'tgs', 'webm', 'webp', 'gif', 'png', 'jpeg', 'apng', 'bmp', 'tiff', 或 'unknown'
        """
        if not data_bytes or len(data_bytes) < 4:
            return "unknown"

        # TGS 是 gzip 压缩的 Lottie JSON，不能把所有 gzip 都当成贴纸。
        if data_bytes[:2] == b"\x1f\x8b":
            try:
                from services.tgs_converter import read_tgs_json
                read_tgs_json(data_bytes)
                return "tgs"
            except ValueError:
                pass

        # WebM / Matroska 魔数: 1A 45 DF A3
        if data_bytes.startswith(b"\x1a\x45\xdf\xa3"):
            return "webm"

        # RIFF 容器 (WebP): RIFF....WEBP
        if data_bytes.startswith(b"RIFF") and len(data_bytes) >= 12 and data_bytes[8:12] == b"WEBP":
            return "webp"

        # GIF 魔数: GIF87a / GIF89a
        if data_bytes.startswith(b"GIF87a") or data_bytes.startswith(b"GIF89a"):
            return "gif"

        # PNG 魔数: 89 50 4E 47 0D 0A 1A 0A
        if data_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            # 检查是否为 APNG
            if b"acTL" in data_bytes[:1024]:
                return "apng"
            return "png"

        # JPEG 魔数: FF D8 FF
        if data_bytes.startswith(b"\xff\xd8\xff"):
            return "jpeg"

        # BMP 魔数: BM
        if data_bytes.startswith(b"BM"):
            return "bmp"

        # TIFF 魔数: II*\x00 或 MM\x00*
        if data_bytes.startswith(b"II*\x00") or data_bytes.startswith(b"MM\x00*"):
            return "tiff"

        return "unknown"

    def _convert_source_to_standard_bytes(self, data_bytes: bytes, source_path=None) -> tuple[bytes, str, bool]:
        """
        魔数识别并对动态格式进行归一化转码
        返回: (standard_bytes, format_type, is_animated)
        若转码失败则抛出异常或返回 None
        """
        fmt = self.detect_format_magic(data_bytes)

        # 矢量动画先渲染为 GIF，再复用 GIF 的单帧归一化和去重流程。
        if fmt == "tgs":
            from services.tgs_converter import convert_tgs
            return self._convert_source_to_standard_bytes(convert_tgs(data_bytes, "gif"))

        # 1. 动态 WebM 视频 -> 转为 GIF
        if fmt == "webm":
            from services.webm_converter import (
                is_ffmpeg_available, convert_video_to_gif, webm_single_frame_png,
            )
            if not is_ffmpeg_available():
                raise RuntimeError("FFmpeg 缺失或不可用，无法转换 WebM 动态贴纸")

            import tempfile
            temp_in = None
            temp_out = None
            need_clean_in = False
            try:
                # 写入临时文件供 FFmpeg 读取（若已有 source_path 且格式相符则直接使用，否则写入临时文件）
                if source_path and os.path.exists(source_path):
                    temp_in = source_path
                    need_clean_in = False
                else:
                    fd_in, temp_in = tempfile.mkstemp(suffix=".webm")
                    with os.fdopen(fd_in, "wb") as f:
                        f.write(data_bytes)
                    need_clean_in = True

                # 单帧不经过 fps/调色板，保留原尺寸和完整 alpha。
                single_png = webm_single_frame_png(temp_in)
                if single_png is not None:
                    return single_png, "png", False

                fd_out, temp_out = tempfile.mkstemp(suffix=".gif")
                os.close(fd_out)

                convert_video_to_gif(temp_in, temp_out)

                if not os.path.exists(temp_out) or os.path.getsize(temp_out) == 0:
                    raise RuntimeError("FFmpeg 转换输出文件无效或为空")

                with open(temp_out, "rb") as f:
                    gif_bytes = f.read()

                # 校验转换后的 GIF
                with Image.open(io.BytesIO(gif_bytes)) as test_img:
                    n_frames = getattr(test_img, "n_frames", 1)
                    if n_frames < 1:
                        raise RuntimeError("转换后的 GIF 图像帧数无效")

                return gif_bytes, "gif", True
            finally:
                if temp_in and need_clean_in and os.path.exists(temp_in):
                    try:
                        os.remove(temp_in)
                    except Exception:
                        pass
                if temp_out and os.path.exists(temp_out):
                    try:
                        os.remove(temp_out)
                    except Exception:
                        pass

        # 2. WebP 格式：判断是动态还是静态
        if fmt == "webp":
            try:
                with Image.open(io.BytesIO(data_bytes)) as img:
                    is_animated = getattr(img, "is_animated", False) and getattr(img, "n_frames", 1) > 1
            except Exception as e:
                raise RuntimeError(f"解析 WebP 图像失败: {e}")

            if is_animated:
                from services.webm_converter import convert_animated_webp_to_gif
                try:
                    gif_bytes = convert_animated_webp_to_gif(data_bytes)
                    with Image.open(io.BytesIO(gif_bytes)) as test_img:
                        if getattr(test_img, "n_frames", 1) < 1:
                            raise RuntimeError("转换后的 GIF 帧数无效")
                    return gif_bytes, "gif", True
                except Exception as e:
                    raise RuntimeError(f"动态 WebP 转 GIF 失败: {e}")
            else:
                # 静态 WebP 不转为 GIF，保持现有静态处理方式
                return data_bytes, "webp", False

        # 3. APNG 格式 -> 转换为 GIF
        if fmt == "apng":
            try:
                from services.qq_extractor import QQExtractor
                import tempfile
                fd_in, temp_in = tempfile.mkstemp(suffix=".png")
                with os.fdopen(fd_in, "wb") as f:
                    f.write(data_bytes)
                temp_gif = None
                try:
                    temp_gif = QQExtractor.convert_apng_to_gif(temp_in)
                    if temp_gif and os.path.exists(temp_gif):
                        with open(temp_gif, "rb") as f:
                            gif_bytes = f.read()
                        return gif_bytes, "gif", True
                    else:
                        raise RuntimeError("APNG 转换 GIF 失败")
                finally:
                    if os.path.exists(temp_in):
                        try:
                            os.remove(temp_in)
                        except Exception:
                            pass
                    if temp_gif and os.path.exists(temp_gif):
                        try:
                            os.remove(temp_gif)
                        except Exception:
                            pass
            except Exception as e:
                raise RuntimeError(f"APNG 转 GIF 异常: {e}")

        # 4. 普通 GIF / PNG / JPEG / BMP / TIFF
        # GIF 不能仅依据文件格式判定为动图：剪贴板发送静态图片时，
        # services.clipboard 会将 PNG 转换为单帧 GIF。单帧 GIF 应先还原为
        # 静态 PNG，使其进入现有的 RGBA 清理与像素哈希去重流程。
        if fmt == "gif":
            try:
                with Image.open(io.BytesIO(data_bytes)) as img:
                    n_frames = getattr(img, "n_frames", 1)
                    if n_frames <= 1:
                        img.seek(0)
                        rgba_img = img.convert("RGBA").copy()
                        output_io = io.BytesIO()
                        rgba_img.save(output_io, format="PNG", optimize=True)
                        return output_io.getvalue(), "png", False
            except Exception as e:
                raise RuntimeError(f"解析单帧 GIF 失败: {e}")

            # 多帧 GIF 保留原始数据，继续走动态资源流程。
            return data_bytes, "gif", True

        return data_bytes, fmt, False

    @_storage_locked
    def _standardize_and_save(self, data_bytes, original_ext, source_path=None, pil_source=None, strict=False, force_new=False):
        stage = "清洗失败"
        try:
            # 步骤 1：格式归一化预处理
            if pil_source is not None:
                img = pil_source
                is_animated = False
                final_ext = '.png'
            else:
                norm_bytes, norm_fmt, is_norm_animated = self._convert_source_to_standard_bytes(data_bytes, source_path)
                img = Image.open(io.BytesIO(norm_bytes))
                is_animated = getattr(img, "is_animated", False) or is_norm_animated
                final_ext = '.gif' if is_animated else '.png'

            # 步骤 2：清洗与编码
            if is_animated:
                # 动态资源（GIF）保留原始帧与透明通道，对转换后的最终 GIF 执行哈希
                final_bytes = norm_bytes
                file_hash = self._calculate_bytes_hash(final_bytes)
            else:
                # 静态资源（静态 WebP/PNG/JPG/BMP 等）
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                clean_img = Image.new('RGBA', img.size)
                clean_img.paste(img, (0, 0))

                output_io = io.BytesIO()
                clean_img.save(output_io, format="PNG", optimize=True)
                final_bytes = output_io.getvalue()
                final_ext = '.png'

                # 语义钉死：写入 image_features.md5 的值一律是 file_md5
                file_hash = self._calculate_bytes_hash(final_bytes)

            # 步骤 3：哈希查重与去重入库
            stage = "索引保存失败"
            # L1 快路径：用最终入库文件的 file_md5 在 _hashes_cache 中查找
            self.import_context.normalized=(final_bytes,final_ext,file_hash)
            if not force_new and file_hash and file_hash in self._hashes_cache:
                existing_filename = self._hashes_cache[file_hash]
                existing_path = self._to_abspath(existing_filename)
                if os.path.exists(existing_path):
                    self._repair_saved_index(existing_path, file_hash, strict=strict)
                    return existing_path, True
                else:
                    del self._hashes_cache[file_hash]

            # L2 也扫描已落盘但缺少哈希记录的资源，支持重启后的恢复。
            pixel_hash = self._calculate_pixel_hash(clean_img) if not is_animated else None
            skey = f"f:{file_hash}" if is_animated else (f"p:{pixel_hash}" if pixel_hash else None)
            if skey and not force_new:
                sync_index = self._get_sync_key_index()
                existing_filename = sync_index.get(skey)
                if existing_filename:
                    existing_path = self._to_abspath(existing_filename)
                    if os.path.exists(existing_path):
                        self._repair_saved_index(existing_path, file_hash, strict=strict)
                        return existing_path, True
                    with self._sync_index_lock:
                        sync_index.pop(skey, None)
                    self._remove_feature_record(existing_filename)

            # 步骤 4：正式写入磁盘
            stage = "图片写入失败"
            filename = self.generate_new_filename(final_ext)
            filepath = os.path.join(self.images_dir, filename)

            with open(filepath, 'wb') as f:
                f.write(final_bytes)

            if file_hash:
                stage = "索引保存失败"
                self._hashes_cache[file_hash] = filename
                self._save_hashes(strict=strict)

            # 获取落盘后的准确文件状态
            try:
                stat_res = os.stat(filepath)
                cur_size = stat_res.st_size
                cur_mtime_ns = getattr(stat_res, 'st_mtime_ns', int(stat_res.st_mtime * 1e9))
            except Exception:
                cur_size = len(final_bytes)
                cur_mtime_ns = 0

            # 同步维护内存中的 sync_key 索引并持久化（强制覆盖，防止被失效旧键阻挡）
            if not is_animated:
                pixel_hash = self._calculate_pixel_hash(clean_img)
                if pixel_hash:
                    skey = f"p:{pixel_hash}"
                    with self._sync_index_lock:
                        self._get_sync_key_index()[skey] = filename
                    self._persist_sync_key(filename, skey, cur_size, cur_mtime_ns, md5_val=file_hash, strict=strict)
            else:
                skey = f"f:{file_hash}"
                with self._sync_index_lock:
                    self._get_sync_key_index()[skey] = filename
                self._persist_sync_key(filename, skey, cur_size, cur_mtime_ns, md5_val=file_hash, strict=strict)

            self._images_dirty = True
            return self._to_abspath(filename), False

        except Exception as e:
            print(f"[ERROR] {stage}: {e}")
            if strict:
                raise RuntimeError(f"{stage}: {e}") from e
            return None, False

    def _repair_saved_index(self, filepath, file_hash, strict=False):
        """重复文件也补齐持久化索引，恢复此前落盘后中断的入库。"""
        filename = self._to_filename(filepath)
        # 像素相同的文件编码可能不同；数据库记录必须使用实际落盘字节的哈希。
        with open(filepath, "rb") as source:
            actual_hash = self._calculate_bytes_hash(source.read())
        self._hashes_cache[file_hash] = filename
        self._hashes_cache[actual_hash] = filename
        self._save_hashes(strict=strict)
        file_hash = actual_hash
        with Image.open(filepath) as image:
            animated = getattr(image, "is_animated", False)
            skey = f"f:{file_hash}" if animated else f"p:{self._calculate_pixel_hash(image)}"
        stat = os.stat(filepath)
        self._persist_sync_key(filename, skey, stat.st_size, stat.st_mtime_ns, file_hash, strict=strict)
        index = self._get_sync_key_index()
        with self._sync_index_lock:
            index[skey] = filename
        self._images_dirty = True

    def _save_qimage_source(self, qimage):
        """
        保存剪贴板或传入的 QImage 对象
        针对静态位图在内存中直接转换为 RGBA PIL Image，消除多余的 Qt PNG 压缩与 PIL 二进制解码
        """
        from PySide6.QtGui import QImage
        if not isinstance(qimage, QImage) or qimage.isNull():
            return None, False

        try:
            qimg_rgba = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
            w, h = qimg_rgba.width(), qimg_rgba.height()
            ptr = qimg_rgba.constBits()
            pil_img = Image.frombuffer("RGBA", (w, h), bytes(ptr), "raw", "RGBA", 0, 1)
            return self._standardize_and_save(None, ".png", pil_source=pil_img)
        except Exception as e:
            print(f"[WARNING] QImage 快速转 PIL 失败，回退至兼容模式: {e}")
            from PySide6.QtCore import QByteArray, QBuffer, QIODevice
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            qimage.save(buffer, "PNG")
            return self._standardize_and_save(byte_array.data(), ".png")

    def _save_file_source(self, source_path, strict=False):
        if not os.path.exists(source_path):
            if strict:
                raise FileNotFoundError(source_path)
            return None, False

        try:
            with open(source_path, 'rb') as f:
                data_bytes = f.read()

            _, ext = os.path.splitext(source_path)
            ext = ext.lower()
            if not ext:
                ext = ".png"

            return self._standardize_and_save(data_bytes, ext, source_path=source_path, strict=strict)
        except Exception as e:
            if strict:
                raise
            print(f"[ERROR] 文件入库失败: {e}")
            return None, False
