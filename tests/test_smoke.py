import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PyQt5.QtWidgets")


def test_overlay_starts_and_paints(monkeypatch, tmp_path):
    monkeypatch.setenv("POOL_AIM_CONFIG", str(tmp_path / "c.json"))
    from pool_aim.app import Overlay

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = Overlay()
    w.resize(1200, 800)
    w.show()
    w.grab()
    w.save_config()
    w.load_config()
    assert app is not None
