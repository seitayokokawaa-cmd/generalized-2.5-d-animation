"""Color parsing, palettes, and blending.

Screenplays may name colors any of these ways:
  - hex: "#f00", "#ff0000", "#ff0000cc" (with alpha)
  - named: "firebrick", "sky blue", "dark_slate_gray" (CSS names; spaces and
    underscores both fine)
  - list: [255, 0, 0] or [255, 0, 0, 200]
  - a name defined in the screenplay's own `palette:` section
Internally every color is an (r, g, b, a) tuple of ints 0..255.
"""
from __future__ import annotations

from motionforge.core.mathutil import clamp01, lerp

RGBA = tuple[int, int, int, int]

# CSS3 extended color keywords (the full standard set).
_NAMED = {
    "aliceblue": "#f0f8ff", "antiquewhite": "#faebd7", "aqua": "#00ffff",
    "aquamarine": "#7fffd4", "azure": "#f0ffff", "beige": "#f5f5dc",
    "bisque": "#ffe4c4", "black": "#000000", "blanchedalmond": "#ffebcd",
    "blue": "#0000ff", "blueviolet": "#8a2be2", "brown": "#a52a2a",
    "burlywood": "#deb887", "cadetblue": "#5f9ea0", "chartreuse": "#7fff00",
    "chocolate": "#d2691e", "coral": "#ff7f50", "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc", "crimson": "#dc143c", "cyan": "#00ffff",
    "darkblue": "#00008b", "darkcyan": "#008b8b", "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9", "darkgreen": "#006400", "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b", "darkmagenta": "#8b008b", "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00", "darkorchid": "#9932cc", "darkred": "#8b0000",
    "darksalmon": "#e9967a", "darkseagreen": "#8fbc8f", "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f", "darkslategrey": "#2f4f4f", "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3", "deeppink": "#ff1493", "deepskyblue": "#00bfff",
    "dimgray": "#696969", "dimgrey": "#696969", "dodgerblue": "#1e90ff",
    "firebrick": "#b22222", "floralwhite": "#fffaf0", "forestgreen": "#228b22",
    "fuchsia": "#ff00ff", "gainsboro": "#dcdcdc", "ghostwhite": "#f8f8ff",
    "gold": "#ffd700", "goldenrod": "#daa520", "gray": "#808080",
    "green": "#008000", "greenyellow": "#adff2f", "grey": "#808080",
    "honeydew": "#f0fff0", "hotpink": "#ff69b4", "indianred": "#cd5c5c",
    "indigo": "#4b0082", "ivory": "#fffff0", "khaki": "#f0e68c",
    "lavender": "#e6e6fa", "lavenderblush": "#fff0f5", "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd", "lightblue": "#add8e6", "lightcoral": "#f08080",
    "lightcyan": "#e0ffff", "lightgoldenrodyellow": "#fafad2", "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90", "lightgrey": "#d3d3d3", "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a", "lightseagreen": "#20b2aa", "lightskyblue": "#87cefa",
    "lightslategray": "#778899", "lightslategrey": "#778899", "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0", "lime": "#00ff00", "limegreen": "#32cd32",
    "linen": "#faf0e6", "magenta": "#ff00ff", "maroon": "#800000",
    "mediumaquamarine": "#66cdaa", "mediumblue": "#0000cd", "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db", "mediumseagreen": "#3cb371", "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a", "mediumturquoise": "#48d1cc", "mediumvioletred": "#c71585",
    "midnightblue": "#191970", "mintcream": "#f5fffa", "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5", "navajowhite": "#ffdead", "navy": "#000080",
    "oldlace": "#fdf5e6", "olive": "#808000", "olivedrab": "#6b8e23",
    "orange": "#ffa500", "orangered": "#ff4500", "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa", "palegreen": "#98fb98", "paleturquoise": "#afeeee",
    "palevioletred": "#db7093", "papayawhip": "#ffefd5", "peachpuff": "#ffdab9",
    "peru": "#cd853f", "pink": "#ffc0cb", "plum": "#dda0dd",
    "powderblue": "#b0e0e6", "purple": "#800080", "rebeccapurple": "#663399",
    "red": "#ff0000", "rosybrown": "#bc8f8f", "royalblue": "#4169e1",
    "saddlebrown": "#8b4513", "salmon": "#fa8072", "sandybrown": "#f4a460",
    "seagreen": "#2e8b57", "seashell": "#fff5ee", "sienna": "#a0522d",
    "silver": "#c0c0c0", "skyblue": "#87ceeb", "slateblue": "#6a5acd",
    "slategray": "#708090", "slategrey": "#708090", "snow": "#fffafa",
    "springgreen": "#00ff7f", "steelblue": "#4682b4", "tan": "#d2b48c",
    "teal": "#008080", "thistle": "#d8bfd8", "tomato": "#ff6347",
    "turquoise": "#40e0d0", "violet": "#ee82ee", "wheat": "#f5deb3",
    "white": "#ffffff", "whitesmoke": "#f5f5f5", "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
    # Friendly extras that show up constantly in screenplays.
    "cream": "#fff5e1", "sand": "#e8d6a0", "wood": "#9c6b3c", "brick": "#b5533c",
    "stone": "#a8a196", "grass": "#5aa02c", "leaf": "#3f8f29", "sky": "#87ceeb",
    "night": "#101a33", "sunset": "#ff9e5e", "water": "#3d85c6", "clay": "#c96f4a",
}


