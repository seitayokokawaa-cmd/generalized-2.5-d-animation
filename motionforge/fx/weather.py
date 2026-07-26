"""Weather particle fields: rain, snow, fog. Seeded, tiled, deterministic."""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from ..core.rng import MFRandom
from ..draw.canvas import Shape, Stroke, path_ellipse, path_line, path_rect


class WeatherField:
    def __init__(self, base: Tuple[str, float], changes: List[tuple],
                 rng: MFRandom, scene_key: str):
        # changes: [(t, kind, intensity, over)]
        self.base = base
        self.changes = sorted(changes)
        r = rng.stream(f"weather:{scene_key}")
        n = 320
        self.px = [float(v) for v in r.uniform(0, 1, n)]
        self.py = [float(v) for v in r.uniform(0, 1, n)]
        self.pj = [float(v) for v in r.uniform(0.6, 1.4, n)]
        self.ps = [float(v) for v in r.uniform(0, 6.28, n)]

    def state_at(self, t: float) -> Tuple[str, float]:
        kind, inten = self.base
        for (ct, k, i, over) in self.changes:
            if t < ct:
                break
            u = 1.0 if over <= 0 else min((t - ct) / over, 1.0)
            if u >= 1.0 or k == kind:
                kind, inten = k, inten + (i - inten) * u
            else:
                # fade the old out then the new in
                if u < 0.5:
                    inten = inten * (1.0 - u * 2)
                else:
                    kind, inten = k, i * ((u - 0.5) * 2)
        return kind, inten

    def shapes(self, t: float, cam_x: float, zoom: float,
               width: int, height: int) -> List[Shape]:
        kind, intensity = self.state_at(t)
        if kind in ("none", "") or intensity <= 0.01:
            return []
        out: List[Shape] = []
        n = int(len(self.px) * min(intensity, 1.0))
        margin = 60
        W = width + margin * 2
        if kind == "rain":
            speed = height * 1.9
            slant = height * 0.18
            for i in range(n):
                j = self.pj[i]
                x = (self.px[i] * W + t * slant * 0.6 - cam_x * 55.0) % W - margin
                y = (self.py[i] * height + t * speed * j) % height
                ln = height * 0.035 * j
                out.append(Shape(path=path_line([(x, y), (x - slant * 0.06 * ln / 10,
                                                          y - ln)]),
                                 stroke=Stroke(paint=(0.75, 0.85, 0.95, 0.4),
                                               width=1.3)))
            # ground splash haze
            out.append(Shape(path=path_rect(0, height * 0.96, width, height * 0.04),
                             fill=(0.75, 0.85, 0.95, 0.08 * intensity)))
        elif kind == "snow":
            speed = height * 0.16
            for i in range(n):
                j = self.pj[i]
                sway = math.sin(t * 1.1 + self.ps[i]) * 26.0 * j
                x = (self.px[i] * W + sway - cam_x * 40.0) % W - margin
                y = (self.py[i] * height + t * speed * j) % height
                r = 1.6 + 2.2 * (j - 0.6)
                out.append(Shape(path=path_ellipse(x, y, r, r),
                                 fill=(1.0, 1.0, 1.0, 0.85)))
        elif kind == "fog":
            for band in range(4):
                yb = height * (0.55 + band * 0.13)
                drift = (t * (8 + band * 5) - cam_x * 30.0) % (width * 2) - width * 0.5
                a = 0.10 + 0.05 * band
                out.append(Shape(
                    path=path_ellipse(drift, yb, width * 0.8, height * 0.08),
                    fill=(0.92, 0.94, 0.96, a * intensity)))
            out.append(Shape(path=path_rect(0, height * 0.45, width, height * 0.55),
                             fill=(0.9, 0.92, 0.95, 0.16 * intensity)))
        return out
