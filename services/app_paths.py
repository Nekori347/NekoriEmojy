"""Program files, app preferences and user libraries have separate lifetimes."""
import os
from pathlib import Path


def app_data_dir():
    override = os.environ.get("NEKORI_APP_DATA")
    return Path(override).expanduser().resolve() if override else Path(
        os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
    ) / "NekoriEmojy"


def default_library_dir():
    return Path.home() / "Pictures" / "NekoriEmojy Library"


def selected_library(config):
    return Path(os.environ.get("NEKORI_LIBRARY") or config.get("library_path") or
                default_library_dir()).expanduser().resolve()
