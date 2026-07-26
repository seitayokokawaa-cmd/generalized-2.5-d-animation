"""Frame rendering: World at time t -> pixels, with scene transitions."""
from __future__ import annotations

import math

from ..draw.cairo_backend import Raster
from ..draw.canvas import path_circle, path_rect
from ..dsl.ir import Production
from ..scene.world import World


def render_frame(world: World, t_abs: float) -> Raster:
    r = Raster(world.width, world.height)
    r.clear((0, 0, 0, 1))
    plan = world.frame_plan(t_abs)
    trans = plan.get("transition")
    w, h = world.width, world.height
    if trans is None:
        r.draw(plan["main"])
    else:
        kind, u, prev = trans
        u = min(max(u, 0.0), 1.0)
        eased = u * u * (3 - 2 * u)
        if kind == "fade":
            r.draw(plan["main"])
            if u < 1.0:
                r.draw([_black(w, h, 1.0 - eased)])
        elif kind == "dissolve":
            if prev is not None:
                r.draw(prev)
            r.draw_with_alpha(plan["main"], eased)
        elif kind == "wipe":
            if prev is not None:
                r.draw(prev)
            r.draw_with_alpha(plan["main"], 1.0,
                              clip_path=path_rect(0, 0, w * eased, h))
        elif kind == "iris":
            if prev is not None:
                r.draw(prev)
            radius = eased * math.hypot(w, h) * 0.55
            r.draw_with_alpha(plan["main"], 1.0,
                              clip_path=path_circle(w / 2, h / 2, max(radius, 0.1)))
        else:
            r.draw(plan["main"])
    fade_out = plan.get("fade_out")
    if fade_out:
        r.draw([_black(w, h, min(max(fade_out, 0.0), 1.0))])
    r.draw(plan["ui"])
    return r


def _black(w: int, h: int, alpha: float):
    from ..draw.canvas import Shape
    return Shape(path=path_rect(0, 0, w, h), fill=(0.0, 0.0, 0.0, alpha))


def render_frame_png(production: Production, t_abs: float, out_path: str) -> None:
    world = World(production)
    r = render_frame(world, t_abs)
    r.to_png(out_path)
