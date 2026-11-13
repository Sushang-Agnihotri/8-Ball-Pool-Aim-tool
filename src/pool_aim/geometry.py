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


def unit(a: Point, b: Point) -> Point:
    """Unit vector pointing from ``a`` to ``b`` (``(0, 0)`` if they coincide)."""
    d = dist(a, b)
    return (0.0, 0.0) if d < 1e-9 else ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def ghost_ball(obj: Point, pocket: Point, ball_radius: float) -> Point:
    """Where the cue ball must be at impact to send ``obj`` towards ``pocket``.

    It sits exactly two ball radii behind the object ball, on the line from the pocket through the object ball.
    """
    ux, uy = unit(obj, pocket)
    return (obj[0] - ux * 2 * ball_radius, obj[1] - uy * 2 * ball_radius)


def angle_between(a: Point, b: Point) -> float:
    """Unsigned angle in degrees (0-180) between two vectors."""
    na, nb = math.hypot(*a), math.hypot(*b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    cos = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / (na * nb)))
    return math.degrees(math.acos(cos))


def cut_angle(cue: Point, obj: Point, pocket: Point) -> float:
    """Cut angle in degrees: 0 is a straight-in shot, 90 is an (impossible) full-thickness miss."""
    return angle_between((obj[0] - cue[0], obj[1] - cue[1]), (pocket[0] - obj[0], pocket[1] - obj[1]))


def best_pocket(
    cue: Point, obj: Point, rect: Rect, ball_radius: float, max_cut: float = 80.0
) -> tuple[int, float] | None:
    """Pick the pocket with the easiest (smallest) cut angle for the object ball.

    Returns ``(pocket_index, cut_angle_degrees)`` or ``None`` when no pocket is makeable. Pockets the object ball is
    already sitting in, and pockets that would need the cue ball behind the ghost position, are skipped.
    """
    best: tuple[int, float] | None = None
    for i, pocket in enumerate(pocket_centers(rect)):
        if dist(obj, pocket) <= 2 * ball_radius:
            continue
        angle = cut_angle(cue, obj, pocket)
        if angle > max_cut:
            continue
        if best is None or angle < best[1]:
            best = (i, angle)
    return best


def path_length(segments: Sequence[tuple[Point, Point]]) -> float:
    return sum(dist(a, b) for a, b in segments)


def difficulty(angle: float, length: float, table_width: float) -> str:
    """Rough shot difficulty label from cut angle and travel distance (relative to table width)."""
    score = angle / 90 * 0.7 + min(length / max(table_width, 1.0), 1.5) / 1.5 * 0.3
    if score < 0.22:
        return "Easy"
    if score < 0.45:
        return "Medium"
    if score < 0.7:
        return "Hard"
    return "Very hard"
