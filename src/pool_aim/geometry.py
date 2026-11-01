"""Pure geometry helpers (no Qt) so the maths can be unit-tested."""

from __future__ import annotations

import math
from collections.abc import Sequence

Point = tuple[float, float]
# (left, top, right, bottom)
Rect = tuple[float, float, float, float]

_EPS = 1e-3


def dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def pocket_centers(rect: Rect) -> list[Point]:
    left, top, right, bottom = rect
    mid = (left + right) / 2
    return [(left, top), (mid, top), (right, top), (left, bottom), (mid, bottom), (right, bottom)]


def nearest_pocket(pt: Point, rect: Rect) -> tuple[Point, float]:
    """Return the closest pocket centre and its distance from ``pt``."""
    best = min(pocket_centers(rect), key=lambda c: dist(pt, c))
    return best, dist(pt, best)


def clamp_to_rect(pt: Point, rect: Rect) -> Point:
    left, top, right, bottom = rect
    return (min(max(pt[0], left), right), min(max(pt[1], top), bottom))


def bank_segments(start: Point, direction: Point, rect: Rect, max_banks: int = 2) -> list[tuple[Point, Point]]:
    """Trace a ray from ``start`` bouncing off the rails of ``rect``.

    ``direction`` need not be normalised but must be finite and non-zero.
    Returns one ``(from, to)`` segment per rail hit.
    """
    vx, vy = direction
    if not (math.isfinite(vx) and math.isfinite(vy)) or (vx == 0 and vy == 0):
        return []
    left, top, right, bottom = rect
    cx, cy = start
    segments: list[tuple[Point, Point]] = []
    for _ in range(max(0, max_banks)):
        candidates: list[tuple[float, str]] = []
        if vx > 0:
            candidates.append(((right - cx) / vx, "x"))
        elif vx < 0:
            candidates.append(((left - cx) / vx, "x"))
        if vy > 0:
            candidates.append(((bottom - cy) / vy, "y"))
        elif vy < 0:
            candidates.append(((top - cy) / vy, "y"))
        valid = [c for c in candidates if c[0] > _EPS]
        if not valid:
            break
        t, axis = min(valid, key=lambda c: c[0])
        hit = (cx + vx * t, cy + vy * t)
        segments.append(((cx, cy), hit))
        if axis == "x":
            vx = -vx
        else:
            vy = -vy
        cx, cy = hit
    return segments


def points_finite(points: Sequence[Sequence[float]]) -> bool:
    return all(math.isfinite(v) for p in points for v in p)
