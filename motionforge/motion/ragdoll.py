"""Deterministic ragdoll physics.

When a ragdoll direction fires, the character's current pose is captured as
a verlet particle system (joints + distance rods), simulated at a fixed
120 Hz — bit-deterministic — then converted back to rig poses each frame.
On `recover`, the final ragdoll pose blends back into normal animation.

The sim runs eagerly at compile time (a few thousand tiny steps), so
sampling stays a pure lookup.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..chars.bodies.base import CharacterRig
from ..chars.rig import FK, Pose
from ..core.vec import clamp

DT = 1.0 / 120.0
GRAVITY = -9.8
GROUND_R = 0.05
ITERS = 10


@dataclass
class _Rod:
    a: int
    b: int
    length: float


class RagdollSim:
    """One ragdoll episode for one character."""

    def __init__(self, rig: CharacterRig, t0: float, t1: float, recover: float,
                 impulse: Tuple[float, float],
                 world_pose: Pose, world_pos: Tuple[float, float], facing: float,
                 prev_pose: Pose, prev_pos: Tuple[float, float], dt_prev: float):
        self.rig = rig
        self.t0 = t0
        self.t1 = t1
        self.recover = max(recover, 1e-3)
        self.origin = world_pos          # entity origin frozen at capture
        self.facing = facing

        # --- capture joints in character-local space (facing-right frame)
        def local_points(pose: Pose, pos: Tuple[float, float]) -> Dict[str, Tuple[float, float]]:
            fk = FK(rig.skeleton, pose)
            pts: Dict[str, Tuple[float, float]] = {}
            sk = rig.skeleton.bones
            root_name = rig.skeleton.order[0]
            pts["pelvis"] = fk.base_point(root_name)
            # torso top: base of the head bone if present, else root tip
            if rig.head_bone in sk:
                pts["chest"] = fk.base_point(rig.head_bone)
                pts["head"] = fk.tip_point(rig.head_bone)
            else:
                pts["chest"] = fk.tip_point(root_name)
                pts["head"] = fk.tip_point(root_name)
            for group in (rig.legs, rig.arms):
                for key, ch in group.items():
                    if ch.upper not in sk:
                        continue
                    pts[f"{ch.upper}:base"] = fk.base_point(ch.upper)
                    pts[f"{ch.upper}:knee"] = fk.tip_point(ch.upper)
                    pts[f"{ch.upper}:end"] = fk.tip_point(ch.lower)
            return pts

        cur = local_points(world_pose, world_pos)
        prev = local_points(prev_pose, prev_pos)
        # entity position delta contributes to velocity
        dpx = (world_pos[0] - prev_pos[0]) * facing
        dpy = world_pos[1] - prev_pos[1]

        self.names: List[str] = list(cur.keys())
        idx = {n: i for i, n in enumerate(self.names)}
        self.pos: List[Tuple[float, float]] = [cur[n] for n in self.names]
        dt_prev = max(dt_prev, 1e-3)
        scale = DT / dt_prev
        imp = (impulse[0] * facing, impulse[1])
        self.old: List[Tuple[float, float]] = []
        for n in self.names:
            vx = (cur[n][0] - prev[n][0] + dpx) * scale + imp[0] * DT
            vy = (cur[n][1] - prev[n][1] + dpy) * scale + imp[1] * DT
            self.old.append((cur[n][0] - vx, cur[n][1] - vy))

        # --- rods
        self.rods: List[_Rod] = []

        def rod(a: str, b: str) -> None:
            if a in idx and b in idx:
                pa, pb = cur[a], cur[b]
                self.rods.append(_Rod(idx[a], idx[b],
                                      math.hypot(pb[0] - pa[0], pb[1] - pa[1])))

        rod("pelvis", "chest")
        rod("chest", "head")
        self.pins: List[Tuple[int, float]] = []   # (point, lerp along pelvis->chest)
        pv, ch_ = cur["pelvis"], cur["chest"]
        axis = (ch_[0] - pv[0], ch_[1] - pv[1])
        axis_len2 = axis[0] ** 2 + axis[1] ** 2 or 1.0
        for group in (self.rig.legs, self.rig.arms):
            for key, chn in group.items():
                b = f"{chn.upper}:base"
                if b not in idx:
                    continue
                p = cur[b]
                lam = ((p[0] - pv[0]) * axis[0] + (p[1] - pv[1]) * axis[1]) / axis_len2
                self.pins.append((idx[b], clamp(lam, -0.2, 1.2)))
                rod(b, f"{chn.upper}:knee")
                rod(f"{chn.upper}:knee", f"{chn.upper}:end")

        self.frames: List[List[Tuple[float, float]]] = []
        self._simulate()
        self.final_pose = self._pose_from(self.frames[-1])

    # ------------------------------------------------------------- physics

    def _simulate(self) -> None:
        steps = max(1, int(round((self.t1 - self.t0) / DT)))
        ip = {i for i, _ in self.pins}
        for _ in range(steps + 1):
            self.frames.append(list(self.pos))
            new_pos: List[Tuple[float, float]] = []
            for i, (p, o) in enumerate(zip(self.pos, self.old)):
                vx = (p[0] - o[0]) * 0.999
                vy = (p[1] - o[1]) * 0.999
                nx = p[0] + vx
                ny = p[1] + vy + GRAVITY * DT * DT
                new_pos.append((nx, ny))
            self.old = self.pos
            self.pos = new_pos
            for _i in range(ITERS):
                pv = self.pos[self.names.index("pelvis")]
                chp = self.pos[self.names.index("chest")]
                for pi, lam in self.pins:
                    tx = pv[0] + (chp[0] - pv[0]) * lam
                    ty = pv[1] + (chp[1] - pv[1]) * lam
                    self.pos[pi] = (tx, ty)
                for r in self.rods:
                    ax, ay = self.pos[r.a]
                    bx, by = self.pos[r.b]
                    dx, dy = bx - ax, by - ay
                    d = math.hypot(dx, dy) or 1e-9
                    diff = (d - r.length) / d * 0.5
                    wa = 0.0 if r.a in ip else 1.0
                    wb = 0.0 if r.b in ip else 1.0
                    tw = wa + wb or 1.0
                    self.pos[r.a] = (ax + dx * diff * 2 * wa / tw,
                                     ay + dy * diff * 2 * wa / tw)
                    self.pos[r.b] = (bx - dx * diff * 2 * wb / tw,
                                     by - dy * diff * 2 * wb / tw)
                # ground
                for i, (px, py) in enumerate(self.pos):
                    if py < GROUND_R:
                        ox, oy = self.old[i]
                        vx = (px - ox) * 0.6      # friction
                        self.pos[i] = (px, GROUND_R)
                        self.old[i] = (px - vx, oy)

    # ------------------------------------------------------- pose recovery

    def _dir(self, pts, a: str, b: str) -> float:
        i, j = self.names.index(a), self.names.index(b)
        return math.degrees(math.atan2(pts[j][1] - pts[i][1],
                                       pts[j][0] - pts[i][0]))

    def _pose_from(self, pts: List[Tuple[float, float]]) -> Pose:
        rig = self.rig
        sk = rig.skeleton.bones
        i_pelvis = self.names.index("pelvis")
        pose = Pose(root=pts[i_pelvis])
        torso_dir = self._dir(pts, "pelvis", "chest")
        root_name = rig.skeleton.order[0]
        rest_dir = sk[root_name].rest
        pose.root_angle = torso_dir - rest_dir
        # zero out torso chain deviations, aim the head
        for b in ("spine", "chest", "neck"):
            if b in sk:
                pose.angles[b] = 0.0
        if rig.head_bone in sk and "head" in self.names:
            head_dir = self._dir(pts, "chest", "head")
            pose.angles[rig.head_bone] = head_dir - torso_dir
            # walk up the head bone's ancestors: they were zeroed, so the
            # accumulated rest offsets must be subtracted
            rest_acc = 0.0
            b = rig.head_bone
            while b is not None and b != root_name:
                rest_acc += sk[b].rest
                b = sk[b].parent
            pose.angles[rig.head_bone] -= rest_acc - 0.0
        for group in (rig.legs, rig.arms):
            for key, ch in group.items():
                base = f"{ch.upper}:base"
                if base not in self.names:
                    continue
                up_dir = self._dir(pts, base, f"{ch.upper}:knee")
                lo_dir = self._dir(pts, f"{ch.upper}:knee", f"{ch.upper}:end")
                parent = sk[ch.upper].parent
                # parent world dir: torso-aligned
                p_dir = torso_dir - rest_dir + self._chain_rest(parent, root_name, sk)
                pose.angles[ch.upper] = up_dir - p_dir - sk[ch.upper].rest
                pose.angles[ch.lower] = lo_dir - up_dir - sk[ch.lower].rest
                if ch.end in sk:
                    pose.angles[ch.end] = 0.0
        pose.morphs["blink"] = 1.0
        return pose

    @staticmethod
    def _chain_rest(bone: Optional[str], root_name: str, sk) -> float:
        acc = 0.0
        b = bone
        while b is not None:
            acc += sk[b].rest
            b = sk[b].parent
        return acc

    # ------------------------------------------------------------ sampling

    def pose_at(self, t: float) -> Tuple[Pose, Tuple[float, float]]:
        """(pose, world entity position) during the episode."""
        u = (t - self.t0) / DT
        i = int(clamp(u, 0, len(self.frames) - 1))
        pts = self.frames[i]
        pose = self._pose_from(pts)
        # keep the entity origin fixed; the pose root carries all movement
        return pose, self.origin
