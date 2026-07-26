"""Multilingual text rendering with genuine font fallback.

Rather than guessing fonts from Unicode ranges, we read each candidate
font's character map (via fontTools) once at startup and pick, per text run,
the first font that actually covers every character. Combined with Pillow's
libraqm shaping (present in this environment), Bengali conjuncts, Arabic
joining/RTL, Devanagari matras, and CJK all render correctly.
"""
from __future__ import annotations

import os
import unicodedata
from functools import lru_cache

from PIL import ImageFont

from motionforge.core.color import RGBA

# Candidate fonts in preference order: (regular, bold) — bold falls back to
# regular when the family has no bold file.
_CANDIDATES: list[tuple[str, str]] = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/freefont/FreeSans.ttf",
     "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    ("/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
     "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
     "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ("/usr/share/fonts/opentype/unifont/unifont_jp.otf",
     "/usr/share/fonts/opentype/unifont/unifont_jp.otf"),
]

_RTL_BLOCKS = (
    (0x0590, 0x08FF),   # Hebrew, Arabic, Syriac, Thaana, ...
    (0xFB1D, 0xFDFF),   # presentation forms
    (0xFE70, 0xFEFF),
)


@lru_cache(maxsize=None)
def _coverage(path: str) -> frozenset[int]:
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(path, fontNumber=0, lazy=True)
        return frozenset(font.getBestCmap().keys())
    except Exception:
        return frozenset()


@lru_cache(maxsize=None)
def _available_candidates() -> list[tuple[str, str]]:
    out = []
    for reg, bold in _CANDIDATES:
        if os.path.exists(reg):
            out.append((reg, bold if os.path.exists(bold) else reg))
    return out


def _significant_chars(s: str) -> list[str]:
    """Characters that must be covered (skip spaces, controls, combining-safe punct)."""
    return [c for c in s if not c.isspace() and unicodedata.category(c) not in ("Cc", "Cf")]


def pick_font_path(s: str, bold: bool = False) -> str:
    cands = _available_candidates()
    if not cands:
        raise RuntimeError(
            "No usable fonts found on this system. Install fonts-dejavu, "
            "fonts-freefont-ttf, or fonts-wqy-zenhei."
        )
    chars = _significant_chars(s)
    if not chars:
        reg, bold_path = cands[0]
        return bold_path if bold else reg
    best_path, best_score = None, -1.0
    for reg, bold_path in cands:
        cov = _coverage(reg)
        if not cov:
            continue
        score = sum(1 for c in chars if ord(c) in cov) / len(chars)
        if score == 1.0:
            return bold_path if bold else reg
        if score > best_score:
            best_score, best_path = score, (bold_path if bold else reg)
    return best_path or (cands[0][1] if bold else cands[0][0])


@lru_cache(maxsize=256)
def _load_font(path: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, px)


def text_direction(s: str) -> str | None:
    """'rtl' if the text is predominantly right-to-left script, else None."""
    rtl = ltr = 0
    for c in s:
        cp = ord(c)
        if any(lo <= cp <= hi for lo, hi in _RTL_BLOCKS):
            rtl += 1
        elif c.isalpha():
            ltr += 1
    return "rtl" if rtl > ltr else None


def _font_kwargs(s: str):
    """Pillow text kwargs for correct shaping when raqm is available."""
    from PIL import features

    if not features.check("raqm"):
        return {}
    kw = {}
    direction = text_direction(s)
    if direction:
        kw["direction"] = direction
    return kw


def measure_text(draw, ss: int, s: str, size: float = 24.0, bold: bool = False,
                 **_ignored) -> tuple[float, float]:
    """(width, height) in final output pixels."""
    px = max(4, round(size * ss))
    font = _load_font(pick_font_path(s, bold), px)
    kw = _font_kwargs(s)
    bbox = draw.textbbox((0, 0), s, font=font, **kw)
    return (bbox[2] - bbox[0]) / ss, (bbox[3] - bbox[1]) / ss


def draw_text(draw, ss: int, x: float, y: float, s: str, size: float = 24.0,
              color: RGBA = (255, 255, 255, 255), bold: bool = False,
              anchor: str = "la", stroke: RGBA | None = None,
              stroke_width: float = 0.0, **_ignored) -> tuple[float, float]:
    """Draw one text run; returns its (width, height) in final pixels.

    anchor follows Pillow's convention ('mm' = centered both ways, 'ma' =
    centered top, 'la' = left top ...).
    """
    if not s:
        return 0.0, 0.0
    px = max(4, round(size * ss))
    font = _load_font(pick_font_path(s, bold), px)
    kw = _font_kwargs(s)
    sw = max(0, round(stroke_width * ss))
    draw.text(
        (x * ss, y * ss), s, font=font, fill=color, anchor=anchor,
        stroke_width=sw, stroke_fill=stroke, **kw,
    )
    bbox = draw.textbbox((x * ss, y * ss), s, font=font, anchor=anchor, **kw)
    return (bbox[2] - bbox[0]) / ss, (bbox[3] - bbox[1]) / ss
