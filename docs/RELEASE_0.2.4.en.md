[简体中文](RELEASE_0.2.4.md) | [繁體中文](RELEASE_0.2.4.zh_TW.md) | [English](RELEASE_0.2.4.en.md) | [日本語](RELEASE_0.2.4.ja.md)

# NekoriEmojy 0.2.4

## v0.2.4 fixes

- Fixed an issue where the app could fail to exit during an in-app update, causing the updater to time out.
- Improved shutdown coordination, error feedback, and update retries.
- Fixed links in update notes that could not be opened.

**Upgrading from v0.2.2 / v0.2.3**: if the in-app update gets stuck preparing to restart, download the Installer from this release. Save your settings and exit the app normally, including its tray instance, before installing manually. Downloading a new package cannot repair the old app's own exit code. Keep your Library; the Installer retains the existing installation location and user data.

The v0.2.3 features below are also included.

This update adds automatic backups and restoration, clipboard text search, operation sounds, new-emoji markers, and a notification button. It also improves organizing, dragging, sending, and settings.

## New features

- **Automatic backups and full restoration**: choose the interval, destination, and retention count, or start a backup manually. Restore into a new Library with categories, tags, and ordering preserved.
- **Clipboard text search**: assign a dedicated shortcut to open Quick Panel and search the current clipboard text. Triggering it again updates the search even when the panel is already open.
- **Operation sounds**: separate switches for sending, adding, deleting, reordering, and adding to categories, with custom files, previews, and shared volume.
- **New-emoji markers**: stars identify newly added emoji and disappear after viewing. They can also be disabled in settings.
- **Notification access**: a title-bar button opens retained notifications and task records.

## Improvements

- Adjacent emoji share a clear insertion line for more precise placement.
- New emoji appear at the front of a category by default. Batch imports keep their order, while explicit drop positions are respected.
- Double-click a category tab to enter its category.
- Settings are grouped more consistently. Sounds have a dedicated page and combined cards; numeric settings have a restore-default icon.
- Clearer sending feedback, update-check layout, and diagnostic export.

## Fixes

- Restored dragging in noninteractive title-bar areas while progress or notifications are visible.
- Fixed a lingering highlight after reordering a single emoji that blocked other hover previews.
- Fixed duplicate drag/drop commits and placement changes caused by delayed handling.
- Improved external-image drops onto blank window areas while preserving category and insertion-target priority.
- Fixed clipping of Live preview and the unsaved-changes notice in settings.

See the [detailed fixes (Simplified Chinese)](RELEASE_0.2.4_FIXES.md).

## Usage and upgrading

- Windows x64 Installer and Portable editions are available. The Installer is recommended for most users. Save settings and exit the application, including its tray instance, before upgrading. If files remain in use, exit normally and retry.
- Automatic backups and operation sounds are off by default. When enabled, backups yield during foreground activity. The clipboard-search shortcut starts unassigned.
- Store backups outside the Library. Restoration creates a separate Library rather than overwriting the one in use.
- Windows 10 uses an opaque background by default. Acrylic can be enabled after acknowledging the compatibility prompt.
- OCR remains optional; normal emoji management does not require it.

## Downloads

[Windows Installer (recommended)](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.3/NekoriEmojy-Setup-0.2.3.exe) · [Windows Portable](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.3/NekoriEmojy-0.2.3-Windows-Portable.zip)
