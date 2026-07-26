"""Mood color grading: a final compositing pass per frame."""
from __future__ import annotations

from typing import List, Optional

from ..draw.canvas import Gradient, Shape, path_rect

# mood -> list of (rgba, operator)
MOODS = {
    "neutral": [],
    "warm":  [((1.0, 0.72, 0.42, 0.16), "multiply"),
              ((1.0, 0.85, 0.6, 0.10), "screen")],
    "cold":  [((0.55, 0.70, 0.95, 0.18), "multiply")],
    "night": [((0.32, 0.38, 0.72, 0.38), "multiply")],
    "dusk":  [((0.85, 0.55, 0.45, 0.22), "multiply")],
    "dream": [((0.95, 0.75, 0.9, 0.16), "screen")],
    "tense": [((0.55, 0.45, 0.45, 0.28), "multiply")],
    "storm": [((0.5, 0.55, 0.62, 0.30), "multiply")],
}


def grade_shapes(mood: str, width: int, height: int,
                 vignette: float = 0.35) -> List[Shape]:
    out: List[Shape] = []
    for color, op in MOODS.get(mood, []):
        out.append(Shape(path=path_rect(0, 0, width, height), fill=color,
                         operator=op))
    if vignette > 0.01:
        cx, cy = width / 2, height / 2
        r = max(width, height) * 0.72
        out.append(Shape(path=path_rect(0, 0, width, height),
                         fill=Gradient(kind="radial",
                                       stops=[(0.0, (0, 0, 0, 0.0)),
                                              (0.75, (0, 0, 0, 0.0)),
                                              (1.0, (0, 0, 0, vignette * 0.5))],
                                       p0=(cx, cy), p1=(cx, cy), r1=r)))
    return out
