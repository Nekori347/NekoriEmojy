"""Legacy compatibility entry point; implicit in-place migration is retired.

Call migrate_legacy(source, target, source_closed=True, choices=...) explicitly.
It creates a verified read-only snapshot and a separate new library.
"""
from services.legacy_import import migrate_legacy, LegacyConflict
from services.library import LibraryError


class MigrationManager:
    def __init__(self, *args, **kwargs):
        raise LibraryError("旧库迁入请使用资源库管理中的只读迁入流程，不支持原地自动迁移。")
