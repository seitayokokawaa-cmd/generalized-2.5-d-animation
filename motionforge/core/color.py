"""Color parsing and manipulation. Colors are (r, g, b, a) floats in 0..1."""
from __future__ import annotations

import colorsys
from typing import Dict, Optional, Tuple

RGBA = Tuple[float, float, float, float]

# A compact set of CSS-style names; palettes in the screenplay extend these.
NAMED: Dict[str, str] = {
    "black": "#000000", "white": "#ffffff", "red": "#d92626", "green": "#2f9e44",
    "blue": "#2b6cd9", "yellow": "#f2c218", "orange": "#e8842c", "purple": "#8447c9",
    "pink": "#e86aa6", "brown": "#8a5a2b", "gray": "#808080", "grey": "#808080",
    "lightgray": "#c8c8c8", "darkgray": "#404040", "cyan": "#27b3bd", "magenta": "#c93bb0",
    "lime": "#8fd433", "navy": "#1d2f66", "teal": "#1f7a72", "maroon": "#7a1f2b",
    "olive": "#6d7a1f", "gold": "#d9a521", "silver": "#b8bcc2", "beige": "#e3d5b8",
    "tan": "#cfa878", "skin": "#e0ac69", "cream": "#f5eeda", "sky": "#87ceeb",
    "grass": "#4a9440", "dirt": "#8b6b47", "sand": "#dbc98f", "stone": "#9a9a94",
    "wood": "#a5793f", "brick": "#b0492f", "snow": "#f4f8fb", "water": "#3d7fb8",
    "night": "#141a33", "transparent": "#00000000", "none": "#00000000",
}


def parse(value, palette: Optional[Dict[str, str]] = None) -> RGBA:
    """Parse '#rgb', '#rrggbb', '#rrggbbaa', a named color, a palette name,
    or an [r,g,b]/[r,g,b,a] list of 0-255 ints. Raises ValueError with a clear message."""
    if isinstance(value, (list, tuple)):
        if len(value) not in (3, 4):
            raise ValueError(f"color list must have 3 or 4 numbers, got {len(value)}")
        vals = [float(c) / 255.0 for c in value]
        if len(vals) == 3:
            vals.append(1.0)
        return tuple(min(1.0, max(0.0, c)) for c in vals)  # type: ignore[return-value]
    if not isinstance(value, str):
        raise ValueError(f"expected a color string or list, got {type(value).__name__}")
    s = value.strip()
    if palette and s in palette:
        s = palette[s]
        if isinstance(s, (list, tuple)):
            return parse(s)
        if not isinstance(s, str):
            raise ValueError(
                f"palette entry '{value}' is {s!r} — palette values must be "
                "color strings like \"#a33b2a\" (quote hex values in YAML)")
    if s in NAMED:
        s = NAMED[s]
    if not s.startswith("#"):
        known = ", ".join(sorted(list(NAMED)[:0]) or [])  # names listed in error below
        raise ValueError(
            f"unknown color '{value}' — use #hex, a palette name, or a built-in name "
            f"such as {', '.join(sorted(NAMED)[:12])}, ..."
        )
    h = s[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    if len(h) != 8:
        raise ValueError(f"bad hex color '{value}' — use #rgb, #rrggbb or #rrggbbaa")
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        a = int(h[6:8], 16) / 255.0
    except ValueError:
        raise ValueError(f"bad hex color '{value}' — contains non-hex digits") from None
    return (r, g, b, a)


def mix(c1: RGBA, c2: RGBA, t: float) -> RGBA:
    return tuple(c1[i] + (c2[i] - c1[i]) * t for i in range(4))  # type: ignore[return-value]


def with_alpha(c: RGBA, a: float) -> RGBA:
    return (c[0], c[1], c[2], a)


def lighten(c: RGBA, amt: float) -> RGBA:
    """amt in -1..1; positive lightens, negative darkens."""
    h, l, s = colorsys.rgb_to_hls(c[0], c[1], c[2])
    l = min(1.0, max(0.0, l + amt))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r, g, b, c[3])


def shift_hue(c: RGBA, deg: float) -> RGBA:
    h, l, s = colorsys.rgb_to_hls(c[0], c[1], c[2])
    r, g, b = colorsys.hls_to_rgb((h + deg / 360.0) % 1.0, l, s)
    return (r, g, b, c[3])


def tint(c: RGBA, tint_color: RGBA, strength: float = 0.5) -> RGBA:
    """Recolor toward tint_color, preserving relative luminance variation."""
    _, l, _ = colorsys.rgb_to_hls(c[0], c[1], c[2])
    th, tl, ts = colorsys.rgb_to_hls(tint_color[0], tint_color[1], tint_color[2])
    nl = tl + (l - 0.5) * 0.6
    nl = min(1.0, max(0.0, nl))
    r, g, b = colorsys.hls_to_rgb(th, nl, ts)
    return mix(c, (r, g, b, c[3]), strength)
