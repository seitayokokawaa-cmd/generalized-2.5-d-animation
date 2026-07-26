"""Special locomotion generators: jump, climb, swim, fly.

Same contract as gait.biped_pose: pure functions of segment-relative
progress, entity-local pose + path-space position out.
"""
from __future__ import annotations

import math
from typing import Tuple

from ..chars.bodies.base import CharacterRig
from ..chars.rig import FK, Pose
from ..core.vec import clamp, lerp
from .gait import LocoState, _solve_leg


def jump_pose(rig: CharacterRig, u: float, p0: Tuple[float, float],
              p1: Tuple[float, float], duration: float, facing: float,
              height: float = 0.0) -> LocoState:
    """One whole jump over the segment: crouch, flight, land-absorb.

    u: raw 0..1 progress. Path x eases through flight; y follows a parabola
    cleared above the higher endpoint by `height` (default: auto).
    """
    leg = rig.height * 0.48
    crouch_t, land_t = 0.18, 0.82
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    apex = max(height, abs(dx) * 0.18 + max(dy, 0.0) * 0.6 + rig.height * 0.25)

    pose = rig.rest_pose()
    airborne = False
    hip_adj = 0.0                       # local hip drop (crouch/absorb)
    if u < crouch_t:
        k = (u / crouch_t) ** 2
        x_off, y_off = 0.0, 0.0
        hip_adj = -leg * 0.35 * k
        lean = -14.0 * k
        legs_bend = 55.0 * k
        arms = -50.0 * k
    elif u < land_t:
        w = (u - crouch_t) / (land_t - crouch_t)
        airborne = True
        x_off = dx * w
        y_off = lerp(0.0, dy, w) + math.sin(w * math.pi) * apex
        lean = 8.0 * math.sin(w * math.pi)
        legs_bend = 35.0 + 40.0 * math.sin(w * math.pi)
        arms = 60.0 * math.sin(w * math.pi * 0.8) + 20.0
    else:
        k = (u - land_t) / (1.0 - land_t)
        absorb = math.sin(k * math.pi)
        x_off, y_off = dx, dy
        hip_adj = -leg * 0.30 * absorb
        lean = -10.0 * absorb
        legs_bend = 50.0 * absorb
        arms = -30.0 * absorb

    pose.root = (0.0, rig.hip_height + hip_adj)
    pose.root_angle = lean
    if airborne:
        # tuck: legs bend freely in the air
        pose.angles.update({
            "thigh_near": 30.0 + legs_bend * 0.6, "shin_near": -legs_bend,
            "thigh_far": 15.0 + legs_bend * 0.5, "shin_far": -legs_bend * 0.9,
            "foot_near": 15.0, "foot_far": 15.0,
        })
    else:
        # grounded: feet planted at start/end, knees bend via IK
        fk0 = FK(rig.skeleton, Pose(root=pose.root, root_angle=pose.root_angle,
                                    angles=dict(pose.angles)))
        ankle = leg * 0.05
        for key, ch in rig.legs.items():
            sx = 0.05 * leg if key == "near" else -0.05 * leg
            _solve_leg(rig, fk0, pose, ch, (sx - 0.0, ankle), 0.0)
    for key, sign in (("near", 1.0), ("far", -1.0)):
        arm = rig.arms.get(key)
        if arm:
            pose.angles[arm.upper] = arms * sign if not airborne else abs(arms) * sign * 1.6
            pose.angles[arm.lower] = 15.0
    return LocoState(pos=(x_off, y_off), facing=facing, pose=pose,
                     phase=u * 2.0, airborne=airborne)


def climb_pose(rig: CharacterRig, dist: float, total: float, facing: float) -> LocoState:
    """Ladder/wall climb: body vertical, alternating reaches. Path is mostly +Y."""
    leg = rig.height * 0.48
    cycle = leg * 0.55
    phi = dist / max(cycle, 1e-9)
    w = math.sin(phi * math.pi)
    v = math.sin(phi * math.pi + math.pi)
    pose = rig.rest_pose()
    pose.root = (0.0, rig.hip_height * 0.92)
    pose.root_angle = 4.0
    pose.angles.update({
        "uarm_near": 150.0 + w * 20.0, "farm_near": 30.0 + max(0.0, -w) * 40.0,
        "uarm_far": -150.0 + v * -20.0, "farm_far": -30.0 - max(0.0, -v) * 40.0,
        "thigh_near": 55.0 + w * 30.0, "shin_near": -70.0 - w * 20.0,
        "thigh_far": 55.0 + v * 30.0, "shin_far": -70.0 - v * 20.0,
        "foot_near": 20.0, "foot_far": 20.0,
        "head": 12.0,
    })
    return LocoState(pos=(0.0, dist), facing=facing, pose=pose, phase=phi)


