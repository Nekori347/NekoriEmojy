"""Build the isolated updater and a reproducible, manifest-owned release zip."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from services.update_protocol import MANIFEST, PROTECTED, atomic_json, read_manifest, sha256, version_key


def package_release(release_dir, flavor, *, compiler_files=None, archive=True):
    release_dir = Path(release_dir).resolve()
    version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    version_key(version["version"])
    if version.get("channel") != "stable":
        raise ValueError("Only stable releases are currently supported")
    from scripts.release_layout import validate_layout
    validate_layout(release_dir,flavor,compiler_files)
    from scripts.windows_version import version_resource
    resource = version_resource(release_dir.parent / "updater-version.txt", "NekoriEmojyUpdater.exe", "NekoriEmojy Updater")
    # Both packaging modes use an independent updater without Qt dependencies.
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--noconsole",
        "--version-file", str(resource), "--icon", str(ROOT / "ico.ico"),
        "--name", "NekoriEmojyUpdater", "--distpath", str(release_dir),
        "--workpath", str(release_dir.parent / "updater-build"),
        "--specpath", str(release_dir.parent), str(ROOT / "updater.py"),
    ], cwd=ROOT, check=True)
    atomic_json(release_dir / "version.json", version)
    from scripts.release_layout import validate_layout
    files = {name:sha256(release_dir/name) for name in validate_layout(release_dir,flavor,compiler_files)}
    atomic_json(release_dir / MANIFEST, {"protocol": 1, "version": version["version"], "flavor": flavor, "files": files})
    read_manifest(release_dir, verify=True)
    if not archive:
        return release_dir
    archive_name = version.get("update_asset", "NekoriEmojy-{version}-Windows-Portable.zip").format(version=version["version"])
    if Path(archive_name).name != archive_name or not archive_name.endswith(".zip"):
        raise ValueError("Invalid release archive name")
    archive = release_dir.parent / archive_name
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name in sorted(files) + [MANIFEST]:
            output.write(release_dir / name, name)
    archive.with_suffix(".zip.sha256").write_text(sha256(archive) + "  " + archive.name + "\n", encoding="ascii")
    print("Release v" + version["version"] + ": " + str(archive))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("release_dir")
    parser.add_argument("--flavor", choices=["standalone", "lightweight"], required=True)
    args = parser.parse_args()
    package_release(args.release_dir, args.flavor)
