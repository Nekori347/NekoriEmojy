"""One-way Suzu → Nekori migration.

Two sources belong to the same feature: a Suzu share package, and a local Suzu
installation whose databases still hold ordering that the package omits. Both
are read-only; nothing in the Suzu installation is modified.
"""
import json
import ctypes
import os
import subprocess
import sqlite3
from contextlib import closing
from pathlib import Path

from services.exchange_import import ExchangeImportService
from services.library_index import ROOT

SUPPORTED = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.webm', '.tgs', '.bmp', '.tiff')


class SuzuMigrationError(RuntimeError):
    pass


class SuzuMigrationService:
    def __init__(self, storage):
        self.storage = storage
        self.index = storage.index

    @staticmethod
    def _window_titles():
        from ctypes import wintypes
        titles = {}
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32 = ctypes.windll.user32
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        @callback_type
        def visit(hwnd, _):
            text = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, text, len(text))
            if 'suzu' in text.value.casefold():
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                titles[pid.value] = text.value
            return True
        user32.EnumWindows(visit, 0)
        return titles

    @staticmethod
    def _command_args(command):
        if not command:
            return []
        from ctypes import wintypes
        shell32 = ctypes.windll.shell32
        shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        count = ctypes.c_int()
        argv = shell32.CommandLineToArgvW(command, ctypes.byref(count))
        if not argv:
            return []
        try:
            return [argv[i] for i in range(count.value)]
        finally:
            ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            ctypes.windll.kernel32.LocalFree(argv)

    @staticmethod
    def _process_executable(pid):
        """CIM may omit paths for an elevated Suzu; limited-query access can still read its exe."""
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return ''
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            return buffer.value if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)) else ''
        finally:
            kernel32.CloseHandle(handle)

    @classmethod
    def resolve_instance(cls, process, title=''):
        """Upstream: frozen exe parent/data; source main.py parent/data, never cwd."""
        exe = Path(process.get('ExecutablePath') or cls._process_executable(process['ProcessId']))
        args = cls._command_args(process.get('CommandLine') or '')
        scripts = [Path(arg) for arg in args[1:] if Path(arg).name.casefold() == 'main.py']
        named = 'suzu' in str(process.get('Name') or '').casefold()
        if not named and not title and not any('suzu' in str(p).casefold() for p in scripts):
            return None
        if named and exe.is_absolute():
            root = exe.parent
        elif scripts and scripts[0].is_absolute():
            root = scripts[0].parent
        else:
            return {'pid': int(process['ProcessId']), 'title': title or process['Name'],
                    'executable': str(exe), 'data_dir': None,
                    'error': '无法从该进程读取可确定的程序位置，请使用 Suzu 官方启动器重新启动。'}
        data_dir = root / 'data'
        valid = (data_dir / 'images').is_dir() and any((data_dir / name).is_file() for name in
                        ('order.db', 'categories.db', 'metadata.db', 'order.json', 'categories.json'))
        return {'pid': int(process['ProcessId']), 'title': title or process['Name'],
                'executable': str(exe), 'data_dir': str(data_dir) if valid else None,
                'error': '' if valid else f'程序位置已识别，但未找到 Suzu 数据：{data_dir}'}

    @classmethod
    def discover_instances(cls):
        if os.name != 'nt':
            raise SuzuMigrationError('运行中实例识别仅支持 Windows')
        titles = cls._window_titles()
        command = r"[Console]::OutputEncoding = [Text.UTF8Encoding]::new(); @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'suzu|^python(w)?\.exe$' } | Select-Object ProcessId,Name,ExecutablePath,CommandLine) | ConvertTo-Json -Compress"
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                    capture_output=True, encoding='utf-8-sig', timeout=12,
                                    creationflags=subprocess.CREATE_NO_WINDOW, check=True)
            processes = json.loads(result.stdout or '[]')
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise SuzuMigrationError(f'无法读取运行中的 Suzu 实例：{error}') from error
        if isinstance(processes, dict):
            processes = [processes]
        instances = []
        for process in processes:
            if process['ProcessId'] == os.getpid():
                continue
            instance = cls.resolve_instance(process, titles.get(process['ProcessId'], ''))
            if instance:
                instances.append(instance)
        return sorted(instances, key=lambda item: (item['data_dir'] is None, item['pid']))

    def preview_data(self, directory):
        data_dir, images = self._locate(Path(directory).resolve())
        if images is None or not images.is_dir():
            raise SuzuMigrationError('Suzu 表情目录已不可用，请刷新运行实例')
        target = self.index.root.resolve()
        source = data_dir.resolve()
        if target == source or target.is_relative_to(source) or source.is_relative_to(target):
            raise SuzuMigrationError('Suzu 源目录与 Nekori Library 必须分开；迁移只读复制，不能接管原目录')
        order = self._read_order(data_dir)
        categories, relations, icons = self._read_categories(data_dir)
        keywords = self._read_keywords(data_dir)
        files = [p for p in images.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED]
        refs = {Path(ref.replace('\\', '/')).name for paths in relations.values() for ref in paths}
        refs.update(Path(ref.replace('\\', '/')).name for ref in order)
        missing = sorted(ref for ref in refs if not (images / ref).is_file())
        return {'resources': len(files), 'nodes': len(categories), 'categories': categories,
                'tags': sum(bool(tags) for tags in keywords.values()), 'icons': len(icons),
                'ordered': len(order), 'missing': missing, 'data_dir': str(data_dir)}

    # ------------------------------------------------------------------
    # Source 1: Suzu share package (flat format)
    # ------------------------------------------------------------------
    def migrate_from_package(self, package_path, progress=None):
        service = ExchangeImportService(storage=self.storage)
        imported, skipped = service.import_zip(package_path, progress)
        self.storage.force_reload()
        return {"resources": imported, "nodes": len(self.index.nodes()), "duplicates": skipped}

    def preview_package(self, package_path, progress=None):
        """Read and validate with the existing package parser before confirmation."""
        import tempfile
        service = ExchangeImportService(storage=self.storage)
        with tempfile.TemporaryDirectory(prefix='nekori-migration-preview-') as folder:
            staging = Path(folder)
            service._extract_zip(Path(package_path), staging, progress)
            manifest = service._load_json(staging / 'manifest.json')
            catalog = service._load_json(staging / 'catalog.json')
            resources, categories = service._parse_catalog(manifest, catalog, staging)
            return {'resources': len(resources), 'nodes': len(categories), 'categories': list(categories.values())}

    # ------------------------------------------------------------------
    # Source 2: a local Suzu data directory
    # ------------------------------------------------------------------
    def migrate_from_data_dir(self, directory, progress=None):
        root = Path(directory).expanduser().resolve()
        if not root.is_dir():
            raise SuzuMigrationError(f"目录不存在：{root}")
        data_dir, images_dir = self._locate(root)
        if images_dir is None or not images_dir.is_dir():
            raise SuzuMigrationError("没有在该目录中找到 Suzu 的 images 表情目录")

        target = self.index.root.resolve()
        source = data_dir.resolve()
        if target == source or target.is_relative_to(source) or source.is_relative_to(target):
            raise SuzuMigrationError('Suzu 源目录与 Nekori Library 必须分开；迁移只读复制，不能接管原目录')
        order = self._read_order(data_dir)
        categories, relations, icons = self._read_categories(data_dir)
        keywords = self._read_keywords(data_dir)

        if not order and not categories and not keywords:
            raise SuzuMigrationError("没有在该目录中找到 Suzu 的分类 / 排序 / 关键词数据")

        known = set()
        if order:
            known.update(Path(p.replace("\\", "/")).name for p in order)
        for paths in relations.values():
            known.update(Path(p.replace("\\", "/")).name for p in paths)
        known.update(Path(p).name for p in keywords)
        for path in sorted(images_dir.iterdir(), key=lambda p: p.name.casefold()):
            if path.is_file() and path.suffix.lower() in SUPPORTED:
                known.add(path.name)

        source_order = list(dict.fromkeys([Path(p.replace("\\", "/")).name for p in order] + sorted(known)))
        sources = [images_dir / name for name in source_order if name in known and (images_dir / name).is_file()]
        root_before = [r["id"] for r in self.index.resources()]
        skipped = sum(not (images_dir / name).is_file() for name in known)
        total = max(1, len(sources) + len(categories))
        step = 0
        imported = duplicates = 0
        saved_by_name = {}

        for source in sources:
            try:
                saved, duplicate = self.storage.save_file(str(source))
            except Exception as exc:
                print(f"[WARNING] Suzu 迁移跳过 {source}: {exc}")
                step += 1
                skipped += 1
                continue
            if saved:
                saved_by_name[source.name] = saved
                duplicates += 1 if duplicate else 0
                imported += 0 if duplicate else 1
                tags = keywords.get(source.name)
                if tags:
                    existing = self.storage.get_image_keywords(saved)
                    self.storage.set_image_keywords(
                        saved, self.storage.merge_tags(existing, self.storage.serialize_tags(tags)))
            step += 1
            if progress:
                progress(step, total, source.name)

        node_ids = {}
        for position, name in enumerate(categories):
            node_ids[name] = self._ensure_node(name, position)
            icon = icons.get(name)
            if icon:
                self._apply_icon(node_ids[name], data_dir, icon)
            step += 1
            if progress:
                progress(step, total, name)

        for name, paths in relations.items():
            node_id = node_ids.get(name)
            if node_id is None:
                continue
            rank = {name: i for i, name in enumerate(source_order)}
            for ref in sorted(paths, key=lambda ref: rank.get(Path(ref.replace("\\", "/")).name, len(rank))):
                saved = saved_by_name.get(Path(ref.replace("\\", "/")).name)
                if saved:
                    self.index.add_membership(self.storage._resource_id(saved), node_id)

        migrated_ids = list(dict.fromkeys(self.storage._resource_id(saved_by_name[name])
                                         for name in source_order if name in saved_by_name))
        current = [r['id'] for r in self.index.resources()]
        ordered_ids = root_before + [rid for rid in migrated_ids if rid not in root_before]
        ordered_ids += [rid for rid in current if rid not in ordered_ids]
        self.index.reorder_resources(ROOT, ordered_ids)
        self.storage.force_reload()
        return {"resources": imported, "nodes": len(node_ids), "duplicates": duplicates, "skipped": skipped}


    # ------------------------------------------------------------------
    # Source layout and readers
    # ------------------------------------------------------------------
    @staticmethod
    def _locate(root):
        """Return (data_dir holding the databases, images_dir or None)."""
        for candidate in (root, root / "data"):
            images = candidate / "images"
            if images.is_dir():
                return candidate, images
        if any(root.glob("*.db")) or any(root.glob("*.json")):
            return root, None
        if (root / "data").is_dir():
            return root / "data", root / "data" / "images"
        return root, None

    @staticmethod
    def _read_rows(db_path, sql):
        if not Path(db_path).is_file():
            return []
        try:
            with closing(sqlite3.connect(Path(db_path).as_uri() + "?mode=ro", uri=True)) as db:
                return db.execute(sql).fetchall()
        except (sqlite3.Error, OSError):
            return []

    def _read_order(self, data_dir):
        rows = self._read_rows(data_dir / "order.db",
                               "SELECT image_path FROM item_orders ORDER BY sort_order")
        if rows:
            return [row[0] for row in rows if row[0]]
        payload = self._read_json(data_dir / "order.json")
        if isinstance(payload, list):
            return [str(item) for item in payload]
        if isinstance(payload, dict):
            result = []
            for value in payload.values():
                if isinstance(value, list):
                    result.extend(str(item) for item in value)
            return result
        return []

    def _read_categories(self, data_dir):
        names = [row[0] for row in self._read_rows(
            data_dir / "categories.db",
            "SELECT name FROM categories ORDER BY sort_order, id") if row[0]]
        relations = {}
        for name, ref in self._read_rows(
                data_dir / "categories.db", "SELECT category_name, image_path FROM category_images"):
            if name:
                relations.setdefault(name, []).append(ref)
        icons = {row[0]: row[1] for row in self._read_rows(
            data_dir / "categories.db",
            "SELECT name, icon_path FROM categories WHERE icon_path IS NOT NULL AND icon_path != ''")}

        if not names:
            payload = self._read_json(data_dir / "categories.json")
            if isinstance(payload, dict):
                names = list(payload)
                relations = {k: list(v) for k, v in payload.items() if isinstance(v, list)}
            elif isinstance(payload, list):
                names = [str(item) for item in payload]
        if not icons:
            payload = self._read_json(data_dir / "category_icons.json")
            if isinstance(payload, dict):
                icons = payload
        names = [n for n in names if n not in ("全部表情", "未分类", "新建分类")]
        return names, relations, icons

    def _read_keywords(self, data_dir):
        rows = self._read_rows(data_dir / "metadata.db",
                               "SELECT image_path, keywords FROM image_metadata")
        if rows:
            return {Path(row[0].replace("\\", "/")).name: self.storage.parse_tags(row[1] or "") for row in rows if row[0]}
        payload = self._read_json(data_dir / "metadata.json")
        if isinstance(payload, dict):
            return {k: self.storage.parse_tags(v or "") for k, v in payload.items()}
        return {}

    @staticmethod
    def _read_json(path):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _ensure_node(self, name, position):
        for sibling in self.index.child_nodes(ROOT):
            if sibling["name"] == name:
                return sibling["id"]
        return self.index.create_node(name, ROOT, position=position)

    def _apply_icon(self, node_id, data_dir, icon):
        if not icon:
            return
        if Path(icon).suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            self.index.update_node(node_id, icon=str(icon))
            return
        for candidate in (Path(icon), data_dir / icon, data_dir / "images" / Path(icon).name, data_dir / "category_icons" / Path(icon).name):
            if candidate.is_file():
                self.storage.set_node_icon(node_id, str(candidate))
                return

