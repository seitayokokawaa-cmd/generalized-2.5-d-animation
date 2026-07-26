"""Skies: gradients, sun/moon/stars, drifting clouds, smooth day-night blends."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from ..core import color as colors
from ..core.color import RGBA
from ..core.rng import MFRandom
from ..draw.canvas import (Gradient, Shape, path_circle, path_ellipse,
                           path_rect)

# kind -> (top, bottom, sun 0..1 height | None, moon, star_alpha)
SKIES: Dict[str, tuple] = {
    "day":   ("#6cbcec", "#cdeafa", 0.80, False, 0.0),
    "dawn":  ("#f7a95c", "#fde8d0", 0.22, False, 0.0),
    "dusk":  ("#8e56b8", "#f2a06e", 0.15, False, 0.15),
    "night": ("#0d1330", "#28356b", None, True, 1.0),
    "storm": ("#3d4a59", "#77869a", None, False, 0.0),
}


def sky_params(kind: str, palette: Optional[dict] = None) -> tuple:
    if kind in SKIES:
        top, bottom, sun, moon, stars = SKIES[kind]
        return (colors.parse(top), colors.parse(bottom), sun, moon, stars)
    try:
        c = colors.parse(kind, palette)
        return (c, colors.lighten(c, 0.18), None, False, 0.0)
    except ValueError:
        top, bottom, sun, moon, stars = SKIES["day"]
        return (colors.parse(top), colors.parse(bottom), sun, moon, stars)


def blend_sky(a: tuple, b: tuple, u: float) -> tuple:
    return (colors.mix(a[0], b[0], u), colors.mix(a[1], b[1], u),
            (a[2] if u < 0.5 else b[2]),
            (a[3] if u < 0.5 else b[3]),
            a[4] + (b[4] - a[4]) * u)


class SkyDome:
    """Per-scene sky with seeded stars/clouds and world-verb transitions."""

    def __init__(self, base_kind: str, changes: List[tuple], rng: MFRandom,
                 scene_key: str, palette: Optional[dict] = None):
        # changes: [(t, kind, over)]
        self.base = base_kind
        self.changes = sorted(changes)
        self.palette = palette
        star_rng = rng.stream(f"stars:{scene_key}")
        self.stars = [(float(star_rng.uniform(0, 1)), float(star_rng.uniform(0, 1)),
                       float(star_rng.uniform(0.4, 1.0)))
                      for _ in range(90)]
        cloud_rng = rng.stream(f"clouds:{scene_key}")
        self.clouds = [(float(cloud_rng.uniform(0, 1)), float(cloud_rng.uniform(0.05, 0.55)),
                        float(cloud_rng.uniform(0.5, 1.4)), float(cloud_rng.uniform(6, 16)))
                       for _ in range(int(cloud_rng.integers(2, 5)))]

    def params_at(self, t: float) -> tuple:
        cur = sky_params(self.base, self.palette)
        for (ct, kind, over) in self.changes:
            if t < ct:
                break
            target = sky_params(kind, self.palette)
            u = 1.0 if over <= 0 else min((t - ct) / over, 1.0)
            cur = blend_sky(cur, target, u)
        return cur

    def shapes(self, t: float, cam_x: float, width: int, height: int,
               horizon: float) -> List[Shape]:
        top, bottom, sun_h, moon, star_a = self.params_at(t)
        hy = max(horizon, 1)
        out: List[Shape] = [Shape(path=path_rect(0, 0, width, hy + 2),
                                  fill=Gradient(kind="linear",
                                                stops=[(0.0, top), (1.0, bottom)],
                                                p0=(0, 0), p1=(0, hy)))]
        # stars
        if star_a > 0.01:
            for i, (sx, sy, tw) in enumerate(self.stars):
                twinkle = 0.55 + 0.45 * math.sin(t * 1.7 + i * 2.3)
                a = star_a * tw * twinkle
                out.append(Shape(path=path_circle(sx * width,
                                                  sy * hy * 0.95,
                                                  1.1 + tw),
                                 fill=(1.0, 1.0, 0.94, a * 0.9)))
        # sun / moon
        if sun_h is not None:
            sy = hy * (1.0 - sun_h)
            sx = width * 0.72 - cam_x * 2.0
            r = height * 0.055
            out.append(Shape(path=path_circle(sx, sy, r * 2.6),
                             fill=Gradient(kind="radial",
                                           stops=[(0.0, (1.0, 0.95, 0.75, 0.55)),
                                                  (1.0, (1.0, 0.95, 0.75, 0.0))],
                                           p0=(sx, sy), p1=(sx, sy), r1=r * 2.6)))
            out.append(Shape(path=path_circle(sx, sy, r),
                             fill=(1.0, 0.96, 0.82, 1.0)))
        if moon:
            mx = width * 0.74 - cam_x * 2.0
            my = hy * 0.28
            r = height * 0.05
            out.append(Shape(path=path_circle(mx, my, r), fill=(0.94, 0.95, 0.90, 1.0)))
            out.append(Shape(path=path_circle(mx + r * 0.42, my - r * 0.18, r * 0.88),
                             fill=colors.mix((0.94, 0.95, 0.90, 1.0),
                                             (0.08, 0.10, 0.22, 1.0), 0.92)))
        # drifting clouds (slight parallax against the camera)
        cloud_c = colors.mix((1.0, 1.0, 1.0, 0.92), top, 0.18)
        for (cx0, cy, scale, speed) in self.clouds:
            cx = ((cx0 * (width + 400) + t * speed - cam_x * 6.0)
                  % (width + 400)) - 200
            cyp = cy * hy
            s = scale * height * 0.05
            for dx, dy, rr in ((-1.2, 0.1, 0.75), (0.0, -0.15, 1.0), (1.15, 0.12, 0.7),
                               (0.45, 0.32, 0.6), (-0.5, 0.3, 0.62)):
                out.append(Shape(path=path_ellipse(cx + dx * s * 1.4, cyp + dy * s,
                                                   rr * s * 1.5, rr * s),
                                 fill=cloud_c))
        return out