class ColorError(ValueError):
    """Raised when a color specification cannot be understood."""


def _norm_name(name: str) -> str:
    return name.strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def parse_color(spec, palette: dict[str, RGBA] | None = None, default_alpha: int = 255) -> RGBA:
    """Parse any supported color spec to (r, g, b, a)."""
    if spec is None:
        raise ColorError("no color given")
    if isinstance(spec, tuple) and len(spec) == 4:
        return spec  # already parsed
    if isinstance(spec, (list, tuple)):
        if len(spec) == 3:
            r, g, b = spec
            return (int(r) & 255, int(g) & 255, int(b) & 255, default_alpha)
        if len(spec) == 4:
            r, g, b, a = spec
            return (int(r) & 255, int(g) & 255, int(b) & 255, int(a) & 255)
        raise ColorError(f"a color list needs 3 or 4 numbers, got {len(spec)}: {spec!r}")
    if not isinstance(spec, str):
        raise ColorError(f"cannot understand color {spec!r}")
    s = spec.strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) == 6:
            h += f"{default_alpha:02x}"
        if len(h) != 8:
            raise ColorError(f"hex color must be #rgb, #rrggbb or #rrggbbaa, got {spec!r}")
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
        except ValueError:
            raise ColorError(f"invalid hex color {spec!r}") from None
    key = _norm_name(s)
    if palette and key in palette:
        return palette[key]
    if key in _NAMED:
        return parse_color(_NAMED[key], default_alpha=default_alpha)
    suggestions = [n for n in _NAMED if key[:3] and n.startswith(key[:3])][:5]
    hint = f" Did you mean one of: {', '.join(suggestions)}?" if suggestions else ""
    raise ColorError(f"unknown color name {spec!r}.{hint}")


def build_palette(raw: dict | None) -> dict[str, RGBA]:
    """Resolve a screenplay `palette:` section into normalized names."""
    palette: dict[str, RGBA] = {}
    for name, spec in (raw or {}).items():
        palette[_norm_name(str(name))] = parse_color(spec, palette)
    return palette


def mix(a: RGBA, b: RGBA, t: float) -> RGBA:
    t = clamp01(t)
    return (
        int(lerp(a[0], b[0], t) + 0.5),
        int(lerp(a[1], b[1], t) + 0.5),
        int(lerp(a[2], b[2], t) + 0.5),
        int(lerp(a[3], b[3], t) + 0.5),
    )


def lighten(c: RGBA, amount: float) -> RGBA:
    return mix(c, (255, 255, 255, c[3]), amount)


def darken(c: RGBA, amount: float) -> RGBA:
    return mix(c, (0, 0, 0, c[3]), amount)


def with_alpha(c: RGBA, alpha: float) -> RGBA:
    return (c[0], c[1], c[2], int(clamp01(alpha) * 255 + 0.5))


def scale_alpha(c: RGBA, factor: float) -> RGBA:
    return (c[0], c[1], c[2], int(clamp01(c[3] / 255.0 * factor) * 255 + 0.5))


def luminance(c: RGBA) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0
