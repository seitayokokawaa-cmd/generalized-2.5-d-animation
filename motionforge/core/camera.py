"""The 2.5D camera: world → screen projection with true depth parallax.

World space: x to the right and y **up**, in meters; the ground is y = 0.
Every entity also has a depth `z`:

    z < 0    in front of the action (foreground props sliding past fast)
    z = 0    the action plane, where characters live by default
    z > 0    behind the action, receding toward the horizon

Projection uses a real perspective factor  pf = focal / (focal + z),
so distant things are both smaller and pan more slowly than near things —
genuine parallax, not a faked layer offset. The horizon is exactly where
pf → 0 converges on screen.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from motionforge.core.mathutil import clamp, fbm_1d

FOCAL = 9.0          # metres from lens to the z=0 action plane
MIN_Z = -0.97 * FOCAL  # anything nearer would blow up the projection


@dataclass
class Camera:
    """Camera state at one instant of film time."""

    x: float = 0.0            # world x the lens looks at
    y: float = 1.5            # world y the lens looks at (metres above ground)
    zoom: float = 1.0         # 1.0 = default framing
    shake: float = 0.0        # 0..1 shake intensity
    width: int = 1280         # output pixels
    height: int = 720
    base_ppm: float = 96.0    # pixels per metre at zoom 1, depth 0, 720p
    _shake_t: float = field(default=0.0, repr=False)

    def scale_at(self, z: float = 0.0) -> float:
        """Pixels per world metre for content at depth z."""
        pf = FOCAL / (FOCAL + max(z, MIN_Z))
        return self.base_ppm * (self.height / 720.0) * self.zoom * pf

    def project(self, wx: float, wy: float, z: float = 0.0) -> tuple[float, float, float]:
        """World point → (screen_x, screen_y, pixels_per_metre_at_that_depth)."""
        z = max(z, MIN_Z)
        pf = FOCAL / (FOCAL + z)
        s = self.base_ppm * (self.height / 720.0) * self.zoom
        sx = self.width * 0.5 + (wx - self.x) * pf * s + self._shake_dx()
        sy = self.height * 0.5 - (wy - self.y) * pf * s + self._shake_dy()
        return sx, sy, s * pf

    def unproject(self, sx: float, sy: float, z: float = 0.0) -> tuple[float, float]:
        """Screen point → world point at the given depth (for layout/tests)."""
        z = max(z, MIN_Z)
        pf = FOCAL / (FOCAL + z)
        s = self.base_ppm * (self.height / 720.0) * self.zoom * pf
        wx = (sx - self._shake_dx() - self.width * 0.5) / s + self.x
        wy = self.y - (sy - self._shake_dy() - self.height * 0.5) / s
        return wx, wy

    def visible_world_rect(self, z: float = 0.0, margin_m: float = 0.0) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) of the world slice visible at depth z."""
        x0, y1 = self.unproject(0.0, 0.0, z)
        x1, y0 = self.unproject(self.width, self.height, z)
        return x0 - margin_m, y0 - margin_m, x1 + margin_m, y1 + margin_m

    def set_shake_time(self, t: float) -> None:
        self._shake_t = t

    def _shake_dx(self) -> float:
        if self.shake <= 0.0:
            return 0.0
        amp = self.shake * 14.0 * (self.height / 720.0)
        return (fbm_1d(self._shake_t * 13.0, 2, "shake_x") - 0.5) * 2.0 * amp

    def _shake_dy(self) -> float:
        if self.shake <= 0.0:
            return 0.0
        amp = self.shake * 10.0 * (self.height / 720.0)
        return (fbm_1d(self._shake_t * 15.0, 2, "shake_y") - 0.5) * 2.0 * amp

    def horizon_screen_y(self) -> float:
        """Screen y of the infinite-distance horizon.

        The limit of H/2 - (wy - cam.y)·pf·s as pf → 0 is exactly H/2 for
        any finite world height, so every depth layer converges there.
        """
        return self.height * 0.5 + self._shake_dy()

    def ground_screen_y(self, z: float = 0.0) -> float:
        """Screen y where the ground line (world y=0) sits at depth z."""
        return self.project(self.x, 0.0, z)[1]


def parallax_factor(z: float) -> float:
    """How fast content at depth z pans relative to the action plane."""
    return FOCAL / (FOCAL + max(z, MIN_Z))


def depth_word_to_z(word) -> float:
    """Screenplay depth words → numeric z. Numbers pass straight through."""
    if isinstance(word, (int, float)):
        return clamp(float(word), MIN_Z * 0.98, 400.0)
    table = {
        "foreground": -4.0, "near": -2.0, "action": 0.0, "mid": 4.0,
        "midground": 4.0, "far": 12.0, "distant": 30.0, "horizon": 90.0,
        "sky": 200.0,
    }
    key = str(word).strip().lower()
    if key not in table:
        raise ValueError(
            f"unknown depth {word!r}. Use a number (metres behind the action; "
            f"negative = in front) or one of: {', '.join(table)}"
        )
    return table[key]


def smooth_zoom_blend(z0: float, z1: float, t: float) -> float:
    """Blend zooms multiplicatively so a 2x→4x zoom feels linear to the eye."""
    return math.exp((1.0 - t) * math.log(max(z0, 1e-6)) + t * math.log(max(z1, 1e-6)))
