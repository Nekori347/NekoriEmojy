"""One flat layer of user-created groups within each logical category."""
from contextlib import nullcontext
from pathlib import Path
import sqlite3
import uuid
from services.library import LibraryError,LibrarySession,read_db
from services.importing import add_relations


def create_schema(conn):
    conn.execute('''CREATE TABLE categories.category_groups (
        id TEXT PRIMARY KEY, category_name TEXT NOT NULL, name TEXT NOT NULL,
        sort_order INTEGER NOT NULL, collapsed INTEGER NOT NULL DEFAULT 0,
        UNIQUE(category_name,name))''')
    conn.execute('''CREATE TABLE categories.group_images (
        group_id TEXT NOT NULL,image_path TEXT NOT NULL,sort_order INTEGER NOT NULL,
        PRIMARY KEY(group_id,image_path))''')
    conn.execute('''CREATE TRIGGER categories.groups_category_rename AFTER UPDATE OF name ON categories
        BEGIN UPDATE category_groups SET category_name=NEW.name WHERE category_name=OLD.name; END''')
    conn.execute('''CREATE TRIGGER categories.groups_category_delete AFTER DELETE ON categories
        BEGIN DELETE FROM category_groups WHERE category_name=OLD.name; END''')
    conn.execute('''CREATE TRIGGER categories.group_members_delete AFTER DELETE ON category_groups
        BEGIN DELETE FROM group_images WHERE group_id=OLD.id; END''')
    conn.execute('''CREATE TRIGGER categories.group_member_category_remove AFTER DELETE ON category_images
        BEGIN DELETE FROM group_images WHERE image_path=OLD.image_path AND group_id IN
            (SELECT id FROM category_groups WHERE category_name=OLD.category_name); END''')


class CategoryGroups:
    def __init__(self, library):
        self.session=library if isinstance(library,LibrarySession) else None
        self.context=library.context if self.session else library

    def _lease(self):
        return self.session.task() if self.session else nullcontext()

    @staticmethod
    def _name(value):
        if not isinstance(value,str) or not value.strip() or len(value.strip())>80 or '\x00' in value:
            raise LibraryError('小分类名称需为 1～80 个字符。')
        return value.strip()

    @staticmethod
    def _group(conn, group_id):
        row=conn.execute('SELECT category_name FROM categories.category_groups WHERE id=?',(group_id,)).fetchone()
        if row is None:
            raise LibraryError('这个小分类已不存在，请刷新后重试。')
        return row[0]

    def create(self, category, name):
        name=self._name(name)
        with self._lease(),self.context.transaction() as conn:
            if conn.execute('SELECT 1 FROM categories.categories WHERE name=?',(category,)).fetchone() is None:
                raise LibraryError('请先选择一个已有的大分类。')
            if conn.execute('SELECT 1 FROM categories.category_groups WHERE category_name=? AND name=?',(category,name)).fetchone():
                raise LibraryError('当前分类内已有同名小分类。')
            group_id=uuid.uuid4().hex
            conn.execute('''INSERT INTO categories.category_groups(id,category_name,name,sort_order)
                VALUES (?,?,?,(SELECT COALESCE(MAX(sort_order),-1)+1 FROM categories.category_groups WHERE category_name=?))''',
                (group_id,category,name,category))
        return group_id

    def rename(self, group_id, name):
        name=self._name(name)
        try:
            with self._lease(),self.context.transaction() as conn:
                self._group(conn,group_id)
                conn.execute('UPDATE categories.category_groups SET name=? WHERE id=?',(name,group_id))
        except sqlite3.IntegrityError as exc:
            raise LibraryError('当前分类内已有同名小分类。') from exc

    def delete(self, group_id):
        with self._lease(),self.context.transaction() as conn:
            self._group(conn,group_id)
            conn.execute('DELETE FROM categories.category_groups WHERE id=?',(group_id,))

    def set_collapsed(self, group_id, collapsed):
        with self._lease(),self.context.transaction() as conn:
            self._group(conn,group_id)
            conn.execute('UPDATE categories.category_groups SET collapsed=? WHERE id=?',(int(bool(collapsed)),group_id))

    def add(self, group_id, paths):
        names=list(dict.fromkeys(self.context.resource(path).name for path in paths))
        with self._lease(),self.context.transaction() as conn:
            category=self._group(conn,group_id)
            if any(not self.context.resource(name).is_file() for name in names):
                raise LibraryError('所选图片已不存在，请刷新后重试。')
            add_relations(conn,names,category)
            next_order=conn.execute('SELECT COALESCE(MAX(sort_order),-1)+1 FROM categories.group_images WHERE group_id=?',(group_id,)).fetchone()[0]
            count=0
            for index,name in enumerate(names):
                count+=conn.execute('INSERT OR IGNORE INTO categories.group_images VALUES (?,?,?)',(group_id,name,next_order+index)).rowcount
        return count

    def remove(self, group_id, paths):
        names=[self.context.resource(path).name for path in paths]
        with self._lease(),self.context.transaction() as conn:
            self._group(conn,group_id)
            conn.executemany('DELETE FROM categories.group_images WHERE group_id=? AND image_path=?',[(group_id,name) for name in names])

    def reorder(self, category, ids):
        with self._lease(),self.context.transaction() as conn:
            existing={r[0] for r in conn.execute('SELECT id FROM categories.category_groups WHERE category_name=?',(category,))}
            if len(set(ids))!=len(ids) or set(ids)!=existing:
                raise LibraryError('小分类列表发生变化，请刷新后重新排序。')
            conn.executemany('UPDATE categories.category_groups SET sort_order=? WHERE id=?',[(i,g) for i,g in enumerate(ids)])

    def list(self, category):
        with read_db(self.context.db('categories')) as conn:
            groups=[dict(id=g,category=category,name=n,collapsed=bool(c),paths=[]) for g,n,c in conn.execute(
                'SELECT id,name,collapsed FROM category_groups WHERE category_name=? ORDER BY sort_order,id',(category,))]
            by_id={g['id']:g for g in groups}
            for group_id,name in conn.execute('''SELECT group_id,image_path FROM group_images
                WHERE group_id IN (SELECT id FROM category_groups WHERE category_name=?) ORDER BY sort_order''',(category,)):
                # Stored members are managed basenames. Display joins need no disk
                # canonicalization; writes still validate the real path via resource().
                if not name or Path(name).name != name or name in ('.', '..') or ':' in name:
                    raise LibraryError('小分类包含无效资源引用，请检查库数据。')
                by_id[group_id]['paths'].append(str(self.context.images_dir / name))
        return groups
