"""CharacterRig: the contract every body template fulfils.

A rig owns a skeleton + style and can draw itself for any Pose. It also
publishes the metadata the motion system needs (leg/arm chains, hip height)
so gait and IK are body-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from ...scene.graph import Node
from ..rig import FK, Pose, Skeleton


@dataclass
class Chain2:
    """A 2-bone IK chain (leg or arm)."""
    upper: str            # bone name (thigh / upper_arm)
    lower: str            # bone name (shin / forearm)
    end: str              # bone name (foot / hand)
    bend: float           # IK bend direction (+1 knee, -1 elbow for humans)
    end_length: float     # foot/hand length (m)


class CharacterRig:
    def __init__(self, name: str, skeleton: Skeleton, style: dict, height: float):
        self.name = name
        self.skeleton = skeleton
        self.style = style
        self.height = height
        self.hip_height: float = height * 0.5
        self.legs: Dict[str, Chain2] = {}       # 'near'/'far' (quadruped: 4 keys)
        self.arms: Dict[str, Chain2] = {}
        self.head_bone: str = "head"
        self.head_radius: float = height * 0.07
        self.stance_offset: Dict[str, float] = {}  # foot x offsets at rest

    # -------------------------------------------------------------- drawing

    def node(self, pose: Pose) -> Node:
        fk = FK(self.skeleton, pose)
        return self.draw(fk, pose)

    def draw(self, fk: FK, pose: Pose) -> Node:  # implemented per body
        raise NotImplementedError

    # ------------------------------------------------------------- standing

    def rest_pose(self) -> Pose:
        return Pose(root=(0.0, self.hip_height))
