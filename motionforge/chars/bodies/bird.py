"""The bird body template: plump body, folded wings, and a beak that talks.

One parametric rig covers songbirds to penguins. Species traits (beak shape,
posture, tail fan, comb / ear tufts / facial disc, flipper wings) key off
style["species"] with a friendly generic-songbird default. Proportions all
derive from `size` (standing body height in meters), so any size stays true.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Tuple

from ...core import color as colors
from ...core.color import RGBA, lighten
from ...core.transform import chain, rotation, translation
from ...draw.canvas import (Shape, Stroke, path_capsule, path_circle,
                            path_ellipse, path_line, path_polygon, path_taper)
from ...scene.graph import Node
from ..rig import FK, Bone, Pose, Skeleton
from .base import Chain2, CharacterRig

# world-frame leg angles at rest (facing right): thigh down-forward, then the
# tarsus rakes down-back so the visible joint (the ankle) points backward.
_THIGH_W = -78.0
_SHIN_W = -96.0


def build_bird(name: str, params: Dict, style: dict) -> "BirdRig":
    S = float(params.get("size") or params.get("height") or 0.35)
    return BirdRig(name, S, style)


def _hex(h: str) -> RGBA:
    return colors.parse(h)


def _traits(species: str) -> Dict:
    """Species-specific shape knobs; every value has a generic default."""
    t: Dict = dict(
        tilt=65.0,               # body bone angle above horizontal
        neck_world=85.0, head_world=55.0,
        leg_f=1.0, neck_f=1.0, neck_r_f=1.0, head_f=1.0,
        body_f=1.0, plump=1.0,
        tail_world=192.0, tail_f=1.0,
        fan=((-10.0, 0.85), (0.0, 1.0), (10.0, 0.92)),
        wing_u_world=202.0, wing_l_rel=-12.0, wing_t_rel=-7.0,
        wing_w=1.0, wing_len_f=1.0, shoulder_back=0.015,
        beak="cone", beak_f=1.0,
        beak_hex="#e0a13c", leg_hex="#d9973f",
        head_hex=None, belly_hex=None, belly_big=False,
        comb=False, wattle=False, tufts=False, disc=False,
        two_eyes=False, eye_f=1.0, brow_ridge=False, webbed=False,
    )
    if species == "crow":
        t.update(beak="point", beak_f=1.15, beak_hex="#3c3c46",
                 leg_hex="#4a4a52", tail_world=190.0, tail_f=1.15, tilt=62.0,
                 fan=((-6.0, 0.9), (0.0, 1.0), (6.0, 0.95)))
    elif species == "sparrow":
        t.update(beak_f=0.7, beak_hex="#7a5c40", tail_world=176.0,
                 tail_f=0.85, plump=1.05, tilt=58.0)
    elif species == "eagle":
        t.update(beak="hook", beak_hex="#e3b53e", leg_hex="#e3b53e",
                 head_hex="#ece7db", brow_ridge=True, tilt=62.0,
                 body_f=1.05, leg_f=1.05, tail_world=194.0, tail_f=1.05,
                 head_world=45.0)
    elif species == "owl":
        t.update(beak="tiny", tilt=78.0, neck_f=0.4, head_f=1.35,
                 neck_world=82.0, head_world=70.0, two_eyes=True, disc=True,
                 tufts=True, eye_f=1.35, tail_world=215.0, tail_f=0.6,
                 leg_f=0.8, plump=1.08, beak_hex="#c8a050",
                 wing_u_world=240.0, wing_l_rel=-8.0, wing_t_rel=-4.0,
                 wing_len_f=0.8, shoulder_back=0.05)
    elif species == "parrot":
        t.update(beak="curve", beak_hex="#b8b0a0", leg_hex="#8a8a92",
                 tail_f=1.4, tail_world=208.0,
                 fan=((-6.0, 0.82), (0.0, 1.0), (6.0, 0.9)), head_world=60.0)
    elif species == "duck":
        t.update(beak="flat", beak_hex="#e8952f", leg_hex="#e8952f",
                 webbed=True, tilt=52.0, neck_f=1.5, neck_r_f=0.85,
                 neck_world=94.0, head_world=60.0, tail_world=162.0,
                 tail_f=0.55, fan=((-12.0, 0.8), (2.0, 1.0)), plump=1.02)
    elif species == "chicken":
        t.update(comb=True, wattle=True, beak_f=0.8, beak_hex="#e3b53e",
                 leg_hex="#e3b53e", tilt=66.0, tail_world=150.0, tail_f=1.15,
                 fan=((-38.0, 0.7), (-19.0, 0.88), (0.0, 1.0), (19.0, 0.8)))
    elif species == "penguin":
        t.update(tilt=88.0, neck_world=90.0, neck_f=0.25, head_world=78.0,
                 beak="point", beak_hex="#d98a4a", leg_f=0.5,
                 leg_hex="#e8964a", belly_hex="#f0f2f5", belly_big=True,
                 body_f=1.35, tail_world=228.0, tail_f=0.4,
                 fan=((-8.0, 0.9), (8.0, 1.0)),
                 wing_u_world=-100.0, wing_l_rel=-5.0, wing_t_rel=-3.0,
                 wing_w=0.55, wing_len_f=0.75, shoulder_back=0.06,
                 webbed=True)
    return t


class BirdRig(CharacterRig):
    def __init__(self, name: str, S: float, style: dict):
        tr = _traits(str(style.get("species", "")))
        self.tr = tr
        d = {
            "S": S,
            "thigh": 0.16 * S * tr["leg_f"],
            "shin": 0.17 * S * tr["leg_f"],
            "foot": 0.10 * S,
            "foot_r": 0.014 * S,
            "leg_r": 0.012 * S,
            "body_len": 0.34 * S * tr["body_f"],
            "body_rx": 0.29 * S * tr["plump"],
            "body_ry": 0.22 * S * tr["plump"],
            "neck": 0.06 * S * tr["neck_f"],
            "neck_r": 0.055 * S * tr["neck_r_f"],
            "head_len": 0.08 * S,
            "wing_u": 0.15 * S * tr["wing_len_f"],
            "wing_l": 0.115 * S * tr["wing_len_f"],
            "wing_t": 0.075 * S * tr["wing_len_f"],
            "tail": 0.26 * S * tr["tail_f"],
        }
        self.dim = d
        tilt = tr["tilt"]
        bones = [
            Bone("body", None, d["body_len"], (0.0, 0.0), tilt),
            Bone("neck", "body", d["neck"], (d["body_len"], 0.0),
                 tr["neck_world"] - tilt),
            Bone("head", "neck", d["head_len"], (d["neck"], 0.0),
                 tr["head_world"] - tr["neck_world"]),
            Bone("tail", "body", d["tail"], (d["body_len"] * 0.12, 0.0),
                 tr["tail_world"] - tilt),
        ]
        for side in ("far", "near"):
            bones += [
                Bone(f"thigh_{side}", "body", d["thigh"], (0.0, 0.0),
                     _THIGH_W - tilt),
                Bone(f"shin_{side}", f"thigh_{side}", d["shin"],
                     (d["thigh"], 0.0), _SHIN_W - _THIGH_W),
                Bone(f"foot_{side}", f"shin_{side}", d["foot"],
                     (d["shin"], 0.0), 0.0 - _SHIN_W),
                Bone(f"wing_u_{side}", "body", d["wing_u"],
                     (d["body_len"] * 0.70, tr["shoulder_back"] * S),
                     tr["wing_u_world"] - tilt),
                Bone(f"wing_l_{side}", f"wing_u_{side}", d["wing_l"],
                     (d["wing_u"], 0.0), tr["wing_l_rel"]),
                Bone(f"wing_t_{side}", f"wing_l_{side}", d["wing_t"],
                     (d["wing_l"], 0.0), tr["wing_t_rel"]),
            ]
        super().__init__(name, Skeleton(bones), style, S)
        self.hip_height = (d["thigh"] * math.sin(math.radians(-_THIGH_W)) +
                           d["shin"] * math.sin(math.radians(-_SHIN_W)) +
                           d["foot_r"])
        self.head_bone = "head"
        self.head_radius = 0.145 * S * tr["head_f"]
        for side in ("near", "far"):
            self.legs[side] = Chain2(f"thigh_{side}", f"shin_{side}",
                                     f"foot_{side}", bend=-1.0,
                                     end_length=d["foot"])
            self.arms[side] = Chain2(f"wing_u_{side}", f"wing_l_{side}",
                                     f"wing_t_{side}", bend=1.0,
                                     end_length=d["wing_t"])

    def rest_pose(self) -> Pose:
        return Pose(root=(0.0, self.hip_height), angles={
            # slight stance splay; feet compensated so both stay flat
            "thigh_near": 4.0, "shin_near": -2.0, "foot_near": -2.0,
            "thigh_far": -4.0, "shin_far": 2.0, "foot_far": 2.0,
        })

    # ----------------------------------------------------------------- draw

    def draw(self, fk: FK, pose: Pose) -> Node:
        d, st, tr = self.dim, self.style, self.tr
        skin: RGBA = st["skin_rgba"]
        belly: RGBA = _hex(tr["belly_hex"]) if tr["belly_hex"] else st["skin2_rgba"]
        head_col: RGBA = _hex(tr["head_hex"]) if tr["head_hex"] else skin
        wing_c = lighten(skin, -0.09)
        far = -0.13
        n = Node(name=self.name)

        self._wing(n, fk, "far", lighten(wing_c, far))
        self._leg(n, fk, "far", far)
        self._leg(n, fk, "near", 0.0)
        self._tail(n, fk, skin)

        # plump body + belly patch
        bl = d["body_len"]
        body_m = fk.base["body"]
        n.add(Shape(path=path_ellipse(bl * 0.45, 0.0, d["body_rx"], d["body_ry"]),
                    fill=skin, transform=body_m))
        if tr["belly_big"]:
            n.add(Shape(path=path_ellipse(bl * 0.50, -d["body_ry"] * 0.42,
                                          d["body_rx"] * 0.78, d["body_ry"] * 0.64),
                        fill=belly, transform=body_m))
        else:
            n.add(Shape(path=path_ellipse(bl * 0.38, -d["body_ry"] * 0.33,
                                          d["body_rx"] * 0.60, d["body_ry"] * 0.62),
                        fill=belly, transform=body_m))

        # neck over the body's top edge, then the head
        n.add(Shape(path=path_taper(-d["neck"] * 0.4, 0.0, d["neck"] * 1.1, 0.0,
                                    d["neck_r"], d["neck_r"] * 0.9),
                    fill=head_col, transform=fk.base["neck"]))
        n.children.append(self._head(fk, pose, head_col))

        self._wing(n, fk, "near", wing_c)
        return n

    # ---------------------------------------------------------------- parts

    def _leg(self, n: Node, fk: FK, side: str, shade: float) -> None:
        d, tr = self.dim, self.tr
        skin = lighten(self.style["skin_rgba"], shade)
        leg_c = lighten(_hex(tr["leg_hex"]), shade)
        n.add(Shape(path=path_taper(0.0, 0.0, d["thigh"], 0.0,
                                    0.035 * d["S"], 0.020 * d["S"]),
                    fill=skin, transform=fk.base[f"thigh_{side}"]))
        n.add(Shape(path=path_taper(0.0, 0.0, d["shin"], 0.0,
                                    d["leg_r"], d["leg_r"] * 0.85),
                    fill=leg_c, transform=fk.base[f"shin_{side}"]))
        foot = f"foot_{side}"
        L = self.skeleton.bones[foot].length
        if tr["webbed"]:
            path = path_taper(-0.22 * L, 0.0, 1.15 * L, 0.0,
                              d["foot_r"] * 0.7, d["foot_r"] * 1.0)
        else:
            path = path_capsule(-0.25 * L, 0.0, L, 0.0, d["foot_r"])
        n.add(Shape(path=path, fill=leg_c, transform=fk.base[foot]))

    def _wing(self, n: Node, fk: FK, side: str, col: RGBA) -> None:
        d = self.dim
        w = self.tr["wing_w"]
        w_u0, w_u1 = 0.085 * d["S"] * w, 0.062 * d["S"] * w
        w_l1 = 0.042 * d["S"] * w
        n.add(Shape(path=path_taper(0.0, 0.0, d["wing_u"], 0.0, w_u0, w_u1),
                    fill=col, transform=fk.base[f"wing_u_{side}"]))
        n.add(Shape(path=path_taper(0.0, 0.0, d["wing_l"], 0.0, w_u1, w_l1),
                    fill=col, transform=fk.base[f"wing_l_{side}"]))
        Lt = d["wing_t"]
        tip = [(0.0, w_l1), (Lt * 1.35, 0.0), (0.0, -w_l1)]
        n.add(Shape(path=path_polygon(tip), fill=lighten(col, -0.06),
                    transform=fk.base[f"wing_t_{side}"]))

    def _tail(self, n: Node, fk: FK, skin: RGBA) -> None:
        d, tr = self.dim, self.tr
        m = fk.base["tail"]
        L = d["tail"]
        for i, (ang, lf) in enumerate(tr["fan"]):
            col = lighten(skin, -0.04 if i % 2 == 0 else -0.11)
            n.add(Shape(path=path_taper(0.0, 0.0, L * lf, 0.0,
                                        0.018 * d["S"], 0.032 * d["S"]),
                        fill=col, transform=chain(m, rotation(ang))))

    # ----------------------------------------------------------------- head

    def _head(self, fk: FK, pose: Pose, head_col: RGBA) -> Node:
        d, st, tr = self.dim, self.style, self.tr
        R = self.head_radius
        m = pose.morphs
        head_m = chain(fk.base["head"], translation(d["head_len"] * 0.6, 0.0),
                       rotation(-tr["head_world"]))
        h = Node(transform=head_m, name="head")

        if tr["comb"]:
            red = _hex("#d5382e")
            for cx, cy, r in ((-0.25, 0.92, 0.24), (0.10, 1.04, 0.27),
                              (0.42, 0.88, 0.22)):
                h.add(Shape(path=path_circle(cx * R, cy * R, r * R), fill=red))
        if tr["tufts"]:
            tuft = lighten(head_col, -0.05)
            h.add(Shape(path=path_polygon([(-0.95 * R, 0.45 * R),
                                           (-0.60 * R, 1.25 * R),
                                           (-0.10 * R, 0.72 * R)]), fill=tuft))
            h.add(Shape(path=path_polygon([(0.15 * R, 0.72 * R),
                                           (0.60 * R, 1.28 * R),
                                           (0.95 * R, 0.42 * R)]), fill=tuft))

        h.add(Shape(path=path_ellipse(0.0, 0.0, R * 0.98, R * 1.02),
                    fill=head_col))
        disc_col = head_col
        if tr["disc"]:
            disc_col = lighten(head_col, 0.14)
            h.add(Shape(path=path_ellipse(R * 0.28, -R * 0.02,
                                          R * 0.72, R * 0.68), fill=disc_col))

        self._beak(h, R, m)
        if tr["wattle"]:
            h.add(Shape(path=path_ellipse(R * 0.42, -R * 0.55,
                                          R * 0.15, R * 0.24),
                        fill=_hex("#d5382e")))
        self._eyes(h, R, m, disc_col)
        return h

    # ----------------------------------------------------------------- beak

    def _beak(self, h: Node, R: float, m: Dict[str, float]) -> None:
        tr = self.tr
        kind, f = tr["beak"], tr["beak_f"]
        beak = _hex(tr["beak_hex"])
        beak_lo = lighten(beak, -0.12)
        open_amt = max(0.0, min(1.0, float(m.get("mouth_open", 0.0))))
        base = {"cone": (0.62, 0.02), "point": (0.62, 0.0),
                "hook": (0.60, 0.02), "curve": (0.55, 0.05),
                "flat": (0.55, -0.10), "tiny": (0.30, -0.15)}[kind]
        bm = translation(base[0] * R, base[1] * R)
        up = chain(bm, rotation(10.0 * open_amt))
        dn = chain(bm, rotation(-24.0 * open_amt))
        if open_amt > 0.05:      # dark mouth interior behind the halves
            h.add(Shape(path=path_ellipse(0.18 * R, -0.02 * R, 0.20 * R * f,
                                          (0.02 + 0.16 * open_amt) * R),
                        fill=(0.25, 0.10, 0.10, 1.0), transform=bm))

        def poly(pts, paint, t) -> None:
            h.add(Shape(path=path_polygon([(x * R, y * R) for x, y in pts]),
                        fill=paint, transform=t))

        if kind == "cone":
            L = 0.95 * f
            poly([(-0.18, 0.30), (L, 0.02), (-0.18, -0.01)], beak, up)
            poly([(-0.18, 0.02), (L * 0.8, 0.0), (-0.18, -0.21)], beak_lo, dn)
        elif kind == "point":
            L = 1.1 * f
            poly([(-0.15, 0.22), (L, 0.0), (-0.15, 0.0)], beak, up)
            poly([(-0.15, 0.01), (L * 0.85, -0.02), (-0.15, -0.17)], beak_lo, dn)
        elif kind == "hook":
            poly([(-0.15, 0.42), (0.35, 0.36), (0.65, 0.18), (0.76, -0.05),
                  (0.70, -0.30), (0.62, -0.02), (0.30, 0.04), (-0.15, 0.02)],
                 beak, up)
            poly([(-0.15, 0.03), (0.55, -0.02), (0.60, -0.10), (-0.15, -0.22)],
                 beak_lo, dn)
        elif kind == "curve":
            poly([(-0.10, 0.45), (0.30, 0.42), (0.60, 0.25), (0.72, -0.02),
                  (0.65, -0.30), (0.52, -0.10), (0.30, 0.02), (-0.10, 0.05)],
                 beak, up)
            poly([(-0.10, 0.02), (0.45, -0.05), (0.40, -0.18), (-0.10, -0.28)],
                 beak_lo, dn)
        elif kind == "flat":
            h.add(Shape(path=path_capsule(0.0, 0.10 * R, 1.05 * R, 0.04 * R,
                                          0.13 * R), fill=beak, transform=up))
            h.add(Shape(path=path_circle(0.30 * R, 0.17 * R, 0.030 * R),
                        fill=lighten(beak, -0.25), transform=up))
            h.add(Shape(path=path_capsule(0.0, -0.08 * R, 0.88 * R, -0.10 * R,
                                          0.08 * R), fill=beak_lo, transform=dn))
        else:  # tiny (owl): a small down-turned wedge
            poly([(-0.12, 0.18), (0.50, -0.18), (-0.12, -0.02)],
                 lighten(beak, -0.10), up)
            poly([(-0.12, -0.02), (0.36, -0.22), (-0.12, -0.16)],
                 lighten(beak_lo, -0.10), dn)

    # ----------------------------------------------------------------- eyes

    def _eyes(self, h: Node, R: float, m: Dict[str, float], bg: RGBA) -> None:
        tr = self.tr
        iris: RGBA = self.style.get("eyes_rgba", (0.13, 0.14, 0.17, 1.0))
        er = R * 0.24 * tr["eye_f"]
        if tr["two_eyes"]:
            self._eye(h, -R * 0.03, R * 0.10, er, m, iris, bg)
            self._eye(h, R * 0.62, R * 0.10, er, m, iris, bg)
        else:
            self._eye(h, R * 0.30, R * 0.22, er, m, iris, bg)
        if tr["brow_ridge"]:
            n_col = lighten(bg, -0.30)
            h.add(Shape(path=path_line([(R * 0.02, R * 0.52), (R * 0.62, R * 0.40)]),
                        stroke=Stroke(paint=n_col, width=R * 0.13)))

    def _eye(self, h: Node, cx: float, cy: float, er: float,
             m: Dict[str, float], iris: RGBA, bg: RGBA) -> None:
        open_amt = 1.0 - max(0.0, min(1.0, float(m.get("blink", 0.0))))
        gx = float(m.get("gaze_x", 0.0)) * er * 0.32
        gy = float(m.get("gaze_y", 0.0)) * er * 0.25
        if open_amt <= 0.06:
            lum = 0.30 * bg[0] + 0.59 * bg[1] + 0.11 * bg[2]
            line = (0.08, 0.07, 0.08, 1.0) if lum > 0.35 else (0.82, 0.82, 0.86, 1.0)
            h.add(Shape(path=path_line([(cx - er * 0.72, cy), (cx + er * 0.72, cy)]),
                        stroke=Stroke(paint=line, width=er * 0.24)))
            return
        ry = er * open_amt
        h.add(Shape(path=path_ellipse(cx, cy, er, ry), fill=(1.0, 1.0, 1.0, 1.0)))
        h.add(Shape(path=path_circle(cx + gx, cy + gy, er * 0.55), fill=iris))
        h.add(Shape(path=path_circle(cx + gx, cy + gy, er * 0.28),
                    fill=(0.05, 0.05, 0.08, 1.0)))
        h.add(Shape(path=path_circle(cx + gx + er * 0.16, cy + gy + er * 0.18,
                                     er * 0.11), fill=(1.0, 1.0, 1.0, 0.9)))
        if open_amt < 0.94:      # upper lid slides down over the eye
            lid_h = ry * (1.0 - open_amt) * 1.35
            h.add(Shape(path=path_ellipse(cx, cy + ry - lid_h / 2 + ry * 0.15,
                                          er * 1.05, max(lid_h, ry * 0.1)),
                        fill=bg))
