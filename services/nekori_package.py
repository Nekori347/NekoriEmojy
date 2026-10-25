"""Nekori native resource package.

Saves what the library actually stores today: resource files, the recursive
category tree with names and icons, node order, the mixed order inside every
category, tags and per-resource software metadata. Re-importing restores those
organising results; identical resources merge instead of being duplicated.
"""
import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

from services.exchange_icons import IMAGE_SUFFIXES, resolve_icon_path
from services.library_index import ROOT
from services.export_control import check_export_cancelled, staged_export_path

FORMAT = "nekori-package"
FORMAT_VERSION = 1
MANIFEST_NAME = "nekori.json"
MAX_PACKAGE_FILES = 50000
MAX_PACKAGE_BYTES = 8 * 1024 ** 3
MAX_MANIFEST_BYTES = 16 * 1024 ** 2


class NekoriPackageError(RuntimeError):
    pass


def _package_path(root, name):
    if not isinstance(name, str) or not name or '\x00' in name:
        raise NekoriPackageError('资源包包含无效路径')
    path = PurePosixPath(name.replace('\\', '/'))
    if (path.is_absolute() or PureWindowsPath(name).drive or PureWindowsPath(name).is_reserved()
            or '..' in path.parts or any(':' in p or p.endswith((' ', '.')) for p in path.parts)):
        raise NekoriPackageError('资源包路径必须位于包内')
    target = (root / Path(*path.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise NekoriPackageError('资源包路径必须位于包内')
    return target


class NekoriPackageService:
    def __init__(self, storage):
        self.storage = storage
        self.index = storage.index

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def build_manifest(self, *, cancel_check=None):
        node_positions = {}
        for node in self.index.nodes():
            check_export_cancelled(cancel_check)
            for entry in self.index.content(node["id"]):
                if entry["kind"] == "node":
                    node_positions[entry["id"]] = entry["position"]

        memberships = {}
        for row in self.index.memberships():
            check_export_cancelled(cancel_check)
            memberships.setdefault(row["resource_id"], []).append(row)

        manifest = {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "app": "NekoriEmojy",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "nodes": [],
            "resources": [],
            "root_order": [{"kind": e["kind"], "id": e["id"]} for e in self.index.content(ROOT)],
        }

        for node in self.index.nodes():
            check_export_cancelled(cancel_check)
            manifest["nodes"].append({
                "id": node["id"],
                "parent_id": node["parent_id"] or ROOT,
                "name": node["name"],
                "icon": node["icon"] or "",
                "position": node_positions.get(node["id"], 0),
                "order": [{"kind": e["kind"], "id": e["id"]}
                          for e in self.index.content(node["id"])],
            })

        for record in self.index.resources():
            check_export_cancelled(cancel_check)
            manifest["resources"].append({
                "id": record["id"],
                "filename": record["filename"],
                "package_path": f"images/{record['filename']}",
                "display_name": record["display_name"],
                "relative_path": record["relative_path"],
                "library_added_seq": record["library_added_seq"],
                "tags": record["tags"],
                "ocr_text": record["ocr_text"],
                "ocr_state": self.index._ocr_state(record),
                "metadata": json.loads(record["metadata_json"] or "{}"),
                "memberships": [{"node_id": m["node_id"], "position": m["position"]}
                                for m in sorted(memberships.get(record["id"], []),
                                                key=lambda m: m["position"])],
            })
        return manifest

    def export(self, target_path, progress=None, *, cancel_check=None):
        check_export_cancelled(cancel_check)
        if progress:
            progress(0, 0, '正在读取合集结构')
        manifest = self.build_manifest(cancel_check=cancel_check)
        root = Path(self.index.root)
        total = len(manifest["resources"]) + len(manifest["nodes"]) + 1
        step = 0

        with staged_export_path(target_path, cancel_check) as temporary, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in manifest["resources"]:
                check_export_cancelled(cancel_check)
                if progress:
                    progress(step, total, '写入资源（工作单元）: ' + entry["display_name"])
                source = root / entry["relative_path"]
                try:
                    if source.is_file():
                        archive.write(source, entry["package_path"])
                except OSError as exc:
                    print(f"[WARNING] 打包资源失败: {source}: {exc}")
                step += 1
                if progress:
                    progress(step, total, '写入资源（工作单元）: ' + entry["display_name"])

            icon_assets = {}
            for node in manifest["nodes"]:
                check_export_cancelled(cancel_check)
                if progress:
                    progress(step, total, '处理分类图标（工作单元）: ' + node["name"])
                icon = node.get("icon") or ""
                if icon and Path(icon).suffix.lower() in IMAGE_SUFFIXES:
                    source = Path(resolve_icon_path(self.index.root, icon))
                    # The package carries its own asset, never the source machine's path.
                    node['icon'] = ''
                    if source.is_file():
                        key = source.resolve()
                        if key not in icon_assets:
                            asset = f"icons/{node['id']}{source.suffix.lower()}"
                            archive.write(source, asset)
                            icon_assets[key] = asset
                        node["icon_asset"] = icon_assets[key]
                step += 1
                if progress:
                    progress(step, total, '处理分类图标（工作单元）: ' + node["name"])

            check_export_cancelled(cancel_check)
            if progress:
                progress(step, total, '写入清单（工作单元）')
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        if progress:
            progress(total, total, "完成")
        return {"resources": len(manifest["resources"]), "nodes": len(manifest["nodes"])}


    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def import_package(self, package_path, progress=None):
        staging = Path(tempfile.mkdtemp(prefix="nekori-package-"))
        try:
            with zipfile.ZipFile(package_path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_PACKAGE_FILES or sum(e.file_size for e in entries) > MAX_PACKAGE_BYTES:
                    raise NekoriPackageError('资源包超过解压大小或文件数量上限')
                seen = {}
                for entry in entries:
                    target = _package_path(staging, entry.filename)
                    key = str(target).casefold()
                    if ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                        raise NekoriPackageError('资源包包含符号链接')
                    previous = seen.get(key)
                    if previous:
                        # Older native exports repeated shared icon assets. Only
                        # byte-identical icon members are unambiguous and safe.
                        if (entry.filename != previous.filename or not entry.filename.startswith('icons/')
                                or entry.is_dir() or entry.file_size != previous.file_size):
                            raise NekoriPackageError('资源包包含重复路径')
                        with archive.open(previous) as first, archive.open(entry) as duplicate:
                            while True:
                                chunk = first.read(64 * 1024)
                                if chunk != duplicate.read(64 * 1024):
                                    raise NekoriPackageError('资源包包含内容冲突的重复图标')
                                if not chunk:
                                    break
                    else:
                        seen[key] = entry
                    if str(target).casefold() == str(staging / MANIFEST_NAME).casefold() and entry.file_size > MAX_MANIFEST_BYTES:
                        raise NekoriPackageError('资源包清单超过大小上限')
                archive.extractall(staging)
            manifest_path = staging / MANIFEST_NAME
            if not manifest_path.is_file():
                raise NekoriPackageError("这不是 Nekori 原生表情合集：缺少 nekori.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("format") != FORMAT:
                raise NekoriPackageError("表情合集格式不受支持")
            # Validate references before creating any nodes or resources.
            for entry in manifest.get('resources', []):
                _package_path(staging, entry.get('package_path'))
            for node in manifest.get('nodes', []):
                if node.get('icon_asset'):
                    _package_path(staging, node['icon_asset'])
                elif node.get('icon'):
                    icon = node['icon']
                    if any(c in icon for c in '/\\:') or Path(icon).suffix.lower() in IMAGE_SUFFIXES:
                        raise NekoriPackageError('图片图标必须包含在资源包中')
            return self._restore(manifest, staging, progress)
        except zipfile.BadZipFile as exc:
            raise NekoriPackageError(f"压缩包无法读取: {exc}") from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _restore(self, manifest, staging, progress):
        nodes = sorted(manifest.get("nodes", []), key=lambda n: n.get("position", 0))
        resources = manifest.get("resources", [])
        existing_ids = {r['id'] for r in self.index.resources()}
        existing_content = {parent: {(e['kind'], e['id']) for e in self.index.content(parent)}
                            for parent in [ROOT, *(n['id'] for n in self.index.nodes())]}
        # An empty target is a full restore. A merge always allocates from the
        # target library, irrespective of sequence numbers in the package.
        full_restore = not self.index.resources() and not self.index.nodes()
        if full_restore:
            sequences = [e['library_added_seq'] for e in resources if e.get('library_added_seq') is not None]
            if any(type(seq) is not int or seq < 1 for seq in sequences) or len(set(sequences)) != len(sequences):
                raise NekoriPackageError('表情合集 library_added_seq 无效或重复')
            if sequences:
                with self.index.connect() as db:
                    # Reserve packaged values before allocating for older entries.
                    db.execute("UPDATE library_meta SET value=MAX(CAST(value AS INTEGER),?) "
                               "WHERE key='next_resource_seq'", (max(sequences) + 1,))
        total = max(1, len(resources) + len(nodes))

        # 1. Nodes. Parents are created before children; a same-named sibling is
        #    reused so repeating the import merges instead of duplicating.
        node_map = {}
        pending = list(nodes)
        while pending:
            remaining = []
            for node in pending:
                parent_ref = node.get("parent_id") or ROOT
                if parent_ref != ROOT and parent_ref not in node_map:
                    remaining.append(node)
                    continue
                parent_id = ROOT if parent_ref == ROOT else node_map[parent_ref]
                node_map[node["id"]] = self._ensure_node(node, parent_id, staging)
            if len(remaining) == len(pending):
                for node in remaining:
                    node_map[node["id"]] = self._ensure_node(node, ROOT, staging)
                break
            pending = remaining

        # 2. Resources plus the package-id to library-id map used by relations.
        resource_map = {}
        imported = duplicates = 0
        step = len(nodes)
        for entry in resources:
            source = _package_path(staging, entry["package_path"])
            if source.is_file():
                from services.resource_import import ImportSkipped
                try:
                    saved, duplicate = self.storage.save_file(str(source),
                        library_added_seq=entry.get('library_added_seq') if full_restore else None)
                except ImportSkipped:
                    if progress:progress(step+1,total,entry.get('display_name',''))
                    step+=1
                    continue
                if saved:
                    record = self.index.resource(saved)
                    resource_map[entry["id"]] = record["id"]
                    if record['id'] not in existing_ids:
                        self._apply_resource_fields(record, entry)
                    duplicates += 1 if duplicate else 0
                    imported += 0 if duplicate else 1
            step += 1
            if progress:
                progress(step, total, entry.get("display_name", ""))

        # 3. Category membership, then the mixed order of every category.
        for entry in resources:
            new_id = resource_map.get(entry["id"])
            if new_id is None:
                continue
            for membership in sorted(entry.get("memberships", []),
                                     key=lambda m: m.get("position", 0)):
                target = node_map.get(membership["node_id"])
                if target:
                    self.index.add_membership(new_id, target)

        restored_orders = 0
        for node in nodes:
            if node.get("order") and node_map.get(node["id"]):
                restored_orders += self._apply_order(node_map[node["id"]], node["order"],
                                                     node_map, resource_map,
                                                     existing_content.get(node_map[node['id']], set()))
        if manifest.get("root_order"):
            restored_orders += self._apply_order(ROOT, manifest["root_order"],
                                                 node_map, resource_map, existing_content[ROOT])

        return {"resources": imported, "nodes": len(node_map), "duplicates": duplicates,
                "orders": restored_orders}

    def _ensure_node(self, node, parent_id, staging):
        for sibling in self.index.child_nodes(parent_id):
            if sibling["name"] == node["name"]:
                # Merging into an existing category keeps whatever icon the
                # library already has; the package only fills a gap, so a local
                # choice is never silently replaced by an import.
                if not sibling.get("icon"):
                    self._apply_node_icon(sibling["id"], node, staging)
                return sibling["id"]
        created = self.index.create_node(node["name"], parent_id)
        self._apply_node_icon(created, node, staging)
        return created

    def _apply_node_icon(self, node_id, node, staging):
        asset = node.get("icon_asset")
        if asset:
            source = _package_path(staging, asset)
            if source.is_file():
                self.storage.set_node_icon(node_id, str(source))
        elif node.get("icon"):
            self.index.update_node(node_id, icon=node["icon"])

    def _apply_resource_fields(self, record, entry):
        resource_id = record["id"]
        # The stored display name is restored too: importing into a library that
        # already holds a same-named file makes register() rename the copy to a
        # generated id, and the package still knows the name the user saw.
        self.index.set_display_name(resource_id, entry.get("display_name"))
        tags = entry.get("tags") or ""
        merged = self.storage.merge_tags(record["tags"], tags) if tags else record["tags"]
        self.index.set_search_fields(resource_id, tags=merged)
        metadata = entry.get("metadata")
        if isinstance(metadata, dict) and metadata:
            current = self.index.resource_metadata(resource_id)
            current.update(metadata)
            self.index.set_resource_metadata(resource_id, current)
        if 'ocr_text' in entry:
            self.index.restore_ocr(resource_id, entry.get('ocr_text') or '', entry.get('ocr_state') or {})

    def _apply_order(self, parent_id, order, node_map, resource_map, existing=()):
        """Restore the package's mixed order, keeping anything it did not know.

        Existing target entries keep their current slots. Only newly imported
        slots take packaged order; a full restore has no existing entries.
        """
        current = self.index.content(parent_id)
        current_keys = {(e["kind"], e["id"]) for e in current}

        wanted = []
        for item in order:
            identifier = item["id"]
            if item["kind"] == "node":
                identifier = node_map.get(identifier)
            else:
                identifier = resource_map.get(identifier)
            if identifier is None:
                continue
            key = (item["kind"], identifier)
            if key in current_keys and key not in wanted:
                wanted.append(key)
        if not wanted:
            return 0
        current_order = [(e['kind'], e['id']) for e in current]
        wanted.extend(key for key in current_order if key not in wanted)
        if existing:
            new_order = iter(key for key in wanted if key not in existing)
            wanted = [key if key in existing else next(new_order) for key in current_order]
        if set(wanted) != current_keys:
            return 0
        if wanted == [(e["kind"], e["id"]) for e in current]:
            return 0
        self.index.set_order(parent_id, wanted)
        return 1
