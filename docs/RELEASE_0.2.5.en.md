[简体中文](RELEASE_0.2.5.md) | [繁體中文](RELEASE_0.2.5.zh_TW.md) | [English](RELEASE_0.2.5.en.md) | [日本語](RELEASE_0.2.5.ja.md)

# NekoriEmojy 0.2.5

This update improves category browsing, search, and animated image display. It also introduces automatic category icons and local crash reports, along with fixes for drag-and-drop, sorting, and image imports.

## New Features and Improvements

- **Category sorting and search**: The category sidebar now has independent display sorting controls. Search within the current category (HERE) or across the entire library (ALL).
- **Automatic category icons**: Optionally assign category icons automatically, while prioritizing icons you've already selected manually.
- **Consistent thumbnail frames**: Selected frames from animated images can now be used in the gallery, category icons, application icons, and the Quick Panel.
- **Animated image badges**: Multi-frame images now have an optional `ANIM` badge. The thumbnail frame picker also includes Previous and Next buttons.
- **Category item counts**: Category headings now include images from nested subcategories, with duplicate images counted only once.
- **Icon mode**: Improved category expansion, collapse, and selection indicators for easier navigation through nested categories.
- **Local crash reports**: After an unexpected exit, the next launch automatically saves a local diagnostic report and displays a notification.

## Bug Fixes

- Fixed an issue where reopening the application from the system tray could restore an outdated gallery position.
- Improved insertion indicators, drag cancellation, and automatic scrolling near the edges when organizing images.
- Improved paste/import placement and category sorting transitions.
- Refined drag-and-drop behavior across sorting modes to reduce accidental ordering changes.
- Improved handling of failed image imports and task completion notifications.
- Fixed an issue that prevented some images copied from Chrome from being recognized and imported correctly.

## Download and Upgrade

Windows x64 Installer and Portable versions are available.

Save your settings and fully exit NekoriEmojy, including its system tray instance, before upgrading.

[**Windows Installer (Recommended)**](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.5/NekoriEmojy-Setup-0.2.5.exe) · [Windows Portable](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.5/NekoriEmojy-0.2.5-Windows-Portable.zip)
