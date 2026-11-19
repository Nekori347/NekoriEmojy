"""All desktop inputs share this small importer and the upstream codecs."""
from dataclasses import dataclass, field
from pathlib import Path
from services.crash_evidence import import_stage
from services.library_index import ROOT

MAX_IMPORT_BYTES=256*1024**2


@dataclass(repr=False)
class ImportBytes:
    """Owned virtual-file bytes, never a retained QMimeData/IDataObject."""
    data: bytes
    fallback_url: str = ''

    def take(self):
        data,self.data=self.data,b''
        return data


@dataclass(frozen=True)
class ImportTarget:
    parent_node: str = ROOT
    insert_position: int | None = None


@dataclass
class ImportResult:
    paths: list[str] = field(default_factory=list)
    imported: int = 0
    duplicates: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    cancelled: int = 0


class ImportSkipped(Exception):
    """The user skipped only this item; not an import failure."""


@dataclass
class DuplicateCandidate:
    existing: str
    source: object
    target: ImportTarget
    before: tuple | None = None
    checkpoint: tuple | None = None


class ImportDeferred(Exception):
    """Collected for this desktop batch; no relation has been accepted yet."""


class ResourceImporter:
    def __init__(self, storage):
        self.storage = storage

    def _accept(self, saved, duplicate, source_name, target, library_added_seq=None):
        if not saved:
            raise RuntimeError("Resource could not be saved")
        import_stage(self.storage.import_context,'store')
        index = self.storage.index
        checkpoint = getattr(self.storage.import_context, 'checkpoint', None)
        if checkpoint:
            index.register(saved, source_name, library_added_seq=library_added_seq, target=target,
                           checkpoint=checkpoint, duplicate=duplicate,
                           kept=getattr(self.storage.import_context,'duplicate_choice','')=='keep' and not duplicate)
            return saved, duplicate
        index.register(saved, source_name, library_added_seq=library_added_seq, target=target)
        return saved, duplicate

    def file(self, source, target=ImportTarget(), strict=False, *, library_added_seq=None):
        decoded = []
        # The first deduplication index build scans the existing library. It
        # owns its own single-flight lock and need not block gallery ordering.
        self.storage._get_sync_key_index()
        with self.storage.lock:
            self._validate_target(target)
            saved, duplicate = self.storage._save_file_source(source, strict=strict, on_decoded=decoded.append)
            if not saved:
                return None, False
            normalized=getattr(self.storage.import_context,'normalized',None)
        if duplicate and getattr(self.storage.import_context,'checkpoint',None) and not self.storage.index.resource(saved):
            # A crash may leave validated bytes/features but no accepted catalog
            # resource. Reuse those bytes as a new acceptance, not a user conflict.
            duplicate=False
        animated = decoded[-1] if decoded and not duplicate else None
        if duplicate:
            self._defer_duplicate(saved,source,target)
            saved,duplicate,animated=self._resolve_duplicate(saved,source,normalized,decoded[-1] if decoded else None)
        with self.storage.lock:
            result = self._accept(saved, duplicate, Path(source).name, target, library_added_seq)
        self._notify(saved,duplicate,target,animated=animated)
        return result

    def image(self, image, target=ImportTarget()):
        decoded = []
        self.storage._get_sync_key_index()
        with self.storage.lock:
            self._validate_target(target)
            saved, duplicate = self.storage._save_qimage_source(image, on_decoded=decoded.append)
            if not saved:
                return None, False
            normalized=getattr(self.storage.import_context,'normalized',None)
        animated = decoded[-1] if decoded and not duplicate else None
        if duplicate:
            self._defer_duplicate(saved,image,target)
            saved,duplicate,animated=self._resolve_duplicate(saved,image,normalized,decoded[-1] if decoded else None)
        with self.storage.lock:
            result = self._accept(saved, duplicate, Path(saved).name, target)
        self._notify(saved,duplicate,target,animated=animated)
        return result

    def _resolve_duplicate(self,saved,source,normalized,animated):
        resolver=getattr(self.storage.import_context,'duplicate_resolver',None)
        if not resolver:return saved,True,None
        # No storage/database lock is held while the GUI waits for a choice.
        decision=resolver(saved,source)
        if decision=='reuse':return saved,True,None
        if decision=='skip':
            context=self.storage.import_context
            context.skipped=getattr(context,'skipped',0)+1
            raise ImportSkipped()
        if decision=='keep':
            with self.storage.lock:
                kept,duplicate=self.storage._standardize_and_save(normalized[0],normalized[1],strict=True,force_new=True)
                return kept,duplicate,animated
        if decision=='replace':
            result=self.storage.replace_normalized(saved,normalized)
            return result,True,animated
        raise ValueError('Unknown duplicate decision')

    def _defer_duplicate(self,saved,source,target):
        pending=getattr(self.storage.import_context,'deferred_duplicates',None)
        if pending is None:return
        before=None
        if target.insert_position is not None:
            entries=self.storage.index.content(target.parent_node)
            if 0<=target.insert_position<len(entries):
                entry=entries[target.insert_position];before=(entry['kind'],entry['id'])
        pending.append(DuplicateCandidate(saved,source,target,before,getattr(self.storage.import_context,'checkpoint',None)))
        raise ImportDeferred()

    def _notify(self,saved,duplicate=False,target=ImportTarget(),*,animated=None):
        # Only this operation's accepted decode result may be persisted here.
        # Missing attributes are scheduled AFTER the normal GUI commit signal.
        import sqlite3
        from services.animation_attributes import store_import_animation
        missing = saved
        try:
            missing = store_import_animation(self.storage, saved, animated)
        except (OSError, ValueError, sqlite3.Error):
            pass  # Keep the saved resource; the same backfill can retry it.
        self.storage.ensure_category_icon(target.parent_node,saved)
        committed=getattr(self.storage.import_context,'committed',None)
        if committed:committed([saved],{ROOT,target.parent_node})
        accepted=getattr(self.storage.import_context,'accepted',None)
        if accepted is not None:accepted.append((saved,duplicate))
        backfill=getattr(self.storage,'animation_backfill',None)
        if missing and backfill is not None:backfill.requested.emit(missing)
        if getattr(self.storage.import_context,'job_id',None):return
        if not self.storage.import_listeners:return
        record=self.storage.index.resource(saved)
        if record:
            for listener in tuple(self.storage.import_listeners):
                try:listener(record['id'])
                except Exception as exc:print('[OCR] Import remains successful:',exc)

    def _validate_target(self, target):
        cancelled=getattr(self.storage.import_context,'cancelled',None)
        if cancelled and cancelled():raise InterruptedError()
        with self.storage.index.connect() as db:
            if not db.execute("SELECT 1 FROM nodes WHERE id=?", (target.parent_node,)).fetchone():
                raise KeyError(target.parent_node)

    def paths(self, sources, target=ImportTarget(), progress=None):
        result = ImportResult()
        self._validate_target(target)

        def visit(source, destination):
            cancelled=getattr(self.storage.import_context,'cancelled',None)
            if cancelled and cancelled():raise InterruptedError()
            path = Path(source)
            try:
                if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                    raise ValueError("Folder import does not follow links or junctions")
                if path.is_dir():
                    # Never recursively import the active library into itself.
                    if self.storage.index.root == path.resolve() or self.storage.index.root.is_relative_to(path.resolve()):
                        raise ValueError("Cannot import the library or an ancestor into itself")
                    siblings = [n for n in self.storage.index.nodes() if n['parent_id'] == destination.parent_node and n['name'] == path.name]
                    node = siblings[0]['id'] if siblings else self.storage.index.create_node(path.name, destination.parent_node,
                        position=destination.insert_position)
                    if siblings and destination.insert_position is not None:
                        self.storage.index.move_node(node, destination.parent_node, destination.insert_position)
                    committed=getattr(self.storage.import_context,'committed',None)
                    if committed:committed([],{destination.parent_node,node})
                    for offset,child in enumerate(sorted(path.iterdir(), key=lambda p: p.name.casefold())):
                        if child.is_dir() or child.suffix.lower() in self.storage.SUPPORTED_FORMATS:
                            visit(child, ImportTarget(node,offset))
                    return
                saved, duplicate = self.file(str(path), destination, strict=True)
                result.paths.append(saved)
                if duplicate:
                    result.duplicates += 1
                else:
                    result.imported += 1
                if progress:
                    progress(result.imported + result.duplicates + len(result.errors), str(path))
            except ImportDeferred:
                pass
            except ImportSkipped:
                result.cancelled+=1
            except InterruptedError:
                raise
            except KeyError:
                if getattr(self.storage.import_context,'checkpoint',None):
                    from services.task_recovery import RecoveryWait
                    raise RecoveryWait('目标分类已改变，无法安全继续')
                raise
            except Exception as exc:
                trace=getattr(self.storage.import_context,'import_trace',None)
                if trace:trace.failure(exc)
                result.errors[str(path)] = str(exc)

        for offset, source in enumerate(sources):
            position = (0 if target.insert_position is None else target.insert_position) + offset
            try:visit(source, ImportTarget(target.parent_node, position))
            except InterruptedError:break
        return result
