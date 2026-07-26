"""Storyboard: a grid of frames sampled across the film."""
from __future__ import annotations

import cairocffi as cairo

from ..dsl.ir import Production
from ..scene.world import World
from .frames import render_frame


def render_storyboard(production: Production, out_path: str,
                      columns: int = 4, count: int = 12) -> int:
    world = World(production)
    dur = production.duration
    count = max(2, count)
    columns = max(1, columns)
    times = [dur * (i + 0.5) / count for i in range(count)]
    thumb_w = 320
    thumb_h = int(thumb_w * world.height / world.width)
    rows = (count + columns - 1) // columns
    pad = 6
    W = columns * (thumb_w + pad) + pad
    H = rows * (thumb_h + pad + 16) + pad
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(out)
    ctx.set_source_rgb(0.12, 0.12, 0.14)
    ctx.paint()
    for i, t in enumerate(times):
        r = render_frame(world, t)
        col, row = i % columns, i // columns
        x = pad + col * (thumb_w + pad)
        y = pad + row * (thumb_h + pad + 16)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(thumb_w / world.width, thumb_h / world.height)
        ctx.set_source_surface(r.surface, 0, 0)
        ctx.paint()
        ctx.restore()
        ctx.set_source_rgb(0.8, 0.8, 0.82)
        ctx.select_font_face("sans-serif")
        ctx.set_font_size(11)
        ctx.move_to(x + 2, y + thumb_h + 12)
        ctx.show_text(f"t={t:.2f}s")
    out.write_to_png(out_path)
    return count
