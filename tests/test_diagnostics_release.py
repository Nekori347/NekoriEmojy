import json
from pathlib import Path
import time
import zipfile

import pytest

from services.diagnostics import Diagnostics, MAX_BYTES, BACKUPS, QUEUE_SIZE
from services.library import create_library
from scripts.release_policy import assert_clean_release


def test_diagnostic_export_has_counts_and_stack_without_private_payload(tmp_path):
    context = create_library(tmp_path / "library")
    diag = Diagnostics(context.data_dir / "logs", context)
    try:
        raise ValueError("secret-token private OCR and clipboard content")
    except ValueError as exc:
        diag.event("test.failure", level="error", error=exc)
    diag.close()
    target = diag.export(tmp_path / "report.zip")
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == {"summary.json", "events.log"}
        data = b"\n".join(archive.read(name) for name in archive.namelist())
        assert b"secret-token" not in data and b"private OCR" not in data
        assert str(tmp_path).encode() not in data
        summary = json.loads(archive.read("summary.json"))
        assert summary["counts"]["categories"] == 0
        assert b"ValueError" in data and b"stack" in data


def test_logging_failure_and_queue_overflow_do_not_break_caller(tmp_path):
    bad_dir = tmp_path / "a-file"
    bad_dir.write_text("not a directory")
    diag = Diagnostics(bad_dir)
    diag.event("safe.event")
    diag.close()
    diag = Diagnostics(tmp_path / "logs")
    # Pause the consumer, then saturate the bounded standard-library queue.
    diag._listener.stop()
    diag._listener = None
    for _ in range(QUEUE_SIZE * 2):
        diag.event("test.event")
    assert diag._queue.qsize() == QUEUE_SIZE
    assert diag._handler.dropped == QUEUE_SIZE
    diag.close()


def test_release_policy_rejects_runtime_state_and_keeps_static_components(tmp_path):
    release = tmp_path / "release"
    (release / "bin/translations").mkdir(parents=True)
    (release / "bin/NekoriEmojy.exe").write_bytes(b"test fixture, not executable")
    (release / "bin/translations/zh.json").write_text("{}")
    assert_clean_release(release)
    (release / "bin/data").mkdir()
    (release / "bin/data/categories.db").write_bytes(b"private")
    with pytest.raises(RuntimeError, match="运行数据"):
        assert_clean_release(release)
