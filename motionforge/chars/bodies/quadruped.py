"""The quadruped body template: dogs to elephants, proportion-safe at any size.

Authored facing right (+X forward). The skeleton root ("spine") sits at the
middle of the back at shoulder-joint height; "rump" mirrors it backward so the
body can arch. Legs are 2-bone chains: front legs bend backward at the middle
joint (elbow, like a human arm), hind legs bend forward (knee), which is how a
side-view animal reads. Species looks (ears, tails, manes, trunks, antlers)
key off style["species"] with a friendly generic default.
"""
from __future__ import annotations

import math
from typing import Dict, List

from ...core.color import RGBA, lighten
from ...core.transform import chain, rotation, translation
from ...draw.canvas import (Shape, Stroke, path_circle, path_ellipse,
                            path_line, path_polygon, path_taper)
from ...scene.graph import Node
from ..ik import two_bone_ik
from ..rig import FK, Bone, Pose, Skeleton, world_angle_to_local
from .base import Chain2, CharacterRig

# ---------------------------------------------------------------- species table
# Every factor is relative to the generic quadruped; unknown species get _default.
#   body     half-body-length factor        bulk     torso radius factor
#   head     head radius factor             muzzle   muzzle length (in head radii)
#   neck     neck length factor             neck_ang neck world angle (deg up from +X)
#   head_ang head bone world angle          leg_r    leg thickness factor
#   ear      pointy|floppy|round|long|side|elephant|none        ear_s  ear size factor
#   tail     curl|upright|bushy|hair|cowtail|tuft|puff|nub|curly|mousetail|plume
#   tail_ang tail bone world angle          tail_len tail length factor
#   hoof     dark hooves                    extras   tuple of feature tags
_DEF = dict(body=1.0, bulk=1.0, head=1.15, muzzle=0.75, neck=1.0, neck_ang=52.0,
            head_ang=4.0, leg_r=1.0, ear="pointy", ear_s=1.0, tail="plume",
            tail_ang=145.0, tail_len=1.0, hoof=False, extras=())

SPECIES: Dict[str, dict] = {
    "_default": dict(_DEF),
    "dog":     dict(_DEF, body=1.12, muzzle=0.8, ear="floppy", tail="curl",
                    tail_ang=115.0),
    "wolf":    dict(_DEF, body=1.12, muzzle=0.85, ear="pointy", ear_s=1.1,
                    tail="bushy", tail_ang=205.0),
    "cat":     dict(_DEF, body=1.02, head=1.22, muzzle=0.42, neck_ang=60.0,
                    ear="pointy", tail="upright", tail_ang=95.0, tail_len=1.15),
    "fox":     dict(_DEF, body=1.05, muzzle=0.75, head=1.2, ear="pointy",
                    ear_s=1.3, tail="bushy", tail_ang=188.0, tail_len=1.2),
    "lion":    dict(_DEF, body=1.15, head=1.25, muzzle=0.65, neck_ang=45.0,
                    tail="tuft", tail_ang=200.0, tail_len=1.25,
                    extras=("mane_lion",)),
    "tiger":   dict(_DEF, body=1.15, head=1.2, muzzle=0.65, neck_ang=48.0,
                    tail="tuft", tail_ang=175.0, tail_len=1.3,
                    extras=("stripes",)),
    "bear":    dict(_DEF, bulk=1.2, head=1.2, muzzle=0.6, neck=0.55,
                    neck_ang=40.0, ear="round", tail="nub", leg_r=1.35),
    "horse":   dict(_DEF, body=1.2, bulk=0.85, head=0.98, muzzle=1.0,
                    neck=1.65, neck_ang=58.0, head_ang=-24.0, ear="pointy",
                    ear_s=0.85, tail="hair", tail_ang=245.0, tail_len=1.1,
                    hoof=True, extras=("mane",)),
    "cow":     dict(_DEF, body=1.25, bulk=1.12, head=1.05, muzzle=0.9,
                    neck=0.7, neck_ang=32.0, head_ang=-8.0, ear="side",
                    tail="cowtail", tail_ang=255.0, tail_len=1.15, hoof=True,
                    extras=("horns", "patches")),
    "sheep":   dict(_DEF, bulk=1.15, head=1.1, muzzle=0.6, neck=0.6,
                    neck_ang=42.0, ear="side", ear_s=0.8, tail="nub",
                    hoof=True, extras=("wool", "dark_face")),
    "goat":    dict(_DEF, bulk=0.95, muzzle=0.7, neck=0.85, neck_ang=50.0,
                    ear="side", tail="nub", tail_ang=100.0, hoof=True,
                    extras=("horns",)),
    "pig":     dict(_DEF, body=1.15, bulk=1.2, head=1.15, muzzle=0.5,
                    neck=0.45, neck_ang=26.0, ear="floppy", ear_s=0.8,
                    tail="curly", tail_ang=140.0, extras=("snout",)),
    "rabbit":  dict(_DEF, body=0.88, bulk=1.05, head=1.4, muzzle=0.38,
                    neck=0.5, neck_ang=62.0, ear="long", tail="puff",
                    tail_ang=140.0, extras=("haunch",)),
    "deer":    dict(_DEF, body=1.05, bulk=0.8, head=0.95, muzzle=0.7,
                    neck=1.45, neck_ang=64.0, head_ang=-10.0, ear="pointy",
                    ear_s=1.15, tail="nub", hoof=True, extras=("antlers",)),
    "elephant": dict(_DEF, body=1.2, bulk=1.12, head=1.45, muzzle=0.0,
                     neck=0.6, neck_ang=42.0, head_ang=0.0, ear="elephant",
                     tail="cowtail", tail_ang=250.0, tail_len=0.9, leg_r=1.9,
                     extras=("trunk", "tusks")),
    "mouse":   dict(_DEF, body=0.95, head=1.5, muzzle=0.5, neck=0.5,
                    neck_ang=48.0, ear="round", ear_s=1.6, tail="mousetail",
                    tail_ang=195.0, tail_len=1.5),
}

