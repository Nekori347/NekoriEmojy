"""One persisted availability state; disk checks happen at action boundaries."""
from pathlib import Path
from PySide6.QtCore import QObject, Signal


class ResourceAvailability(QObject):
    changed = Signal(str, str)  # absolute path, normal / missing

    def __init__(self, index):
        super().__init__()
        self.index = index

    def exists(self, value, *, revalidate=False):
        record = self.index.resource(value)
        if record is None:
            return False
        if not revalidate:
            return record['status'] == 'normal'
        path = self.index.absolute_path(record)
        status = 'normal' if Path(path).is_file() else 'missing'
        if status != record['status']:
            with self.index.connect() as db:
                db.execute('UPDATE resources SET status=? WHERE id=?', (status, record['id']))
            self.changed.emit(path, status)
        return status == 'normal'

    def refresh(self):
        changes = []
        with self.index.connect() as db:
            for record in db.execute('SELECT * FROM resources').fetchall():
                path = self.index.absolute_path(record)
                status = 'normal' if Path(path).is_file() else 'missing'
                if status != record['status']:
                    db.execute('UPDATE resources SET status=? WHERE id=?', (status, record['id']))
                    changes.append((path, status))
        for path, status in changes:
            self.changed.emit(path, status)
