[简体中文](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.md) | [繁體中文](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.zh_TW.md) | [English](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.en.md) | [日本語](https://github.com/Nekori347/NekoriEmojy/blob/main/docs/RELEASE_0.2.6.ja.md)

# NekoriEmojy 0.2.6

This update makes large sticker libraries easier to search, browse, and organize. It also adds library switching without restarting the app and improves installation and updating.

## Features and improvements

- **Switch libraries without restarting**: Choose another local sticker library directly from Settings, without restarting NekoriEmojy.
- **Faster Quick Panel**: Faster initial searches and thumbnail loading make it easier to find stickers in large collections.
- **More consistent browsing position**: Improved scroll position restoration when switching categories, searches, recent items, or returning from the system tray.
- **Animated sticker display**: Representative frames and cropping stay synchronized between the Gallery and Quick Panel. ANIM badges now use a subtle translucent style and fade when hovered.

## Fixes

- Fixed the Recent list sometimes showing outdated items after sending stickers elsewhere or changing the display limit.
- Fixed missing resources retaining their previous animation badge after being relinked to a different file.
- Improved state handling when switching libraries and reopening update dialogs.
- Fixed duplicate folder nesting in some installation paths. Installation and uninstallation now check for running application files to prevent incomplete replacement or removal.
- Improved application shutdown, recovery, and retry behavior during built-in updates, along with local diagnostics for prolonged unresponsiveness.

## Download and upgrade

Windows x64 Installer and Portable packages are available. OCR text recognition remains optional.

Before upgrading with the Installer, save any pending edits and fully exit the old version, including its system tray instance. For built-in updates, follow the prompts in the app.

Your existing settings and separate sticker library will continue to be used.

[**Windows Installer (recommended)**](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.6/NekoriEmojy-Setup-0.2.6.exe) · [Windows Portable](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.6/NekoriEmojy-0.2.6-Windows-Portable.zip)
