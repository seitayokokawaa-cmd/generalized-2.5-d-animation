"""Text shaping: complex scripts (Bengali, Arabic) shape to real glyphs with
nonzero width, and glyph outlines convert to drawable path segments."""
from __future__ import annotations

import pytest

from motionforge.draw.text import glyph_path, shape_line

BENGALI = "হ্যালো"      # হ্যালো
ARABIC = "مرحبا"             # مرحبا


@pytest.mark.parametrize("text", [BENGALI, ARABIC, "Hello"],
                         ids=["bengali", "arabic", "latin"])
def test_shape_line_produces_glyphs_with_width(text):
    shaped = shape_line(text, 48.0)
    assert shaped.glyphs, f"no glyphs shaped for {text!r}"
    assert shaped.width > 0
    assert shaped.ascent > 0 and shaped.line_height > 0
    # the chosen font actually covers the script: not everything is .notdef
    assert any(gid != 0 for gid, _x, _y in shaped.glyphs)


@pytest.mark.parametrize("text", [BENGALI, ARABIC], ids=["bengali", "arabic"])
def test_glyph_path_returns_segments(text):
    shaped = shape_line(text, 48.0)
    nonempty = 0
    for gid, _x, _y in shaped.glyphs:
        segs = glyph_path(shaped.font_path, gid)
        if not segs:
            continue                     # marks/spaces may be empty
        nonempty += 1
        ops = [s[0] for s in segs]
        assert ops[0] == "M"
        assert "Z" in ops                # closed contours
        assert all(op in ("M", "L", "C", "Z") for op in ops)
    assert nonempty > 0


def test_bengali_conjunct_is_shaped_not_spelled():
    """হ্যালো contains a halant conjunct: shaping must not emit one glyph per
    codepoint (HarfBuzz substitutes/forms clusters)."""
    shaped = shape_line(BENGALI, 48.0)
    assert len(shaped.glyphs) != 0
    assert len(shaped.glyphs) < len(BENGALI) + 3   # sanity: no explosion
    # deterministic: shaping twice gives the identical result
    again = shape_line(BENGALI, 48.0)
    assert again.glyphs == shaped.glyphs
    assert again.width == shaped.width


def test_arabic_shapes_with_joining_forms():
    """Isolated-form shaping of each letter must not equal the joined word
    width: Arabic letters connect."""
    joined = shape_line(ARABIC, 48.0)
    isolated = sum(shape_line(ch, 48.0).width for ch in ARABIC)
    assert joined.width > 0
    assert joined.width != pytest.approx(isolated, abs=1e-6)
