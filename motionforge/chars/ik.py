"""Analytic 2-bone inverse kinematics (legs, arms)."""
from __future__ import annotations

import math
from typing import Tuple


def two_bone_ik(base: Tuple[float, float], target: Tuple[float, float],
                l1: float, l2: float, bend: float = 1.0) -> Tuple[float, float]:
    """World angles (degrees) for the two segments of a 2-bone chain.

    base: chain origin (hip/shoulder). target: desired end point (ankle/wrist).
    l1, l2: segment lengths. bend: +1 bends one way (human knee forward when
    facing right), -1 the other (elbow).

    Returns (upper_world_angle, lower_world_angle). If the target is out of
    reach the chain points straight at it (never overextends or snaps).
    """
    dx = target[0] - base[0]
    dy = target[1] - base[1]
    d = math.hypot(dx, dy)
    d = max(1e-9, min(d, l1 + l2 - 1e-9))
    base_ang = math.atan2(dy, dx)
    # law of cosines
    cos_a = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    cos_a = max(-1.0, min(1.0, cos_a))
    a = math.acos(cos_a)
    upper = base_ang + a * (1.0 if bend >= 0 else -1.0)
    # elbow/knee position
    ex = base[0] + math.cos(upper) * l1
    ey = base[1] + math.sin(upper) * l1
    lower = math.atan2(target[1] - ey, target[0] - ex)
    return math.degrees(upper), math.degrees(lower)
