"""Text -> vector paths: harfbuzz shaping + freetype outlines.

Handles complex scripts (Bengali conjuncts, Arabic joining, CJK) because
shaping is done by HarfBuzz; right-to-left runs come back in visual order.
Glyphs are drawn as filled bezier paths — resolution-independent and
deterministic, no font rasterizer involved.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import freetype
import uharfbuzz as hb

from ..core.transform import Mat, chain, scaling, translation
from .canvas import Seg, Shape
from . import fonts as fontmod


@lru_cache(maxsize=32)
def _hb_font(path: str) -> hb.Font:
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob, 0)
    return hb.Font(face)


@lru_cache(maxsize=32)
def _ft_face(path: str) -> freetype.Face:
    face = freetype.Face(path)
    return face


@lru_cache(maxsize=32)
def _upem(path: str) -> int:
    return _hb_font(path).face.upem or 1000


_glyph_cache: Dict[Tuple[str, int], List[Seg]] = {}


def glyph_path(font_path: str, glyph_id: int) -> List[Seg]:
    """Glyph outline in font units (y up), as canvas path segments."""
    key = (font_path, glyph_id)
    cached = _glyph_cache.get(key)
    if cached is not None:
        return cached
    face = _ft_face(font_path)
    face.load_glyph(glyph_id, freetype.FT_LOAD_NO_SCALE | freetype.FT_LOAD_NO_BITMAP)
    outline = face.glyph.outline
    segs: List[Seg] = []
    start = 0
    points = outline.points
    tags = outline.tags
    for end in outline.contours:
        pts = points[start:end + 1]
        tgs = tags[start:end + 1]
        segs.extend(_contour_to_segs(pts, tgs))
        start = end + 1
    _glyph_cache[key] = segs
    return segs


def _contour_to_segs(pts: List[Tuple[float, float]], tags: List[int]) -> List[Seg]:
    """Convert one TrueType/CFF contour (on/off points) to M/L/C segments."""
    n = len(pts)
    if n == 0:
        return []
    on = [(t & 1) == 1 for t in tags]
    cubic = [(t & 2) == 2 for t in tags]

    # find a starting on-curve point; if none, synthesize midpoint
    starti = next((i for i in range(n) if on[i]), None)
    if starti is None:
        p0 = ((pts[0][0] + pts[1 % n][0]) / 2, (pts[0][1] + pts[1 % n][1]) / 2)
        order = list(range(1, n)) + [0]
        virtual_start = True
    else:
        p0 = pts[starti]
        order = [(starti + k) % n for k in range(1, n)]
        virtual_start = False

    segs: List[Seg] = [("M", p0[0], p0[1])]
    cur = p0
    pending: List[Tuple[float, float]] = []
    pending_cubic = False

    def flush_to(pt: Tuple[float, float]) -> None:
        nonlocal cur, pending, pending_cubic
        if not pending:
            segs.append(("L", pt[0], pt[1]))
        elif pending_cubic and len(pending) == 2:
            segs.append(("C", pending[0][0], pending[0][1],
                         pending[1][0], pending[1][1], pt[0], pt[1]))
        else:
            # quadratic (possibly a chain): convert each to cubic
            q = pending[0]
            c1 = (cur[0] + 2.0 / 3.0 * (q[0] - cur[0]), cur[1] + 2.0 / 3.0 * (q[1] - cur[1]))
            c2 = (pt[0] + 2.0 / 3.0 * (q[0] - pt[0]), pt[1] + 2.0 / 3.0 * (q[1] - pt[1]))
            segs.append(("C", c1[0], c1[1], c2[0], c2[1], pt[0], pt[1]))
        cur = pt
        pending = []
        pending_cubic = False

    for i in order:
        p = pts[i]
        if on[i]:
            flush_to(p)
        else:
            if pending and not cubic[i] and not pending_cubic:
                # two consecutive quadratic off-points: implicit on-point between
                q = pending[0]
                mid = ((q[0] + p[0]) / 2, (q[1] + p[1]) / 2)
                flush_to(mid)
            pending.append(p)
            pending_cubic = pending_cubic or cubic[i]
    # close back to start
    flush_to(p0)
    segs.append(("Z",))
    return segs


class ShapedText:
    """Result of shaping: positioned glyphs + metrics, in pixels."""

    def __init__(self, font_path: str, size: float,
                 glyphs: List[Tuple[int, float, float]], width: float):
        self.font_path = font_path
        self.size = size
        self.glyphs = glyphs          # (glyph_id, x_px, y_px)
        self.width = width
        upem = _upem(font_path)
        face = _ft_face(font_path)
        self.ascent = size * (face.ascender / upem)
        self.descent = size * (-face.descender / upem)
        self.line_height = self.ascent + self.descent


def shape_line(text: str, size: float, font_path: Optional[str] = None,
               bold: bool = False) -> ShapedText:
    if font_path is None:
        font_path = fontmod.resolve(text, bold=bold)
    font = _hb_font(font_path)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True, "calt": True})
    upem = _upem(font_path)
    s = size / upem
    glyphs: List[Tuple[int, float, float]] = []
    x = y = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append((info.codepoint, x + pos.x_offset * s, y + pos.y_offset * s))
        x += pos.x_advance * s
        y += pos.y_advance * s
    return ShapedText(font_path, size, glyphs, width=x)


def wrap_text(text: str, size: float, max_width: float,
              font_path: Optional[str] = None, bold: bool = False) -> List[ShapedText]:
    """Split on newlines, then wrap by words to fit max_width."""
    lines: List[ShapedText] = []
    for raw in text.split("\n"):
        if not raw.strip():
            lines.append(shape_line(" ", size, font_path, bold))
            continue
        words = raw.split(" ")
        cur = ""
        for word in words:
            trial = (cur + " " + word).strip()
            shaped = shape_line(trial, size, font_path, bold)
            if shaped.width > max_width and cur:
                lines.append(shape_line(cur, size, font_path, bold))
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(shape_line(cur, size, font_path, bold))
    return lines


def text_shapes(shaped: ShapedText, origin: Tuple[float, float], fill,
                alpha: float = 1.0, extra: Optional[Mat] = None) -> List[Shape]:
    """Shapes for one shaped line; origin is the baseline start point (screen px)."""
    upem = _upem(shaped.font_path)
    s = shaped.size / upem
    out: List[Shape] = []
    for gid, gx, gy in shaped.glyphs:
        path = glyph_path(shaped.font_path, gid)
        if not path:
            continue
        m = chain(translation(origin[0] + gx, origin[1] - gy), scaling(s, -s))
        if extra is not None:
            m = chain(extra, m)
        out.append(Shape(path=path, fill=fill, transform=m, alpha=alpha))
    return out
