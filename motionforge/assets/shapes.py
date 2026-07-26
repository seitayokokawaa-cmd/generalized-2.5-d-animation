"""Shape primitives: declarative params -> path segments.

Every shape is centered/anchored sensibly for building objects that sit on
the ground: y grows upward, and shapes with a natural base (trapezoid,
triangle, rect by default) anchor their base at y=0 unless `at` moves them.

Registry SHAPES maps name -> (builder, param_doc) and feeds the spec generator.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Sequence, Tuple

from ..draw.canvas import (Seg, path_capsule, path_circle, path_ellipse,
                           path_line, path_polygon, path_rect,
                           path_round_rect)


def _get(params: dict, key: str, default=None, *aliases):
    for k in (key, *aliases):
        if k in params:
            return params[k]
    if default is None:
        raise ValueError(f"shape needs '{key}'")
    return default


def s_rect(p: dict) -> List[Seg]:
    w, h = float(_get(p, "w", None, "width")), float(_get(p, "h", None, "height"))
    r = float(p.get("round", 0.0))
    if r > 0:
        return path_round_rect(-w / 2, 0.0, w, h, r)
    return path_rect(-w / 2, 0.0, w, h)


def s_square(p: dict) -> List[Seg]:
    s = float(_get(p, "size", None, "s", "w"))
    return path_rect(-s / 2, 0.0, s, s)


def s_circle(p: dict) -> List[Seg]:
    r = float(_get(p, "r", None, "radius"))
    return path_circle(0.0, float(p.get("cy", r)), r)


def s_ellipse(p: dict) -> List[Seg]:
    rx, ry = float(_get(p, "rx")), float(_get(p, "ry"))
    return path_ellipse(0.0, float(p.get("cy", ry)), rx, ry)


def s_capsule(p: dict) -> List[Seg]:
    w = float(_get(p, "w", None, "width"))
    h = float(_get(p, "h", None, "height", "length"))
    r = w / 2
    return path_capsule(0.0, r, 0.0, h - r, r)


def s_polygon(p: dict) -> List[Seg]:
    pts = _get(p, "points")
    return path_polygon([(float(a), float(b)) for a, b in pts])


def s_triangle(p: dict) -> List[Seg]:
    w, h = float(_get(p, "w")), float(_get(p, "h"))
    return path_polygon([(-w / 2, 0.0), (w / 2, 0.0), (0.0, h)])


def s_trapezoid(p: dict) -> List[Seg]:
    w1 = float(_get(p, "w1"))   # base width
    w2 = float(_get(p, "w2"))   # top width
    h = float(_get(p, "h"))
    return path_polygon([(-w1 / 2, 0.0), (w1 / 2, 0.0), (w2 / 2, h), (-w2 / 2, h)])


def s_star(p: dict) -> List[Seg]:
    n = int(p.get("points_n", 5))
    r1 = float(_get(p, "r", None, "radius"))
    r2 = float(p.get("inner", r1 * 0.45))
    cy = float(p.get("cy", r1))
    pts = []
    for i in range(n * 2):
        r = r1 if i % 2 == 0 else r2
        a = math.pi / 2 + i * math.pi / n
        pts.append((math.cos(a) * r, cy + math.sin(a) * r))
    return path_polygon(pts)


def s_arc(p: dict) -> List[Seg]:
    """Filled pie/arc segment. a0/a1 in degrees, CCW from +X."""
    r = float(_get(p, "r"))
    a0 = math.radians(float(p.get("a0", 0.0)))
    a1 = math.radians(float(p.get("a1", 180.0)))
    cy = float(p.get("cy", 0.0))
    return [("M", 0.0, cy), ("A", 0.0, cy, r, a0, a1), ("Z",)]


def s_ring(p: dict) -> List[Seg]:
    """Annulus (donut) via two opposite-wound circles."""
    r = float(_get(p, "r"))
    thickness = float(p.get("thickness", r * 0.25))
    cy = float(p.get("cy", r))
    ri = max(r - thickness, 0.01)
    return [
        ("M", r, cy), ("A", 0.0, cy, r, 0.0, 2 * math.pi), ("Z",),
        ("M", ri, cy), ("A", 0.0, cy, ri, 2 * math.pi, 0.0), ("Z",),
    ]


def s_gear(p: dict) -> List[Seg]:
    r = float(_get(p, "r"))
    teeth = int(p.get("teeth", 8))
    depth = float(p.get("depth", r * 0.22))
    cy = float(p.get("cy", 0.0))
    pts = []
    steps = teeth * 4
    for i in range(steps):
        a = i / steps * 2 * math.pi
        rr = r if (i % 4) in (0, 1) else r - depth
        pts.append((math.cos(a) * rr, cy + math.sin(a) * rr))
    return path_polygon(pts)


def s_blob(p: dict) -> List[Seg]:
    """Smooth closed curve through the given points (catmull-rom -> bezier)."""
    pts = [(float(a), float(b)) for a, b in _get(p, "points")]
    n = len(pts)
    if n < 3:
        return path_polygon(pts)
    segs: List[Seg] = [("M", pts[0][0], pts[0][1])]
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        segs.append(("C", c1[0], c1[1], c2[0], c2[1], p2[0], p2[1]))
    segs.append(("Z",))
    return segs


def s_crescent(p: dict) -> List[Seg]:
    r = float(_get(p, "r"))
    inset = float(p.get("inset", r * 0.35))
    cy = float(p.get("cy", 0.0))
    return [
        ("M", 0.0, cy + r), ("A", 0.0, cy, r, math.pi / 2, 3 * math.pi / 2), ("Z",),
        ("M", 0.0 + inset, cy + r * 0.92),
        ("A", inset, cy, r * 0.92, 3 * math.pi / 2, math.pi / 2), ("Z",),
    ]


def s_path(p: dict) -> List[Seg]:
    """Raw path: list of [op, ...] where op is M/L/C/A/Z (same as canvas segs)."""
    raw = _get(p, "d", None, "segments")
    return [tuple([seg[0]] + [float(x) for x in seg[1:]]) for seg in raw]


def s_line(p: dict) -> List[Seg]:
    pts = [(float(a), float(b)) for a, b in _get(p, "points")]
    return path_line(pts, close=bool(p.get("close", False)))


SHAPES: Dict[str, Tuple[Callable[[dict], List[Seg]], str]] = {
    "rect":      (s_rect, "w, h, round?: rectangle, base centered at y=0"),
    "square":    (s_square, "size: square, base centered at y=0"),
    "circle":    (s_circle, "r, cy?=r: circle; by default sits on y=0"),
    "ellipse":   (s_ellipse, "rx, ry, cy?=ry: ellipse; by default sits on y=0"),
    "capsule":   (s_capsule, "w, h: vertical rounded bar from y=0 to y=h"),
    "polygon":   (s_polygon, "points: [[x,y],...] closed polygon"),
    "triangle":  (s_triangle, "w, h: isoceles triangle pointing up, base at y=0"),
    "trapezoid": (s_trapezoid, "w1 (base), w2 (top), h: symmetric trapezoid"),
    "star":      (s_star, "r, inner?, points_n?=5: star; sits on y=0"),
    "arc":       (s_arc, "r, a0?, a1? (degrees): filled pie slice at origin"),
    "ring":      (s_ring, "r, thickness?: annulus; sits on y=0"),
    "gear":      (s_gear, "r, teeth?=8, depth?: gear wheel centered at origin"),
    "blob":      (s_blob, "points: smooth organic closed curve through points"),
    "crescent":  (s_crescent, "r, inset?: crescent moon centered at origin"),
    "path":      (s_path, "d: raw [op,...] segments (M/L/C/A/Z) for anything else"),
    "line":      (s_line, "points, close?: open/closed polyline (stroke it)"),
}
