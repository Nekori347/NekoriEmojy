"""Real-file tests default to the project's disposable DevData directory."""
import os
import tempfile
from pathlib import Path

DEV_DATA = Path(__file__).resolve().parents[2] / 'DevData'
DEV_DATA.mkdir(exist_ok=True)
tempfile.tempdir = str(DEV_DATA)
os.environ['TEMP'] = os.environ['TMP'] = str(DEV_DATA)
os.environ['NEKORI_APP_DATA'] = str(DEV_DATA / 'pytest-app')
os.environ['NEKORI_LIBRARY'] = str(DEV_DATA / 'pytest-library')


def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = str(DEV_DATA / 'pytest')