_NOSE: RGBA = (0.16, 0.12, 0.12, 1.0)
_MOUTH_DARK: RGBA = (0.22, 0.09, 0.10, 1.0)
_TONGUE: RGBA = (0.92, 0.48, 0.52, 1.0)
_HORN: RGBA = (0.88, 0.85, 0.78, 1.0)
_TUSK: RGBA = (0.96, 0.94, 0.88, 1.0)


def build_quadruped(name: str, params: Dict, style: dict) -> "QuadrupedRig":
    S = float(params.get("size") or params.get("height") or 0.6)
    return QuadrupedRig(name, S, style)


class QuadrupedRig(CharacterRig):
    def __init__(self, name: str, S: float, style: dict):
        sp = SPECIES.get(style.get("species", ""), SPECIES["_default"])
        self.sp = sp
        body_r = 0.30 * S * sp["bulk"]
        spine_y = S - body_r                     # spine axis = shoulder joint height
        half = 0.52 * S * sp["body"]             # half body length
        R = 0.175 * S * sp["head"]               # head radius
        self.dim = {
            "S": S, "body_r": body_r, "spine_y": spine_y, "half": half,
            "u_len": spine_y * 0.52, "l_len": spine_y * 0.48,
            "foot_len": 0.17 * S, "leg_r": 0.075 * S * sp["leg_r"],
            "neck_len": 0.34 * S * sp["neck"], "R": R, "head_len": R * 1.1,
            "muzzle": R * sp["muzzle"], "tail_len": 0.42 * S * sp["tail_len"],
        }
        d = self.dim
        d["foot_r"] = d["leg_r"] * 0.72
        d["ankle_h"] = d["foot_r"] * 0.95
        bones: List[Bone] = [
            Bone("spine", None, half, (0.0, 0.0), 0.0),
            Bone("rump", "spine", half, (0.0, 0.0), 180.0),
            Bone("neck", "spine", d["neck_len"], (half * 0.95, body_r * 0.3),
                 sp["neck_ang"]),
            Bone("head", "neck", d["head_len"], (d["neck_len"], 0.0),
                 sp["head_ang"] - sp["neck_ang"]),
            Bone("tail", "rump", d["tail_len"],
                 # hanging tails clear the round rear cap; raised ones start
                 # at the top back corner of the haunches
                 (half * 0.88 + body_r * (0.85 if sp["tail_ang"] > 180.0 else 0.5),
                  -body_r * (0.25 if sp["tail_ang"] > 180.0 else 0.5)),
                 sp["tail_ang"] - 180.0),
        ]
        for side in ("far", "near"):
            bones += [
                Bone(f"u_front_{side}", "spine", d["u_len"],
                     (half * 0.86, -body_r * 0.1), -90.0),
                Bone(f"l_front_{side}", f"u_front_{side}", d["l_len"],
                     (d["u_len"], 0.0), 0.0),
                Bone(f"f_front_{side}", f"l_front_{side}", d["foot_len"],
                     (d["l_len"], 0.0), 90.0),
                Bone(f"u_back_{side}", "rump", d["u_len"],
                     (half * 0.86, body_r * 0.1), 90.0),
                Bone(f"l_back_{side}", f"u_back_{side}", d["l_len"],
                     (d["u_len"], 0.0), 0.0),
                Bone(f"f_back_{side}", f"l_back_{side}", d["foot_len"],
                     (d["l_len"], 0.0), 90.0),
            ]
        super().__init__(name, Skeleton(bones), style, S)
        self.hip_height = spine_y
        self.head_bone = "head"
        self.head_radius = R
        for side in ("near", "far"):
            self.legs[f"{side}_front"] = Chain2(
                f"u_front_{side}", f"l_front_{side}", f"f_front_{side}",
                bend=-1.0, end_length=d["foot_len"])
            self.legs[f"{side}_back"] = Chain2(
                f"u_back_{side}", f"l_back_{side}", f"f_back_{side}",
                bend=1.0, end_length=d["foot_len"])
        fx = half * 0.86
        split = 0.05 * S
        self.stance_offset = {
            "near_front": fx + split, "far_front": fx - split,
            "near_back": -fx + split, "far_back": -fx - split,
        }

    # ------------------------------------------------------------- rest pose

    def rest_pose(self) -> Pose:
        """Feet planted exactly on the ground at any size/species: solve IK."""
        d = self.dim
        pose = Pose(root=(0.0, self.hip_height))
        fk = FK(self.skeleton, pose)
        for key, ch in self.legs.items():
            base = fk.base_point(ch.upper)
            target = (self.stance_offset[key], d["ankle_h"])
            ua, la = two_bone_ik(base, target, d["u_len"], d["l_len"], ch.bend)
            pose.angles[ch.upper] = world_angle_to_local(fk, ch.upper, ua)
            pose.angles[ch.lower] = la - ua                     # lower rest = 0
            pose.angles[ch.end] = -la - 90.0                    # foot flat, rest = 90
        return pose

    # ----------------------------------------------------------------- draw

    def draw(self, fk: FK, pose: Pose) -> Node:
        n = Node(name=self.name)
        far_shade = -0.13
        self._leg(n, fk, "back", "far", far_shade)
        self._leg(n, fk, "front", "far", far_shade)
        self._tail(n, fk)
        self._body(n, fk)
        self._leg(n, fk, "back", "near", 0.0)
        self._leg(n, fk, "front", "near", 0.0)
        self._neck(n, fk)
        self._head(n, fk, pose)
        return n

    # ----------------------------------------------------------------- legs

    def _leg(self, n: Node, fk: FK, end: str, side: str, shade: float) -> None:
        d, sp = self.dim, self.sp
        skin = self.style["skin_rgba"]
        col = lighten(skin, shade - (0.28 if "dark_face" in sp["extras"] else 0.0))
        r = d["leg_r"]
        n.add(Shape(path=path_taper(-r * 0.4, 0.0, d["u_len"], 0.0, r * 1.15, r * 0.85),
                    fill=col, transform=fk.base[f"u_{end}_{side}"]))
        n.add(Shape(path=path_taper(0.0, 0.0, d["l_len"], 0.0, r * 0.85, d["foot_r"]),
                    fill=col, transform=fk.base[f"l_{end}_{side}"]))
        foot = f"f_{end}_{side}"
        L = d["foot_len"]
        n.add(Shape(path=path_taper(-L * 0.2, 0.0, L * 0.72, 0.0,
                                    d["foot_r"], d["foot_r"] * 0.92),
                    fill=col, transform=fk.base[foot]))
        if sp["hoof"]:
            n.add(Shape(path=path_taper(L * 0.35, 0.0, L * 0.75, 0.0,
                                        d["foot_r"] * 0.95, d["foot_r"] * 0.9),
                        fill=lighten(skin, shade - 0.45), transform=fk.base[foot]))

    # ----------------------------------------------------------------- torso

    def _body(self, n: Node, fk: FK) -> None:
        d, sp, st = self.dim, self.sp, self.style
        skin, skin2 = st["skin_rgba"], st["skin2_rgba"]
        br, half = d["body_r"], d["half"]
        front_m, rear_m = fk.base["spine"], fk.base["rump"]
        # rear half (haunches slightly fuller), then front half (chest deep)
        n.add(Shape(path=path_taper(-half * 0.18, 0.0, half * 0.88, 0.0,
                                    br * 0.94, br), fill=skin, transform=rear_m))
        n.add(Shape(path=path_taper(-half * 0.18, 0.0, half * 0.92, 0.0,
                                    br * 0.94, br), fill=skin, transform=front_m))
        if "haunch" in sp["extras"]:      # rabbit: big rounded hindquarters
            n.add(Shape(path=path_circle(half * 0.62, 0.0, br * 1.18),
                        fill=skin, transform=rear_m))
        # belly accent
        n.add(Shape(path=path_ellipse(half * 0.08, -br * 0.42, half * 0.66, br * 0.52),
                    fill=skin2, transform=front_m))
        if "patches" in sp["extras"]:     # cow
            spot = lighten(skin, -0.5)
            n.add(Shape(path=path_ellipse(half * 0.42, br * 0.28, half * 0.3, br * 0.5),
                        fill=spot, transform=front_m))
            n.add(Shape(path=path_ellipse(half * 0.5, -br * 0.1, half * 0.26, br * 0.42),
                        fill=spot, transform=rear_m))
        if "stripes" in sp["extras"]:     # tiger
            dark = lighten(skin, -0.42)
            for u in (-0.55, -0.15, 0.3, 0.72):
                m = front_m if u >= 0 else rear_m
                x = abs(u) * half
                n.add(Shape(path=path_polygon([
                    (x - br * 0.16, br * 0.95), (x + br * 0.16, br * 0.95),
                    (x + br * 0.04, br * 0.1), (x - br * 0.04, br * 0.1)]),
                    fill=dark, transform=m))
        if "wool" in sp["extras"]:        # sheep: bumpy fleece outline
            for (x, y, r) in ((-0.95, 0.35, 0.42), (-0.75, 0.75, 0.45),
                              (-0.35, 0.95, 0.48), (0.1, 1.0, 0.5),
                              (0.55, 0.92, 0.48), (0.9, 0.6, 0.45),
                              (1.0, 0.1, 0.4), (-1.05, -0.1, 0.38)):
                n.add(Shape(path=path_circle(x * half * 0.92, y * br * 0.72,
                                             r * br * 0.85),
                            fill=skin, transform=front_m))

    # ----------------------------------------------------------------- tail

    def _tail(self, n: Node, fk: FK) -> None:
        d, sp, st = self.dim, self.sp, self.style
        skin, skin2 = st["skin_rgba"], st["skin2_rgba"]
        kind = sp["tail"]
        m = fk.base["tail"]
        L, br = d["tail_len"], d["body_r"]
        tn = Node(transform=m, name="tail")
        n.children.append(tn)

        def segments(rel_angles, r0, r1, color):
            x, y, a = 0.0, 0.0, 0.0
            seg = L / len(rel_angles)
            k = len(rel_angles)
            for i, da in enumerate(rel_angles):
                a += da
                nx = x + seg * math.cos(math.radians(a))
                ny = y + seg * math.sin(math.radians(a))
                rr0 = r0 + (r1 - r0) * i / k
                rr1 = r0 + (r1 - r0) * (i + 1) / k
                tn.add(Shape(path=path_taper(x, y, nx, ny, rr0, rr1), fill=color))
                x, y = nx, ny
            return x, y

        if kind == "curl":   # spitz curl: up, then tipping forward over the back
            segments([0.0, -38.0, -40.0, -42.0], br * 0.28, br * 0.12, skin)
        elif kind == "upright":
            segments([0.0, 20.0, 35.0], br * 0.2, br * 0.11, skin)
        elif kind == "bushy":
            tn.add(Shape(path=path_taper(0.0, 0.0, L * 0.95, 0.0,
                                         br * 0.34, br * 0.42), fill=skin))
            tn.add(Shape(path=path_circle(L * 0.98, 0.0, br * 0.36), fill=skin2))
        elif kind == "hair":
            hair = st["hair_rgba"]
            tn.add(Shape(path=path_taper(0.0, 0.0, L, 0.0, br * 0.3, br * 0.12),
                         fill=hair))
            tn.add(Shape(path=path_taper(L * 0.2, br * 0.12, L * 1.05, br * 0.2,
                                         br * 0.14, br * 0.05), fill=hair))
        elif kind == "cowtail":
            x, y = segments([0.0, 12.0], br * 0.12, br * 0.07, skin)
            tn.add(Shape(path=path_circle(x, y, br * 0.16),
                         fill=lighten(skin, -0.4)))
        elif kind == "tuft":
            x, y = segments([0.0, 18.0, 30.0], br * 0.13, br * 0.08, skin)
            tn.add(Shape(path=path_circle(x, y, br * 0.18),
                         fill=lighten(skin, -0.3)))
        elif kind == "puff":
            tn.add(Shape(path=path_circle(L * 0.25, 0.0, br * 0.34), fill=skin2))
        elif kind == "nub":
            tn.add(Shape(path=path_taper(0.0, 0.0, L * 0.32, 0.0,
                                         br * 0.2, br * 0.1), fill=skin))
        elif kind == "curly":
            r = br * 0.22
            tn.add(Shape(path=[("M", 0.0, 0.0),
                               ("A", r * 0.9, r * 0.5, r, -1.2, 3.6),
                               ("A", r * 1.4, r * 0.9, r * 0.55, 3.6, 7.5)],
                         stroke=Stroke(paint=skin, width=br * 0.14)))
        elif kind == "mousetail":
            pts = [(u * L, -math.sin(u * 2.6) * L * 0.16) for u in
                   (0.0, 0.25, 0.5, 0.75, 1.0)]
            tn.add(Shape(path=path_line(pts),
                         stroke=Stroke(paint=lighten(skin, -0.12),
                                       width=br * 0.11)))
        else:  # plume: friendly generic feathered-up tail
            segments([0.0, 30.0, 45.0], br * 0.22, br * 0.1, skin)

    # ----------------------------------------------------------------- neck

    def _neck(self, n: Node, fk: FK) -> None:
        d, sp, st = self.dim, self.sp, self.style
        skin = st["skin_rgba"]
        L, br, R = d["neck_len"], d["body_r"], d["R"]
        m = fk.base["neck"]
        r0 = min(br * 0.62, R * 1.15)
        r1 = R * 0.72
        n.add(Shape(path=path_taper(-L * 0.15, 0.0, L * 1.05, 0.0, r0, r1),
                    fill=skin, transform=m))
        if "mane" in sp["extras"]:  # horse: crest of hair along the neck top
            hair = st["hair_rgba"]
            for u in (0.05, 0.3, 0.55, 0.8, 1.0):
                rr = r0 + (r1 - r0) * u
                n.add(Shape(path=path_circle(L * u, rr * 0.72, rr * 0.5),
                            fill=hair, transform=m))

    # ----------------------------------------------------------------- head

    def _head(self, n: Node, fk: FK, pose: Pose) -> None:
        d, sp, st = self.dim, self.sp, self.style
        R = d["R"]
        m = pose.morphs
        skin = st["skin_rgba"]
        skin2 = st["skin2_rgba"]
        face_c = lighten(skin, -0.28) if "dark_face" in sp["extras"] else skin
        muzz_c = skin2 if "dark_face" not in sp["extras"] else lighten(skin, -0.2)
        hn = Node(transform=chain(fk.base["head"],
                                  translation(d["head_len"] * 0.42, 0.0)),
                  name="head")
        n.children.append(hn)

        if "mane_lion" in sp["extras"]:
            mane = lighten(skin, -0.3)
            for i in range(9):
                a = math.radians(i * 40.0 + 10.0)
                hn.add(Shape(path=path_circle(math.cos(a) * R * 1.28,
                                              math.sin(a) * R * 1.28, R * 0.62),
                             fill=lighten(mane, -0.05 if i % 2 else 0.0)))
            hn.add(Shape(path=path_circle(0.0, 0.0, R * 1.45), fill=mane))
        self._ear(hn, R, far=True)
        if "antlers" in sp["extras"]:
            self._antler(hn, R, -R * 0.28, shade=-0.13)
            self._antler(hn, R, R * 0.18, shade=0.0)
        if "horns" in sp["extras"]:
            for x0, s in ((-R * 0.38, -0.16), (R * 0.1, -0.04)):
                hn.add(Shape(path=path_line([(x0, R * 0.68), (x0 + R * 0.2, R * 1.12),
                                             (x0 + R * 0.52, R * 1.28)]),
                             stroke=Stroke(paint=lighten(_HORN, s), width=R * 0.2)))
        # skull
        hn.add(Shape(path=path_ellipse(0.0, 0.0, R * 1.0, R * 0.94), fill=face_c))
        if "wool" in sp["extras"]:
            for (x, y, r) in ((-0.55, 0.75, 0.4), (0.0, 0.92, 0.45), (0.55, 0.7, 0.38)):
                hn.add(Shape(path=path_circle(x * R, y * R, r * R), fill=skin))
        # muzzle + jaw (species may replace with trunk)
        if "trunk" in sp["extras"]:
            self._trunk(hn, R, m)
        else:
            self._muzzle(hn, R, m, face_c, muzz_c, sp)
        self._ear(hn, R, far=False)
        self._eyes(hn, R, m, face_c)
        if "mane" in sp["extras"]:  # horse forelock
            hn.add(Shape(path=path_ellipse(R * 0.1, R * 0.78, R * 0.5, R * 0.32),
                         fill=st["hair_rgba"]))

    # -------------------------------------------------------------- features

    def _muzzle(self, hn: Node, R: float, m: Dict[str, float],
                face_c: RGBA, muzz_c: RGBA, sp: dict) -> None:
        mlen = self.dim["muzzle"]
        tipx = R * 0.45 + mlen
        lip_y = -R * 0.34
        open_amt = float(m.get("mouth_open", 0.0))
        # dropped jaw: rotate about a pivot at the back of the muzzle
        px, py = R * 0.1, lip_y
        if open_amt > 0.04:
            ang = open_amt * 30.0
            ca, sa = math.cos(math.radians(-ang)), math.sin(math.radians(-ang))
            jx = px + (tipx - px) * ca
            jy = py + (tipx - px) * sa
            hn.add(Shape(path=path_polygon([(px, py + R * 0.06),
                                            (tipx, py + R * 0.06), (jx, jy)]),
                         fill=_MOUTH_DARK))
            if open_amt > 0.35:
                hn.add(Shape(path=path_ellipse((px + jx) / 2, (py + jy) / 2,
                                               (tipx - px) * 0.3, R * 0.1),
                             fill=_TONGUE))
            jaw = Node(transform=chain(translation(px, py), rotation(-ang)))
            jaw.add(Shape(path=path_taper(0.0, -R * 0.06, tipx - px - R * 0.06,
                                          -R * 0.04, R * 0.18, R * 0.12),
                          fill=lighten(muzz_c, -0.06)))
            hn.children.append(jaw)
        # upper muzzle
        hn.add(Shape(path=path_taper(R * 0.05, -R * 0.14, tipx - R * 0.1, -R * 0.18,
                                     R * 0.46, R * 0.28), fill=muzz_c))
        if "snout" in sp["extras"]:   # pig disc snout
            sc = lighten(self.style["skin_rgba"], -0.1)
            hn.add(Shape(path=path_ellipse(tipx + R * 0.02, -R * 0.1,
                                           R * 0.2, R * 0.26), fill=sc))
            for dy in (-R * 0.18, -R * 0.02):
                hn.add(Shape(path=path_circle(tipx + R * 0.06, dy, R * 0.045),
                             fill=_NOSE))
        else:
            hn.add(Shape(path=path_circle(tipx + R * 0.02, -R * 0.02, R * 0.14),
                         fill=_NOSE))
        if open_amt <= 0.04:          # closed: a soft mouth line with smile
            smile = float(m.get("smile", 0.0))
            pts = []
            for i in range(7):
                u = i / 6.0
                x = tipx - R * 0.05 - u * mlen * 0.6 - R * 0.15
                y = lip_y + R * 0.04 - math.sin(u * math.pi) * smile * R * 0.1
                pts.append((x, y))
            hn.add(Shape(path=path_line(pts),
                         stroke=Stroke(paint=lighten(muzz_c, -0.28),
                                       width=R * 0.05)))

    def _trunk(self, hn: Node, R: float, m: Dict[str, float]) -> None:
        skin = self.style["skin_rgba"]
        open_amt = float(m.get("mouth_open", 0.0))
        # mouth behind the trunk base
        if open_amt > 0.04:
            hn.add(Shape(path=path_ellipse(R * 0.5, -R * 0.55, R * 0.22,
                                           R * (0.06 + 0.2 * open_amt)),
                         fill=_MOUTH_DARK))
        for sx, col in ((-R * 0.05, lighten(_TUSK, -0.12)), (R * 0.12, _TUSK)):
            hn.add(Shape(path=path_line([(R * 0.55 + sx, -R * 0.42),
                                         (R * 0.85 + sx, -R * 0.55),
                                         (R * 1.05 + sx, -R * 0.45)]),
                         stroke=Stroke(paint=col, width=R * 0.14)))
        # the trunk: chain of tapered segments, curls up when "mouth" opens
        x, y = R * 0.72, -R * 0.05
        a = -38.0
        seg = R * 0.62
        r0 = R * 0.38
        for i, (da, lift) in enumerate(((0.0, 0.0), (-34.0, 40.0), (-32.0, 60.0))):
            a += da + lift * open_amt
            nx = x + seg * math.cos(math.radians(a))
            ny = y + seg * math.sin(math.radians(a))
            r1 = r0 * 0.78
            hn.add(Shape(path=path_taper(x, y, nx, ny, r0, r1), fill=skin))
            x, y, r0 = nx, ny, r1
        hn.add(Shape(path=path_circle(x, y, r0 * 1.05),
                     fill=lighten(skin, -0.1)))

    def _ear(self, hn: Node, R: float, far: bool) -> None:
        sp, st = self.sp, self.style
        skin, skin2 = st["skin_rgba"], st["skin2_rgba"]
        s = R * sp["ear_s"]
        shade = -0.13 if far else 0.0
        col = lighten(skin, shade)
        kind = sp["ear"]
        if kind == "none":
            return
        if kind == "pointy":
            bx = -R * 0.48 if far else R * 0.16
            hn.add(Shape(path=path_polygon([(bx - s * 0.36, R * 0.45),
                                            (bx + s * 0.4, R * 0.5),
                                            (bx + s * 0.06, R * 0.55 + s * 0.85)]),
                         fill=col))
            if not far:
                hn.add(Shape(path=path_polygon([(bx - s * 0.16, R * 0.55),
                                                (bx + s * 0.24, R * 0.58),
                                                (bx + s * 0.06, R * 0.55 + s * 0.58)]),
                             fill=skin2))
        elif kind == "floppy":
            cx = -R * 0.85 if far else -R * 0.38
            e = Node(transform=chain(translation(cx, R * 0.5), rotation(16.0)))
            e.add(Shape(path=path_ellipse(0.0, -s * 0.5, s * 0.38, s * 0.72),
                        fill=lighten(skin, shade - 0.14)))
            hn.children.append(e)
        elif kind == "round":
            cx = -R * 0.6 if far else R * 0.32
            hn.add(Shape(path=path_circle(cx, R * 0.85, s * 0.46), fill=col))
            if not far:
                hn.add(Shape(path=path_circle(cx, R * 0.85, s * 0.28), fill=skin2))
        elif kind == "long":
            bx = -R * 0.38 if far else R * 0.12
            e = Node(transform=chain(translation(bx, R * 0.6),
                                     rotation(-16.0 if far else -6.0)))
            e.add(Shape(path=path_ellipse(0.0, s * 0.8, s * 0.26, s * 0.95),
                        fill=col))
            if not far:
                e.add(Shape(path=path_ellipse(0.0, s * 0.78, s * 0.13, s * 0.68),
                            fill=skin2))
            hn.children.append(e)
        elif kind == "side":
            cx = -R * 0.78 if far else -R * 0.55
            e = Node(transform=chain(translation(cx, R * 0.35),
                                     rotation(150.0 if not far else 165.0)))
            e.add(Shape(path=path_ellipse(s * 0.42, 0.0, s * 0.5, s * 0.24),
                        fill=col))
            hn.children.append(e)
        elif kind == "elephant":
            cx = -R * 0.9 if far else -R * 0.42
            hn.add(Shape(path=path_ellipse(cx, R * 0.1, s * 0.62, s * 0.92),
                         fill=lighten(skin, shade - 0.07)))
            if not far:
                hn.add(Shape(path=path_ellipse(cx - s * 0.06, R * 0.06,
                                               s * 0.44, s * 0.7),
                             fill=lighten(skin, -0.16)))

    def _antler(self, hn: Node, R: float, x0: float, shade: float) -> None:
        col = lighten((0.45, 0.33, 0.2, 1.0), shade)
        w = R * 0.15
        y0 = R * 0.66
        hn.add(Shape(path=path_line([(x0, y0), (x0 - R * 0.38, y0 + R * 0.85),
                                     (x0 - R * 0.55, y0 + R * 1.6)]),
                     stroke=Stroke(paint=col, width=w)))
        hn.add(Shape(path=path_line([(x0 - R * 0.32, y0 + R * 0.75),
                                     (x0 - R * 0.95, y0 + R * 1.1)]),
                     stroke=Stroke(paint=col, width=w * 0.85)))
        hn.add(Shape(path=path_line([(x0 - R * 0.47, y0 + R * 1.25),
                                     (x0 - R * 0.05, y0 + R * 1.72)]),
                     stroke=Stroke(paint=col, width=w * 0.85)))

    # ------------------------------------------------------------------ face

    def _eyes(self, hn: Node, R: float, m: Dict[str, float], face_c: RGBA) -> None:
        iris = self.style.get("eyes_rgba", (0.13, 0.14, 0.17, 1.0))
        er = R * 0.21
        self._eye(hn, -R * 0.24, R * 0.34, er * 0.9, m, iris, face_c)
        self._eye(hn, R * 0.34, R * 0.32, er, m, iris, face_c)
        # brows: tiny, but they carry expression
        brow = lighten(face_c, -0.3)
        raise_amt = float(m.get("brow_raise", 0.0)) * er * 0.8
        angry = float(m.get("brow_angry", 0.0))
        for cx, sign in ((-R * 0.24, 1.0), (R * 0.34, -1.0)):
            tilt = angry * -0.4 * sign * er
            y = R * 0.32 + er * 1.7 + raise_amt
            hn.add(Shape(path=path_line([(cx - er * 0.8, y - tilt),
                                         (cx + er * 0.8, y + tilt)]),
                         stroke=Stroke(paint=brow, width=er * 0.32)))

    @staticmethod
    def _eye(hn: Node, cx: float, cy: float, r: float, m: Dict[str, float],
             iris: RGBA, skin: RGBA) -> None:
        open_amt = 1.0 - float(m.get("blink", 0.0))
        gx = float(m.get("gaze_x", 0.0)) * r * 0.35
        gy = float(m.get("gaze_y", 0.0)) * r * 0.28
        if open_amt <= 0.08:
            hn.add(Shape(path=path_line([(cx - r, cy), (cx + r, cy)]),
                         stroke=Stroke(paint=(0.1, 0.08, 0.08, 1.0),
                                       width=r * 0.28)))
            return
        ry = r * 1.1 * open_amt
        hn.add(Shape(path=path_ellipse(cx, cy, r, ry), fill=(1.0, 1.0, 1.0, 1.0)))
        hn.add(Shape(path=path_circle(cx + gx, cy + gy, r * 0.55), fill=iris))
        hn.add(Shape(path=path_circle(cx + gx + r * 0.16, cy + gy + r * 0.18,
                                      r * 0.12), fill=(1.0, 1.0, 1.0, 0.9)))
        if open_amt < 0.92:   # upper lid
            hn.add(Shape(path=path_ellipse(cx, cy + ry * 1.15, r * 1.08,
                                           ry * (1.0 - open_amt) * 1.4),
                         fill=skin))