def swim_pose(rig: CharacterRig, dist: float, total: float, t: float,
              facing: float) -> LocoState:
    """Front-crawl-ish swim: body horizontal, alternating strokes, flutter kick."""
    stroke = math.sin(t * 2 * math.pi / 1.1)
    stroke2 = math.sin(t * 2 * math.pi / 1.1 + math.pi)
    kick = math.sin(t * 2 * math.pi / 0.45)
    pose = rig.rest_pose()
    pose.root = (0.0, rig.height * 0.32)
    pose.root_angle = -78.0
    pose.angles.update({
        "head": 55.0, "neck": 12.0,
        "uarm_near": 110.0 + stroke * 80.0, "farm_near": 25.0 + abs(stroke) * 30.0,
        "uarm_far": -110.0 + stroke2 * -80.0, "farm_far": -25.0 - abs(stroke2) * 30.0,
        "thigh_near": 8.0 + kick * 14.0, "shin_near": -10.0 - kick * 10.0,
        "thigh_far": -8.0 - kick * 14.0, "shin_far": -10.0 + kick * 10.0,
        "foot_near": 35.0, "foot_far": 35.0,
    })
    return LocoState(pos=(dist, 0.0), facing=facing, pose=pose,
                     phase=t * 1.8, airborne=True)


def fish_swim_pose(rig: CharacterRig, dist: float, total: float, t: float,
                   facing: float) -> LocoState:
    """Fish stay level; a traveling wave runs down the spine to the tail."""
    pose = rig.rest_pose()
    omega = 2 * math.pi / 0.55
    for i, bone in enumerate(("body2", "body3", "tail")):
        if bone in rig.skeleton.bones:
            pose.angles[bone] = math.sin(t * omega - i * 0.9) * (5.0 + i * 8.0)
    pose.root = (0.0, pose.root[1])
    return LocoState(pos=(dist, 0.0), facing=facing, pose=pose,
                     phase=t * 2.0, airborne=True)


def fly_pose(rig: CharacterRig, dist: float, total: float, t: float,
             facing: float) -> LocoState:
    """Flight: birds flap their wings; others soar superhero-style."""
    pose = rig.rest_pose()
    flap = math.sin(t * 2 * math.pi / 0.5)
    is_bird = bool(rig.style.get("body") == "bird")
    if is_bird and rig.arms:
        pose.root = (0.0, rig.hip_height)
        pose.root_angle = -8.0
        for key, sign in (("near", 1.0), ("far", -1.0)):
            arm = rig.arms.get(key)
            if arm:
                pose.angles[arm.upper] = sign * (55.0 + flap * 50.0)
                pose.angles[arm.lower] = sign * (15.0 + flap * 25.0)
                pose.angles[arm.end] = sign * (5.0 + flap * 15.0)
        for key, ch in rig.legs.items():
            pose.angles[ch.upper] = 40.0
            pose.angles[ch.lower] = -50.0
    else:
        pose.root = (0.0, rig.height * 0.5)
        pose.root_angle = -72.0
        pose.angles.update({
            "head": 60.0, "neck": 10.0,
            "uarm_near": 165.0, "farm_near": 5.0,
            "uarm_far": -35.0, "farm_far": -8.0,
            "thigh_near": 4.0 + flap * 3.0, "shin_near": -6.0,
            "thigh_far": -4.0 - flap * 3.0, "shin_far": -4.0,
            "foot_near": 30.0, "foot_far": 30.0,
        })
    return LocoState(pos=(dist, 0.0), facing=facing, pose=pose,
                     phase=t * 2.0, airborne=True)
