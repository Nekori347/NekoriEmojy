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
The shipped README is docs/PACKAGE_README.md, not the developer README.
Unknown files cause packaging to fail; exclusion keywords are not the boundary.

## Commands

From Source: `.venv\Scripts\python.exe scripts\build_release.py` (or build.bat).
The output directory must be new; no previous application tree is reused.
Launcher and independent updater are built with PyInstaller. Compiler scratch
and matching application source archive stay beside the application stage,
not inside it. No source archives are added to Git history.

The default creates a validated application stage and updater manifest only.
`--archive` explicitly enables ZIP creation for the next distribution phase.
Current executables are NekoriEmojy.exe and NekoriEmojyUpdater.exe. Protocol 1
keeps its manifest schema; its required files use these names. No old Demo
executable aliases are shipped. Update assets use the target release version:
NekoriEmojy-{version}-Windows-Portable.zip.

Nuitka's existing compiler pipeline is preserved; its final application stage
is moved under ../Build before allowlist validation. It is a separate, slower
build and is not implied by a successful lightweight build.

For the complete independent build run `.venv\Scripts\python.exe build_nuitka.py`.
It requires MSVC and includes pypinyin/OpenCC data plus the bundled FFmpeg.
The build prints VALIDATION_STAGE and writes compiler-files.json beside it.

After checking that stage, generate both distributions from that exact file set:

```powershell
.venv\Scripts\python.exe scripts\build_distribution.py <stage> --compiler-files <inventory.json> --iscc <ISCC.exe> --output <new-output-directory>
```

The output must be new. It contains NekoriEmojy-<version>-Windows-Portable.zip,
NekoriEmojy-Setup-<version>.exe, NekoriEmojy-<version>-Source.zip and hashes.
ISCC is an external build tool, not an application dependency. The generated
installer lists each verified file explicitly; it never recursively packages
the project. No user library/configuration or Demo cleanup actions are defined.

Keep LICENSE, original copyright, font/icon notices and
THIRD_PARTY_NOTICES.md. Standalone also preserves original installed dependency
notices in THIRD_PARTY_LICENSES.txt. BUILD_INFO records the application commit;
the accompanying Source.zip provides its application source. Local unpublished
commits are not claimed to exist on GitHub. Optional OCR has separate notices
and distribution. The standalone file set is the only input for both Portable ZIP and Inno Setup.
Installation is per-user; uninstall must not remove user configuration or library.
Build products are local candidates, not a public release.
