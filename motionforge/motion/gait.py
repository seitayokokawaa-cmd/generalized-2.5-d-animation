"""The gait engine: procedural locomotion with feet that cannot slide.

Core idea: the *feet own the ground*. Plant positions are fixed world points
computed from the step index (n * step_length along the path); during its
stance window a foot's IK target IS its plant point, so slide is impossible
by construction. The body glides over the feet with an eased speed profile;
swing feet travel plant->next-plant on a lifted arc.

Everything is a pure function of (segment, t): deterministic, seekable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..chars.bodies.base import Chain2, CharacterRig
from ..chars.ik import two_bone_ik
from ..chars.rig import FK, Pose
from ..core.vec import clamp, lerp

# Mode table: parameters that define each locomotion style.
#   step_h: step length as fraction of leg length      duty: stance fraction of a step
#   lift: swing foot lift (fraction of leg)            bob: hip bob (fraction of leg)
#   lean: forward body lean (deg)                      crouch: hip drop (fraction of leg)
#   arm_swing: arm swing amplitude (deg)               elbow: elbow bend (deg)
#   max_speed: validator hint (m/s per meter of height)
GAITS: Dict[str, dict] = {
    "walk":  dict(step_h=0.72, duty=0.62, lift=0.10, bob=0.030, lean=2.0,
                  crouch=0.00, arm_swing=24.0, elbow=12.0, max_speed=1.1),
    "run":   dict(step_h=1.05, duty=0.42, lift=0.22, bob=0.055, lean=12.0,
                  crouch=0.03, arm_swing=45.0, elbow=80.0, max_speed=2.6),
    "sneak": dict(step_h=0.45, duty=0.70, lift=0.14, bob=0.015, lean=16.0,
                  crouch=0.16, arm_swing=8.0, elbow=55.0, max_speed=0.45),
    "march": dict(step_h=0.70, duty=0.58, lift=0.20, bob=0.035, lean=0.0,
                  crouch=0.00, arm_swing=40.0, elbow=5.0, max_speed=1.0),
    "limp":  dict(step_h=0.55, duty=0.66, lift=0.08, bob=0.045, lean=5.0,
                  crouch=0.04, arm_swing=14.0, elbow=20.0, max_speed=0.7,
                  asym=0.45),
}


@dataclass
class LocoState:
    """What the locomotion layer decided for one instant."""
    pos: Tuple[float, float]            # entity origin (ground point under root)
    facing: float                       # +1 right, -1 left
    pose: Pose
    phase: float                        # continuous step count (for footstep SFX)
    airborne: bool = False
    plants: Dict[str, float] = field(default_factory=dict)  # leg key -> world foot x


def ease_travel(u: float) -> float:
    """Smooth accel/decel travel profile (smoothstep)."""
    u = clamp(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def _leg_geometry(rig: CharacterRig, chain: Chain2):
    sk = rig.skeleton
    l1 = sk.bones[chain.upper].length
    l2 = sk.bones[chain.lower].length
    return l1, l2


def _solve_leg(rig: CharacterRig, fk: FK, pose: Pose, chain: Chain2,
               target: Tuple[float, float], foot_world_deg: float) -> None:
    """Write IK angles into pose for one leg chain (target = ankle point)."""
    sk = rig.skeleton
    base = fk.base_point(chain.upper)
    l1, l2 = _leg_geometry(rig, chain)
    up_w, lo_w = two_bone_ik(base, target, l1, l2, chain.bend)
    parent = sk.bones[chain.upper].parent
    parent_dir = fk.world_angle(parent) if parent else pose.root_angle
    pose.angles[chain.upper] = up_w - parent_dir - sk.bones[chain.upper].rest
    pose.angles[chain.lower] = lo_w - up_w - sk.bones[chain.lower].rest
    pose.angles[chain.end] = foot_world_deg - lo_w - sk.bones[chain.end].rest


def _arm_swing(pose: Pose, rig: CharacterRig, phase: float, g: dict,
               speed_norm: float) -> None:
    if not rig.arms:
        return
    amp = g["arm_swing"] * speed_norm
    elbow = g["elbow"]
    for key, sign in (("near", 1.0), ("far", -1.0)):
        if key not in rig.arms:
            continue
        ch = rig.arms[key]
        swing = math.sin(math.pi * phase) * amp * sign
        pose.angles[ch.upper] = swing + (10.0 * sign if elbow < 30 else 0.0)
        # elbows bend forward; more when the arm swings back
        back = max(0.0, -swing / max(amp, 1e-6))
        pose.angles[ch.lower] = elbow * 0.35 + back * elbow * 0.65
        pose.angles[ch.end] = 0.0


def _foot_cycle(phi: float, parity: float, duty: float,
                step: float, total: float, stagger: float
                ) -> Tuple[float, float, float, bool]:
    """One foot's position along the path.

    phi: continuous step count. parity: this foot's offset in steps (0 or 1;
    quadrupeds use quarters). Returns (x_along_path, lift_y, foot_tilt_deg,
    planted). x is clamped to [0, total] so the last step lands on the mark.
    """
    # the step index this foot last began (its steps are every 2 units)
    n = math.floor((phi - parity) / 2.0) * 2.0 + parity
    u = phi - n                       # 0..2 progress through this foot's cycle
    stance_len = 2.0 * duty           # in step units
    plant_x = clamp(n * step + stagger, 0.0, total)
    next_x = clamp((n + 2.0) * step + stagger, 0.0, total)
    if u <= stance_len or plant_x == next_x:
        return plant_x, 0.0, 0.0, True
    w = (u - stance_len) / max(2.0 - stance_len, 1e-6)   # swing progress 0..1
    w = clamp(w, 0.0, 1.0)
    we = w * w * (3 - 2 * w)
    x = lerp(plant_x, next_x, we)
    lift = math.sin(math.pi * w)
    tilt = math.sin(math.pi * w) * -25.0 + (1 - w) * 12.0
    return x, lift, tilt, False


def biped_pose(rig: CharacterRig, mode: str, dist: float, total: float,
               phase_scale: Optional[float], t_in_seg: float, duration: float,
               facing: float) -> LocoState:
    """Locomotion pose for a 2-legged rig moving along +X of its path.

    dist: distance traveled so far (monotone, eased). total: full path length.
    The caller rotates/flips for actual world direction.
    """
    g = GAITS.get(mode, GAITS["walk"])
    l1, l2 = _leg_geometry(rig, rig.legs["near"])
    leg = l1 + l2
    step = g["step_h"] * leg * 0.55
    if total > 1e-6:
        # fit a whole number of steps so the last one lands exactly on target
        n_steps = max(1, round(total / step))
        step = total / n_steps
    phi = dist / step if step > 1e-9 else 0.0
    duty = g["duty"]
    speed_norm = clamp((total / max(duration, 1e-6)) / (g["max_speed"] * rig.height + 1e-6) + 0.35, 0.4, 1.0)

    pose = rig.rest_pose()
    base_pose = pose.copy()
    hip_h = rig.hip_height - g["crouch"] * leg
    bob = g["bob"] * leg
    hip_y = hip_h - bob + bob * abs(math.sin(math.pi * phi + 0.35))
    airborne = False
    if duty < 0.5:  # running has a flight phase: both feet off near phi int+.5
        flight = max(0.0, math.sin(math.pi * (phi % 1.0))) ** 2
        hop = (0.5 - duty) * leg * 0.35
        hip_y += flight * hop
    # pose is in entity-local space: entity origin = ground under the root
    pose.root = (0.0, hip_y)
    pose.root_angle = -g["lean"]

    ankle_h = leg * 0.045
    asym = g.get("asym", 0.0)
    plants: Dict[str, float] = {}
    fk0 = FK(rig.skeleton, Pose(root=pose.root, root_angle=pose.root_angle,
                                angles=dict(base_pose.angles)))
    stagger = {"near": 0.03 * leg, "far": -0.03 * leg}
    parity = {"near": 0.0, "far": 1.0}
    planted_any = False
    for key, ch in rig.legs.items():
        par = parity.get(key, 0.0)
        lift_scale = 1.0 - (asym if key == "far" else 0.0)
        x, lift, tilt, planted = _foot_cycle(phi, par, duty, step, total,
                                             stagger.get(key, 0.0))
        planted_any = planted_any or planted
        target = (x - dist, ankle_h + lift * g["lift"] * leg * lift_scale)
        _solve_leg(rig, fk0, pose, ch, target, tilt)
        if planted:
            plants[key] = x
    _arm_swing(pose, rig, phi, g, speed_norm)
    # subtle counter-rotation of the head keeps the gaze level
    pose.angles["head"] = pose.angles.get("head", 0.0) + g["lean"] * 0.7
    return LocoState(pos=(dist, 0.0), facing=facing, pose=pose, phase=phi,
                     airborne=not planted_any, plants=plants)


def quadruped_pose(rig: CharacterRig, mode: str, dist: float, total: float,
                   t_in_seg: float, duration: float, facing: float) -> LocoState:
    """Trot gait for 4-legged rigs: diagonal pairs, same no-slide guarantee."""
    g = GAITS.get(mode, GAITS["walk"])
    any_leg = next(iter(rig.legs.values()))
    l1, l2 = _leg_geometry(rig, any_leg)
    leg = l1 + l2
    step = g["step_h"] * leg * 0.8
    if total > 1e-6:
        n_steps = max(1, round(total / step))
        step = total / n_steps
    phi = dist / step if step > 1e-9 else 0.0
    duty = min(g["duty"] + 0.05, 0.75)

    pose = rig.rest_pose()
    bob = g["bob"] * leg * 0.7
    hip_y = rig.hip_height - bob + bob * abs(math.sin(math.pi * phi))
    pose.root = (0.0, hip_y)

    # rest FK gives each leg's shoulder/haunch x-offset from the root
    fk0 = FK(rig.skeleton, pose)
    ankle_h = leg * 0.06
    # trot: diagonal pairs move together
    parity = {"near_front": 0.0, "far_back": 0.0, "far_front": 1.0, "near_back": 1.0}
    plants: Dict[str, float] = {}
    for key, ch in rig.legs.items():
        base_off = fk0.base_point(ch.upper)[0]
        x, lift, tilt, planted = _foot_cycle(phi, parity.get(key, 0.0), duty,
                                             step, total, base_off)
        target = (x - dist, ankle_h + lift * g["lift"] * leg)
        _solve_leg(rig, fk0, pose, ch, target, tilt * 0.5)
        if planted:
            plants[key] = x
    return LocoState(pos=(dist, 0.0), facing=facing, pose=pose, phase=phi,
                     plants=plants)
