"""Materialize only the pinned Git baseline into new, isolated P0 cases."""
import io
import os
from pathlib import Path
import subprocess
import zipfile

BASELINE = "c84e5b2c201fe5103e721fca062283cadf97ca0d"
repo = Path(__file__).resolve().parents[2]
work = Path(os.environ["P0_WORK_DIR"]).resolve()
work.mkdir(parents=True, exist_ok=True)
archive = subprocess.check_output(["git", "-C", str(repo), "archive", "--format=zip", BASELINE])
with zipfile.ZipFile(io.BytesIO(archive)) as source:
    for name in ("tests", "empty", "behavior", "build"):
        target = work / f"p0-{name}-source"
        target.mkdir()  # Never reuse or delete an existing case.
        for entry in source.infolist():
            if entry.is_dir() or (name != "build" and entry.filename.startswith("data/")):
                continue
            path = target / entry.filename
            if not path.resolve().is_relative_to(target):
                raise ValueError("Archive path escapes isolated case")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read(entry))
print(f"Prepared four isolated cases at {work} from {BASELINE}")
