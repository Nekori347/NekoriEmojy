[简体中文](RELEASE_0.2.5.md) | [繁體中文](RELEASE_0.2.5.zh_TW.md) | [English](RELEASE_0.2.5.en.md) | [日本語](RELEASE_0.2.5.ja.md)

# NekoriEmojy 0.2.5

## Features and improvements

- Per-category display sorting and HERE / ALL search scope preserve manual ordering.
- Optional one-time automatic category icons respect manually assigned icons. Gallery, category/application icons and Quick Panel share the resource's custom representative frame.
- Category titles count distinct resources across the category and all descendants.
- Optional ANIM badges identify actual multi-frame images. Settings use the real star and ANIM graphics; the frame picker adds previous/next frame buttons.
- Icon-mode category cards have independent drawer chevrons, full-card hover, distinct child hover and a dashed outline when a collapsed ancestor contains the selected category.
- After an abnormal exit, the next launch saves a bounded, sanitized local diagnostic ZIP and shows a one-time reminder. Hidden startup defers the reminder until the main window is opened. Nothing is uploaded automatically.

## Fixes

- Closing to the tray now saves the current gallery position before restoration can use an outdated snapshot.
- Improved drag cancellation, first sidebar insertion, edge scrolling and paste/drop placement; faster sidebar sort switching.
- Same-category manual reordering is silently disabled under non-manual display sorting; cross-category drops, external imports and drag-out remain available.
- Import queue cleanup distinguishes business results from native thread completion, improving failure recovery.
- Fixed valid Chrome OLE image content being ignored when no file-size declaration is present; added anonymous import lifecycle context and lightweight native-fault correlation.

## Known limitations

R04 native access violations remain investigated, unresolved and deferred. R12 sending degradation, R13 selection/scroll jumps and R17 long-running web import failures remain under observation; this release does not claim complete fixes. Gallery Scroll Ownership and whole-Library hot switching are plans only.

## Upgrade

Windows x64 Installer and Portable are available; OCR is optional. Save settings and exit the application, including its tray instance, before upgrading. If files are in use, exit normally and retry. Keep existing settings and Library. For the exit issue in the v0.2.2 / v0.2.3 updater, exit normally and install manually.

[Installer](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.5/NekoriEmojy-Setup-0.2.5.exe) · [Portable](https://github.com/Nekori347/NekoriEmojy/releases/download/v0.2.5/NekoriEmojy-0.2.5-Windows-Portable.zip)
