# Build and distribution boundary

The sole active project is F:\NekoriEmojy; Git remains in Source/. Historical
projects, snapshots and test assets are not application inputs.

## Positive inventory

scripts/release_layout.py is the application file allowlist:

- Explicit entry, dependency requirements, OCR component descriptor, icon,
  README, GPL license and third-party notice.
- Tracked Python modules in fluent_ui/ and services/ (including actual Suzu
  migration/compatibility implementations).
- Tracked UI font/icon resources under fluent_ui/assets/, with their notices.
- Exactly zh/en/ja/zh_TW translation dictionaries.
- Generated launcher/updater, version and build information.
- For standalone only: the exact dependency file list captured from the fresh
  compiler output. A bin directory copied from an old release is not accepted
  as an implicit dependency inventory.

The root assets/ directory contains historical documentation/demo media and is
not needed by the current UI; it is not a release input. Personal config,
indexes, images, OCR runtimes, tests, .git, assistant files, archives, logs,
screenshots, downloads and developer environments are absent from the inventory.
Unknown files cause packaging to fail; exclusion keywords are not the boundary.

## Commands

From Source: `.venv\Scripts\python.exe scripts\build_release.py` (or build.bat).
The output directory must be new; no previous application tree is reused.
Launcher and independent updater are built with PyInstaller. Compiler scratch
and matching application source archive stay beside the application stage,
not inside it. No source archives are added to Git history.

The default creates a validated application stage and updater manifest only.
`--archive` explicitly enables ZIP creation for the next distribution phase.
Do not publish validation stages. The package names inherited from protocol 1
(SuzuEmojy.exe and SuzuEmojyUpdater.exe) are intentional compatibility names.

Nuitka's existing compiler pipeline is preserved; its final application stage
is moved under ../Build before allowlist validation. It is a separate, slower
build and is not implied by a successful lightweight build.

Keep LICENSE, original copyright, font/icon notices and
THIRD_PARTY_NOTICES.md. BUILD_INFO records the exact local commit; the adjacent
corresponding-source.zip preserves its application source. Local unpublished
commits are not claimed to exist on GitHub. Optional OCR has separate notices
and distribution. Inno Setup and public release remain a later phase.
