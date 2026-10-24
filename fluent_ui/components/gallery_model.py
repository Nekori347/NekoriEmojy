"""Lightweight ordered entries; no QWidget, thumbnail or view ownership."""
from difflib import SequenceMatcher


def entry_id(entry):
    return f"{entry['kind']}:{entry['id']}"


def occurrence_id(entry):
    return entry_id(entry), entry.get('_parent', '')


class GalleryEntryModel:
    def __init__(self, storage):
        self.storage = storage
        self.direct = {}
        self.snapshots = {}
        self.projected = {}

    def bind_projection(self, entries):
        """Index occurrences only when the logical projection changes."""
        self.projected = {}
        for index,entry in enumerate(entries):
            key=entry['path'] if entry['kind']=='resource' else entry['id']
            self.projected.setdefault(key,[]).append((index,entry))

    def selected_entries(self, keys, parents):
        chosen=[]
        for key in keys:
            occurrences=self.projected.get(key,())
            if occurrences:
                chosen.append(next((item for item in occurrences if item[1]['_parent']==parents.get(key)),occurrences[0]))
        return [entry for _,entry in sorted(chosen,key=lambda item:item[0])]

    def entries_of(self, parent):
        if parent not in self.direct:
            self.direct[parent] = self.storage.entries_of(parent)
        return self.direct[parent]

    def invalidate(self):
        self.direct.clear()
        self.snapshots.clear()

    def sync(self, parents=None, paths=(), *, nodes=None, counts=None):
        """Read ordered identities, fetching resource records only when changed.

        Existing records survive insertion/removal/order changes. A Tag edit
        supplies its paths and doesn't query membership at all.
        """
        self.snapshots.clear()
        changed = {record['id']: record for record in self.storage.index.resource_records(paths)} if paths else {}
        counts = self.storage.node_counts() if counts is None else counts
        nodes = self.storage.index.nodes() if nodes is None else nodes
        node_records = {node['id']: node for node in nodes}
        for parent in list(self.direct):
            old = self.direct[parent]
            records = {entry_id(e): e for e in old}
            order = (self.storage.index.content(parent) if parents is None or parent in parents
                     else [{'kind': e['kind'], 'id': e['id'], 'position': e['position']} for e in old])
            updated = []
            for item in order:
                previous = records.get(entry_id(item))
                if item['kind'] == 'resource':
                    record = changed.get(item['id'])
                    if previous is None and record is None:
                        record = self.storage.index.resource_by_id(item['id'])
                    if record is not None:
                        value = dict(kind='resource', id=record['id'], name=record['display_name'],
                                     path=self.storage.index.absolute_path(record), status=record['status'],
                                     tags=record['tags'], resource=record, position=item['position'])
                    elif previous is not None:
                        value = previous if previous['position'] == item['position'] else dict(previous, position=item['position'])
                    else:
                        continue
                else:
                    record = node_records.get(item['id'])
                    if record is None:
                        continue
                    stats = counts.get(record['id'], {})
                    value = dict(kind='node', id=record['id'], name=record['name'], icon=record['icon'],
                                 children=stats.get('children', 0), total=stats.get('resources', 0),
                                 node=record, position=item['position'])
                updated.append(value)
            self.direct[parent] = updated
        return node_records

    @staticmethod
    def patch(entries, incoming):
        """Splice changed identity ranges; metadata-only edits never relayout."""
        before = [occurrence_id(e) for e in entries]
        after = [occurrence_id(e) for e in incoming]
        first = len(entries)
        if before != after:
            operations = SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
            for tag, i, j, a, b in reversed(operations):
                if tag != 'equal':
                    entries[i:j] = incoming[a:b]
                    first = min(first, i)
        for i, value in enumerate(incoming):
            if entries[i] != value:
                if any(entries[i].get(k) != value.get(k) for k in ('_depth', '_source_label')):
                    first = min(first, i)
                entries[i] = value
        return first

    def patch_normal(self, entries, root, expanded):
        """Keep entry objects; edit only changed ranges in the mixed stream."""
        from services.library_index import ROOT
        desired = []
        records = {}
        def visit(parent, depth):
            for value in self.entries_of(parent):
                if parent == ROOT and value['kind'] == 'node':
                    continue
                key = (entry_id(value), parent)
                desired.append(key)
                records[key] = value, depth
                if value['kind'] == 'node' and value['id'] in expanded:
                    visit(value['id'], depth+1)
        visit(root, 0)
        before = [occurrence_id(e) for e in entries]
        first = len(entries)
        for tag, i, j, a, b in reversed(SequenceMatcher(None, before, desired, autojunk=False).get_opcodes()):
            if tag != 'equal':
                entries[i:j] = [dict(records[key][0], _parent=key[1], _depth=records[key][1])
                                for key in desired[a:b]]
                first = min(first, i)
        for entry in entries:
            value, depth = records[occurrence_id(entry)]
            entry.update(value)
            entry['_depth'] = depth
        return first
