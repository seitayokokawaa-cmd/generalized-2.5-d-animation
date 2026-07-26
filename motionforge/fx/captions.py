"""Captions: titles, subtitles, lower thirds — any script, with fades."""
from __future__ import annotations

from typing import List, Optional, Tuple

from ..core import color as colors
from ..core.vec import clamp
from ..draw.canvas import Shape, path_rect, path_round_rect
from ..draw.text import text_shapes, wrap_text
from ..dsl.ir import Caption

# style: (rel_size, pos, color, bg, bold, align)
STYLES = {
    "title":       {"size": 64, "pos": (0.5, 0.40), "color": "#ffffff", "bg": "none",
                    "bold": True, "shadow": True},
    "subtitle":    {"size": 30, "pos": (0.5, 0.90), "color": "#ffffff", "bg": "#000000a0",
                    "bold": False, "shadow": False},
    "lower_third": {"size": 26, "pos": (0.02, 0.88), "color": "#ffffff", "bg": "#1a2740d0",
                    "bold": False, "shadow": False, "align": "left"},
    "caption":     {"size": 30, "pos": (0.5, 0.82), "color": "#ffffff", "bg": "#00000080",
                    "bold": False, "shadow": False},
}


def caption_alpha(c: Caption, t: float) -> float:
    from ..core.coerce import fnum
    fade = fnum(c.params.get("fade", 0.25), 0.25, lo=0.0)
    if t < c.t or t > c.until:
        return 0.0
    a = 1.0
    if fade > 0:
        a = min(a, (t - c.t) / fade, (c.until - t) / fade)
    return clamp(a, 0.0, 1.0)


def _safe_color(spec, palette, fallback: str):
    try:
        return colors.parse(spec, palette)
    except ValueError:
        return colors.parse(fallback)


def render_caption(c: Caption, t: float, width: int, height: int,
                   palette: Optional[dict] = None) -> List[Shape]:
    from ..core.coerce import fnum, fvec2
    alpha = caption_alpha(c, t)
    if alpha <= 0.0:
        return []
    style = dict(STYLES.get(c.style, STYLES["caption"]))
    scale = height / 720.0
    size = fnum(c.params.get("size", style["size"]), float(style["size"]),
                lo=4.0, hi=400.0) * scale
    color = _safe_color(c.params.get("color", style["color"]), palette,
                        style["color"])
    bg_spec = c.params.get("bg", style["bg"])
    bg = None if str(bg_spec) in ("none", "") else \
        _safe_color(bg_spec, palette, "#00000080")
    bold = bool(style.get("bold", False))
    align = style.get("align", "center")

    pos = c.params.get("pos", style["pos"])
    if isinstance(pos, str):
        pos = {"top": (0.5, 0.12), "center": (0.5, 0.45), "bottom": (0.5, 0.9)}.get(pos, (0.5, 0.85))
    pos = fvec2(pos, tuple(style["pos"]))
    px, py = pos[0] * width, pos[1] * height

    max_w = width * 0.86
    lines = wrap_text(c.text, size, max_w, bold=bold)
    line_h = max(l.line_height for l in lines) * 1.12
    total_h = line_h * len(lines)
    block_w = max(l.width for l in lines)

    out: List[Shape] = []
    pad = size * 0.45
    if bg is not None:
        bx = px - (block_w / 2 if align == "center" else 0) - pad
        by = py - lines[0].ascent - pad * 0.6
        out.append(Shape(
            path=path_round_rect(bx, by, block_w + pad * 2,
                                 total_h + pad * 1.2, size * 0.3),
            fill=bg, alpha=alpha))
    y = py
    for line in lines:
        x = px - (line.width / 2 if align == "center" else 0)
        if style.get("shadow"):
            sh = (0.0, 0.0, 0.0, 0.55)
            out.extend(text_shapes(line, (x + size * 0.045, y + size * 0.045), sh, alpha))
        out.extend(text_shapes(line, (x, y), color, alpha))
        y += line_h
    return out


def render_captions(captions: List[Caption], t: float, width: int, height: int,
                    palette: Optional[dict] = None) -> List[Shape]:
    out: List[Shape] = []
    for c in captions:
        out.extend(render_caption(c, t, width, height, palette))
    return out
