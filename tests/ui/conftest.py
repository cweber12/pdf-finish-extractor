"""Session-scoped QApplication fixture for UI unit tests."""
from __future__ import annotations

import os
import sys

import pytest

# Must be set before any Qt import so the offscreen platform is used in
# headless / CI environments that have no display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app

