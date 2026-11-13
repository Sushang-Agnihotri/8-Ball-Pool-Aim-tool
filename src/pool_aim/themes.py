"""Colour themes for the overlay lines."""

from __future__ import annotations

THEMES: list[tuple[str, tuple[int, int, int]]] = [
    ("Classic White", (255, 255, 255)),
    ("Neon Green", (57, 255, 20)),
    ("Cyber Cyan", (0, 229, 255)),
    ("Hot Pink", (255, 64, 160)),
    ("Solar Amber", (255, 193, 7)),
    ("Crimson", (255, 82, 82)),
    ("Violet", (179, 136, 255)),
]


def next_theme(rgb: tuple[int, int, int]) -> tuple[str, tuple[int, int, int]]:
    """Return the theme after the one matching ``rgb`` (wraps; unknown colours start at the first theme)."""
    for i, (_, c) in enumerate(THEMES):
        if c == tuple(rgb):
            return THEMES[(i + 1) % len(THEMES)]
    return THEMES[0]
