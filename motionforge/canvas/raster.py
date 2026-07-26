"""Supersampled raster canvas on Pillow.

Everything is drawn at `ss`× resolution and downsampled with Lanczos, which
gives clean anti-aliased vector edges deterministically. The draw context is
created in "RGBA" blend mode so translucent fills composite correctly.

Coordinates given to Canvas methods are in FINAL output pixels; the
supersampling factor is applied internally.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from motionforge.core.color import RGBA

Pt = tuple[float, float]


class Canvas:
    def __init__(self, width: int, height: int, ss: int = 3):
        self.width = int(width)
        self.height = int(height)
        self.ss = max(1, int(ss))
        self._im = Image.new("RGB", (self.width * self.ss, self.height * self.ss), (0, 0, 0))
        self._draw = ImageDraw.Draw(self._im, "RGBA")

    # -- scaling helpers ---------------------------------------------------

    def _s(self, v: float) -> float:
        return v * self.ss

    def _spts(self, pts: list[Pt]) -> list[Pt]:
        s = self.ss
        return [(x * s, y * s) for x, y in pts]

    # -- painting ----------------------------------------------------------

    def fill(self, color: RGBA) -> None:
        self._draw.rectangle(
            (0, 0, self.width * self.ss, self.height * self.ss), fill=color
        )

    def vgradient(self, y0: float, y1: float, c0: RGBA, c1: RGBA,
                  x0: float | None = None, x1: float | None = None, bands: int = 96) -> None:
        """Vertical linear gradient from c0 at y0 to c1 at y1."""
        gx0 = 0.0 if x0 is None else x0
        gx1 = float(self.width) if x1 is None else x1
        if y1 <= y0:
            return
        for i in range(bands):
            t0 = i / bands
            t1 = (i + 1) / bands
            col = (
                int(c0[0] + (c1[0] - c0[0]) * t0),
                int(c0[1] + (c1[1] - c0[1]) * t0),
                int(c0[2] + (c1[2] - c0[2]) * t0),
                int(c0[3] + (c1[3] - c0[3]) * t0),
            )
            self._draw.rectangle(
                (self._s(gx0), self._s(y0 + (y1 - y0) * t0),
                 self._s(gx1), self._s(y0 + (y1 - y0) * t1) + 1),
                fill=col,
            )

    def polygon(self, pts: list[Pt], fill: RGBA | None = None,
                outline: RGBA | None = None, outline_width: float = 0.0) -> None:
        if len(pts) < 3:
            return
        spts = self._spts(pts)
        if fill is not None and fill[3] > 0:
            self._draw.polygon(spts, fill=fill)
        if outline is not None and outline_width > 0:
            self._draw.line(spts + [spts[0]], fill=outline,
                            width=max(1, round(self._s(outline_width))), joint="curve")

    def polyline(self, pts: list[Pt], color: RGBA, width: float = 1.0) -> None:
        if len(pts) < 2:
            return
        self._draw.line(self._spts(pts), fill=color,
                        width=max(1, round(self._s(width))), joint="curve")

    def line(self, x0: float, y0: float, x1: float, y1: float, color: RGBA,
             width: float = 1.0) -> None:
        self._draw.line(
            [(self._s(x0), self._s(y0)), (self._s(x1), self._s(y1))],
            fill=color, width=max(1, round(self._s(width))),
        )

    def circle(self, cx: float, cy: float, r: float, fill: RGBA | None = None,
               outline: RGBA | None = None, outline_width: float = 0.0) -> None:
        if r <= 0:
            return
        bbox = (self._s(cx - r), self._s(cy - r), self._s(cx + r), self._s(cy + r))
        ow = max(1, round(self._s(outline_width))) if outline is not None and outline_width > 0 else 0
        self._draw.ellipse(bbox, fill=fill, outline=outline, width=ow)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float,
                fill: RGBA | None = None, outline: RGBA | None = None,
                outline_width: float = 0.0) -> None:
        if rx <= 0 or ry <= 0:
            return
        bbox = (self._s(cx - rx), self._s(cy - ry), self._s(cx + rx), self._s(cy + ry))
        ow = max(1, round(self._s(outline_width))) if outline is not None and outline_width > 0 else 0
        self._draw.ellipse(bbox, fill=fill, outline=outline, width=ow)

    def pieslice(self, cx: float, cy: float, r: float, a0_deg: float, a1_deg: float,
                 fill: RGBA) -> None:
        bbox = (self._s(cx - r), self._s(cy - r), self._s(cx + r), self._s(cy + r))
        self._draw.pieslice(bbox, a0_deg, a1_deg, fill=fill)

    def blur_region_overlay(self, color: RGBA) -> None:
        """Full-frame translucent wash (fog, night tint, flash)."""
        if color[3] <= 0:
            return
        self._draw.rectangle((0, 0, self._im.width, self._im.height), fill=color)

    def vignette(self, strength: float = 0.25) -> None:
        """Darken frame corners; applied at finish-resolution for speed."""
        self._vignette = strength

    _vignette: float = 0.0

    # -- text (delegates to textdraw for shaping/fonts) --------------------

    def text(self, x: float, y: float, s: str, **kw) -> tuple[float, float]:
        from motionforge.canvas.textdraw import draw_text

        return draw_text(self._draw, self.ss, x, y, s, **kw)

    def measure_text(self, s: str, **kw) -> tuple[float, float]:
        from motionforge.canvas.textdraw import measure_text

        return measure_text(self._draw, self.ss, s, **kw)

    # -- output ------------------------------------------------------------

    def finish_image(self) -> Image.Image:
        im = self._im
        if self.ss != 1:
            im = im.resize((self.width, self.height), Image.LANCZOS)
        if self._vignette > 0.0:
            im = _apply_vignette(im, self._vignette)
        return im

    def finish_rgb24(self) -> bytes:
        return self.finish_image().tobytes()

    def finish_array(self) -> np.ndarray:
        return np.asarray(self.finish_image(), dtype=np.uint8)


_VIGNETTE_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _apply_vignette(im: Image.Image, strength: float) -> Image.Image:
    key = (im.width, im.height)
    mask = _VIGNETTE_CACHE.get(key)
    if mask is None:
        yy, xx = np.mgrid[0:im.height, 0:im.width]
        nx = (xx / im.width - 0.5) * 2.0
        ny = (yy / im.height - 0.5) * 2.0
        d = np.sqrt(nx * nx + ny * ny)
        mask = np.clip((d - 0.68) / 0.75, 0.0, 1.0) ** 2
        _VIGNETTE_CACHE[key] = mask
    arr = np.asarray(im, dtype=np.float32)
    arr *= (1.0 - strength * mask)[..., None]
    return Image.fromarray(arr.astype(np.uint8), "RGB")
