"""Fail the build if runtime/user state leaks into a portable release tree."""
from pathlib import Path


def assert_clean_release(root):
    root = Path(root).resolve()
    forbidden = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        lower = tuple(part.lower() for part in relative.parts)
        if (not path.resolve().is_relative_to(root) or path.is_symlink()
                or any(part in {"data", ".git", "__pycache__", ".pytest_cache", ".venv"} for part in lower)
                or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".pyc", ".swp", ".log"}
                or path.name.lower() in {"nekori-library.json", "bootstrap.json", "config.json", "nuitka-crash-report.xml"}):
            forbidden.append(relative.as_posix())
    if forbidden:
        raise RuntimeError("发布目录含运行数据或开发缓存：" + ", ".join(forbidden[:20]))
