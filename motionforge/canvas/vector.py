"""Vector geometry helpers: bezier flattening, capsules, arcs, rounded rects.

All functions return plain point lists (deterministic fixed subdivision, so
the same input always tessellates identically) ready for polygon rasterization.
"""
from __future__ import annotations

import math

Pt = tuple[float, float]

BEZIER_STEPS = 14
ARC_STEPS_PER_RAD = 6.0


def quad_bezier(p0: Pt, p1: Pt, p2: Pt, steps: int = BEZIER_STEPS) -> list[Pt]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        pts.append((
            u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
        ))
    return pts


def cubic_bezier(p0: Pt, p1: Pt, p2: Pt, p3: Pt, steps: int = BEZIER_STEPS) -> list[Pt]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        pts.append((
            u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
        ))
    return pts


class PathBuilder:
    """Tiny SVG-like path: move/line/quad/cubic/arc/close → flat polygon(s)."""

    def __init__(self) -> None:
        self._subpaths: list[list[Pt]] = []
        self._cur: list[Pt] = []

    def move_to(self, x: float, y: float) -> "PathBuilder":
        if self._cur:
            self._subpaths.append(self._cur)
        self._cur = [(x, y)]
        return self

    def line_to(self, x: float, y: float) -> "PathBuilder":
        self._cur.append((x, y))
        return self

    def quad_to(self, cx: float, cy: float, x: float, y: float) -> "PathBuilder":
        if not self._cur:
            self._cur = [(cx, cy)]
        self._cur.extend(quad_bezier(self._cur[-1], (cx, cy), (x, y))[1:])
        return self

    def cubic_to(self, c1x: float, c1y: float, c2x: float, c2y: float, x: float, y: float) -> "PathBuilder":
        if not self._cur:
            self._cur = [(c1x, c1y)]
        self._cur.extend(cubic_bezier(self._cur[-1], (c1x, c1y), (c2x, c2y), (x, y))[1:])
        return self

    def arc_to(self, cx: float, cy: float, r: float, a0: float, a1: float) -> "PathBuilder":
        self._cur.extend(arc_points(cx, cy, r, r, a0, a1))
        return self

    def close(self) -> "PathBuilder":
        if self._cur:
            self._subpaths.append(self._cur)
            self._cur = []
        return self

    def points(self) -> list[Pt]:
        """The first (or only) subpath as a flat point list."""
        subs = self.subpaths()
        return subs[0] if subs else []

    def subpaths(self) -> list[list[Pt]]:
        out = list(self._subpaths)
        if self._cur:
            out.append(self._cur)
        return out


def arc_points(cx: float, cy: float, rx: float, ry: float, a0: float, a1: float,
               steps: int | None = None) -> list[Pt]:
    """Points along an ellipse arc from angle a0 to a1 (radians, y-down screen)."""
    if steps is None:
        steps = max(3, int(abs(a1 - a0) * ARC_STEPS_PER_RAD) + 1)
    pts = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def ellipse_points(cx: float, cy: float, rx: float, ry: float, rotation: float = 0.0,
                   steps: int = 40) -> list[Pt]:
    cr, sr = math.cos(rotation), math.sin(rotation)
    pts = []
    for i in range(steps):
        a = math.tau * i / steps
        x, y = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return pts


def capsule_points(x0: float, y0: float, x1: float, y1: float, r0: float,
                   r1: float | None = None) -> list[Pt]:
    """A round-capped, optionally tapered thick line — the limb primitive."""
    if r1 is None:
        r1 = r0
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)
    if d < 1e-9:
        return ellipse_points(x0, y0, max(r0, r1), max(r0, r1))
    ang = math.atan2(dy, dx)
    a0 = ang + math.pi / 2
    pts = arc_points(x0, y0, r0, r0, a0, a0 + math.pi)
    pts += arc_points(x1, y1, r1, r1, a0 + math.pi, a0 + math.tau)
    return pts


def rounded_rect_points(x0: float, y0: float, x1: float, y1: float, r: float) -> list[Pt]:
    r = min(r, abs(x1 - x0) / 2, abs(y1 - y0) / 2)
    if r <= 0.5:
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    pts: list[Pt] = []
    pts += arc_points(x1 - r, y0 + r, r, r, -math.pi / 2, 0.0)
    pts += arc_points(x1 - r, y1 - r, r, r, 0.0, math.pi / 2)
    pts += arc_points(x0 + r, y1 - r, r, r, math.pi / 2, math.pi)
    pts += arc_points(x0 + r, y0 + r, r, r, math.pi, math.pi * 1.5)
    return pts


def regular_polygon_points(cx: float, cy: float, r: float, sides: int,
                           rotation: float = 0.0) -> list[Pt]:
    return [
        (cx + r * math.cos(rotation + math.tau * i / sides),
         cy + r * math.sin(rotation + math.tau * i / sides))
        for i in range(sides)
    ]


def star_points(cx: float, cy: float, r_outer: float, r_inner: float, points: int = 5,
                rotation: float = -math.pi / 2) -> list[Pt]:
    pts = []
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        a = rotation + math.pi * i / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def smooth_closed(pts: list[Pt], tension: float = 0.5, steps: int = 6) -> list[Pt]:
    """Catmull-Rom smooth a closed polygon — used for organic blobby shapes."""
    n = len(pts)
    if n < 3:
        return list(pts)
    out: list[Pt] = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        for j in range(steps):
            t = j / steps
            t2, t3 = t * t, t * t * t
            out.append((
                tension * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                           + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                           + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                + (1 - tension) * (p1[0] + (p2[0] - p1[0]) * t),
                tension * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                           + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                           + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                + (1 - tension) * (p1[1] + (p2[1] - p1[1]) * t),
            ))
    return out


def polyline_ribbon(pts: list[Pt], half_widths: list[float]) -> list[Pt]:
    """Turn a centerline + per-point half widths into a filled ribbon polygon
    (tapered tails, snakes, tree trunks)."""
    if len(pts) < 2:
        return []
    left: list[Pt] = []
    right: list[Pt] = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        w = half_widths[min(i, len(half_widths) - 1)]
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]
