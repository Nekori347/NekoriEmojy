"""Run unmodified upstream tests in an empty-data copy with a virtual clipboard."""
import os
from pathlib import Path
import sys
from unittest.mock import patch

work = Path(os.environ["P0_WORK_DIR"]).resolve()
source = work / "p0-tests-source"
os.chdir(source)
sys.path.insert(0, str(source))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

import pytest
import requests

# The original about-page tests spawn an avatar downloader. External avatar
# availability is not their subject; fail that optional request immediately so
# teardown cannot destroy a still-running QThread. No product code is changed.
with patch("requests.sessions.Session.request",
           side_effect=requests.ConnectionError("P0: external network disabled")):
    status = pytest.main(["-q", "tests", "--basetemp=" + str(work / "p0-pytest-tmp-1"),
                          "--junitxml=" + str(work / "p0-pytest.xml")])
sys.exit(status)
