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


def test_hotkey_actions_and_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("POOL_AIM_CONFIG", str(tmp_path / "c.json"))
    from pool_aim.app import Overlay

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = Overlay(animate=False)
    w.resize(1200, 800)
    a, b = w.p1.x(), w.p2.x()
    w.swap_balls()
    assert (w.p1.x(), w.p2.x()) == (b, a)
    w.set_flag("ghost", False)
    w.cycle_theme()
    w.toggle_help()
    w.toggle_lock()
    w.grab()
    w.save_config()
    w.set_flag("ghost", True)
    w.load_config()
    assert w.flags["ghost"] is False
    w.reset_all()
    assert w.locked is True


def test_cli_args():
    from pool_aim.app import parse_args

    assert parse_args(["--no-animation"]).no_animation is True
    assert parse_args([]).fullscreen is False
