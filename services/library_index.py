"""The authoritative library catalog. No Qt dependency and no image decoding.

Stable IDs describe resources and recursive nodes. Content entries are both
membership and manual position: resources and direct children share one order.
ROOT is a virtual library view, never a user category.
"""
import json
import os
import sqlite3
import uuid
import itertools
from contextlib import contextmanager
from pathlib import Path

ROOT = "__library__"
SCHEMA_VERSION = 3


class LibraryIndex:
    def __init__(self, root):
        self._changes = itertools.count()
        self.search_revision = 0
        self._search_projections = {}
        self._search_snapshot = None
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "index.sqlite3"
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, SCHEMA_VERSION):
                raise ValueError(f"Unsupported library schema: {version}")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL UNIQUE,
                    relative_path TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '', ocr_text TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'normal' CHECK(status IN ('normal','missing')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY, parent_id TEXT REFERENCES nodes(id),
                    name TEXT NOT NULL, icon TEXT NOT NULL DEFAULT '',
                    UNIQUE(parent_id, name)
                );
                CREATE TABLE IF NOT EXISTS content (
                    parent_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                    resource_id TEXT REFERENCES resources(id) ON DELETE CASCADE,
                    node_id TEXT REFERENCES nodes(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    CHECK((resource_id IS NULL) != (node_id IS NULL)),
                    UNIQUE(parent_id, resource_id), UNIQUE(node_id)
                );
                CREATE INDEX IF NOT EXISTS content_order ON content(parent_id, position);
                CREATE INDEX IF NOT EXISTS content_resource ON content(resource_id);
                CREATE TABLE IF NOT EXISTS recent (
                    resource_id TEXT PRIMARY KEY REFERENCES resources(id) ON DELETE CASCADE,
                    used_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS library_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS task_checkpoints (
                    task_id TEXT NOT NULL, unit_id TEXT NOT NULL, kind TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(task_id,unit_id)
                );
            """)
            db.execute("INSERT OR IGNORE INTO nodes(id,name) VALUES (?,?)", (ROOT, "Library"))
            db.execute("INSERT OR IGNORE INTO library_meta VALUES ('library_id',?)", (uuid.uuid4().hex,))
            columns = {row['name'] for row in db.execute('PRAGMA table_info(resources)')}
            if 'ocr_state_json' not in columns:
                db.execute("ALTER TABLE resources ADD COLUMN ocr_state_json TEXT NOT NULL DEFAULT '{}'")
            if 'library_added_seq' not in columns:
                db.execute('ALTER TABLE resources ADD COLUMN library_added_seq INTEGER')
            # Best-effort history only. Same-second imports use the stable ID.
            next_seq = db.execute('SELECT COALESCE(MAX(library_added_seq),0) FROM resources').fetchone()[0]
            for row in db.execute('SELECT id FROM resources WHERE library_added_seq IS NULL '
                                  'ORDER BY created_at ASC, id ASC').fetchall():
                next_seq += 1
                db.execute('UPDATE resources SET library_added_seq=? WHERE id=?', (next_seq, row['id']))
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS resource_added_seq ON resources(library_added_seq)')
            db.execute("INSERT INTO library_meta VALUES ('next_resource_seq',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=MAX(CAST(value AS INTEGER),CAST(excluded.value AS INTEGER))",
                       (str(next_seq + 1),))
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def connect(self, *, search=True):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
            if search and db.total_changes:
                self.search_revision = next(self._changes) + 1
        finally:
            db.close()

    def relative_path(self, path):
        # Resolve junctions as well as '..'; the library never owns outside files.
        return Path(path).resolve().relative_to(self.root).as_posix()

    def absolute_path(self, resource):
        """Absolute path of a stored resource, resolved without a syscall.

        Path.resolve() asks the filesystem for the real path of every component,
        and this runs once per rendered card and once per search hit: on a
        three-thousand-resource library that alone cost seconds of start-up and
        search time. relative_path() already stores a normalised,
        library-relative path, so a lexical join is both cheaper and sufficient;
        the containment check below stays lexical for the same reason.
        """
        root = str(self.root)
        path = os.path.normpath(os.path.join(root, resource["relative_path"]))
        folded_root = os.path.normcase(root)
        folded = os.path.normcase(path)
        if folded != folded_root and not folded.startswith(folded_root + os.sep):
            raise ValueError(f"资源路径超出资源库范围: {resource['relative_path']}")
        return folded

    def resources(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT r.* FROM content c JOIN resources r "
                    "ON c.resource_id=r.id WHERE c.parent_id=? ORDER BY c.position", (ROOT,))]

    def resource(self, value):
        with self.connect() as db:
            row = self._resource_row(db, value)
            return dict(row) if row else None

    def resource_ids(self, values):
        """Resolve one batch through a single catalog connection."""
        with self.connect() as db:
            return [row['id'] if (row := self._resource_row(db, value)) else None for value in values]

    def resource_records(self, values):
        """Read a changed batch using the existing identity rules, one connection."""
        with self.connect() as db:
            return [dict(row) for value in values if (row := self._resource_row(db, value)) is not None]

    def _resource_row(self, db, value):
        row = db.execute("SELECT * FROM resources WHERE id=? OR filename=?", (str(value), str(value))).fetchone()
        if row is None and Path(value).is_absolute():
            try:
                relative = self.relative_path(value)
            except ValueError:
                return None
            row = db.execute("SELECT * FROM resources WHERE relative_path=? COLLATE NOCASE", (relative,)).fetchone()
        return row

    def resource_by_id(self, resource_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM resources WHERE id=?", (str(resource_id),)).fetchone()
            return dict(row) if row else None

    def node(self, node_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM nodes WHERE id=?", (str(node_id),)).fetchone()
            return dict(row) if row else None

    def node_path(self, node_id):
        """Ancestors from the library root down to this node; ROOT itself is excluded."""
        chain = []
        current = str(node_id)
        with self.connect() as db:
            seen = set()
            while current and current != ROOT and current not in seen:
                seen.add(current)
                row = db.execute("SELECT id,parent_id,name,icon FROM nodes WHERE id=?", (current,)).fetchone()
                if row is None:
                    break
                chain.append(dict(row))
                current = row["parent_id"]
        chain.reverse()
        return chain

    def child_nodes(self, parent_id=ROOT):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT n.*, c.position FROM content c JOIN nodes n ON c.node_id=n.id "
                "WHERE c.parent_id=? ORDER BY c.position", (parent_id or ROOT,))]

    def entries(self, parent_id=ROOT):
        """Direct content of one node: interleaved resources and child nodes in manual order."""
        parent_id = parent_id or ROOT
        with self.connect() as db:
            result = []
            for position, (kind, item_id) in enumerate(self._entries(db, parent_id)):
                if kind == "resource":
                    row = db.execute("SELECT * FROM resources WHERE id=?", (item_id,)).fetchone()
                else:
                    row = db.execute("SELECT * FROM nodes WHERE id=?", (item_id,)).fetchone()
                if row is None:
                    continue
                result.append({"kind": kind, "position": position, "record": dict(row)})
            return result

    def subtree(self, node_id=ROOT):
        """All descendants of a node as a flat list with depth, used by packages."""
        node_id = node_id or ROOT
        with self.connect() as db:
            rows = db.execute("WITH RECURSIVE tree(id, depth) AS (SELECT ?, 0 UNION ALL "
                "SELECT n.id, t.depth + 1 FROM nodes n JOIN tree t ON n.parent_id=t.id) "
                "SELECT n.id, n.parent_id, n.name, n.icon, t.depth FROM tree t JOIN nodes n ON n.id=t.id "
                "WHERE n.id!=? ORDER BY t.depth", (node_id, ROOT)).fetchall()
            return [dict(r) for r in rows]

    def memberships(self):
        """Every (resource, node, position) relation that lives under a user category."""
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT c.parent_id AS node_id, c.resource_id, c.position FROM content c "
                "WHERE c.resource_id IS NOT NULL AND c.parent_id!=? ORDER BY c.parent_id, c.position", (ROOT,))]

    @staticmethod
    def _entries(db, parent):
        return [("resource", r[0]) if r[0] else ("node", r[1]) for r in db.execute(
            "SELECT resource_id,node_id FROM content WHERE parent_id=? ORDER BY position", (parent,))]

    @staticmethod
    def _write_order(db, parent, entries):
        db.execute("DELETE FROM content WHERE parent_id=?", (parent,))
        db.executemany("INSERT INTO content VALUES (?,?,?,?)", [(parent,
            item if kind == "resource" else None, item if kind == "node" else None, i)
            for i, (kind, item) in enumerate(entries)])

    @classmethod
    def _insert(cls, db, parent, kind, item, position=None):
        column = 'resource_id' if kind == 'resource' else 'node_id'
        exists = db.execute(f'SELECT 1 FROM content WHERE parent_id=? AND {column}=?',
                            (parent, item)).fetchone()
        if exists:
            # Repositioning an existing entry still uses the canonical mixed
            # stream, including child nodes and resources.
            entries = cls._entries(db, parent)
            entries.remove((kind, item))
            slot = len(entries) if position is None else max(0, min(position, len(entries)))
            entries.insert(slot, (kind, item))
            cls._write_order(db, parent, entries)
            return
        if position is None:
            slot = db.execute('SELECT COALESCE(MAX(position)+1,0) FROM content WHERE parent_id=?',
                              (parent,)).fetchone()[0]
        elif position <= 0:
            slot = db.execute('SELECT COALESCE(MIN(position)-1,0) FROM content WHERE parent_id=?',
                              (parent,)).fetchone()[0]
        else:
            next_row = db.execute('SELECT position FROM content WHERE parent_id=? '
                                  'ORDER BY position LIMIT 1 OFFSET ?', (parent, position)).fetchone()
            if next_row is None:
                slot = db.execute('SELECT COALESCE(MAX(position)+1,0) FROM content WHERE parent_id=?',
                                  (parent,)).fetchone()[0]
            else:
                previous = db.execute('SELECT position FROM content WHERE parent_id=? '
                                      'ORDER BY position LIMIT 1 OFFSET ?', (parent, position-1)).fetchone()[0]
                slot = previous + 1
                if slot >= next_row[0]:
                    db.execute('UPDATE content SET position=position+1 WHERE parent_id=? AND position>=?',
                               (parent, next_row[0]))
        db.execute('INSERT INTO content VALUES (?,?,?,?)',
                   (parent, item if kind == 'resource' else None,
                    item if kind == 'node' else None, slot))

    def register(self, path, display_name=None, *, library_added_seq=None, target=None, checkpoint=None, duplicate=False, kept=False):
        relative = self.relative_path(path)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute("SELECT id FROM resources WHERE relative_path=?", (relative,)).fetchone()
            resource_id = existing[0] if existing else uuid.uuid4().hex
            if existing:
                if target is not None and not db.execute('SELECT 1 FROM content WHERE parent_id=? AND resource_id=?',
                                                         (target.parent_node, resource_id)).fetchone():
                    self._insert(db, target.parent_node, 'resource', resource_id, target.insert_position)
                if checkpoint:
                    from services.task_recovery import write_checkpoint
                    write_checkpoint(db, checkpoint, state='done', resource=resource_id, duplicate=duplicate, kept=kept)
                return resource_id
            filename = Path(path).name
            if db.execute("SELECT 1 FROM resources WHERE filename=?", (filename,)).fetchone():
                filename = resource_id + Path(path).suffix
            next_seq = int(db.execute("SELECT value FROM library_meta WHERE key='next_resource_seq'").fetchone()[0])
            seq = next_seq if library_added_seq is None else library_added_seq
            if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
                raise ValueError('library_added_seq must be a positive integer')
            db.execute("INSERT INTO resources(id,filename,relative_path,display_name,library_added_seq) VALUES (?,?,?,?,?)",
                       (resource_id, filename, relative, display_name or Path(path).name, seq))
            db.execute("UPDATE library_meta SET value=? WHERE key='next_resource_seq'", (str(max(next_seq, seq + 1)),))
            self._insert(db, ROOT, "resource", resource_id, 0)
            if target is not None:
                if target.parent_node != ROOT:
                    self._insert(db, target.parent_node, 'resource', resource_id, target.insert_position)
                elif target.insert_position is not None:
                    self._insert(db, ROOT, 'resource', resource_id, target.insert_position)
            if checkpoint:
                from services.task_recovery import write_checkpoint
                write_checkpoint(db, checkpoint, state='done', resource=resource_id, duplicate=duplicate, kept=kept)
            return resource_id

    def nodes(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT n.*,c.position FROM nodes n JOIN content c "
                "ON c.node_id=n.id WHERE n.id!=? ORDER BY c.position", (ROOT,))]

    def create_node(self, name, parent_id=ROOT, icon="", position=None, *, checkpoint=None, reuse=False):
        name = name.strip()
        if not name:
            raise ValueError("Node name is required")
        node_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT id FROM nodes WHERE parent_id=? AND name=?',(parent_id or ROOT,name)).fetchone() if reuse else None
            if existing:
                node_id=existing[0]
                if position is not None:self._insert(db,parent_id or ROOT,'node',node_id,position)
                if checkpoint:
                    from services.task_recovery import write_checkpoint
                    write_checkpoint(db,checkpoint,state='done',node=node_id)
                return node_id
            try:
                db.execute("INSERT INTO nodes VALUES (?,?,?,?)", (node_id, parent_id or ROOT, name, icon))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Same-level node already exists: {name}") from exc
            self._insert(db, parent_id or ROOT, "node", node_id, position)
            if checkpoint:
                from services.task_recovery import write_checkpoint
                write_checkpoint(db, checkpoint, state='done', node=node_id)
        return node_id

    def update_node(self, node_id, *, name=None, icon=None):
        if node_id == ROOT:
            raise ValueError("Cannot edit the library root")
        with self.connect() as db:
            if name is not None:
                if not name.strip():
                    raise ValueError("Node name is required")
                try:
                    db.execute("UPDATE nodes SET name=? WHERE id=?", (name.strip(), node_id))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f"Same-level node already exists: {name.strip()}") from exc
            if icon is not None:
                db.execute("UPDATE nodes SET icon=? WHERE id=?", (icon, node_id))

    def move_node(self, node_id, parent_id=ROOT, position=None):
        parent_id = parent_id or ROOT
        if node_id == ROOT:
            raise ValueError("Cannot move the library root")
        with self.connect() as db:
            old = db.execute("SELECT parent_id FROM nodes WHERE id=?", (node_id,)).fetchone()
            if old is None:
                raise KeyError(node_id)
            descendants = {r[0] for r in db.execute("WITH RECURSIVE tree(id) AS (SELECT ? UNION ALL "
                "SELECT n.id FROM nodes n JOIN tree t ON n.parent_id=t.id) SELECT id FROM tree", (node_id,))}
            if parent_id in descendants:
                raise ValueError("A node cannot be moved into its own subtree")
            try:
                db.execute("UPDATE nodes SET parent_id=? WHERE id=?", (parent_id, node_id))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Same-level node already exists at the destination") from exc
            db.execute("DELETE FROM content WHERE node_id=?", (node_id,))
            self._insert(db, parent_id, "node", node_id, position)

    def move_nodes(self, node_ids, parent_id=ROOT, position=None):
        """Commit an ordered category block in one transaction and one order write per parent."""
        moving = list(dict.fromkeys(node_ids))
        parent_id = parent_id or ROOT
        if not moving or ROOT in moving:
            return
        with self.connect() as db:
            parents = {row['id']: row['parent_id'] or ROOT for row in
                       db.execute('SELECT id,parent_id FROM nodes')}
            if any(node_id not in parents for node_id in moving):
                raise KeyError(next(node_id for node_id in moving if node_id not in parents))
            if parent_id not in parents:
                raise KeyError(parent_id)
            for node_id in moving:
                ancestor = parent_id
                while ancestor != ROOT:
                    if ancestor == node_id:
                        raise ValueError('A node cannot be moved into its own subtree')
                    ancestor = parents[ancestor]
            affected = {parents[node_id] for node_id in moving} | {parent_id}
            streams = {key: self._entries(db, key) for key in affected}
            selected = set(moving)
            for key in affected:
                streams[key] = [entry for entry in streams[key]
                                if not (entry[0] == 'node' and entry[1] in selected)]
            from services.manual_order import insert_block
            streams[parent_id] = insert_block(streams[parent_id],
                                               [('node', node_id) for node_id in moving], position)
            for node_id in moving:
                try:
                    db.execute('UPDATE nodes SET parent_id=? WHERE id=?', (parent_id, node_id))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('Same-level node already exists at the destination') from exc
            for key in affected:
                db.execute('DELETE FROM content WHERE parent_id=?', (key,))
            for key, entries in streams.items():
                db.executemany('INSERT INTO content VALUES (?,?,?,?)',
                               [(key, item if kind == 'resource' else None,
                                 item if kind == 'node' else None, index)
                                for index, (kind, item) in enumerate(entries)])

    def delete_node(self, node_id):
        """Remove this node's relations; promote children without touching files."""
        if node_id == ROOT:
            raise ValueError("Cannot delete the library root")
        with self.connect() as db:
            row = db.execute("SELECT parent_id FROM nodes WHERE id=?", (node_id,)).fetchone()
            if not row:
                return False
            parent = row[0]
            for child in db.execute("SELECT id FROM nodes WHERE parent_id=?", (node_id,)).fetchall():
                db.execute("UPDATE nodes SET parent_id=? WHERE id=?", (parent, child[0]))
                db.execute("DELETE FROM content WHERE node_id=?", (child[0],))
                self._insert(db, parent, "node", child[0])
            db.execute("DELETE FROM nodes WHERE id=?", (node_id,))
            return True

    def content(self, parent_id=ROOT):
        with self.connect() as db:
            return [{"kind": k, "id": i, "position": p} for p, (k, i) in
                    enumerate(self._entries(db, parent_id or ROOT))]

    def set_order(self, parent_id, entries):
        parent_id = parent_id or ROOT
        entries = [(e["kind"], e["id"]) if isinstance(e, dict) else tuple(e) for e in entries]
        with self.connect() as db:
            current = self._entries(db, parent_id)
            if len(entries) != len(current) or set(entries) != set(current):
                raise ValueError("Order must contain each direct content entry exactly once")
            self._write_order(db, parent_id, entries)

    def reorder_resources(self, parent_id, resource_ids):
        """Reorder only the resource slots, leaving interleaved child nodes in place."""
        parent_id = parent_id or ROOT
        with self.connect() as db:
            entries = self._entries(db, parent_id)
            current = [item for kind, item in entries if kind == "resource"]
            resource_ids = list(resource_ids)
            if len(resource_ids) != len(current) or set(resource_ids) != set(current):
                raise ValueError("Resource order must contain the current resources exactly once")
            sequence = iter(resource_ids)
            self._write_order(db, parent_id,
                              [(kind, next(sequence)) if kind == "resource" else (kind, item)
                               for kind, item in entries])

    def add_membership(self, resource_id, node_id, position=None):
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM content WHERE parent_id=? AND resource_id=?",
                                (node_id, resource_id)).fetchone()
            if not exists or position is not None:
                self._insert(db, node_id, "resource", resource_id, position)
            return not bool(exists)

    def remove_membership(self, resource_id, node_id):
        if node_id == ROOT:
            raise ValueError("Use forget_resource to remove a library record")
        with self.connect() as db:
            return bool(db.execute("DELETE FROM content WHERE parent_id=? AND resource_id=?",
                                   (node_id, resource_id)).rowcount)

    def move_membership(self, resource_id, source, target, position=None):
        if source == ROOT or source == target:
            return self.add_membership(resource_id, target, position)
        with self.connect() as db:
            self._insert(db, target, "resource", resource_id, position)
            db.execute("DELETE FROM content WHERE parent_id=? AND resource_id=?", (source, resource_id))

    def assign_memberships(self, resource_ids, target, *, copy=True, source=None, position=None):
        """Apply a batch to the existing mixed content streams in one transaction."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            target_entries = self._entries(db, target)
            source_entries = self._entries(db, source) if not copy and source not in (None, ROOT, target) else None
            target_changed = source_changed = False
            added = 0
            for offset, resource_id in enumerate(resource_ids):
                if resource_id is None:
                    continue
                entry = ('resource', resource_id)
                exists = entry in target_entries
                if not exists:
                    added += 1
                if not exists or position is not None:
                    if exists:
                        target_entries.remove(entry)
                    slot = len(target_entries) if position is None else max(0, min(position + offset, len(target_entries)))
                    target_entries.insert(slot, entry)
                    target_changed = True
                if source_entries is not None and entry in source_entries:
                    source_entries.remove(entry)
                    source_changed = True
            if target_changed:
                self._write_order(db, target, target_entries)
            if source_changed:
                self._write_order(db, source, source_entries)
            return added

    def refresh_status(self):
        resources = self.resources()
        with self.connect() as db:
            for r in resources:
                status = "normal" if Path(self.absolute_path(r)).is_file() else "missing"
                db.execute("UPDATE resources SET status=? WHERE id=?", (status, r["id"]))

    def rebind(self, resource_id, path):
        relative = self.relative_path(path)
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM resources WHERE id=?', (resource_id,)).fetchone()
            if row:
                state = self._ocr_state(dict(row))
                state.update(source=None, revision=state.get('revision',0)+1)
                if not state.get('manual'):
                    state['status']='unrecognized'
                    db.execute("UPDATE resources SET ocr_text='' WHERE id=?", (resource_id,))
                db.execute('UPDATE resources SET ocr_state_json=? WHERE id=?', (json.dumps(state,ensure_ascii=False),resource_id))
            if not db.execute("UPDATE resources SET relative_path=?,status='normal' WHERE id=?",
                              (relative, resource_id)).rowcount:
                raise KeyError(resource_id)

    def forget_resource(self, resource_id):
        with self.connect() as db:
            return bool(db.execute("DELETE FROM resources WHERE id=?", (resource_id,)).rowcount)

    def set_resource_metadata(self, resource_id, metadata):
        with self.connect() as db:
            db.execute("UPDATE resources SET metadata_json=? WHERE id=?",
                       (json.dumps(metadata or {}, ensure_ascii=False), resource_id))

    def resource_metadata(self, resource_id):
        with self.connect() as db:
            row = db.execute("SELECT metadata_json FROM resources WHERE id=?", (resource_id,)).fetchone()
        if not row:
            return {}
        try:
            value = json.loads(row[0] or "{}")
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    def set_display_name(self, resource_id, name):
        if not name:
            return
        with self.connect() as db:
            db.execute("UPDATE resources SET display_name=? WHERE id=?", (str(name), str(resource_id)))

    def tag_strings(self, node_id=None, resource_ids=None):
        """Raw tag text for a location's whole subtree, in one query.

        The panel is rebuilt on every refresh, so counting tags must not cost a
        recursive walk plus a full membership scan plus a full resource scan;
        the scope is resolved inside SQLite and only the tag column comes back.
        """
        with self.connect() as db:
            if resource_ids is not None:
                ids = [str(value) for value in resource_ids]
                if not ids:
                    return []
                marks = ','.join('?'*len(ids))
                rows = db.execute(f"SELECT tags FROM resources WHERE id IN ({marks})", ids)
            elif node_id and node_id != ROOT:
                rows = db.execute(
                    "WITH RECURSIVE scope(id) AS (SELECT ? UNION ALL "
                    "SELECT n.id FROM nodes n JOIN scope s ON n.parent_id=s.id) "
                    "SELECT r.tags FROM content c JOIN scope s ON c.parent_id=s.id "
                    "JOIN resources r ON c.resource_id=r.id", (node_id,))
            else:
                rows = db.execute("SELECT tags FROM resources")
            return [row[0] or '' for row in rows]

    def meta(self, key, default=None):
        """Library-scoped value from `library_meta` (tag order lives here)."""
        with self.connect() as db:
            row = db.execute("SELECT value FROM library_meta WHERE key=?", (str(key),)).fetchone()
        return row[0] if row else default

    def set_meta(self, key, value):
        with self.connect(search=False) as db:
            db.execute("INSERT INTO library_meta(key,value) VALUES (?,?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (str(key), str(value)))

    def set_search_fields(self, resource_id, *, tags=None, ocr_text=None):
        with self.connect() as db:
            if tags is not None:
                db.execute("UPDATE resources SET tags=? WHERE id=?", (tags, resource_id))
            if ocr_text is not None:
                db.execute("UPDATE resources SET ocr_text=? WHERE id=?", (ocr_text, resource_id))

    def search_texts(self):
        from services.search_text import search_projection
        revision=self.search_revision
        if self._search_snapshot is not None and self._search_snapshot[0]==revision:
            return self._search_snapshot[1]
        with self.connect() as db:
            names = {}
            for resource_id, name in db.execute("SELECT c.resource_id,n.name FROM content c "
                    "JOIN nodes n ON c.parent_id=n.id WHERE c.resource_id IS NOT NULL AND n.id!=?", (ROOT,)):
                names.setdefault(resource_id, []).append(name)
            result={}
            for r in db.execute('SELECT id,display_name,filename,tags,ocr_text FROM resources'):
                raw=' '.join([r['display_name'],r['filename'],r['tags'],r['ocr_text'],*names.get(r['id'],[])])
                cached=self._search_projections.get(r['id'])
                if cached is None or cached[0]!=raw:
                    cached=(raw,search_projection(raw))
                    self._search_projections[r['id']]=cached
                result[r['id']]=cached[1]
            for rid in self._search_projections.keys()-result.keys():self._search_projections.pop(rid,None)
            if self.search_revision==revision:self._search_snapshot=(revision,result)
            return result

    @staticmethod
    def _ocr_state(record):
        state = json.loads(record.get('ocr_state_json') or '{}')
        if not state and record.get('ocr_text'):
            # Legacy/package text has no trustworthy automatic provenance.
            state = dict(status='ready',manual=True,revision=0)
        return {'status':'unrecognized','manual':False,'revision':0,**state}

    def ocr_info(self, resource_id):
        record = self.resource_by_id(resource_id)
        return dict(text=record['ocr_text'],**self._ocr_state(record)) if record else None

    def edit_ocr_text(self, resource_id, text):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM resources WHERE id=?',(resource_id,)).fetchone()
            if not row:raise KeyError(resource_id)
            state=self._ocr_state(dict(row))
            state.update(manual=True,status='ready' if text.strip() else 'empty',error='',revision=state['revision']+1)
            db.execute('UPDATE resources SET ocr_text=?,ocr_state_json=? WHERE id=?',
                       (str(text),json.dumps(state,ensure_ascii=False),resource_id))

    def commit_ocr(self, resource_id, result, *, revision, source, version, overwrite=False, error='', checkpoint=None):
        """Compare-and-set protects edits, rebinds and deletions during inference."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM resources WHERE id=?',(resource_id,)).fetchone()
            if not row:return False
            state=self._ocr_state(dict(row))
            if state['revision'] != revision or (state.get('manual') and not overwrite):return False
            state.update(status='failed' if error else ('ready' if result.get('text','').strip() else 'empty'),
                revision=revision+1,source=source,version=version,error=str(error))
            text=row['ocr_text'] if error else result.get('text','')
            if not error:state.update(manual=False,raw_text=result.get('raw_text',''))
            db.execute('UPDATE resources SET ocr_text=?,ocr_state_json=? WHERE id=?',
                       (text,json.dumps(state,ensure_ascii=False),resource_id))
            if checkpoint:
                from services.task_recovery import write_checkpoint
                write_checkpoint(db,checkpoint,state='done',outcome='failed' if error else 'done')
            return True

    def restore_ocr(self, resource_id, text, incoming):
        """Package text is portable; a local manual edit always wins a merge."""
        from services.ocr_data import source_stamp
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM resources WHERE id=?',(resource_id,)).fetchone()
            if not row:return
            record=dict(row)
            current=self._ocr_state(record)
            if current.get('manual'):return
            state=dict(incoming) if isinstance(incoming,dict) else {}
            if not state and text:state=dict(manual=True,status='ready')
            if not state:return
            state['revision']=current['revision']+1
            try:state['source']=source_stamp(self,record)
            except OSError:state['source']=None
            db.execute('UPDATE resources SET ocr_text=?,ocr_state_json=? WHERE id=?',
                       (str(text),json.dumps(state,ensure_ascii=False),resource_id))
