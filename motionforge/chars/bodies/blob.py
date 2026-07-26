"""The blob body template: a friendly mascot with squash-and-stretch.

One rounded gumdrop of a creature: stubby feet, tiny arm nubs, and a big
face_node face. It is the fallback body, so it must always look charming.
Squash comes from two places, both anchored at the ground so the blob never
sinks or floats: the explicit pose morph "squash" (-1 stretch .. +1 squash),
and an automatic term derived from how far the root sits below/above its
rest height — so crouches flatten the blob and jumps stretch it for free.
Species accents (ears, horns, tails) key off style["species"]; unknown
species get a clean blob with a little sprout curl on top.
"""
from __future__ import annotations

import math
from typing import Dict

from ...core.color import RGBA, lighten
from ...core.transform import chain, rotation, scaling, translation
from ...draw.canvas import (Shape, Stroke, path_circle, path_ellipse,
                            path_line, path_polygon, path_round_rect,
                            path_taper)
from ...scene.graph import Node
from ..face import face_node
from ..rig import FK, Bone, Pose, Skeleton
from .base import CharacterRig

# ------------------------------------------------------------- species accents
#   ear:   pointy | floppy | round | long | horns | None      ear_s: size factor
#   tail:  nub | bushy | puff | thin | curl | None
# Anything not listed (including no species) gets the default sprout curl.
_DEF_ACC = dict(ear=None, ear_s=1.0, tail=None, sprout=True)

ACCENTS: Dict[str, dict] = {
    "cat":    dict(_DEF_ACC, ear="pointy", tail="nub", sprout=False),
    "dog":    dict(_DEF_ACC, ear="floppy", tail="nub", sprout=False),
    "fox":    dict(_DEF_ACC, ear="pointy", ear_s=1.25, tail="bushy", sprout=False),
    "wolf":   dict(_DEF_ACC, ear="pointy", ear_s=1.1, tail="bushy", sprout=False),
    "bear":   dict(_DEF_ACC, ear="round", sprout=False),
    "mouse":  dict(_DEF_ACC, ear="round", ear_s=1.55, tail="thin", sprout=False),
    "rabbit": dict(_DEF_ACC, ear="long", tail="puff", sprout=False),
    "pig":    dict(_DEF_ACC, ear="pointy", ear_s=0.8, tail="curl", sprout=False),
    "cow":    dict(_DEF_ACC, ear="horns", sprout=False),
    "goat":   dict(_DEF_ACC, ear="horns", sprout=False),
}

_HORN: RGBA = (0.88, 0.85, 0.78, 1.0)
_FAR_SHADE = -0.13


def build_blob(name: str, params: Dict, style: dict) -> "BlobRig":
    H = float(params.get("size") or params.get("height") or 0.8)
    return BlobRig(name, H, style)


