"""One-time Suzu import into a new library; every source access is read-only.

The old application must be closed. Raw DB/WAL/JSON and image copies are hashed
before and after copying. SQLite only opens the private snapshot, never the source.
"""
import json
import ntpath
from pathlib import Path
import shutil
import sqlite3
import uuid

from services.library import (LibraryContext, LibraryError, atomic_json, create_library,
                              digest, independent_root, inspect_library, read_db)
from services.diagnostics import event


class LegacyConflict(LibraryError):
    def __init__(self, report, report_path):
        super().__init__("旧 DB 与 JSON 存在差异，请查看报告并逐项选择来源；原库未修改。")
        self.report = report
        self.report_path = report_path


def source_data_root(path):
    root = Path(path).resolve()
    candidates = [p for p in (root, root / "data", root / "bin/data") if (p / "images").is_dir()]
    if len(candidates) != 1:
        raise LibraryError("无法唯一识别旧数据，请直接选择包含 images 的 data 文件夹。")
    return candidates[0]


def inventory(root):
    records = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()) or not path.resolve().is_relative_to(root):
            raise LibraryError("旧源包含链接路径，无法保证只读快照范围。")
        if path.is_file():
            records[path.relative_to(root).as_posix()] = digest(path)
    return records


def _json(root, name, default):
    path = root / (name + ".json")
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, type(default)):
        raise LibraryError(f"旧 {name}.json 结构不兼容，已保留快照。")
    return value


def inspect_snapshot(root):
    """Read both sources independently, including empty-but-existing databases."""
    db = {name: None for name in ("categories", "order", "metadata", "icons", "recent")}
    features = []
    if (root / "categories.db").exists():
        with read_db(root / "categories.db") as conn:
            db["categories"] = {row[0]: [] for row in conn.execute("SELECT name FROM categories ORDER BY sort_order, id")}
            for category, path in conn.execute("SELECT category_name, image_path FROM category_images"):
                db["categories"].setdefault(category, []).append(path)
            db["icons"] = {name: icon for name, icon in conn.execute("SELECT name, icon_path FROM categories") if icon}
    if (root / "order.db").exists():
        with read_db(root / "order.db") as conn:
            db["order"] = [row[0] for row in conn.execute("SELECT image_path FROM item_orders ORDER BY sort_order")]
    if (root / "metadata.db").exists():
        with read_db(root / "metadata.db") as conn:
            conn.row_factory = sqlite3.Row
            db["metadata"] = {row["image_path"]: dict(row) for row in conn.execute("SELECT * FROM image_metadata")}
    if (root / "recent.db").exists():
        with read_db(root / "recent.db") as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(recent_history)")}
            stamp = "updated_at" if "updated_at" in columns else "used_at"
            db["recent"] = list(dict.fromkeys(row[0] for row in conn.execute(
                f"SELECT image_path FROM recent_history ORDER BY {stamp} DESC, id DESC")))
    if (root / "features.db").exists():
        with read_db(root / "features.db") as conn:
            conn.row_factory = sqlite3.Row
            features = [dict(row) for row in conn.execute("SELECT * FROM image_features")]
    js = {"categories": _json(root, "categories", {}), "order": _json(root, "order", []),
          "metadata": _json(root, "metadata", {}), "icons": _json(root, "category_icons", {}),
          "recent": _json(root, "recent", [])}
    settings = _json(root, "config", {}) or {}
    return db, js, features, settings


def _comparable(name, value):
    if value is None:
        return None
    basename = lambda p: ntpath.basename(str(p))
    if name == "categories":
        return [(cat, sorted(basename(p) for p in paths)) for cat, paths in value.items()]
    if name in ("order", "recent"):
        return [basename(p) for p in value]
    if name == "icons":
        return {cat: basename(icon) for cat, icon in value.items()}
    if name == "metadata":
        return {basename(path): (meta.get("keywords", "") if isinstance(meta, dict) else meta)
                for path, meta in value.items()}
    return value


def _summary(layers):
    result = {name: None if value is None else len(value) for name, value in layers.items()}
    cats = layers["categories"]
    result["relations"] = None if cats is None else sum(len(paths) for paths in cats.values())
    return result


