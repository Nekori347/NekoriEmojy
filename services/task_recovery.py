"""Import source manifests and commit receipts in the existing library database."""
import json
from pathlib import Path
from services.library_index import ROOT


class RecoveryWait(Exception):
    """Keep the manifest and require a later explicit user action."""


def write_checkpoint(db, key, **changes):
    row = db.execute('SELECT payload FROM task_checkpoints WHERE task_id=? AND unit_id=?', key).fetchone()
    if not row:
        return
    value = json.loads(row[0]); value.update(changes)
    db.execute('UPDATE task_checkpoints SET payload=? WHERE task_id=? AND unit_id=?',
               (json.dumps(value, ensure_ascii=False), *key))


def source_identity(path):
    stat = Path(path).stat()
    return [stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino]


class ImportCheckpoint:
    def __init__(self, storage, job_id):
        self.storage, self.index, self.id = storage, storage.index, job_id
        self.units = {}

    @staticmethod
    def discover(index):
        with index.connect(search=False) as db:
            return [(r[0], json.loads(r[1])) for r in db.execute(
                "SELECT task_id,payload FROM task_checkpoints WHERE unit_id='' AND kind='import'")]

    def create(self, sources, target, before, delete_after):
        value = dict(sources=[str(Path(s).absolute()) for s in sources], parent=target.parent_node, before=before,
                     delete_after=delete_after, planned=False)
        with self.index.connect(search=False) as db:
            db.execute('INSERT INTO task_checkpoints VALUES (?,?,?,?)',
                       (self.id, '', 'import', json.dumps(value, ensure_ascii=False)))

    def prepare(self):
        with self.index.connect(search=False) as db:
            header = json.loads(db.execute('SELECT payload FROM task_checkpoints WHERE task_id=? AND unit_id=?',
                                          (self.id, '')).fetchone()[0])
            rows = [json.loads(r[0]) for r in db.execute(
                "SELECT payload FROM task_checkpoints WHERE task_id=? AND unit_id!='' ORDER BY rowid", (self.id,))]
        if getattr(self,'resuming',False) and header.get('delete_after'):
            raise RecoveryWait('删除来源任务需人工核对，不能自动重放')
        if not header['planned']:
            rows = []
            def visit(path, parent):
                path = Path(path)
                if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                    raise RecoveryWait('来源已改变，无法安全继续')
                try:
                    stamp = source_identity(path)
                except OSError as exc:
                    raise RecoveryWait('来源不可用，请连接原设备后继续') from exc
                directory = path.is_dir()
                if directory and (self.index.root == path.resolve() or self.index.root.is_relative_to(path.resolve())):
                    raise RecoveryWait('不能导入资源库或其上级目录')
                key = str(len(rows))
                rows.append(dict(id=key, source=str(path.absolute()), stamp=stamp, parent=parent,
                                 directory=directory, state='pending'))
                if directory:
                    for child in sorted(path.iterdir(), key=lambda p:p.name.casefold()):
                        if child.is_dir() or child.suffix.lower() in self.storage.SUPPORTED_FORMATS:
                            visit(child, key)
            for source in header['sources']:
                visit(source, None)
            with self.index.connect(search=False) as db:
                db.executemany('INSERT INTO task_checkpoints VALUES (?,?,?,?)',
                               [(self.id, u['id'], 'import', json.dumps(u, ensure_ascii=False)) for u in rows])
                write_checkpoint(db, (self.id, ''), planned=True)
        self.header = header
        self.units = {u['id']:u for u in rows}
        self.nodes={ROOT,*[n['id'] for n in self.index.nodes()]}
        if any(u['state']=='uncertain' for u in rows):
            raise RecoveryWait('保留两者、替换或删除来源的执行结果需人工核对，不能自动重放')
        return rows

    def target(self, unit):
        from services.resource_import import ImportTarget
        parent = self.units[unit['parent']].get('node') if unit['parent'] is not None else self.header['parent']
        if not parent or parent not in self.nodes:
            raise RecoveryWait('目标分类已改变，无法安全继续')
        before = self.header.get('before') if unit['parent'] is None else None
        position = None
        if before:
            position = next((i for i,e in enumerate(self.index.content(parent)) if [e['kind'],e['id']]==list(before)), None)
        return ImportTarget(parent, position)

    def validate(self, unit):
        try:
            stamp = source_identity(unit['source'])
        except OSError as exc:
            raise RecoveryWait('来源不可用，请连接原设备后继续') from exc
        # Directory contents may change; replay only the frozen manifest, never new files.
        expected = unit['stamp']
        if (stamp[2:] != expected[2:] if unit['directory'] else stamp != expected):
            raise RecoveryWait('来源已改变，无法安全继续')

    def directory(self, unit, target):
        if unit['state']=='done':
            return
        self.validate(unit)
        name = Path(unit['source']).name
        node = self.index.create_node(name, target.parent_node, position=target.insert_position,
                                     checkpoint=(self.id, unit['id']),reuse=True)
        unit.update(state='done', node=node)
        self.nodes.add(node)

    def mark(self, unit, **changes):
        with self.index.connect(search=False) as db:
            write_checkpoint(db, (self.id, unit['id']), **changes)
        unit.update(changes)

    def forget(self):
        with self.index.connect(search=False) as db:
            db.execute("DELETE FROM task_checkpoints WHERE task_id=? AND kind='import'", (self.id,))
