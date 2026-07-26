"""two_bone_ik: exact reach for reachable targets, graceful clamp otherwise."""
from __future__ import annotations

import math

import pytest

from motionforge.chars.ik import two_bone_ik


def _fk(base, upper_deg, lower_deg, l1, l2):
    """Forward kinematics of the returned world angles -> (elbow, tip)."""
    ur, lr = math.radians(upper_deg), math.radians(lower_deg)
    ex = base[0] + math.cos(ur) * l1
    ey = base[1] + math.sin(ur) * l1
    tx = ex + math.cos(lr) * l2
    ty = ey + math.sin(lr) * l2
    return (ex, ey), (tx, ty)


L1, L2 = 0.42, 0.38
BASE = (0.15, 0.9)

REACHABLE = [
    (0.15, 0.15),        # straight-ish down (near full extension)
    (0.55, 0.55),        # diagonal
    (-0.30, 0.75),       # behind
    (0.15, 0.95),        # very close to the base (folded)
    (0.75, 0.90),        # to the side
    (0.40, 1.40),        # above
]


@pytest.mark.parametrize("target", REACHABLE)
@pytest.mark.parametrize("bend", [1.0, -1.0])
def test_reachable_target_hit_exactly(target, bend):
    d = math.hypot(target[0] - BASE[0], target[1] - BASE[1])
    assert abs(L1 - L2) + 1e-3 < d < L1 + L2 - 1e-3   # test data sanity
    up, lo = two_bone_ik(BASE, target, L1, L2, bend)
    _elbow, tip = _fk(BASE, up, lo, L1, L2)
    assert math.hypot(tip[0] - target[0], tip[1] - target[1]) < 1e-6


def test_bend_direction_flips_the_joint():
    target = (0.55, 0.55)
    up_p, lo_p = two_bone_ik(BASE, target, L1, L2, +1.0)
    up_n, lo_n = two_bone_ik(BASE, target, L1, L2, -1.0)
    elbow_p, tip_p = _fk(BASE, up_p, lo_p, L1, L2)
    elbow_n, tip_n = _fk(BASE, up_n, lo_n, L1, L2)
    # same tip, mirrored joint: the elbow sits on opposite sides of base->target
    assert math.hypot(tip_p[0] - tip_n[0], tip_p[1] - tip_n[1]) < 1e-6
    ax, ay = target[0] - BASE[0], target[1] - BASE[1]
    cross_p = ax * (elbow_p[1] - BASE[1]) - ay * (elbow_p[0] - BASE[0])
    cross_n = ax * (elbow_n[1] - BASE[1]) - ay * (elbow_n[0] - BASE[0])
    assert cross_p * cross_n < 0


@pytest.mark.parametrize("target", [
    (5.0, 0.0),          # far to the side
    (0.15, 9.0),         # far above
    (-4.0, -4.0),        # far diagonal
])
def test_unreachable_target_clamps_without_nan(target):
    up, lo = two_bone_ik(BASE, target, L1, L2, 1.0)
    assert math.isfinite(up) and math.isfinite(lo)
    _elbow, tip = _fk(BASE, up, lo, L1, L2)
    assert all(math.isfinite(c) for c in tip)
    # chain points straight at the target: tip = base + (l1+l2) * unit(dir)
    d = math.hypot(target[0] - BASE[0], target[1] - BASE[1])
    want = (BASE[0] + (target[0] - BASE[0]) / d * (L1 + L2),
            BASE[1] + (target[1] - BASE[1]) / d * (L1 + L2))
    assert math.hypot(tip[0] - want[0], tip[1] - want[1]) < 1e-3


def test_degenerate_target_at_base_no_nan():
    up, lo = two_bone_ik(BASE, BASE, L1, L2, 1.0)
    assert math.isfinite(up) and math.isfinite(lo)
    _elbow, tip = _fk(BASE, up, lo, L1, L2)
    assert all(math.isfinite(c) for c in tip)