def migrate_legacy(source, target, *, source_closed=False, choices=None):
    """Conflicting layers require an explicit db/json choice; no automatic guess.

    The complete review snapshot and source→target mapping stay inside the new
    library. Failed attempts stay in separate staging directories for inspection.
    """
    if not source_closed:
        raise LibraryError("请先关闭旧 SuzuEmojy，再执行只读迁入以保护一致性。")
    source = source_data_root(source)
    target = independent_root(target)
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise LibraryError("新库与旧源不能互相包含。")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise LibraryError("迁入目标必须为空。已完成的库请直接打开，不重复迁入。")
    run_id = uuid.uuid4().hex
    stage = target.with_name(target.name + ".legacy-" + run_id)
    snapshot = stage / "source-snapshot"
    snapshot.mkdir(parents=True)
    report = {"run_id": run_id, "source_read_only": True, "state": "snapshot",
              "conflicts": [], "skipped": [], "failed": [], "choices": choices or {}}
    report_path = stage / "report.json"
    try:
        before = inventory(source)
        for name, expected in before.items():
            dest = snapshot / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, dest)
            if digest(dest) != expected:
                raise LibraryError("旧源在复制时改变，快照未通过校验。")
        if inventory(source) != before:
            raise LibraryError("旧源仍在写入，快照未通过校验，请关闭旧程序再试。")
        # WAL recovery, if necessary, occurs solely in the private copy. Keep the
        # raw verified snapshot intact and inspect a second DB/JSON working copy.
        working = stage / "inspection"
        working.mkdir()
        for name in before:
            if "/" not in name:
                shutil.copy2(snapshot / name, working / name)
        db, js, features, settings = inspect_snapshot(working)
        report["source_counts"] = {"db": _summary(db), "json": _summary(js)}
        selected = {}
        for name in db:
            different = db[name] is not None and js[name] is not None and _comparable(name, db[name]) != _comparable(name, js[name])
            choice = (choices or {}).get(name)
            if different:
                report["conflicts"].append(name)
                if choice not in ("db", "json"):
                    continue
            else:
                choice = "db" if db[name] is not None else "json"
            selected[name] = (db if choice == "db" else js)[name]
            report["choices"][name] = choice
        atomic_json(report_path, report)
        if len(selected) != len(db):
            report["state"] = "needs_source_choice"
            atomic_json(report_path, report)
            raise LegacyConflict(report, report_path)
        fingerprint = __import__("hashlib").sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
        report["source_fingerprint"] = fingerprint
        context = create_library(stage / "library")
        extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".webm")
        image_names = [name[7:] for name in before if name.startswith("images/") and name.lower().endswith(extensions)]
        mapping, by_basename, occupied = {}, {}, set()
        for relative in image_names:
            name = ntpath.basename(relative)
            if name.casefold() in occupied:
                path = Path(name)
                name = path.stem + "_" + uuid.uuid5(uuid.NAMESPACE_URL, relative).hex[:12] + path.suffix
            occupied.add(name.casefold())
            mapping[relative] = name
            by_basename.setdefault(ntpath.basename(relative).casefold(), []).append(relative)
            dest = context.images_dir / name
            shutil.copy2(snapshot / "images" / relative, dest)
            if digest(dest) != before["images/" + relative]:
                raise LibraryError("目标图片校验失败，旧源仍保留。")

        def resolve(value, kind):
            raw = str(value).replace("\\", "/")
            relative = raw.split("/images/", 1)[-1]
            if relative in mapping:
                return mapping[relative]
            matches = by_basename.get(ntpath.basename(raw).casefold(), [])
            if len(matches) == 1:
                return mapping[matches[0]]
            report["skipped"].append({"kind": kind, "reference": str(value),
                                      "reason": "ambiguous" if matches else "missing_resource"})
            return None

        # Compute identities during the explicit migration, never on first paste.
        from services.identity import inspect_bytes, put_identity
        identities = {}
        for name in mapping.values():
            try:
                identities[name] = inspect_bytes((context.images_dir / name).read_bytes())
            except Exception as exc:
                report["failed"].append({"kind": "identity", "reference": name, "reason": type(exc).__name__})
        with context.transaction() as conn:
            for name, identity in identities.items():
                put_identity(conn, context.images_dir / name, identity)
            for index, (category, paths) in enumerate((selected["categories"] or {}).items()):
                conn.execute("INSERT INTO categories.categories(name, sort_order) VALUES (?, ?)", (category, index))
                for path in paths:
                    name = resolve(path, "category_relation")
                    if name:
                        conn.execute("INSERT OR IGNORE INTO categories.category_images VALUES (?, ?)", (category, name))
            ordered = list(dict.fromkeys(filter(None, (resolve(path, "order") for path in selected["order"] or []))))
            # Unordered resources follow the recovered manual order, with no claim
            # that the old source contained an order for these additional images.
            already_ordered = set(ordered)
            ordered.extend(name for name in mapping.values() if name not in already_ordered)
            conn.executemany('INSERT INTO "order".item_orders VALUES (?, ?)', [(name, i) for i, name in enumerate(ordered)])
            for path, value in (selected["metadata"] or {}).items():
                name = resolve(path, "metadata")
                if name:
                    meta = value if isinstance(value, dict) else {"keywords": str(value)}
                    conn.execute("INSERT OR REPLACE INTO metadata.image_metadata(image_path, tags, keywords) VALUES (?, ?, ?)",
                                 (name, meta.get("tags"), meta.get("keywords", "")))
            for category, icon in (selected["icons"] or {}).items():
                value = resolve(icon, "category_icon") if str(icon).lower().endswith(extensions) else icon
                conn.execute("UPDATE categories.categories SET icon_path=? WHERE name=?", (value, category))
            recent = list(dict.fromkeys(filter(None, (resolve(p, "recent") for p in selected["recent"] or []))))
            for name in reversed(recent):
                conn.execute("INSERT INTO recent.recent_history(image_path) VALUES (?)", (name,))
            for feature in features:
                name = resolve(feature["image_path"], "feature")
                if name:
                    conn.execute("""INSERT OR REPLACE INTO features.image_features
                        (image_path, md5, dhash, phash, quality_score) VALUES (?, ?, ?, ?, ?)""",
                        (name, feature.get("md5"), feature.get("dhash"), feature.get("phash"), feature.get("quality_score", 0)))
            # Legacy hashes are retained exactly, without claiming whether a
            # historical md5 denotes file bytes or pixels; P2 versions identities.
            hashes = _json(working, "hashes", {}) or {}
            for key, value in hashes.items():
                if isinstance(value, str):
                    md5, path = (key, value) if len(key) == 32 and all(c in "0123456789abcdefABCDEF" for c in key) else (value, key)
                    name = resolve(path, "legacy_hash")
                    if name:
                        conn.execute("INSERT OR IGNORE INTO features.image_features(image_path, md5) VALUES (?, ?)", (name, md5))
            conn.executemany("INSERT INTO preferences VALUES (?, ?)", [(key, json.dumps(value, ensure_ascii=False)) for key, value in settings.items()])
            report["target_counts"] = {"images": len(mapping), "categories": conn.execute("SELECT COUNT(*) FROM categories.categories").fetchone()[0],
                "relations": conn.execute("SELECT COUNT(*) FROM categories.category_images").fetchone()[0],
                "order": len(ordered), "metadata": conn.execute("SELECT COUNT(*) FROM metadata.image_metadata").fetchone()[0],
                "settings": len(settings), "skipped": len(report["skipped"]), "failed": len(report["failed"])}
            conn.execute("INSERT INTO migration_runs(id, kind, source_fingerprint, report_path) VALUES (?, ?, ?, ?)",
                         (run_id, "suzu_readonly", fingerprint, "data/reports/legacy-" + run_id + ".json"))
        report.update(state="verified", mapping=mapping, source_sha256=before)
        for db_path in context.data_dir.glob("*.db"):
            with read_db(db_path) as conn:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise LibraryError("迁入数据库完整性校验失败。")
        snapshot.rename(context.data_dir / "snapshots" / ("suzu-" + run_id))
        atomic_json(context.data_dir / "reports" / ("legacy-" + run_id + ".json"), report)
        atomic_json(report_path, report)
        if inventory(source) != before:
            raise LibraryError("迁入期间旧源发生变化，目标未启用，请关闭旧程序后重试。")
        if target.exists():
            target.rmdir()
        context.root.rename(target)
        result, _ = inspect_library(target)
        event("library.legacy_import", count=report["target_counts"], status="verified")
        return result, report
    except LegacyConflict:
        raise
    except Exception as exc:
        report.update(state="failed", error_type=type(exc).__name__)
        atomic_json(report_path, report)
        event("library.legacy_import_failed", level="error", error=exc)
        raise
