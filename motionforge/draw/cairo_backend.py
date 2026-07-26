"""The concrete rasterizer: draw-list -> pixels via cairocffi (CPU, deterministic)."""
from __future__ import annotations

import math
from typing import List, Sequence

import cairocffi as cairo
import numpy as np

from ..core.color import RGBA
from .canvas import Gradient, Shape, Stroke

_CAPS = {"butt": cairo.LINE_CAP_BUTT, "round": cairo.LINE_CAP_ROUND,
         "square": cairo.LINE_CAP_SQUARE}
_JOINS = {"miter": cairo.LINE_JOIN_MITER, "round": cairo.LINE_JOIN_ROUND,
          "bevel": cairo.LINE_JOIN_BEVEL}


class Raster:
    def __init__(self, width: int, height: int):
        self.width = int(width)
        self.height = int(height)
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        self.ctx = cairo.Context(self.surface)

    def clear(self, color: RGBA = (0, 0, 0, 1)) -> None:
        c = self.ctx
        c.save()
        c.set_matrix(cairo.Matrix())
        c.set_operator(cairo.OPERATOR_SOURCE)
        c.set_source_rgba(color[0], color[1], color[2], color[3])
        c.paint()
        c.restore()

    # ------------------------------------------------------------- drawing

    def _build_path(self, path: Sequence[tuple]) -> None:
        c = self.ctx
        c.new_path()
        for seg in path:
            op = seg[0]
            if op == "M":
                c.move_to(seg[1], seg[2])
            elif op == "L":
                c.line_to(seg[1], seg[2])
            elif op == "C":
                c.curve_to(seg[1], seg[2], seg[3], seg[4], seg[5], seg[6])
            elif op == "A":
                _, cx, cy, r, a0, a1 = seg
                if a1 >= a0:
                    c.arc(cx, cy, r, a0, a1)
                else:
                    c.arc_negative(cx, cy, r, a0, a1)
            elif op == "Z":
                c.close_path()

    def _set_paint(self, paint, alpha: float) -> None:
        c = self.ctx
        if isinstance(paint, Gradient):
            if paint.kind == "radial":
                g = cairo.RadialGradient(paint.p0[0], paint.p0[1], paint.r0,
                                         paint.p1[0], paint.p1[1], paint.r1)
            else:
                g = cairo.LinearGradient(paint.p0[0], paint.p0[1],
                                         paint.p1[0], paint.p1[1])
            for off, col in paint.stops:
                g.add_color_stop_rgba(off, col[0], col[1], col[2], col[3] * alpha)
            c.set_source(g)
        else:
            r, g_, b, a = paint
            c.set_source_rgba(r, g_, b, a * alpha)

    def draw(self, shapes: List[Shape]) -> None:
        c = self.ctx
        for s in shapes:
            if s.alpha <= 0.0:
                continue
            m = s.transform
            c.save()
            c.set_matrix(cairo.Matrix(m[0], m[1], m[2], m[3], m[4], m[5]))
            self._build_path(s.path)
            if s.fill is not None:
                self._set_paint(s.fill, s.alpha)
                if s.stroke is not None:
                    c.fill_preserve()
                else:
                    c.fill()
            if s.stroke is not None:
                st: Stroke = s.stroke
                self._set_paint(st.paint, s.alpha)
                c.set_line_width(st.width)
                c.set_line_cap(_CAPS.get(st.cap, cairo.LINE_CAP_ROUND))
                c.set_line_join(_JOINS.get(st.join, cairo.LINE_JOIN_ROUND))
                if st.dash:
                    c.set_dash(list(st.dash))
                c.stroke()
                if st.dash:
                    c.set_dash([])
            c.restore()

    # ------------------------------------------------------------- output

    def to_png(self, path: str) -> None:
        self.surface.flush()
        self.surface.write_to_png(path)

    def png_bytes(self) -> bytes:
        import io
        self.surface.flush()
        buf = io.BytesIO()
        self.surface.write_to_png(buf)
        return buf.getvalue()

    def rgb24(self) -> bytes:
        """Raw RGB24 bytes for piping to ffmpeg (assumes opaque background)."""
        self.surface.flush()
        buf = np.frombuffer(self.surface.get_data(), dtype=np.uint8)
        arr = buf.reshape(self.height, self.surface.get_stride() // 4, 4)
        arr = arr[:, : self.width, :]
        # cairo ARGB32 little-endian memory order is B, G, R, A
        rgb = arr[:, :, [2, 1, 0]]
        return np.ascontiguousarray(rgb).tobytes()