class BlobRig(CharacterRig):
    def __init__(self, name: str, H: float, style: dict):
        build = float(style.get("build", 1.0))
        self.acc = ACCENTS.get(str(style.get("species", "")), _DEF_ACC)
        seg = 0.16 * H                    # body / chest / head bone lengths
        self.dim = {
            "H": H, "seg": seg,
            "hip": 0.42 * H,              # root sits mid-blob at rest
            "hw": 0.37 * H * build,       # body half-width
            "foot_rx": 0.125 * H, "foot_ry": 0.062 * H,
            "arm_r": 0.055 * H,
            "face_x": 0.11 * H, "face_y": 0.63 * H, "face_r": 0.20 * H,
        }
        d = self.dim
        bones = [
            # a short spine so idle sway / emotes / ragdoll have joints to move
            Bone("body", None, seg, (0.0, 0.0), 90.0),
            Bone("chest", "body", seg, (seg, 0.0), 0.0),
            Bone("head", "chest", seg, (seg, 0.0), 0.0),
        ]
        super().__init__(name, Skeleton(bones), style, H)
        self.hip_height = d["hip"]
        self.head_bone = "head"
        self.head_radius = 0.26 * H
        # legs / arms stay {}: the gait engine glides blobs, actions still work

    def rest_pose(self) -> Pose:
        return Pose(root=(0.0, self.hip_height))

    # ------------------------------------------------------------- squash math

    def _squash(self, pose: Pose) -> float:
        """Total squash: explicit morph + automatic ground-press/stretch."""
        H = self.dim["H"]
        delta = pose.root[1] - self.hip_height
        if delta < 0.0:                   # pressed down: flatten to stay grounded
            auto = min(1.0, -delta / (0.30 * H))
        else:                             # airborne: a gentle stretch
            auto = -min(0.35, delta / (1.2 * H))
        s = float(pose.morphs.get("squash", 0.0)) + auto
        return max(-0.9, min(1.0, s))

    # ----------------------------------------------------------------- draw

    def draw(self, fk: FK, pose: Pose) -> Node:
        d, st, acc = self.dim, self.style, self.acc
        H, hw = d["H"], d["hw"]
        skin: RGBA = st["skin_rgba"]
        skin2: RGBA = st["skin2_rgba"]
        m = pose.morphs

        s = self._squash(pose)
        sy = 1.0 - 0.30 * s
        sx = (1.0 / sy) ** 0.7            # near volume-preserving widen/narrow
        lift = max(0.0, self.hip_height - pose.root[1])  # keep the base grounded
        sway = max(-14.0, min(14.0, pose.angles.get("chest", 0.0))) * 0.5

        # The blob frame: origin on the ground under the root, +X forward, +Y up.
        # Squash scales about the origin, so the base never leaves the ground.
        n = Node(name=self.name)
        b = n.child(transform=chain(
            translation(0.0, lift), fk.base["body"], rotation(-90.0),
            translation(0.0, -self.hip_height), rotation(sway), scaling(sx, sy)))

        # ---- back-to-front inside the blob frame
        self._tail(b, H, hw, skin, skin2)
        self._ear(b, H, hw, far=True)
        self._foot(b, -0.15 * H, H, lighten(skin, -0.18 + _FAR_SHADE))
        self._arm(b, H, hw, far=True)

        # body: a big top ellipse over a wider rounded base = gumdrop
        b.add(Shape(path=path_round_rect(-hw * 1.02, 0.05 * H, 2.04 * hw,
                                         0.47 * H, 0.15 * H), fill=skin))
        b.add(Shape(path=path_ellipse(0.0, 0.56 * H, hw * 0.96, 0.44 * H),
                    fill=skin))
        b.add(Shape(path=path_ellipse(0.09 * H, 0.30 * H, min(hw * 0.60, 0.25 * H),
                                      0.22 * H), fill=skin2))
        if acc["sprout"]:
            b.add(Shape(path=[("M", 0.0, 0.98 * H),
                              ("C", 0.01 * H, 1.09 * H, 0.10 * H, 1.11 * H,
                               0.085 * H, 1.03 * H)],
                        stroke=Stroke(paint=lighten(skin, -0.2),
                                      width=0.022 * H)))

        self._ear(b, H, hw, far=False)
        self._foot(b, 0.17 * H, H, lighten(skin, -0.18))
        self._arm(b, H, hw, far=False)

        # rosy cheeks, then the full face (drawn over them where they overlap)
        blush = (0.95, 0.45, 0.50, 0.30)
        b.add(Shape(path=path_circle(0.275 * H, 0.555 * H, 0.045 * H), fill=blush))
        b.add(Shape(path=path_circle(-0.05 * H, 0.555 * H, 0.04 * H), fill=blush))

        head_tilt = max(-25.0, min(25.0, pose.angles.get("head", 0.0))) * 0.6
        fn = Node(transform=chain(translation(d["face_x"], d["face_y"]),
                                  rotation(head_tilt)), name="face_anchor")
        fn.children.append(face_node(d["face_r"], m, st))
        b.children.append(fn)
        return n

    # ---------------------------------------------------------------- parts

    def _foot(self, b: Node, x: float, H: float, col: RGBA) -> None:
        d = self.dim
        b.add(Shape(path=path_ellipse(x, d["foot_ry"], d["foot_rx"],
                                      d["foot_ry"]), fill=col))

    def _arm(self, b: Node, H: float, hw: float, far: bool) -> None:
        """Stubby mitt nubs angled downward from the sides."""
        skin = self.style["skin_rgba"]
        r = self.dim["arm_r"]
        sgn = -1.0 if far else 1.0
        col = lighten(skin, _FAR_SHADE) if far else skin
        b.add(Shape(path=path_taper(sgn * hw * 0.52, 0.40 * H,
                                    sgn * (hw + 0.055 * H), 0.26 * H,
                                    r, r * 0.62), fill=col))

    def _ear(self, b: Node, H: float, hw: float, far: bool) -> None:
        acc, st = self.acc, self.style
        kind = acc["ear"]
        if kind is None:
            return
        skin, skin2 = st["skin_rgba"], st["skin2_rgba"]
        s = H * acc["ear_s"]
        shade = _FAR_SHADE if far else 0.0
        col = lighten(skin, shade)
        x = -hw * 0.46 if far else hw * 0.42
        if kind == "pointy":
            b.add(Shape(path=path_polygon([
                (x - 0.085 * s, 0.84 * H), (x + 0.085 * s, 0.86 * H),
                (x + 0.02 * s, 0.86 * H + 0.24 * s)]), fill=col))
            if not far:
                b.add(Shape(path=path_polygon([
                    (x - 0.04 * s, 0.88 * H), (x + 0.05 * s, 0.89 * H),
                    (x + 0.02 * s, 0.88 * H + 0.15 * s)]), fill=skin2))
        elif kind == "floppy":
            # both floppy ears hang over the top edge, so both draw over the body
            e = b.child(transform=chain(
                translation(x + (0.05 * H if far else 0.02 * H), 0.93 * H),
                rotation(28.0 if far else -24.0)))
            e.add(Shape(path=path_ellipse(0.0, -0.11 * s, 0.062 * s, 0.15 * s),
                        fill=lighten(skin, shade - 0.14)))
        elif kind == "round":
            cy = 0.93 * H
            b.add(Shape(path=path_circle(x, cy, 0.095 * s), fill=col))
            if not far:
                b.add(Shape(path=path_circle(x, cy, 0.058 * s), fill=skin2))
        elif kind == "long":
            e = b.child(transform=chain(translation(x, 0.92 * H),
                                        rotation(9.0 if far else -7.0)))
            e.add(Shape(path=path_ellipse(0.0, 0.16 * s, 0.055 * s, 0.20 * s),
                        fill=col))
            if not far:
                e.add(Shape(path=path_ellipse(0.0, 0.16 * s, 0.028 * s,
                                              0.14 * s), fill=skin2))
        elif kind == "horns":
            sgn = -1.0 if far else 1.0
            b.add(Shape(path=path_line([
                (x, 0.90 * H), (x + sgn * 0.05 * s, 0.90 * H + 0.10 * s),
                (x + sgn * 0.12 * s, 0.90 * H + 0.145 * s)]),
                stroke=Stroke(paint=lighten(_HORN, shade), width=0.05 * s)))

    def _tail(self, b: Node, H: float, hw: float, skin: RGBA,
              skin2: RGBA) -> None:
        kind = self.acc["tail"]
        if kind is None:
            return
        bx = -hw * 0.92
        if kind == "nub":
            b.add(Shape(path=path_circle(bx - 0.02 * H, 0.20 * H, 0.075 * H),
                        fill=skin))
        elif kind == "bushy":
            b.add(Shape(path=path_taper(bx + 0.04 * H, 0.20 * H,
                                        bx - 0.24 * H, 0.34 * H,
                                        0.09 * H, 0.115 * H), fill=skin))
            b.add(Shape(path=path_circle(bx - 0.26 * H, 0.355 * H, 0.10 * H),
                        fill=skin2))
        elif kind == "puff":
            b.add(Shape(path=path_circle(bx - 0.015 * H, 0.22 * H, 0.08 * H),
                        fill=lighten(skin, 0.25)))
        elif kind == "thin":
            pts = [(bx + 0.02 * H, 0.12 * H)]
            for u in (0.25, 0.5, 0.75, 1.0):
                pts.append((bx + 0.02 * H - u * 0.34 * H,
                            0.12 * H + math.sin(u * 2.6) * 0.10 * H))
            b.add(Shape(path=path_line(pts),
                        stroke=Stroke(paint=lighten(skin, -0.1),
                                      width=0.028 * H)))
        elif kind == "curl":
            r = 0.055 * H
            b.add(Shape(path=[("M", bx + 0.03 * H, 0.30 * H),
                              ("A", bx - 0.02 * H, 0.30 * H, r, -1.1, 3.6),
                              ("A", bx - 0.05 * H, 0.27 * H, r * 0.55, 3.6, 7.4)],
                        stroke=Stroke(paint=skin, width=0.035 * H)))
