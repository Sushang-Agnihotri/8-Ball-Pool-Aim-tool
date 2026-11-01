"""Safe, validated, atomic settings persistence.

* Stored in a per-user config directory (never the current working directory,
  so a hostile folder cannot feed the app a crafted file).
* Size-limited and type/range validated on load; bad values fall back to defaults.
* Written atomically with owner-only permissions.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

MAX_CONFIG_BYTES = 64 * 1024
MAX_COORD = 20000.0  # generous upper bound for any screen coordinate


def default_config_path() -> Path:
    override = os.environ.get("POOL_AIM_CONFIG")
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "pool-aim" / "config.json"


def _num(v: Any, lo: float, hi: float) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return min(max(float(v), lo), hi)


def _pair(v: Any) -> tuple[float, float] | None:
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        return None
    a, b = _num(v[0], -MAX_COORD, MAX_COORD), _num(v[1], -MAX_COORD, MAX_COORD)
    return None if a is None or b is None else (a, b)


def sanitize(raw: Any) -> dict[str, Any]:
    """Return only valid, in-range settings from untrusted ``raw`` data."""
    out: dict[str, Any] = {}
    if not isinstance(raw, dict):
        return out

    tr = raw.get("table_rect")
    if isinstance(tr, (list, tuple)) and len(tr) == 4:
        vals = [
            _num(tr[0], -MAX_COORD, MAX_COORD),
            _num(tr[1], -MAX_COORD, MAX_COORD),
            _num(tr[2], 120, MAX_COORD),
            _num(tr[3], 80, MAX_COORD),
        ]
        if None not in vals:
            out["table_rect"] = tuple(vals)

    for key in ("p1", "p2", "marker"):
        pair = _pair(raw.get(key))
        if pair:
            out[key] = pair

    if raw.get("last_target") in ("p1", "p2"):
        out["last_target"] = raw["last_target"]

    toggles = raw.get("toggles")
    if isinstance(toggles, dict):
        out["toggles"] = {
            k: toggles[k] for k in ("lines", "single", "bank", "double_bank") if isinstance(toggles.get(k), bool)
        }

    visuals = raw.get("visuals")
    if isinstance(visuals, dict):
        vis: dict[str, float] = {}
        t = _num(visuals.get("thickness"), 1, 10)
        o = _num(visuals.get("opacity"), 0.3, 1.0)
        if t is not None:
            vis["thickness"] = int(t)
        if o is not None:
            vis["opacity"] = o
        out["visuals"] = vis

    col = raw.get("color")
    if isinstance(col, (list, tuple)) and len(col) in (3, 4):
        chan = [_num(c, 0, 255) for c in col]
        if None not in chan:
            out["color"] = [int(c) for c in chan] + ([255] if len(chan) == 3 else [])
    return out


def load(path: Path | None = None) -> dict[str, Any]:
    """Load settings; returns ``{}`` if missing, oversized, corrupt or invalid."""
    path = path or default_config_path()
    try:
        if not path.is_file() or path.stat().st_size > MAX_CONFIG_BYTES:
            return {}
        with path.open("r", encoding="utf-8") as fh:
            return sanitize(json.load(fh))
    except (OSError, ValueError, RecursionError):
        return {}


def save(cfg: dict[str, Any], path: Path | None = None) -> Path:
    """Atomically write ``cfg`` as JSON with 0600 permissions."""
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path
