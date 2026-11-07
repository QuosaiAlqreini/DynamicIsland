import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Keep tests away from the real user config
_home = tempfile.mkdtemp(prefix="di-home-")
os.environ["HOME"] = _home
os.environ["USERPROFILE"] = _home


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
