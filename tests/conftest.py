import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """One QApplication kept alive for the whole session (Qt aborts if it is garbage collected)."""
    widgets = pytest.importorskip("PyQt5.QtWidgets")
    app = widgets.QApplication.instance() or widgets.QApplication([])
    yield app
