"""Ragdoll determinism: two sims with identical inputs produce identical
frames, and the sim stays finite and above ground."""
from __future__ import annotations

import math

import pytest

from motionforge.chars.factory import make_rig
from motionforge.dsl.ir import CharacterDef
from motionforge.motion.ragdoll import RagdollSim


def _make_sim():
    rig = make_rig(CharacterDef(name="stunt", body="human",
                                params={"height": 1.7}))
    cur = rig.rest_pose()
    prev = rig.rest_pose()
    return RagdollSim(rig, t0=1.0, t1=2.2, recover=0.5,
                      impulse=(2.5, 3.0),
                      world_pose=cur, world_pos=(0.5, 0.0), facing=1.0,
                      prev_pose=prev, prev_pos=(0.45, 0.0),
                      dt_prev=1.0 / 60.0)


@pytest.fixture(scope="module")
def sims():
    return _make_sim(), _make_sim()


def test_identical_inputs_identical_frames(sims):
    a, b = sims
    assert a.names == b.names
    assert len(a.frames) == len(b.frames)
    assert a.frames == b.frames          # exact float equality, every step


def test_identical_final_pose(sims):
    a, b = sims
    assert a.final_pose.root == b.final_pose.root
    assert a.final_pose.root_angle == b.final_pose.root_angle
    assert a.final_pose.angles == b.final_pose.angles


def test_pose_at_is_a_pure_lookup(sims):
    a, _ = sims
    p1, pos1 = a.pose_at(1.6)
    p2, pos2 = a.pose_at(1.6)
    assert pos1 == pos2 == a.origin
    assert p1.angles == p2.angles
    assert p1.root == p2.root


def test_sim_is_finite_and_respects_ground(sims):
    a, _ = sims
    for frame in a.frames:
        for (x, y) in frame:
            assert math.isfinite(x) and math.isfinite(y)
    # after settling under gravity, no joint may end below the ground plane
    for (x, y) in a.frames[-1]:
        assert y >= -1e-6


def test_fixed_step_frame_count(sims):
    a, _ = sims
    # 1.2 s episode at 120 Hz -> 144 steps (+1 initial snapshot)
    assert len(a.frames) == int(round((a.t1 - a.t0) * 120)) + 1
