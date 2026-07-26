"""2D vector math on plain (x, y) tuples — small, allocation-light, deterministic."""
from __future__ import annotations

import math
from typing import Tuple

Vec = Tuple[float, float]


def v(x: float, y: float) -> Vec:
    return (float(x), float(y))


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1])


def mul(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def length(a: Vec) -> float:
    return math.hypot(a[0], a[1])


def dist(a: Vec, b: Vec) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def normalize(a: Vec) -> Vec:
    n = math.hypot(a[0], a[1])
    if n < 1e-12:
        return (0.0, 0.0)
    return (a[0] / n, a[1] / n)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def vlerp(a: Vec, b: Vec, t: float) -> Vec:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def angle_of(a: Vec) -> float:
    """Angle of vector in degrees, CCW from +X."""
    return math.degrees(math.atan2(a[1], a[0]))


def from_angle(deg: float, mag: float = 1.0) -> Vec:
    r = math.radians(deg)
    return (math.cos(r) * mag, math.sin(r) * mag)


def rotate(a: Vec, deg: float) -> Vec:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (a[0] * c - a[1] * s, a[0] * s + a[1] * c)


def angle_lerp(a: float, b: float, t: float) -> float:
    """Interpolate angles (degrees) along the shortest arc."""
    d = (b - a) % 360.0
    if d > 180.0:
        d -= 360.0
    return a + d * t


def bezier(p0: Vec, p1: Vec, p2: Vec, p3: Vec, t: float) -> Vec:
    """Cubic bezier point."""
    u = 1.0 - t
    a = u * u * u
    b = 3 * u * u * t
    c = 3 * u * t * t
    d = t * t * t
    return (
        a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
        a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
    )
