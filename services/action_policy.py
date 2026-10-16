"""Shared predicates for resource menus and selection commands."""
from dataclasses import dataclass
from services.library_index import ROOT
from services.image_frames import is_animated


@dataclass(frozen=True)
class ActionContext:
    paths: tuple[str, ...]
    existing: tuple[str, ...]
    active_view: str
    all_direct: bool
    animated: bool

    @classmethod
    def from_entries(cls, entries, direct_ids, active_view=ROOT):
        """UI projection already carries the shared availability cache; no per-row SQL."""
        paths = tuple(e['path'] for e in entries)
        existing = tuple(e['path'] for e in entries if e.get('status') != 'missing')
        return cls(paths, existing, active_view,
                   bool(paths) and all(e['id'] in direct_ids for e in entries),
                   len(paths) == 1 and bool(existing) and is_animated(paths[0]))

    @classmethod
    def build(cls, storage, paths, active_view=ROOT, *, revalidate=False):
        paths = tuple(dict.fromkeys(paths))
        existing = tuple(p for p in paths if storage.availability.exists(p, revalidate=revalidate))
        direct = {e['id'] for e in storage.index.content(active_view) if e['kind'] == 'resource'} if paths and active_view != ROOT else set()
        all_direct = bool(paths) and all((storage.resource_of(p) or {}).get('id') in direct for p in paths)
        animated = len(paths) == 1 and bool(existing) and is_animated(paths[0])
        return cls(paths, existing, active_view, all_direct, animated)


class ActionPolicy:
    @staticmethod
    def enabled(action, context):
        selected = bool(context.paths)
        if action in ('tag_edit', 'copy_path', 'delete', 'category_membership'):
            return selected
        if action == 'thumbnail_frame':
            return len(context.paths) == 1 and bool(context.existing) and context.animated
        if action in ('show_in_explorer', 'send', 'set_icon'):
            return len(context.paths) == 1 and bool(context.existing)
        if action == 'export':
            return bool(context.existing)
        if action == 'remove_from_category':
            return context.active_view != ROOT and selected and context.all_direct
        if action == 'forget':
            return selected and not context.existing
        raise ValueError(action)

    @staticmethod
    def delete_label(context):
        if len(context.paths) != 1:
            return '从 Nekori 删除所选资源'
        return '删除资源（回收站）' if context.existing else '移除失效记录'
