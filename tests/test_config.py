import json
import os

from pool_aim import config


def test_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    cfg = {
        "p1": [1, 2],
        "toggles": {"lines": False},
        "visuals": {"thickness": 5, "opacity": 0.5},
        "color": [1, 2, 3, 255],
        "last_target": "p1",
        "table_rect": [0, 0, 500, 300],
    }
    config.save(cfg, p)
    out = config.load(p)
    assert out["p1"] == (1.0, 2.0) and out["toggles"] == {"lines": False} and out["last_target"] == "p1"
    if os.name == "posix":
        assert (p.stat().st_mode & 0o777) == 0o600


def test_rejects_garbage(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "p1": ["a", 1],
                "visuals": {"thickness": 9999, "opacity": -4},
                "color": [999, -1, "x"],
                "table_rect": [0, 0, 1, 1],
                "last_target": "evil",
                "toggles": {"lines": "yes"},
            }
        )
    )
    out = config.load(p)
    assert "p1" not in out and "color" not in out and "last_target" not in out
    assert out["visuals"] == {"thickness": 10, "opacity": 0.3}
    assert out["table_rect"][2:] == (120.0, 80.0)
    assert out["toggles"] == {}


def test_nan_inf_and_bool_rejected(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"p1": [NaN, 1], "p2": [Infinity, 2], "marker": [true, 1]}')
    assert config.load(p) == {}


def test_bad_inputs_return_empty(tmp_path):
    p = tmp_path / "c.json"
    assert config.load(p) == {}
    p.write_text("{not json")
    assert config.load(p) == {}
    p.write_text("[" * 100000)
    assert config.load(p) == {}
    p.write_text(" " * (config.MAX_CONFIG_BYTES + 1))
    assert config.load(p) == {}


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("POOL_AIM_CONFIG", str(tmp_path / "x.json"))
    assert config.default_config_path() == tmp_path / "x.json"


def test_new_toggles_roundtrip(tmp_path):
    from pool_aim import config

    p = tmp_path / "c.json"
    config.save({"toggles": {"ghost": False, "hud": True, "animate": False, "snap": True, "evil": True}}, p)
    out = config.load(p)
    assert out["toggles"] == {"ghost": False, "hud": True, "animate": False, "snap": True}
