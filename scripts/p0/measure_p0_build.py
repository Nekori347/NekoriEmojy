"""Inventory and measure the internal upstream comparison build, not a release."""
import hashlib
import json
import os
from pathlib import Path
import time
import zipfile

work = Path(os.environ["P0_WORK_DIR"]).resolve()
release = work / "p0-build-source/dist/SuzuEmojy_Release"
archive_path = work / "p0-upstream-comparison.zip"
assert release.is_dir() and not archive_path.exists()
files = sorted(p for p in release.rglob("*") if p.is_file())
started = time.perf_counter()
with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED,
                     compresslevel=6, allowZip64=True) as archive:
    for path in files:
        archive.write(path, "SuzuEmojy_Release/" + path.relative_to(release).as_posix())
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
hash_file = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = {
    "source_commit": "c84e5b2c201fe5103e721fca062283cadf97ca0d",
    "product_sources_and_upstream_build_recipe_unchanged": True,
    "extra_nuitka_options": ["--zig", "--jobs=4"],
    "nuitka": "4.2.1", "zig": "0.16.0", "python": "3.12.14", "qt": "6.11.2",
    "compile_and_launcher_success": True,
    "zip_compression": "Python zipfile ZIP_DEFLATED level 6",
    "file_count": len(files), "unpacked_bytes": sum(p.stat().st_size for p in files),
    "zip_bytes": archive_path.stat().st_size,
    "zip_sha256": hash_file(archive_path),
    "core_exe_sha256": hash_file(release / "bin/SuzuEmojy.exe"),
    "launcher_exe_sha256": hash_file(release / "SuzuEmojy.exe"),
    "runtime_data_paths": [p.relative_to(release).as_posix() for p in files
                           if p.relative_to(release).as_posix().startswith("bin/data/")],
    "avx512_check": "not verified: original checker returned success after objdump was absent",
    "binary_native_interaction": "not verified; existing user SuzuEmojy instance was not stopped",
    "distribution": "internal baseline comparison only; not an approved NekoriEmojy release",
    "zip_validation_elapsed_seconds": time.perf_counter() - started,
}
(work / "p0-build-measurement.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
