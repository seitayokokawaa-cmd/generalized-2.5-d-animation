"""The fish body template: streamlined swimmers from goldfish to whales.

Authored facing right (+X forward). The skeleton root sits on the spine near
mid-body: a "head" bone runs forward to the nose while "body1".."body3" and
"tail" run backward, so swim actions can wiggle the rear half and the caudal
fin while the face stays stable. Fish have no legs or arms — they float at
their placed height (hip_height = mid-body height above the entity origin).
Species looks (fins, tails, gills, blowholes, teeth) key off style["species"]
with a friendly generic-reef-fish default.

Note on frames: the backward spine bones are rotated 180 degrees, so in their
local coordinates +X points toward the tail and *up is -Y*. The head bone
frame is upright (+X to the nose, +Y up).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from ...core.color import RGBA, lighten
from ...core.transform import chain, rotation, translation
from ...draw.canvas import (Seg, Shape, Stroke, path_circle, path_ellipse,
                            path_line, path_polygon, path_taper)
from ...scene.graph import Node
from ..rig import FK, Bone, Pose, Skeleton
from .base import CharacterRig

_MOUTH_DARK: RGBA = (0.25, 0.09, 0.10, 1.0)
_TEETH: RGBA = (0.97, 0.96, 0.92, 1.0)

# ---------------------------------------------------------------- species table
# Every factor has a generic default; unknown species get _DEF.
#   body_f  spine length (nose..peduncle) / size      depth  half-depth / spine
#   nose    nose cap radius (in body half-depths: 1 = blunt, 0.25 = pointy)
#   eye_x/eye_y  eye position (fractions of front length / half-depth)
#   dorsal  round|triangle|flowy|bump   tail  fork|fan|crescent|fluke
#   tail_h  caudal fin half-height / size    pect  round|pointed
#   gill    arc|slits|none               mouth  small|under|long
_DEF = dict(body_f=0.72, depth=0.28, nose=0.62,
            eye_x=0.58, eye_y=0.34, eye_f=1.0,
            dorsal="round", dorsal_f=1.0,
            tail="fork", tail_h=0.15,
            pect="round", pect_f=1.0, pect_x=0.12, pect_y=-0.30, pect_ang=-140.0,
            gill="arc", mouth="small", smile0=0.25,
            anal=True, extras=())

SPECIES: Dict[str, dict] = {
    "_default": dict(_DEF),
    "goldfish": dict(_DEF, body_f=0.60, depth=0.38, nose=0.80,
                     eye_x=0.55, eye_y=0.28, eye_f=1.25,
                     dorsal="flowy", tail="fan", tail_h=0.20, pect_f=1.1),
    "shark":   dict(_DEF, body_f=0.80, depth=0.20, nose=0.30,
                    eye_x=0.60, eye_y=0.42, eye_f=0.72,
                    dorsal="triangle", dorsal_f=1.3, tail="crescent",
                    tail_h=0.19, pect="pointed", pect_f=1.15,
                    gill="slits", mouth="under", smile0=-0.3,
                    extras=("teeth", "pale_belly")),
    "whale":   dict(_DEF, body_f=0.78, depth=0.31, nose=0.90,
                    eye_x=0.68, eye_y=0.04, eye_f=0.6,
                    dorsal="bump", tail="fluke", tail_h=0.18,
                    pect="round", pect_f=1.1, pect_x=-0.04, pect_y=-0.62,
                    pect_ang=-152.0, gill="none", mouth="long",
                    smile0=0.5, anal=False, extras=("blowhole", "grooves")),
    "salmon":  dict(_DEF, body_f=0.78, depth=0.23, nose=0.38,
                    eye_x=0.64, eye_y=0.32, eye_f=0.9,
                    dorsal="triangle", dorsal_f=0.75, tail="fork",
                    tail_h=0.14, extras=("adipose", "spots")),
}


def build_fish(name: str, params: Dict, style: dict) -> "FishRig":
    S = float(params.get("size") or params.get("height") or 0.5)
    return FishRig(name, S, style)


class FishRig(CharacterRig):
    def __init__(self, name: str, S: float, style: dict):
        sp = SPECIES.get(style.get("species", ""), SPECIES["_default"])
        self.sp = sp
        bl = S * sp["body_f"]                    # spine: nose .. peduncle
        ry = bl * sp["depth"]                    # body half-depth at the root
        front = bl * 0.42                        # root .. nose
        back = bl - front                        # root .. peduncle
        ext = S - bl                             # peduncle .. caudal fin tip
        fh = S * sp["tail_h"]                    # caudal fin half-height
        self.dim = {
            "S": S, "bl": bl, "ry": ry, "front": front, "ext": ext, "fh": fh,
            "seg1": back * 0.36, "seg2": back * 0.33, "seg3": back * 0.31,
            "tailb": ext * 0.5,
            "nose_r": max(ry * sp["nose"], 0.01 * S),
            # half-depth of the body at the root and at each spine joint
            "radii": [ry, ry * 0.88, ry * 0.60, max(ry * 0.26, 0.015 * S)],
        }
        d = self.dim
        bones: List[Bone] = [
            Bone("body1", None, d["seg1"], (0.0, 0.0), 180.0),
            Bone("body2", "body1", d["seg2"], (d["seg1"], 0.0), 0.0),
            Bone("body3", "body2", d["seg3"], (d["seg2"], 0.0), 0.0),
            Bone("tail", "body3", d["tailb"], (d["seg3"], 0.0), 0.0),
            Bone("head", "body1", front, (0.0, 0.0), 180.0),   # points forward
        ]
        super().__init__(name, Skeleton(bones), style, S)
        # floats: the spine sits at hip_height above the entity origin, high
        # enough that neither the belly nor the caudal fin dips below it
        self.hip_height = max(ry, fh * 0.9) + 0.05 * S
        self.head_bone = "head"
        self.head_radius = ry * 0.95
        self.legs = {}
        self.arms = {}

    def rest_pose(self) -> Pose:
        # a gentle relaxed tail droop (positive deviations curl backward bones
        # downward); swim actions wiggle these same angles
        return Pose(root=(0.0, self.hip_height),
                    angles={"body2": 1.0, "body3": 2.0, "tail": 3.0})

    # ----------------------------------------------------------------- draw

    def draw(self, fk: FK, pose: Pose) -> Node:
        st = self.style
        skin: RGBA = st["skin_rgba"]
        belly: RGBA = (lighten(skin, 0.30) if "pale_belly" in self.sp["extras"]
                       else st["skin2_rgba"])
        n = Node(name=self.name)
        self._pectoral(n, fk, far=True)
        self._caudal(n, fk, skin, st["skin2_rgba"])
        self._dorsal(n, fk, skin)
        if self.sp["anal"]:
            self._anal(n, fk, skin)
        self._spine(n, fk, skin)
        self._front(n, fk, pose, skin, belly)
        self._pectoral(n, fk, far=False)
        return n

    # ------------------------------------------------------------ body masses

    def _spine(self, n: Node, fk: FK, skin: RGBA) -> None:
        d = self.dim
        rr = d["radii"]
        for i, bone in enumerate(("body1", "body2", "body3")):
            L = self.skeleton.bones[bone].length
            n.add(Shape(path=path_taper(-L * 0.12, 0.0, L, 0.0, rr[i], rr[i + 1]),
                        fill=skin, transform=fk.base[bone]))
        # peduncle: slim bridge to the caudal fin (tail frame, +X backward)
        tb = d["tailb"]
        n.add(Shape(path=path_taper(-tb * 0.25, 0.0, tb * 0.9, 0.0,
                                    rr[3], rr[3] * 0.8),
                    fill=skin, transform=fk.base["tail"]))
        if "spots" in self.sp["extras"]:   # salmon: dots along the upper back
            spot = lighten(skin, -0.14)
            for bone, u, v in (("body1", 0.25, -0.52), ("body1", 0.62, -0.38),
                               ("body2", 0.30, -0.42), ("body2", 0.72, -0.20),
                               ("body3", 0.40, -0.25)):
                L = self.skeleton.bones[bone].length
                i = ("body1", "body2", "body3").index(bone)
                r_here = rr[i] + (rr[i + 1] - rr[i]) * u
                n.add(Shape(path=path_circle(L * u, r_here * v, d["bl"] * 0.022),
                            fill=spot, transform=fk.base[bone]))

    def _front(self, n: Node, fk: FK, pose: Pose, skin: RGBA,
               belly: RGBA) -> None:
        """Head half of the body + belly, gills, face (head frame, +Y up)."""
        d, sp = self.dim, self.sp
        front, ry, nr = d["front"], d["ry"], d["nose_r"]
        m = pose.morphs
        hm = fk.base["head"]
        # start well behind the root so the cap edge never lines up with the
        # body1 cap edge (coincident same-color edges leave an AA seam)
        n.add(Shape(path=path_taper(-front * 0.22, 0.0, front - nr, 0.0, ry, nr),
                    fill=skin, transform=hm))
        # belly accent hugging the lower half, front body only
        n.add(Shape(path=path_ellipse(front * 0.10, -ry * 0.50,
                                      front * 0.78, ry * 0.46),
                    fill=belly, transform=hm))
        if "grooves" in sp["extras"]:      # whale throat pleats
            g = lighten(belly, -0.12)
            for yy in (0.42, 0.60, 0.78):
                n.add(Shape(path=path_line([(front * 0.72, -ry * (yy - 0.06)),
                                            (front * 0.38, -ry * yy),
                                            (front * 0.06, -ry * (yy + 0.02))]),
                            stroke=Stroke(paint=g, width=d["bl"] * 0.010),
                            transform=hm))
        self._gill(n, hm, skin)
        if "blowhole" in sp["extras"]:
            n.add(Shape(path=path_ellipse(front * 0.30, ry * 0.88,
                                          d["bl"] * 0.045, d["bl"] * 0.020),
                        fill=lighten(skin, -0.30), transform=hm))
        self._mouth(n, hm, m, skin)
        self._eye(n, hm, m, skin)

    # ------------------------------------------------------------------ fins

    def _dorsal(self, n: Node, fk: FK, skin: RGBA) -> None:
        """Top fin. body1/body2 frames: +X backward, up is -Y."""
        d, sp = self.dim, self.sp
        bl, r0 = d["bl"], d["radii"][0]
        kind, f = sp["dorsal"], sp["dorsal_f"]
        col = lighten(skin, -0.07)
        if kind == "triangle":             # shark / salmon: raked blade
            w, h = bl * 0.26 * f, bl * 0.30 * f
            x0 = d["seg1"] * 0.02
            n.add(Shape(path=path_polygon([
                (x0, -r0 * 0.70), (x0 + w * 0.42, -(r0 * 0.70 + h)),
                (x0 + w * 0.72, -(r0 * 0.70 + h * 0.48)),
                (x0 + w * 1.12, -r0 * 0.55)]),
                fill=col, transform=fk.base["body1"]))
        elif kind == "flowy":              # goldfish: soft swept sail
            fin = Node(transform=chain(fk.base["body1"],
                                       translation(d["seg1"] * 0.12, -r0 * 0.82),
                                       rotation(-42.0)))
            fin.add(Shape(path=path_ellipse(bl * 0.17, 0.0,
                                            bl * 0.22 * f, bl * 0.095 * f),
                          fill=col))
            fin.add(Shape(path=path_ellipse(bl * 0.24, bl * 0.035,
                                            bl * 0.14 * f, bl * 0.055 * f),
                          fill=lighten(skin, 0.06)))
            n.children.append(fin)
        elif kind == "bump":               # whale: small nub far back
            w, h = bl * 0.13, bl * 0.075
            r1 = self.dim["radii"][1]
            n.add(Shape(path=path_polygon([
                (d["seg2"] * 0.25, -r1 * 0.75),
                (d["seg2"] * 0.25 + w * 0.38, -(r1 * 0.75 + h)),
                (d["seg2"] * 0.25 + w, -r1 * 0.60)]),
                fill=col, transform=fk.base["body2"]))
        else:                              # generic: low swept half-moon
            fin = Node(transform=chain(fk.base["body1"],
                                       translation(d["seg1"] * 0.28, -r0 * 0.72),
                                       rotation(-20.0)))
            fin.add(Shape(path=path_ellipse(bl * 0.10, 0.0,
                                            bl * 0.21 * f, bl * 0.082 * f),
                          fill=col))
            n.children.append(fin)
        if "adipose" in sp["extras"]:      # salmon: tiny nub near the tail
            r2 = self.dim["radii"][2]
            n.add(Shape(path=path_ellipse(d["seg3"] * 0.45, -r2 * 0.85,
                                          bl * 0.045, bl * 0.032),
                        fill=col, transform=fk.base["body3"]))

    def _anal(self, n: Node, fk: FK, skin: RGBA) -> None:
        """Small lower fin under the rear body (body2 frame: up is -Y)."""
        d = self.dim
        r1 = d["radii"][1]
        fin = Node(transform=chain(fk.base["body2"],
                                   translation(d["seg2"] * 0.45, r1 * 0.62),
                                   rotation(32.0)))
        fin.add(Shape(path=path_ellipse(d["bl"] * 0.055, 0.0,
                                        d["bl"] * 0.085, d["bl"] * 0.045),
                      fill=lighten(skin, -0.07)))
        n.children.append(fin)

    def _pectoral(self, n: Node, fk: FK, far: bool) -> None:
        """Side fin behind the gill (head frame, +Y up)."""
        d, sp = self.dim, self.sp
        skin = self.style["skin_rgba"]
        col = lighten(skin, -0.13 if far else -0.04)
        pl = d["bl"] * 0.20 * sp["pect_f"]
        base = translation(d["front"] * (sp["pect_x"] - (0.08 if far else 0.0)),
                           d["ry"] * sp["pect_y"])
        ang = sp["pect_ang"] - (12.0 if far else 0.0)    # points down-back
        fin = Node(transform=chain(fk.base["head"], base, rotation(ang)))
        if sp["pect"] == "pointed":
            fin.add(Shape(path=path_polygon([
                (0.0, pl * 0.16), (pl * 1.05, -pl * 0.06),
                (pl * 0.55, -pl * 0.22), (0.0, -pl * 0.16)]), fill=col))
        else:
            fin.add(Shape(path=path_ellipse(pl * 0.48, 0.0, pl * 0.55,
                                            pl * 0.26), fill=col))
        n.children.append(fin)

    # ------------------------------------------------------------- caudal fin

    def _caudal(self, n: Node, fk: FK, skin: RGBA, skin2: RGBA) -> None:
        """Tail fin at the peduncle (tail frame: +X backward, up is -Y)."""
        d, sp = self.dim, self.sp
        kind = sp["tail"]
        rb = d["radii"][3]
        x0 = d["tailb"] * 0.70
        fl = max(d["ext"] - x0, d["ext"] * 0.5)
        fh = d["fh"]
        tn = Node(transform=fk.base["tail"], name="caudal")
        n.children.append(tn)
        if kind == "fan":                  # goldfish: three flowy petals
            for ang, lf, col in ((-30.0, 1.0, skin),
                                 (26.0, 0.95, lighten(skin, -0.06)),
                                 (-2.0, 0.74, skin2)):
                p = Node(transform=chain(translation(x0, 0.0), rotation(ang)))
                p.add(Shape(path=path_ellipse(fl * 0.55 * lf, 0.0,
                                              fl * 0.58 * lf, fl * 0.24),
                            fill=col))
                tn.children.append(p)
            tn.add(Shape(path=path_circle(x0, 0.0, rb * 1.1), fill=skin))
            return
        rnd = 1.04
        if kind == "crescent":             # shark: big top lobe, swept
            tt: Tuple[float, float] = (fl * 1.15, fh * 1.15)
            bt: Tuple[float, float] = (fl * 0.58, -fh * 0.78)
            notch = 0.48
        elif kind == "fluke":              # whale: broad round symmetric lobes
            fl *= 1.3
            tt, bt, notch, rnd = (fl, fh), (fl, -fh), 0.32, 1.18
        else:                              # fork (generic / salmon)
            tt, bt, notch = (fl * 1.0, fh * 0.85), (fl * 0.95, -fh * 0.80), 0.42
        tn.add(Shape(path=self._caudal_path(x0, rb, fl, tt, bt, notch, rnd),
                     fill=lighten(skin, -0.05)))

    @staticmethod
    def _caudal_path(x0: float, rb: float, fl: float, tt, bt,
                     notch: float, rnd: float = 1.04) -> List[Seg]:
        """Two-lobed fin outline; built in (back, up) coords, y then flipped."""
        pts: List[Seg] = []

        def M(x: float, u: float) -> None:
            pts.append(("M", x, -u))

        def C(x1, u1, x2, u2, x, u) -> None:
            pts.append(("C", x1, -u1, x2, -u2, x, -u))

        nx, nu = x0 + fl * notch, 0.0
        M(x0, rb * 0.9)
        C(x0 + tt[0] * 0.30, rb + (tt[1] - rb) * 0.38,
          x0 + tt[0] * 0.78, tt[1] * rnd,
          x0 + tt[0], tt[1])                              # top lobe tip
        C(x0 + tt[0] * 0.72, tt[1] * 0.52,
          nx + fl * 0.14, tt[1] * 0.14, nx, nu)           # into the notch
        C(nx + fl * 0.14, bt[1] * 0.14,
          x0 + bt[0] * 0.72, bt[1] * 0.52,
          x0 + bt[0], bt[1])                              # bottom lobe tip
        C(x0 + bt[0] * 0.78, bt[1] * rnd,
          x0 + bt[0] * 0.30, -rb + (bt[1] + rb) * 0.38,
          x0, -rb * 0.9)
        pts.append(("Z",))
        return pts

    # ------------------------------------------------------------------ face

    def _gill(self, n: Node, hm, skin: RGBA) -> None:
        d, sp = self.dim, self.sp
        front, ry = d["front"], d["ry"]
        kind = sp["gill"]
        if kind == "none":
            return
        col = lighten(skin, -0.18)
        if kind == "slits":                # shark: three short slanted lines
            for i, xx in enumerate((0.10, 0.19, 0.28)):
                x = front * xx
                n.add(Shape(path=path_line([(x + front * 0.02, ry * 0.30),
                                            (x - front * 0.03, -ry * 0.26)]),
                            stroke=Stroke(paint=col, width=d["bl"] * 0.016),
                            transform=hm))
            return
        n.add(Shape(path=[("M", front * 0.17, ry * 0.55),
                          ("C", front * 0.02, ry * 0.24,
                           front * 0.02, -ry * 0.24, front * 0.17, -ry * 0.55)],
                    stroke=Stroke(paint=col, width=d["bl"] * 0.018),
                    transform=hm))

    def _eye(self, n: Node, hm, m: Dict[str, float], skin: RGBA) -> None:
        d, sp = self.dim, self.sp
        cx = d["front"] * sp["eye_x"]
        cy = d["ry"] * sp["eye_y"]
        er = min(d["ry"] * 0.34 * sp["eye_f"], d["front"] * 0.20)
        open_amt = 1.0 - max(0.0, min(1.0, float(m.get("blink", 0.0))))
        gx = float(m.get("gaze_x", 0.0)) * er * 0.32
        gy = float(m.get("gaze_y", 0.0)) * er * 0.25
        e = Node(transform=hm, name="eye")
        n.children.append(e)
        if open_amt <= 0.06:               # closed: a curved lash line
            e.add(Shape(path=path_line([(cx - er * 0.8, cy), (cx + er * 0.8, cy)]),
                        stroke=Stroke(paint=(0.10, 0.08, 0.08, 1.0),
                                      width=er * 0.26)))
            return
        ry_e = er * open_amt
        iris: RGBA = self.style.get("eyes_rgba", (0.13, 0.14, 0.17, 1.0))
        e.add(Shape(path=path_ellipse(cx, cy, er, ry_e), fill=(1.0, 1.0, 1.0, 1.0)))
        e.add(Shape(path=path_circle(cx + gx, cy + gy, er * 0.58), fill=iris))
        e.add(Shape(path=path_circle(cx + gx, cy + gy, er * 0.30),
                    fill=(0.05, 0.05, 0.08, 1.0)))
        e.add(Shape(path=path_circle(cx + gx + er * 0.17, cy + gy + er * 0.19,
                                     er * 0.11), fill=(1.0, 1.0, 1.0, 0.9)))
        if open_amt < 0.94:                # upper lid slides down
            lid_h = ry_e * (1.0 - open_amt) * 1.35
            e.add(Shape(path=path_ellipse(cx, cy + ry_e - lid_h / 2 + ry_e * 0.15,
                                          er * 1.06, max(lid_h, ry_e * 0.1)),
                        fill=skin))

    def _mouth(self, n: Node, hm, m: Dict[str, float], skin: RGBA) -> None:
        d, sp = self.dim, self.sp
        front, ry, bl = d["front"], d["ry"], d["bl"]
        kind = sp["mouth"]
        if kind == "under":                # shark: back under the snout
            mcx, mcy, hw = front * 0.62, -ry * 0.52, bl * 0.14
        elif kind == "long":               # whale: sweeping jawline
            mcx, mcy, hw = front * 0.52, -ry * 0.52, front * 0.42
        else:                              # small: right at the nose
            mcx, mcy, hw = front * 0.84, -ry * 0.32, bl * 0.085
        open_amt = max(0.0, min(1.0, float(m.get("mouth_open", 0.0))))
        smile = float(m.get("smile", 0.0)) + sp["smile0"]
        if open_amt > 0.05:
            if kind == "long":             # keep the whale gape tucked in
                mcx, rx = mcx - hw * 0.25, hw * 0.55
                ryo = bl * (0.02 + 0.075 * open_amt)
            elif kind == "small":          # pull back so the gape stays on the head
                mcx, mcy = front * 0.74, -ry * 0.28
                rx = hw * (0.8 + 0.2 * open_amt)
                ryo = ry * (0.05 + 0.30 * open_amt)   # scale with body depth
            else:
                rx = hw * (0.75 + 0.25 * open_amt)
                ryo = bl * (0.02 + 0.13 * open_amt)
            mn = Node(transform=hm, name="mouth")
            mn.add(Shape(path=path_ellipse(mcx, mcy - ryo * 0.4, rx, ryo),
                         fill=_MOUTH_DARK))
            if "teeth" in sp["extras"] and open_amt > 0.2:
                tw = rx * 2.0 / 4.0
                ytop = mcy - ryo * 0.4 + ryo * 0.75
                for i in range(4):
                    x = mcx - rx + tw * i + tw * 0.12
                    mn.add(Shape(path=path_polygon([
                        (x, ytop), (x + tw * 0.76, ytop),
                        (x + tw * 0.38, ytop - ryo * 0.8)]), fill=_TEETH))
            n.children.append(mn)
            return
        pts = []
        curve = bl * (0.09 if kind == "long" else 0.05)
        for i in range(9):                 # closed: smile-able mouth line
            u = i / 8.0
            x = mcx - hw + 2.0 * hw * u
            # smile > 0 dips the middle and lifts the corners (a "U")
            y = mcy - (math.sin(u * math.pi) - 0.55) * smile * curve
            pts.append((x, y))
        n.add(Shape(path=path_line(pts),
                    stroke=Stroke(paint=lighten(skin, -0.30),
                                  width=bl * (0.015 if kind == "long" else 0.024)),
                    transform=hm))
