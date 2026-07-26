"""Frame rendering: World at time t -> pixels."""
from __future__ import annotations

from ..draw.cairo_backend import Raster
from ..dsl.ir import Production
from ..scene.world import World


def render_frame(world: World, t_abs: float) -> Raster:
    r = Raster(world.width, world.height)
    r.clear((0, 0, 0, 1))
    r.draw(world.frame_shapes(t_abs))
    return r


def render_frame_png(production: Production, t_abs: float, out_path: str) -> None:
    world = World(production)
    r = render_frame(world, t_abs)
    r.to_png(out_path)
