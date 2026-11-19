"""One synchronous GUI transaction for replacing Library-bound surfaces."""
from pathlib import Path


def busy_reason(window):
    from PySide6.QtWidgets import QApplication
    from fluent_ui.components.update_dialog import active_tasks
    from services.drag_activity import drag_activity
    storage=window.storage
    imports=getattr(storage,'desktop_imports',None)
    ocr=getattr(storage,'ocr',None)
    backup=getattr(storage,'backup_service',None)
    if (QApplication.activeModalWidget() is not None or drag_activity().operation is not None or active_tasks() or (imports and (imports.worker or imports.waiting or imports._decisions))
        or (ocr and (ocr.busy or ocr.installing)) or (backup and backup.pending)
        or getattr(storage,'_sync_index_building',False)):
        return '请等待当前任务完成后再切换表情库。'
    return ''


def same_library(storage, directory):
    current = storage.index.root
    target = Path(directory).expanduser().resolve()
    return current == target or (target.exists() and current.samefile(target))


def _bind(window, bundle, page):
    storage, gallery, quick, settings = bundle
    window.storage = storage
    window.gallery_interface = gallery
    window.quick_panel = quick
    window.settings_window = settings
    window.setting_interface = settings.center
    window.config.backup_service = gallery.backups
    window._window_import_receiver.gallery = gallery
    window.stacked_widget.setCurrentWidget(page)


def _cleanup(action):
    """Retirement errors belong to the retired objects, not the saved config."""
    import logging
    try:
        action()
    except Exception:
        logging.getLogger(__name__).exception('Library cleanup failed in %s', action)


def _dispose(storage, widgets):
    animation = getattr(storage, 'animation_backfill', None)
    if animation is not None:
        _cleanup(animation.stop)
    for name, method in (('desktop_imports', 'shutdown'), ('ocr', 'close'),
                         ('backup_service', 'shutdown')):
        service = getattr(storage, name, None)
        if service is not None:
            _cleanup(getattr(service, method))
            _cleanup(service.deleteLater)
    for widget in widgets:
        _cleanup(widget.hide)
        _cleanup(widget.deleteLater)


def _prepare_views(window, storage):
    from PySide6.QtWidgets import QApplication, QWidget
    from fluent_ui.views.gallery_view import GalleryInterface
    from fluent_ui.components.quick_panel import QuickPanel
    from fluent_ui.window_shell import SettingsWindow

    # Constructors are synchronous. Include partially constructed Qt windows
    # in cleanup if a constructor raises before returning its Python wrapper.
    existing = set(QApplication.topLevelWidgets()) | set(window.children())
    try:
        gallery = GalleryInterface(storage, window.clipboard, window.config, window,
                                   send_target_service=window.send_target_service,
                                   defer_background=True)
        quick = QuickPanel(storage, window.clipboard, window.config,
                           send_target_service=window.send_target_service,
                           representative_source=gallery)
        settings = SettingsWindow(window.config, storage, window)
        quick.feedback_owner = gallery.feedback_host
        return storage, gallery, quick, settings
    except Exception:
        created = set(QApplication.topLevelWidgets()) | set(window.children())
        _dispose(storage, [obj for obj in created - existing if isinstance(obj, QWidget)])
        raise


def _connect_views(window, gallery, settings, *, connect):
    for signal, receiver in (
        (gallery.hide_after_paste_requested, window._hide_after_paste),
        (gallery.setting_requested, window.show_settings),
        (gallery.exchange_requested, window.show_exchange),
        (gallery.similarity_requested, window.show_similarity),
        (gallery.qq_requested, window.show_qq_scan),
        (gallery.tg_requested, window.show_tg_sticker),
        (gallery.about_requested, window.show_about),
        (settings.center.settings_changed, window.on_settings_changed),
        (window.destroyed, settings.deleteLater),
    ):
        (signal.connect if connect else signal.disconnect)(receiver)


def _restore_config_file(path, original):
    from tempfile import NamedTemporaryFile
    import os

    if original is None:
        path.unlink(missing_ok=True)
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(original)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def switch_library(window, directory, mode, values, *, clear_markers=False):
    """Prepare inactive views, persist settings, then publish the new bundle."""
    from contextlib import nullcontext
    from services.library_setup import prepare_library

    reason = busy_reason(window)
    if reason:
        raise RuntimeError(reason)
    config = window.config
    original = dict(config.config)
    path = Path(config.config_path)
    try:
        disk = path.read_bytes()
    except FileNotFoundError:
        disk = None
    old = (window.storage, window.gallery_interface, window.quick_panel, window.settings_window)
    old_page = window.stacked_widget.currentWidget()
    values = dict(values, library_view_states=old[1].library_view_states())

    with prepare_library(directory, mode, config, fill_icons=False) as storage:
        candidate = _prepare_views(window, storage)
        _, gallery, quick, settings = candidate
        try:
            # Owned signals are dormant until this bundle becomes visible.
            _connect_views(window, gallery, settings, connect=True)
            config._save_config(values)
            try:
                config.config.update(values)
                markers = (storage.index.connect(search=False)
                           if clear_markers else nullcontext())
                with markers as db:
                    if db is not None:
                        db.execute('DELETE FROM resource_unseen')
                    window.stacked_widget.addWidget(gallery)
                    _bind(window, candidate, gallery if old_page is old[1] else old_page)
            except Exception:
                try:
                    _bind(window, old, old_page)
                finally:
                    config.config.clear()
                    config.config.update(original)
                    _restore_config_file(path, disk)
                raise
        except Exception:
            window.stacked_widget.removeWidget(gallery)
            _dispose(storage, candidate[1:])
            raise

    # The old center can finish Save, but only the current center dispatches.
    _cleanup(lambda: _connect_views(window, old[1], old[3], connect=False))
    return old


def retire_library(window, old):
    """Release the previous bundle after the committed settings are delivered."""
    gallery = window.gallery_interface
    settings = window.settings_window
    was_visible = old[3].isVisible()
    gallery._defer_background = False
    _cleanup(old[2].shutdown)
    _cleanup(lambda: window.stacked_widget.removeWidget(old[1]))
    _dispose(old[0], old[1:])
    window._tray_hidden_windows = []
    for name in ('qq_window', 'tg_window', '_similarity_window'):
        widget = getattr(window, name, None)
        if widget is not None:
            _cleanup(widget.hide)
            _cleanup(widget.deleteLater)
        setattr(window, name, None)
    window.qq_scan_interface = window.tg_sticker_interface = None

    errors = []
    for title, start in (
        ('文字识别恢复失败', gallery.ocr.start),
        ('备份服务启动失败', gallery.backups.start),
        ('动画属性补录启动失败', gallery.renderer.loader.animation_backfill.start),
    ):
        try:
            start()
        except Exception as error:
            import logging
            logging.getLogger(__name__).exception('%s', title)
            errors.append((title, str(error) or type(error).__name__))
    if was_visible:
        _cleanup(settings.present)
    return errors
