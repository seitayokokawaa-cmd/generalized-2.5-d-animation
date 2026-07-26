"""Backend-agnostic drawing model.

A frame is a flat, ordered list of Shape ops. Paths are lists of segments:

    ("M", x, y)                    move to
    ("L", x, y)                    line to
    ("C", x1, y1, x2, y2, x, y)    cubic bezier to
    ("A", cx, cy, r, a0, a1)       circular arc (radians, CCW if a1 > a0)
    ("Z",)                         close

Coordinates are local; each Shape carries the full device transform.
Paints are solid RGBA tuples or Gradient objects (in local coordinates).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from ..core.color import RGBA
from ..core.transform import IDENTITY, Mat

Seg = tuple


@dataclass
class Gradient:
    kind: str                       # 'linear' | 'radial'
    stops: List[Tuple[float, RGBA]]
    p0: Tuple[float, float] = (0.0, 0.0)
    p1: Tuple[float, float] = (0.0, 1.0)
    r0: float = 0.0
    r1: float = 1.0

Paint = object  # RGBA tuple | Gradient


@dataclass
class Stroke:
    paint: Paint
    width: float = 0.02
    cap: str = "round"              # butt | round | square
    join: str = "round"             # miter | round | bevel
    dash: Optional[Sequence[float]] = None


@dataclass
class Shape:
    path: List[Seg]
    fill: Optional[Paint] = None
    stroke: Optional[Stroke] = None
    transform: Mat = IDENTITY
    alpha: float = 1.0


# ---------------------------------------------------------------- path makers

def path_rect(x: float, y: float, w: float, h: float) -> List[Seg]:
    return [("M", x, y), ("L", x + w, y), ("L", x + w, y + h), ("L", x, y + h), ("Z",)]


def path_round_rect(x: float, y: float, w: float, h: float, r: float) -> List[Seg]:
    r = min(r, w / 2, h / 2)
    k = r * 0.5523  # bezier circle constant * r
    return [
        ("M", x + r, y),
        ("L", x + w - r, y),
        ("C", x + w - r + k, y, x + w, y + r - k, x + w, y + r),
        ("L", x + w, y + h - r),
        ("C", x + w, y + h - r + k, x + w - r + k, y + h, x + w - r, y + h),
        ("L", x + r, y + h),
        ("C", x + r - k, y + h, x, y + h - r + k, x, y + h - r),
        ("L", x, y + r),
        ("C", x, y + r - k, x + r - k, y, x + r, y),
        ("Z",),
    ]


def path_circle(cx: float, cy: float, r: float) -> List[Seg]:
    return [("M", cx + r, cy), ("A", cx, cy, r, 0.0, 2 * math.pi), ("Z",)]


def path_ellipse(cx: float, cy: float, rx: float, ry: float) -> List[Seg]:
    k = 0.5523
    return [
        ("M", cx + rx, cy),
        ("C", cx + rx, cy + ry * k, cx + rx * k, cy + ry, cx, cy + ry),
        ("C", cx - rx * k, cy + ry, cx - rx, cy + ry * k, cx - rx, cy),
        ("C", cx - rx, cy - ry * k, cx - rx * k, cy - ry, cx, cy - ry),
        ("C", cx + rx * k, cy - ry, cx + rx, cy - ry * k, cx + rx, cy),
        ("Z",),
    ]


def path_polygon(points: Sequence[Tuple[float, float]]) -> List[Seg]:
    if not points:
        return []
    segs: List[Seg] = [("M", points[0][0], points[0][1])]
    segs += [("L", p[0], p[1]) for p in points[1:]]
    segs.append(("Z",))
    return segs


def path_capsule(x0: float, y0: float, x1: float, y1: float, r: float) -> List[Seg]:
    """A line from (x0,y0) to (x1,y1) thickened with radius r, round ends."""
    dx, dy = x1 - x0, y1 - y0
    ang = math.atan2(dy, dx)
    a90 = ang + math.pi / 2
    px, py = math.cos(a90) * r, math.sin(a90) * r
    return [
        ("M", x0 + px, y0 + py),
        ("A", x0, y0, r, a90, a90 + math.pi),
        ("L", x1 - px, y1 - py),
        ("A", x1, y1, r, a90 + math.pi, a90 + 2 * math.pi),
        ("Z",),
    ]


def path_taper(x0: float, y0: float, x1: float, y1: float,
               r0: float, r1: float) -> List[Seg]:
    """Capsule with different end radii (limbs that taper toward the tip)."""
    dx, dy = x1 - x0, y1 - y0
    ang = math.atan2(dy, dx)
    a90 = ang + math.pi / 2
    p0x, p0y = math.cos(a90) * r0, math.sin(a90) * r0
    p1x, p1y = math.cos(a90) * r1, math.sin(a90) * r1
    return [
        ("M", x0 + p0x, y0 + p0y),
        ("A", x0, y0, r0, a90, a90 + math.pi),
        ("L", x1 - p1x, y1 - p1y),
        ("A", x1, y1, r1, a90 + math.pi, a90 + 2 * math.pi),
        ("Z",),
    ]


def path_line(points: Sequence[Tuple[float, float]], close: bool = False) -> List[Seg]:
    if not points:
        return []
    segs: List[Seg] = [("M", points[0][0], points[0][1])]
    segs += [("L", p[0], p[1]) for p in points[1:]]
    if close:
        segs.append(("Z",))
    return segs
