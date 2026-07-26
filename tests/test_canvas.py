import numpy as np

from motionforge.canvas import Canvas
from motionforge.canvas.vector import (
    PathBuilder,
    capsule_points,
    polyline_ribbon,
    rounded_rect_points,
    smooth_closed,
    star_points,
)


def _scene(c: Canvas) -> None:
    c.fill((20, 30, 60, 255))
    c.vgradient(0, 120, (90, 140, 220, 255), (240, 220, 200, 255))
    c.polygon(star_points(60, 60, 30, 14), fill=(255, 220, 0, 255))
    c.polygon(rounded_rect_points(100, 40, 180, 100, 12), fill=(200, 60, 60, 255),
              outline=(0, 0, 0, 255), outline_width=2)
    c.polygon(capsule_points(30, 150, 120, 170, 10), fill=(120, 220, 120, 200))
    c.circle(200, 150, 20, fill=(255, 255, 255, 120))
    p = PathBuilder().move_to(10, 10).quad_to(60, -20, 110, 10).line_to(60, 40).close()
    c.polygon(p.points(), fill=(250, 120, 180, 255))
    c.text(120, 200, "Hello", size=18, color=(255, 255, 255, 255))


def test_canvas_renders_and_is_deterministic():
    frames = []
    for _ in range(2):
        c = Canvas(240, 240, ss=2)
        _scene(c)
        frames.append(c.finish_array())
    assert frames[0].shape == (240, 240, 3)
    assert np.array_equal(frames[0], frames[1])
    assert frames[0].std() > 10  # actually drew something


def test_multilingual_text_produces_ink():
    for s in ["আমার সোনার বাংলা", "مرحبا بالعالم", "你好世界", "नमस्ते"]:
        c = Canvas(400, 80, ss=2)
        c.fill((0, 0, 0, 255))
        w, h = c.text(200, 40, s, size=28, anchor="mm", color=(255, 255, 255, 255))
        arr = c.finish_array()
        assert arr.max() > 200, f"no ink for {s!r}"
        assert w > 10, f"zero width for {s!r}"


def test_text_measurement_close_to_draw():
    c = Canvas(400, 80, ss=2)
    w, h = c.measure_text("Hello world", size=24)
    assert 60 < w < 300 and 8 < h < 60


def test_ribbon_and_smooth():
    pts = [(0, 0), (10, 5), (20, 0), (30, 8)]
    rib = polyline_ribbon(pts, [3, 3, 2, 1])
    assert len(rib) == 8
    blob = smooth_closed([(0, 0), (10, 0), (10, 10), (0, 10)], steps=4)
    assert len(blob) == 16
