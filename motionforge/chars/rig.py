"""Skeletons, poses, and forward kinematics.

Conventions
-----------
- A bone has a base and a tip, length in meters, and lives in its parent's
  frame: `offset` is the base attachment point in the parent's local frame
  (parent base at origin, +X along the parent bone).
- `rest` is the bone's rest direction in degrees relative to the parent
  bone's direction (for root bones: relative to world +X when facing right).
- A Pose stores *deviations* from rest per bone, so poses blend cleanly and
  a zero pose is always the neutral stance.
- Characters are authored facing right; the entity node mirrors for left.
- The character origin is at the ground between the feet; the pelvis (root
  bone base) sits at `root` (defaults to standing hip height).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.transform import (IDENTITY, Mat, apply, chain, rotation,
                              translation)
from ..core.vec import angle_lerp


@dataclass
class Bone:
    name: str
    parent: Optional[str]
    length: float
    offset: Tuple[float, float] = (0.0, 0.0)   # base point in parent frame
    rest: float = 0.0                          # rest angle rel. to parent dir (deg)


class Skeleton:
    def __init__(self, bones: List[Bone]):
        self.bones: Dict[str, Bone] = {}
        self.order: List[str] = []
        for b in bones:
            if b.parent is not None and b.parent not in self.bones:
                raise ValueError(f"bone '{b.name}' declared before its parent '{b.parent}'")
            self.bones[b.name] = b
            self.order.append(b.name)

    def names(self) -> List[str]:
        return list(self.order)


@dataclass
class Pose:
    root: Tuple[float, float] = (0.0, 0.0)     # root bone base, character space
    root_angle: float = 0.0                    # extra rotation of the whole body
    angles: Dict[str, float] = field(default_factory=dict)   # deviation from rest
    morphs: Dict[str, float] = field(default_factory=dict)   # face & misc 0..1 / -1..1

    def copy(self) -> "Pose":
        return Pose(self.root, self.root_angle, dict(self.angles), dict(self.morphs))


def blend(a: Pose, b: Pose, t: float, mask: Optional[set] = None) -> Pose:
    """Blend b over a by t. If mask given, only bones/morphs in mask move."""
    out = a.copy()
    if mask is None or "__root__" in mask:
        out.root = (a.root[0] + (b.root[0] - a.root[0]) * t,
                    a.root[1] + (b.root[1] - a.root[1]) * t)
        out.root_angle = angle_lerp(a.root_angle, b.root_angle, t)
    keys = set(a.angles) | set(b.angles)
    if mask is not None:
        keys &= mask
    for k in keys:
        out.angles[k] = angle_lerp(a.angles.get(k, 0.0), b.angles.get(k, 0.0), t)
    for k in set(a.morphs) | set(b.morphs):
        if mask is None or k in mask:
            out.morphs[k] = a.morphs.get(k, 0.0) + (b.morphs.get(k, 0.0) - a.morphs.get(k, 0.0)) * t
        else:
            out.morphs.setdefault(k, a.morphs.get(k, 0.0))
    return out


class FK:
    """Forward kinematics solve: world (character-space) transform per bone."""

    def __init__(self, skeleton: Skeleton, pose: Pose):
        self.skeleton = skeleton
        self.pose = pose
        self.base: Dict[str, Mat] = {}      # bone base frame: origin at base, +X along bone
        self._solve()

    def _solve(self) -> None:
        sk = self.skeleton
        root_m = chain(translation(self.pose.root[0], self.pose.root[1]),
                       rotation(self.pose.root_angle))
        for name in sk.order:
            b = sk.bones[name]
            ang = b.rest + self.pose.angles.get(name, 0.0)
            if b.parent is None:
                m = chain(root_m, translation(b.offset[0], b.offset[1]), rotation(ang))
            else:
                pm = self.base[b.parent]
                m = chain(pm, translation(b.offset[0], b.offset[1]), rotation(ang))
            self.base[name] = m

    def base_point(self, bone: str) -> Tuple[float, float]:
        return apply(self.base[bone], (0.0, 0.0))

    def tip_point(self, bone: str) -> Tuple[float, float]:
        return apply(self.base[bone], (self.skeleton.bones[bone].length, 0.0))

    def world_angle(self, bone: str) -> float:
        m = self.base[bone]
        return math.degrees(math.atan2(m[1], m[0]))


def world_angle_to_local(fk: FK, bone: str, world_deg: float) -> float:
    """The pose deviation that makes `bone` point at world_deg (character space)."""
    sk = fk.skeleton
    b = sk.bones[bone]
    if b.parent is None:
        parent_dir = fk.pose.root_angle
    else:
        parent_dir = fk.world_angle(b.parent)
    return world_deg - parent_dir - b.rest
