"""Camera: keyed pan/zoom (+ follow mode) and the 2.5D parallax projection.

Projection model
----------------
World: meters, Y up, ground at y=0. Every entity sits on a depth plane z >= 0
(z can be slightly negative for foreground). Reference distance D = 10 m.

    k(z)    = D / (D + z)          perspective factor: 1 at z=0, ->0 far away
    screen  = center + (world - cam) * k * zoom * ppm     (y flipped)

Far planes therefore both shrink *and* pan slower than near ones — true
parallax from a single affine transform per plane. The horizon (z -> inf)
sits exactly at the screen anchor line.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from ..core.transform import Mat, chain, scaling, translation
from ..dsl.ir import CameraSpec, Direction, Scene
from ..motion.tracks import Track

DEPTH_REF = 10.0          # perspective reference distance (m)
VISIBLE_HEIGHT = 7.2      # meters of world visible vertically at zoom 1, z=0
HORIZON_FRAC = 0.42       # screen fraction (from top) where the horizon sits
DEFAULT_CAM_Y = 1.0


@dataclass
class CamState:
    x: float = 0.0
    y: float = DEFAULT_CAM_Y
    zoom: float = 1.0


def perspective(z: float) -> float:
    z = max(z, -DEPTH_REF * 0.9)
    return DEPTH_REF / (DEPTH_REF + z)


def view_matrix(cam: CamState, depth: float, width: int, height: int) -> Mat:
    k = perspective(depth)
    ppm = height / VISIBLE_HEIGHT
    s = cam.zoom * ppm * k
    # anchor: the camera position projects to (w/2, horizon line)
    return chain(
        translation(width / 2.0, height * HORIZON_FRAC),
        scaling(s, -s),
        translation(-cam.x, -cam.y),
    )


def horizon_y(cam: CamState, height: int) -> float:
    """Screen y of the infinite-distance horizon (independent of camera pan)."""
    return height * HORIZON_FRAC


def ground_screen_y(cam: CamState, depth: float, width: int, height: int) -> float:
    """Screen y of the ground line (world y=0) at a given depth plane."""
    from ..core.transform import apply
    return apply(view_matrix(cam, depth, width, height), (cam.x, 0.0))[1]


class CameraTrack:
    """Compiled camera movement for one scene."""

    def __init__(self, spec: CameraSpec, directions: list[Direction],
                 duration: float):
        self.follow: Optional[dict] = spec.follow
        self.x = Track(0.0)
        self.y = Track(DEFAULT_CAM_Y)
        self.zoom = Track(1.0)
        events: list[tuple[float, dict]] = []
        for k in spec.keys:
            events.append((float(k.get("t", 0.0)), dict(k)))
        for d in directions:
            p = dict(d.params)
            over = float(p.pop("over", 0.0) or 0.0)
            if d.until is not None and over == 0.0:
                over = max(d.until - d.t, 0.0)
            p["__over__"] = over
            events.append((d.t, p))
        events.sort(key=lambda e: e[0])
        for t, k in events:
            ez = str(k.get("ease", "in_out"))
            over = float(k.get("__over__", 0.0))
            t_end = t + over
            for field, track in (("x", self.x), ("y", self.y), ("zoom", self.zoom)):
                if field in k and isinstance(k[field], (int, float)):
                    if over > 0.0:
                        track.hold(t)
                    track.add(t_end, float(k[field]), ez)

    def state(self, t: float,
              follow_pos: Optional[Tuple[float, float]] = None) -> CamState:
        if self.follow is not None and follow_pos is not None:
            off = self.follow.get("offset", [0.0, 1.0])
            zoom = float(self.follow.get("zoom", 1.0))
            return CamState(x=follow_pos[0] + float(off[0]),
                            y=follow_pos[1] + float(off[1]),
                            zoom=zoom)
        return CamState(x=float(self.x.sample(t)),
                        y=float(self.y.sample(t)),
                        zoom=float(self.zoom.sample(t)))


def compile_camera(scene: Scene) -> CameraTrack:
    cam_dirs = [d for d in scene.timeline if d.subject_kind == "camera"]
    return CameraTrack(scene.camera, cam_dirs, scene.duration)
