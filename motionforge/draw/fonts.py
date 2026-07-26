"""Font discovery and script-aware resolution.

Finds installed fonts, checks actual glyph coverage of the text to draw, and
picks the best available face. Override/extend with MOTIONFORGE_FONT_DIR
(searched first). Deterministic: same system fonts -> same choice.
"""
from __future__ import annotations

import os
import unicodedata
from functools import lru_cache
from typing import List, Optional, Tuple

import freetype

FONT_DIRS = [
    os.environ.get("MOTIONFORGE_FONT_DIR", ""),
    os.path.join(os.path.dirname(__file__), "..", "data", "fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "C:\\Windows\\Fonts",
]

# Preference order (substring match on filename, case-insensitive).
PREFERENCE = [
    "notosans", "noto-sans", "notoserif",
    "freesans", "freeserif",
    "dejavusans", "dejavu-sans",
    "liberationsans",
    "wqy", "unifont",
]


@lru_cache(maxsize=1)
def installed_fonts() -> List[str]:
    out: List[str] = []
    for d in FONT_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for f in sorted(files):
                if f.lower().endswith((".ttf", ".otf", ".ttc")):
                    out.append(os.path.join(root, f))
    def rank(path: str) -> Tuple[int, str]:
        name = os.path.basename(path).lower()
        for i, pref in enumerate(PREFERENCE):
            if pref in name:
                return (i, name)
        return (len(PREFERENCE), name)
    out.sort(key=rank)
    return out


@lru_cache(maxsize=64)
def _face(path: str) -> Optional[freetype.Face]:
    try:
        return freetype.Face(path)
    except Exception:
        return None


def _significant_chars(text: str) -> List[str]:
    sig = []
    for ch in text:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("C"):  # control/format marks
            continue
        sig.append(ch)
    return sig


def coverage(path: str, text: str) -> float:
    face = _face(path)
    if face is None:
        return 0.0
    chars = _significant_chars(text)
    if not chars:
        return 1.0
    hit = sum(1 for ch in chars if face.get_char_index(ch) != 0)
    return hit / len(chars)


@lru_cache(maxsize=256)
def resolve(text: str, bold: bool = False) -> str:
    """Best font file for this text. Raises RuntimeError if no font covers it."""
    fonts = installed_fonts()
    if not fonts:
        raise RuntimeError(
            "no fonts found — install system fonts or set MOTIONFORGE_FONT_DIR")
    best, best_cov = None, -1.0
    want = "bold" if bold else ""
    # two passes: exact weight preference first, then any
    for pass_ in (0, 1):
        for path in fonts:
            name = os.path.basename(path).lower()
            is_bold = "bold" in name
            if pass_ == 0 and (is_bold != bool(want)):
                continue
            if "italic" in name or "oblique" in name:
                continue
            cov = coverage(path, text)
            if cov > best_cov + 1e-9:
                best, best_cov = path, cov
            if cov >= 0.999:
                return path
        if best is not None and best_cov >= 0.999:
            return best
    if best is None or best_cov <= 0.0:
        raise RuntimeError(
            f"no installed font has glyphs for this text: {text[:40]!r} — "
            "set MOTIONFORGE_FONT_DIR to a directory containing a suitable font "
            "(e.g. a Noto font for this script)")
    return best
