"""The human body template: proportion-safe at any height, build, and age."""
from __future__ import annotations

from typing import Dict

from ...core.color import lighten
from ...core.transform import chain, rotation, translation
from ...draw.canvas import (Shape, path_capsule, path_circle, path_ellipse,
                            path_taper)
from ...scene.graph import Node
from ..face import face_node
from ..rig import FK, Bone, Pose, Skeleton
from .base import Chain2, CharacterRig


def build_human(name: str, params: Dict, style: dict) -> "HumanRig":
    H = float(params.get("height", 1.7))
    return HumanRig(name, H, style)


class HumanRig(CharacterRig):
    def __init__(self, name: str, H: float, style: dict):
        age = style.get("age", {"head": 1.0, "limb": 1.0})
        build = float(style.get("build", 1.0))
        limb = age["limb"]
        hip_h = 0.50 * H
        thigh = 0.245 * H * limb
        shin = hip_h - thigh - 0.012 * H            # ankle clearance
        self.dim = {
            "H": H, "hip_h": hip_h, "thigh": thigh, "shin": shin,
            "pelvis": 0.05 * H, "spine": 0.16 * H, "chest": 0.11 * H,
            "neck": 0.035 * H, "head_len": 0.13 * H,
            "uarm": 0.16 * H * limb, "farm": 0.145 * H * limb, "hand": 0.06 * H,
            "foot": 0.115 * H,
            "hip_w": 0.062 * H * build, "shoulder_w": 0.070 * H * build,
            "arm_r": 0.026 * H * build, "leg_r": 0.034 * H * build,
        }
        d = self.dim
        bones = [
            Bone("pelvis", None, d["pelvis"], (0.0, 0.0), 90.0),
            Bone("spine", "pelvis", d["spine"], (d["pelvis"], 0.0), 0.0),
            Bone("chest", "spine", d["chest"], (d["spine"], 0.0), 0.0),
            Bone("neck", "chest", d["neck"], (d["chest"], 0.0), 0.0),
            Bone("head", "neck", d["head_len"], (d["neck"], 0.0), 0.0),
            # legs hang from the pelvis base (hips)
            Bone("thigh_far", "pelvis", d["thigh"], (0.0, 0.0), -180.0),
            Bone("shin_far", "thigh_far", d["shin"], (d["thigh"], 0.0), 0.0),
            Bone("foot_far", "shin_far", d["foot"], (d["shin"], 0.0), 90.0),
            Bone("thigh_near", "pelvis", d["thigh"], (0.0, 0.0), -180.0),
            Bone("shin_near", "thigh_near", d["shin"], (d["thigh"], 0.0), 0.0),
            Bone("foot_near", "shin_near", d["foot"], (d["shin"], 0.0), 90.0),
            # arms hang from the chest tip (shoulders)
            Bone("uarm_far", "chest", d["uarm"], (d["chest"], 0.0), -180.0),
            Bone("farm_far", "uarm_far", d["farm"], (d["uarm"], 0.0), 0.0),
            Bone("hand_far", "farm_far", d["hand"], (d["farm"], 0.0), 0.0),
            Bone("uarm_near", "chest", d["uarm"], (d["chest"], 0.0), -180.0),
            Bone("farm_near", "uarm_near", d["farm"], (d["uarm"], 0.0), 0.0),
            Bone("hand_near", "farm_near", d["hand"], (d["farm"], 0.0), 0.0),
        ]
        super().__init__(name, Skeleton(bones), style, H)
        self.hip_height = hip_h
        self.head_radius = 0.078 * H * age["head"]
        for side in ("near", "far"):
            self.legs[side] = Chain2(f"thigh_{side}", f"shin_{side}", f"foot_{side}",
                                     bend=1.0, end_length=d["foot"])
            self.arms[side] = Chain2(f"uarm_{side}", f"farm_{side}", f"hand_{side}",
                                     bend=-1.0, end_length=d["hand"])

    def rest_pose(self) -> Pose:
        return Pose(root=(0.0, self.hip_height), angles={
            # natural stance: legs slightly split, arms slightly out, soft elbows
            "thigh_near": 5.0, "shin_near": -3.0, "foot_near": -2.0,
            "thigh_far": -5.0, "shin_far": 3.0, "foot_far": 2.0,
            "uarm_near": 12.0, "farm_near": 7.0,
            "uarm_far": -12.0, "farm_far": -7.0,
        })

    # ----------------------------------------------------------------- draw

    def _limb_capsule(self, fk: FK, bone: str, r0: float, r1: float, paint) -> Shape:
        L = self.skeleton.bones[bone].length
        return Shape(path=path_taper(0.0, 0.0, L, 0.0, r0, r1), fill=paint,
                     transform=fk.base[bone])

    def draw(self, fk: FK, pose: Pose) -> Node:
        d = self.dim
        st = self.style
        skin = st["skin_rgba"]
        far_shade = -0.13
        top = st["top_rgba"] if st.get("has_top") else skin
        bottom = st["bottom_rgba"] if st.get("has_bottom") else skin
        shoe = st["shoe_rgba"]
        n = Node(name=self.name)

        def leg(side: str, shade: float) -> None:
            sbot = lighten(bottom, shade)
            sshoe = lighten(shoe, shade)
            n.add(self._limb_capsule(fk, f"thigh_{side}", d["leg_r"], d["leg_r"] * 0.8, sbot))
            n.add(self._limb_capsule(fk, f"shin_{side}", d["leg_r"] * 0.8, d["leg_r"] * 0.55, sbot))
            foot_bone = f"foot_{side}"
            L = self.skeleton.bones[foot_bone].length
            n.add(Shape(path=path_taper(-L * 0.15, 0.0, L * 0.85, 0.0,
                                        d["leg_r"] * 0.55, d["leg_r"] * 0.5),
                        fill=sshoe, transform=fk.base[foot_bone]))

        def arm(side: str, shade: float) -> None:
            stop = lighten(top, shade)
            n.add(self._limb_capsule(fk, f"uarm_{side}", d["arm_r"], d["arm_r"] * 0.85, stop))
            n.add(self._limb_capsule(fk, f"farm_{side}", d["arm_r"] * 0.85, d["arm_r"] * 0.6,
                                     lighten(skin, shade)))
            hand_bone = f"hand_{side}"
            L = self.skeleton.bones[hand_bone].length
            n.add(Shape(path=path_circle(L * 0.5, 0.0, d["hand"] * 0.62),
                        fill=lighten(skin, shade), transform=chain(
                            fk.base[hand_bone], rotation(0))))

        # ---- draw order: far arm, far leg, torso, near leg, head, near arm
        arm("far", far_shade)
        leg("far", far_shade)

        # torso: hips capsule (bottom color) + chest capsule (top color)
        hip_m = fk.base["pelvis"]
        n.add(Shape(path=path_capsule(-d["pelvis"] * 0.9, 0.0, d["pelvis"] * 0.9, 0.0,
                                      d["hip_w"]),
                    fill=bottom, transform=hip_m))
        spine_m = fk.base["spine"]
        torso_len = d["spine"] + d["chest"]
        n.add(Shape(path=path_taper(0.0, 0.0, torso_len, 0.0,
                                    d["hip_w"] * 0.94, d["shoulder_w"]),
                    fill=top, transform=spine_m))

        leg("near", 0.0)

        # neck + head
        n.add(self._limb_capsule(fk, "neck", d["arm_r"] * 0.9, d["arm_r"] * 0.9, skin))
        R = self.head_radius
        head_m = fk.base["head"]
        head_center = chain(head_m, translation(d["head_len"] * 0.55, 0.0),
                            rotation(-90.0))
        hnode = Node(transform=head_center, name="head")
        self._hair_back(hnode, R)
        hnode.add(Shape(path=path_ellipse(0.0, -R + R, R * 0.98, R * 1.04),
                        fill=skin))
        # ear on the far side of the 3/4 face
        hnode.add(Shape(path=path_circle(-R * 0.85, -R * 0.05, R * 0.22), fill=skin))
        hnode.children.append(face_node(R, pose.morphs, st))
        self._hair_front(hnode, R)
        n.children.append(hnode)

        arm("near", 0.0)
        return n

    # ----------------------------------------------------------------- hair

    def _hair_back(self, hnode: Node, R: float) -> None:
        style = self.style.get("hair_style", "short")
        hair = self.style["hair_rgba"]
        if style in ("long",):
            hnode.add(Shape(path=path_ellipse(-R * 0.35, -R * 0.7, R * 0.85, R * 1.25),
                            fill=lighten(hair, -0.06)))
        elif style == "ponytail":
            hnode.add(Shape(path=path_ellipse(-R * 1.05, -R * 0.1, R * 0.32, R * 0.75),
                            fill=lighten(hair, -0.06)))
        elif style == "bun":
            hnode.add(Shape(path=path_circle(-R * 0.9, R * 0.55, R * 0.38), fill=hair))

    def _hair_front(self, hnode: Node, R: float) -> None:
        style = self.style.get("hair_style", "short")
        hair = self.style["hair_rgba"]
        if style in ("none", "bald"):
            return
        if style == "curly":
            for dx, dy, r in ((-0.55, 0.75, 0.45), (0.0, 0.95, 0.5), (0.55, 0.75, 0.45),
                              (-0.85, 0.35, 0.35), (0.85, 0.35, 0.35)):
                hnode.add(Shape(path=path_circle(dx * R, dy * R, r * R), fill=hair))
        elif style == "spiky":
            from ...draw.canvas import path_polygon
            pts = []
            import math
            for i in range(7):
                a = math.pi * (0.15 + 0.7 * i / 6)
                r_out = R * (1.35 if i % 2 == 0 else 1.02)
                pts.append((math.cos(a) * r_out, math.sin(a) * r_out * 0.95))
            pts += [(-R * 0.95, R * 0.1), (R * 0.95, R * 0.1)][::-1]
            hnode.add(Shape(path=path_polygon(pts), fill=hair))
        else:
            # short / bun / ponytail / long share a fitted cap (top half of the head)
            hnode.add(Shape(path=[("M", R * 1.02, R * 0.02),
                                  ("A", 0.0, R * 0.02, R * 1.02, 0.0, 3.14159),
                                  ("Z",)],
                            fill=hair))
            hnode.add(Shape(path=path_ellipse(R * 0.55, R * 0.72, R * 0.5, R * 0.28),
                            fill=hair))
