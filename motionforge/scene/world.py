"""The compiled world: turns a Production into per-frame draw lists.

This module is the compositor spine. Entity visuals and motion get richer in
later milestones (assets, characters, gait, physics); the structure here —
compile once, then `frame(t)` as a pure function — is permanent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..core import color as colors
from ..core.rng import MFRandom
from ..core.transform import chain, scaling, translation
from ..draw.canvas import (Gradient, Shape, path_capsule, path_circle,
                           path_rect)
from ..dsl.ir import Placement, Production, Scene
from .camera import (CamState, CameraTrack, compile_camera, ground_screen_y,
                     horizon_y, view_matrix)
from .graph import Node, flatten

SKY_COLORS = {
    "day": ("#7ec8f0", "#cdeafa"),
    "dawn": ("#f7b267", "#fde8d0"),
    "dusk": ("#a45fb8", "#f2b380"),
    "night": ("#0d1330", "#28356b"),
    "storm": ("#4a5766", "#8b98a6"),
}

GROUND_COLORS = {
    "grass": "#4a9440", "dirt": "#8b6b47", "sand": "#dbc98f", "stone": "#9a9a94",
    "snow": "#eef3f8", "water": "#3d7fb8", "road": "#5a5c60",
}


@dataclass
class Entity:
    """One placed instance in a scene."""
    placement: Placement
    palette: Dict[str, str]
    obj_type: Optional[Any] = None       # compiled assets.builder.ObjectType
    rig: Optional[Any] = None            # chars.bodies.base.CharacterRig
    program: Optional[Any] = None        # motion.program.CharProgram | ObjProgram

    @property
    def id(self) -> str:
        return self.placement.id

    @property
    def depth(self) -> float:
        return self.placement.depth

    def position(self, t: float) -> Tuple[float, float]:
        if self.program is not None:
            return self.program.position(t)
        return self.placement.at

    def node(self, t: float, resolve_pos=None) -> Node:
        p = self.placement
        if p.kind == "char" and self.rig is not None and self.program is not None:
            st = self.program.state(t, resolve_pos)
            flip = st.facing < 0
            n = Node(transform=chain(
                translation(st.pos[0], st.pos[1]),
                scaling(-p.scale if flip else p.scale, p.scale),
            ), name=p.id)
            n.children.append(self.rig.node(st.pose))
            return n
        x, y = self.position(t)
        n = Node(transform=chain(
            translation(x, y),
            scaling(-p.scale if p.flip or p.facing == "left" else p.scale, p.scale),
        ), name=p.id)
        if p.kind == "char":
            body = (0.35, 0.35, 0.4, 1.0)
            n.add(Shape(path=path_capsule(0, 0.45, 0, 1.25, 0.22), fill=body))
            n.add(Shape(path=path_circle(0, 1.55, 0.16), fill=body))
        elif self.obj_type is not None:
            part_state = self.program.part_state(t) if self.program else {}
            n.opacity = self.program.opacity_at(t) if self.program else 1.0
            n.children.append(self.obj_type.node(part_state, p.tint, self.palette))
        else:
            col = colors.parse(p.tint, self.palette) if p.tint else (0.5, 0.45, 0.4, 1.0)
            n.add(Shape(path=path_rect(-0.5, 0.0, 1.0, 1.0), fill=col))
        return n


@dataclass
class CompiledScene:
    scene: Scene
    camera: CameraTrack
    entities: List[Entity] = field(default_factory=list)

    def entity(self, eid: str) -> Optional[Entity]:
        for e in self.entities:
            if e.id == eid:
                return e
        return None


class World:
    def __init__(self, production: Production):
        from ..assets.catalog import Catalog
        self.production = production
        self.rng = MFRandom(production.meta.seed)
        self.width, self.height = production.meta.resolution
        self.catalog = Catalog(production)
        self.scenes: List[CompiledScene] = []
        from ..chars.factory import make_rig
        from ..motion.program import CharProgram, ObjProgram
        rig_cache: Dict[str, Any] = {}
        for sc in production.scenes:
            cs = CompiledScene(scene=sc, camera=compile_camera(sc))
            by_subject: Dict[str, List[Any]] = {}
            for d in sc.timeline:
                if d.subject_kind in ("char", "obj"):
                    by_subject.setdefault(d.subject, []).append(d)
            for p in sc.place:
                obj_type = self.catalog.get(p.name) if p.kind == "obj" else None
                rig = None
                program = None
                dirs = by_subject.get(p.id, [])
                if p.kind == "char" and p.name in production.characters:
                    if p.name not in rig_cache:
                        rig_cache[p.name] = make_rig(production.characters[p.name],
                                                     production.palette)
                    rig = rig_cache[p.name]
                    program = CharProgram(p, rig, dirs, sc, self.rng)
                elif p.kind == "obj":
                    program = ObjProgram(p, obj_type, dirs, sc)
                cs.entities.append(Entity(placement=p, palette=production.palette,
                                          obj_type=obj_type, rig=rig,
                                          program=program))
            self.scenes.append(cs)

    # ------------------------------------------------------------ per frame

    def scene_at(self, t_abs: float) -> Tuple[CompiledScene, float]:
        acc = 0.0
        for cs in self.scenes:
            if t_abs < acc + cs.scene.duration or cs is self.scenes[-1]:
                return cs, min(max(t_abs - acc, 0.0), cs.scene.duration)
            acc += cs.scene.duration
        raise ValueError("no scenes")

    def camera_state(self, cs: CompiledScene, t: float) -> CamState:
        follow_pos = None
        if cs.camera.follow is not None:
            target = cs.camera.follow.get("char") or cs.camera.follow.get("obj")
            ent = cs.entity(str(target)) if target else None
            if ent is not None:
                follow_pos = ent.position(t)
        return cs.camera.state(t, follow_pos)

    def background_shapes(self, cs: CompiledScene, cam: CamState,
                          t: float) -> List[Shape]:
        w, h = self.width, self.height
        bg = cs.scene.background
        out: List[Shape] = []
        sky = bg.get("sky", "day")
        if isinstance(sky, str) and sky in SKY_COLORS:
            top, bottom = (colors.parse(c) for c in SKY_COLORS[sky])
        else:
            try:
                top = bottom = colors.parse(sky, self.production.palette)
            except ValueError:
                top, bottom = (colors.parse(c) for c in SKY_COLORS["day"])
        hy = horizon_y(cam, h)
        out.append(Shape(path=path_rect(0, 0, w, max(hy, 0) + 2), fill=Gradient(
            kind="linear", stops=[(0.0, top), (1.0, bottom)], p0=(0, 0), p1=(0, max(hy, 1)))))
        # ground: from the horizon down, shaded darker when nearer
        ground = bg.get("ground", "grass")
        gcolor = None
        if isinstance(ground, dict):
            gname = ground.get("kind", "grass")
            gcolor = ground.get("color")
        else:
            gname = str(ground)
        if gname != "none":
            base = colors.parse(gcolor, self.production.palette) if gcolor else \
                colors.parse(GROUND_COLORS.get(gname, GROUND_COLORS["grass"]))
            far_c = colors.mix(base, bottom, 0.45)
            near_c = colors.lighten(base, -0.06)
            out.append(Shape(path=path_rect(0, hy, w, h - hy), fill=Gradient(
                kind="linear", stops=[(0.0, far_c), (1.0, near_c)],
                p0=(0, hy), p1=(0, h))))
        return out

    def frame_shapes(self, t_abs: float) -> List[Shape]:
        cs, t = self.scene_at(t_abs)
        cam = self.camera_state(cs, t)
        shapes = self.background_shapes(cs, cam, t)

        def resolve_pos(eid: str, tt: float):
            e = cs.entity(eid)
            return e.position(tt) if e is not None else None

        order = sorted(cs.entities, key=lambda e: (-e.depth, e.placement.layer))
        for ent in order:
            view = view_matrix(cam, ent.depth, self.width, self.height)
            flatten(ent.node(t, resolve_pos), view, 1.0, shapes)

        from ..fx.captions import render_captions
        shapes.extend(render_captions(cs.scene.captions, t, self.width,
                                      self.height, self.production.palette))
        shapes.extend(self._say_subtitles(cs, t))
        return shapes

    def _say_subtitles(self, cs: CompiledScene, t: float) -> List[Shape]:
        from ..dsl.ir import Caption
        from ..fx.captions import render_caption
        out: List[Shape] = []
        row = 0
        for ent in cs.entities:
            prog = ent.program
            if prog is None or not hasattr(prog, "say_captions"):
                continue
            for say in prog.say_captions():
                if say.t0 <= t <= say.t1 and say.text.strip():
                    cap = Caption(t=say.t0, until=say.t1, text=say.text,
                                  style="subtitle",
                                  params={"pos": [0.5, 0.90 - row * 0.075]})
                    out.extend(render_caption(cap, t, self.width, self.height,
                                              self.production.palette))
                    row += 1
        return out
