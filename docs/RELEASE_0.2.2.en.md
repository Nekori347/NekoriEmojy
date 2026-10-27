[简体中文](RELEASE_0.2.2.md) | [English](RELEASE_0.2.2.en.md) | [日本語](RELEASE_0.2.2.ja.md)

# NekoriEmojy 0.2.2

This update improves emoji organization, drag-and-drop, batch importing, and everyday usability, alongside fixes for issues reported after version 0.2.1.

## New and improved

### Organizing your library
- **Unified selection:** Select emojis and category nodes with consistent Ctrl/Shift and batch-operation behavior.
- **Sticky category headers:** Keep the current category heading visible while scrolling.
- **Improved drag-and-drop:** Move emojis or category nodes onto category tabs, with a clear cancellation area.
- **Recycle Bin protection:** Dragging from the main gallery uses separate file copies and requires confirmation before removing originals from your library.

### Importing and tasks
- **Global import shortcut:** Press `Ctrl + Alt + V` to import copied images. The shortcut can be changed or disabled.
- **Batch duplicate handling:** Review and resolve duplicate emojis together during batch imports.
- **Interrupted task recovery:** Resume, postpone, or discard supported interrupted local import and OCR tasks without blindly repeating completed work.
- Improved progress reporting, incremental gallery updates, and safe stopping of export tasks.

### Interface and usability
- Improved task notifications while preserving the original layered display of progress and temporary results.
- Clearer sorting, settings, import/export, and tool messages across Simplified Chinese, Traditional Chinese, English, and Japanese.
- Separate controls for interface animations and window acrylic effects.
- Optional background checks for updates, without automatic installation.
- Reopening the app attempts to bring the existing window forward.
- New **Feedback & Suggestions** links in the application menu and About page, plus user-initiated copying of basic environment information.

### Performance, security, and reliability
- Reduced redundant work in selected gallery queries, category indexing, menu construction, and batch category operations.
- Strengthened validation of resource-package paths, archive contents, and image download sizes.
- Improved recovery of invalid Telegram default connection settings and handling of custom credentials and proxy transport.
- Improved bounded diagnostic logging and user-initiated export. No automatic upload of your library or diagnostic files.

## Fixes and technical details

Detailed issue histories are available for:

- [Gallery performance and batch operations](https://github.com/Nekori347/NekoriEmojy/issues/26)
- [Category drag-and-drop](https://github.com/Nekori347/NekoriEmojy/issues/17)
- [Tag panel interaction](https://github.com/Nekori347/NekoriEmojy/issues/24)
- [Window maximize and restore](https://github.com/Nekori347/NekoriEmojy/issues/57)
- [Button hover and focus](https://github.com/Nekori347/NekoriEmojy/issues/60)
- [Tooltips and interface copy](https://github.com/Nekori347/NekoriEmojy/issues/62)
- [Complete post-0.2.1 development history](https://github.com/Nekori347/NekoriEmojy/issues/37)

## Known issues

Window-edge resizing, dragging responsiveness on some Windows systems, and performance spikes when scrolling large libraries remain under investigation. See [#9](https://github.com/Nekori347/NekoriEmojy/issues/9), [#7](https://github.com/Nekori347/NekoriEmojy/issues/7), and [#26](https://github.com/Nekori347/NekoriEmojy/issues/26).

## Download and upgrade

Windows x64 installer and portable editions are available. OCR remains an optional component.

Back up your emoji library and settings before upgrading. User data may be stored separately from the application folder; do not delete your user-data directory when updating.

For bug reports and feature suggestions, use the new in-app feedback entry or visit [GitHub Issues](https://github.com/Nekori347/NekoriEmojy/issues).
