"""Per-entity motion programs: compile a scene's directions once, then
sample as a pure function of time.

Layering for characters (later layers blend over earlier by body mask):

    idle/locomotion -> action clips -> say (mouth) -> emote/look -> custom
    pose_track -> (ragdoll takes over everything when active)
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..chars.bodies.base import CharacterRig
from ..chars.face import VISEMES, apply_expression
from ..chars.rig import Pose
from ..core.rng import MFRandom
from ..core.vec import clamp, lerp
from ..dsl.ir import Direction, Placement, Scene
from .actions import ACTIONS, ActionDef
from .gait import GAITS, LocoState, biped_pose, ease_travel, quadruped_pose
from .tracks import Track

LOCO_VERBS = set(GAITS) | {"jump", "climb", "swim", "fly"}

MASKS = {
    "full": None,   # None = everything incl. __root__
    "upper": {"spine", "chest", "neck", "head",
              "uarm_near", "farm_near", "hand_near",
              "uarm_far", "farm_far", "hand_far"},
    "arms": {"uarm_near", "farm_near", "hand_near",
             "uarm_far", "farm_far", "hand_far"},
    "arm": {"uarm_near", "farm_near", "hand_near",
            "uarm_far", "farm_far", "hand_far"},
    "head": {"neck", "head"},
    "lower": {"thigh_near", "shin_near", "foot_near",
              "thigh_far", "shin_far", "foot_far"},
    "face": set(),
}


@dataclass
class LocoSegment:
    t0: float
    t1: float
    mode: str
    p0: Tuple[float, float]
    p1: Tuple[float, float]

    @property
    def total(self) -> float:
        return math.hypot(self.p1[0] - self.p0[0], self.p1[1] - self.p0[1])

    @property
    def dir(self) -> float:
        dx = self.p1[0] - self.p0[0]
        return 1.0 if dx >= 0 else -1.0


@dataclass
class ActionInstance:
    t0: float
    t1: float
    adef: ActionDef
    params: Dict[str, Any]


@dataclass
class SayInstance:
    t0: float
    t1: float
    text: str
    visemes: List[str]


def _text_visemes(text: str) -> List[str]:
    """Deterministic text -> viseme sequence (cartoon lip sync)."""
    vmap = {"a": "A", "e": "E", "i": "I", "o": "O", "u": "U",
            "m": "M", "b": "M", "p": "M", "w": "U", "f": "E", "v": "E"}
    out: List[str] = []
    for ch in text.lower():
        if ch.isspace():
            out.append("rest")
        elif ch in vmap:
            out.append(vmap[ch])
        elif ch.isalpha():
            out.append("E" if len(out) % 2 == 0 else "A")
    return out or ["A"]


class CharProgram:
    def __init__(self, placement: Placement, rig: CharacterRig,
                 directions: List[Direction], scene: Scene, seed_rng: MFRandom):
        self.placement = placement
        self.rig = rig
        self.scene = scene
        self.is_quad = "near_front" in rig.legs
        self.has_legs = bool(rig.legs)

        self.segments: List[LocoSegment] = []
        self.actions: List[ActionInstance] = []
        self.says: List[SayInstance] = []
        self.emotes: List[Tuple[float, float, str]] = []
        self.looks: List[Tuple[float, float, Any]] = []
        self.pose_tracks: List[Tuple[float, list]] = []
        self.facing_changes: List[Tuple[float, float]] = []
        self.ragdolls: List[Direction] = []
        self.attach_cmds: List[Direction] = []   # consumed by attach.SceneLinks

        base_facing = -1.0 if placement.facing == "left" else 1.0
        self.facing_changes.append((-1e9, base_facing))

        pos = placement.at
        cursor = 0.0
        for d in directions:
            if d.verb in LOCO_VERBS:
                to = d.params.get("to")
                if not (isinstance(to, (list, tuple)) and len(to) == 2):
                    continue  # validator reports this
                t1 = d.until if d.until is not None else d.t + max(
                    abs(float(to[0]) - pos[0]) / 1.2, 0.4)
                seg = LocoSegment(t0=d.t, t1=t1, mode=d.verb,
                                  p0=pos, p1=(float(to[0]), float(to[1])))
                self.segments.append(seg)
                if abs(seg.p1[0] - seg.p0[0]) > 1e-6:
                    self.facing_changes.append((d.t, seg.dir))
                pos = seg.p1
                cursor = t1
            elif d.verb == "teleport":
                to = d.params.get("to")
                if isinstance(to, (list, tuple)) and len(to) == 2:
                    pos = (float(to[0]), float(to[1]))
                    self.segments.append(LocoSegment(d.t, d.t, "teleport", pos, pos))
            elif d.verb in ACTIONS:
                adef = ACTIONS[d.verb]
                t1 = d.until if d.until is not None else d.t + adef.dur
                self.actions.append(ActionInstance(d.t, t1, adef, dict(d.params)))
            elif d.verb == "say":
                text = str(d.params.get("text", ""))
                t1 = d.until if d.until is not None else d.t + max(len(text) * 0.06, 0.8)
                self.says.append(SayInstance(d.t, t1, text, _text_visemes(text)))
            elif d.verb == "emote":
                t1 = d.until if d.until is not None else d.t + 2.0
                self.emotes.append((d.t, t1, str(d.params.get("expression", "neutral"))))
            elif d.verb == "look":
                t1 = d.until if d.until is not None else d.t + 2.0
                self.looks.append((d.t, t1, d.params.get("target")))
            elif d.verb == "face":
                target = d.params.get("target")
                if target == "left":
                    self.facing_changes.append((d.t, -1.0))
                elif target == "right":
                    self.facing_changes.append((d.t, 1.0))
            elif d.verb == "pose_track":
                keys = d.params.get("keys")
                if isinstance(keys, list):
                    self.pose_tracks.append((d.t, keys))
            elif d.verb == "ragdoll":
                self.ragdolls.append(d)
            elif d.verb in ("pickup", "drop", "give", "throw", "catch",
                            "ride", "sit_on", "mount", "dismount", "stand"):
                self.attach_cmds.append(d)
                if d.verb == "pickup":
                    self.actions.append(ActionInstance(
                        d.t, d.t + 0.9, ACTIONS["reach_down"], dict(d.params)))
                elif d.verb in ("give", "catch"):
                    self.actions.append(ActionInstance(
                        d.t, d.until or d.t + 1.0, ACTIONS["reach_forward"],
                        dict(d.params)))
                elif d.verb == "throw":
                    self.actions.append(ActionInstance(
                        d.t, d.t + 0.7, ACTIONS["windup_throw"], dict(d.params)))
                elif d.verb in ("ride", "sit_on", "mount"):
                    t1 = d.until if d.until is not None else scene.duration
                    self.actions.append(ActionInstance(
                        d.t, t1, ACTIONS["sit"], dict(d.params, seat=0.1)))

        # carry poses between pickup and release; truncate ride-sits at dismount
        for d in self.attach_cmds:
            if d.verb == "pickup":
                obj = d.params.get("obj")
                t_rel = scene.duration
                for d2 in self.attach_cmds:
                    if (d2.t > d.t and d2.verb in ("drop", "give", "throw")
                            and d2.params.get("obj") == obj):
                        t_rel = d2.t + 0.35
                        break
                if t_rel > d.t + 0.9:
                    self.actions.append(ActionInstance(
                        d.t + 0.85, t_rel, ACTIONS["hold_item"], dict(d.params)))
            elif d.verb in ("dismount", "stand"):
                for inst in self.actions:
                    if (inst.adef.name == "sit" and inst.t0 < d.t
                            and inst.t1 > d.t):
                        inst.t1 = d.t
        self.actions.sort(key=lambda a: a.t0)

        self.facing_changes.sort(key=lambda x: x[0])
        self._ragdoll_sims: Optional[List[Any]] = None
        self._capturing = False
        # deterministic blink schedule for the whole scene
        rng = seed_rng.stream(f"blink:{placement.id}")
        self.blinks: List[float] = []
        t = float(rng.uniform(0.6, 2.4))
        while t < scene.duration:
            self.blinks.append(t)
            t += float(rng.uniform(2.2, 4.8))
        self.idle_phase = float(seed_rng.stream(f"idle:{placement.id}").uniform(0, 6.28))

    def insert_teleport(self, t: float, pos: Tuple[float, float]) -> None:
        """Continue from `pos` after time t (used by dismounts, ragdolls)."""
        self.segments.append(LocoSegment(t, t, "teleport", pos, pos))
        self.segments.sort(key=lambda s: s.t0)

    # ------------------------------------------------------------- position

    def _segment_at(self, t: float) -> Tuple[Optional[LocoSegment], Tuple[float, float]]:
        """Active segment (if any) and the held position otherwise."""
        pos = self.placement.at
        for seg in self.segments:
            if t < seg.t0:
                return None, pos
            if t <= seg.t1 and seg.t1 > seg.t0:
                return seg, pos
            pos = seg.p1
        return None, pos

    def position(self, t: float) -> Tuple[float, float]:
        seg, held = self._segment_at(t)
        if seg is None:
            p = held
        else:
            u = ease_travel((t - seg.t0) / max(seg.t1 - seg.t0, 1e-9))
            p = (lerp(seg.p0[0], seg.p1[0], u), lerp(seg.p0[1], seg.p1[1], u))
        # posture root offsets (sit drops etc.) move the entity origin
        return p

    def facing(self, t: float) -> float:
        f = 1.0
        for tt, val in self.facing_changes:
            if tt <= t:
                f = val
            else:
                break
        return f

    # ----------------------------------------------------------------- pose

    def _idle_pose(self, t: float) -> Pose:
        pose = self.rig.rest_pose()
        ph = t * 2 * math.pi / 3.8 + self.idle_phase
        pose.angles["chest"] = pose.angles.get("chest", 0.0) + math.sin(ph) * 1.4
        pose.angles["head"] = pose.angles.get("head", 0.0) + math.sin(ph * 0.7) * 1.2
        for key, sign in (("near", 1.0), ("far", -1.0)):
            arm = self.rig.arms.get(key)
            if arm:
                pose.angles[arm.upper] = pose.angles.get(arm.upper, 0.0) + math.sin(ph) * sign * 1.0
        return pose

    def _loco_state(self, t: float) -> LocoState:
        seg, held = self._segment_at(t)
        facing = self.facing(t)
        if seg is None or seg.total <= 1e-6 or seg.t1 <= seg.t0:
            pose = self._idle_pose(t)
            pos = self.position(t)
            return LocoState(pos=pos, facing=facing, pose=pose, phase=0.0)
        dur = seg.t1 - seg.t0
        u_raw = clamp((t - seg.t0) / dur, 0.0, 1.0)
        u = ease_travel(u_raw)
        dist = seg.total * u

        if seg.mode == "jump":
            from .gait_special import jump_pose
            st = jump_pose(self.rig, u_raw, seg.p0, seg.p1, dur, seg.dir,
                           float(0.0))
            st.pos = (seg.p0[0] + st.pos[0], seg.p0[1] + st.pos[1])
            st.facing = seg.dir
            return st
        if seg.mode == "climb":
            from .gait_special import climb_pose
            climb_dist = (seg.p1[1] - seg.p0[1]) * u
            st = climb_pose(self.rig, abs(climb_dist), abs(seg.p1[1] - seg.p0[1]),
                            seg.dir)
            st.pos = (lerp(seg.p0[0], seg.p1[0], u), lerp(seg.p0[1], seg.p1[1], u))
            st.facing = seg.dir
            return st
        if seg.mode in ("swim", "fly"):
            from .gait_special import fly_pose, swim_pose
            fn = swim_pose if seg.mode == "swim" else fly_pose
            st = fn(self.rig, dist, seg.total, t - seg.t0, seg.dir)
            st.pos = (seg.p0[0] + dist * seg.dir, lerp(seg.p0[1], seg.p1[1], u))
            st.facing = seg.dir
            return st

        mode = seg.mode if seg.mode in GAITS else "walk"
        if self.is_quad:
            st = quadruped_pose(self.rig, mode, dist, seg.total, t - seg.t0, dur, seg.dir)
        elif self.has_legs:
            st = biped_pose(self.rig, mode, dist, seg.total, None, t - seg.t0, dur, seg.dir)
        else:
            st = LocoState(pos=(dist, 0.0), facing=seg.dir, pose=self.rig.rest_pose(),
                           phase=dist * 2.0)
        # map path-local to world
        wx = seg.p0[0] + st.pos[0] * seg.dir
        wy = lerp(seg.p0[1], seg.p1[1], u)
        st.pos = (wx, wy)
        st.facing = seg.dir
        return st

    def _apply_action(self, pose: Pose, root_extra: list, inst: ActionInstance,
                      t: float) -> None:
        adef = inst.adef
        span = inst.t1 - inst.t0
        if span <= 0:
            return
        local = t - inst.t0
        if adef.loop:
            u = local / adef.dur
        else:
            u = local / (span if inst.params.get("__scaled__", span != adef.dur) else adef.dur)
            u = clamp(u, 0.0, 1.0)
        fade = min(0.25, span * 0.25)
        w = 1.0
        if local < fade:
            w = local / fade
        if inst.t1 - t < fade:
            w = min(w, (inst.t1 - t) / fade)
        w = clamp(w, 0.0, 1.0)
        w = w * w * (3 - 2 * w)
        angles, morphs, root_d = adef.fn(u, inst.params, self.rig)
        mask = MASKS.get(adef.mask)
        sk = self.rig.skeleton.bones
        for bone, val in angles.items():
            if bone not in sk:
                continue
            if mask is not None and bone not in mask:
                continue
            cur = pose.angles.get(bone, 0.0)
            pose.angles[bone] = lerp(cur, val, w)
        for m, val in morphs.items():
            pose.morphs[m] = lerp(pose.morphs.get(m, 0.0), val, w)
        if root_d != (0.0, 0.0, 0.0):
            root_extra[0] += root_d[0] * w
            root_extra[1] += root_d[1] * w
            root_extra[2] += root_d[2] * w

    def _apply_say(self, pose: Pose, say: SayInstance, t: float) -> None:
        span = say.t1 - say.t0
        if span <= 0 or not say.visemes:
            return
        u = (t - say.t0) / span
        idx = int(u * len(say.visemes) * 0.999)
        idx = max(0, min(idx, len(say.visemes) - 1))
        # ease between visemes for smooth mouths
        frac = (u * len(say.visemes)) % 1.0
        v0 = VISEMES.get(say.visemes[idx], VISEMES["rest"])
        v1 = VISEMES.get(say.visemes[min(idx + 1, len(say.visemes) - 1)],
                         VISEMES["rest"])
        k = frac * frac * (3 - 2 * frac)
        pose.morphs["mouth_open"] = lerp(v0[0], v1[0], k)
        pose.morphs["mouth_wide"] = lerp(v0[1], v1[1], k)
        pose.morphs["mouth_round"] = lerp(v0[2], v1[2], k)
        # gentle head emphasis
        pose.angles["head"] = pose.angles.get("head", 0.0) + math.sin(u * math.pi * 3) * 1.5

    def _apply_look(self, pose: Pose, target: Any, t: float, w: float,
                    resolve_pos) -> None:
        pos = self.position(t)
        facing = self.facing(t)
        head_y = pos[1] + self.rig.height * 0.9
        tp: Optional[Tuple[float, float]] = None
        if isinstance(target, (list, tuple)) and len(target) == 2:
            tp = (float(target[0]), float(target[1]))
        elif target == "camera":
            pose.morphs["gaze_x"] = lerp(pose.morphs.get("gaze_x", 0.0), -0.25 * facing, w)
            pose.morphs["gaze_y"] = lerp(pose.morphs.get("gaze_y", 0.0), 0.1, w)
            return
        elif isinstance(target, str) and resolve_pos is not None:
            rp = resolve_pos(target, t)
            if rp is not None:
                tp = (rp[0], rp[1] + 1.0)
        if tp is None:
            return
        dx = (tp[0] - pos[0]) * facing
        dy = tp[1] - head_y
        d = math.hypot(dx, dy) + 1e-9
        pose.morphs["gaze_x"] = lerp(pose.morphs.get("gaze_x", 0.0),
                                     clamp(dx / d, -1.0, 1.0), w)
        pose.morphs["gaze_y"] = lerp(pose.morphs.get("gaze_y", 0.0),
                                     clamp(dy / d, -1.0, 1.0), w)
        head_turn = clamp(math.degrees(math.atan2(dy, abs(dx))) * 0.35, -25.0, 25.0)
        pose.angles["head"] = pose.angles.get("head", 0.0) + head_turn * w

    def _apply_pose_track(self, pose: Pose, t0: float, keys: list, t: float) -> None:
        """Raw declarative keyframes: [{t, bones: {...}, morphs: {...}, root: [x,y]}]"""
        local = t - t0
        prev = None
        nxt = None
        for k in keys:
            kt = float(k.get("t", 0.0))
            if kt <= local:
                prev = k
            elif nxt is None:
                nxt = k
                break
        if prev is None:
            return
        if nxt is None:
            cur, k = prev, 1.0
            blend_from = prev
        else:
            t0k, t1k = float(prev.get("t", 0.0)), float(nxt.get("t", 0.0))
            k = (local - t0k) / max(t1k - t0k, 1e-9)
            blend_from, cur = prev, nxt
        b0 = blend_from.get("bones", {}) or {}
        b1 = cur.get("bones", {}) or {}
        for bone in set(b0) | set(b1):
            if bone not in self.rig.skeleton.bones:
                continue
            v0 = float(b0.get(bone, pose.angles.get(bone, 0.0)))
            v1 = float(b1.get(bone, v0))
            pose.angles[bone] = lerp(v0, v1, k)
        m0 = blend_from.get("morphs", {}) or {}
        m1 = cur.get("morphs", {}) or {}
        for m in set(m0) | set(m1):
            v0 = float(m0.get(m, pose.morphs.get(m, 0.0)))
            v1 = float(m1.get(m, v0))
            pose.morphs[m] = lerp(v0, v1, k)

    # --------------------------------------------------------------- ragdoll

    def _ensure_ragdolls(self) -> List[Any]:
        if self._ragdoll_sims is not None:
            return self._ragdoll_sims
        from .ragdoll import RagdollSim
        self._ragdoll_sims = []
        self._capturing = True
        try:
            for d in self.ragdolls:
                t0 = d.t
                t1 = d.until if d.until is not None else t0 + 1.6
                recover = float(d.params.get("recover", 0.6))
                imp = d.params.get("impulse", [0.0, 0.0])
                if not (isinstance(imp, (list, tuple)) and len(imp) == 2):
                    imp = [0.0, 0.0]
                dt_prev = 1.0 / 60.0
                cur = self.state(max(t0 - 1e-3, 0.0))
                prev = self.state(max(t0 - 1e-3 - dt_prev, 0.0))
                sim = RagdollSim(self.rig, t0, t1, recover,
                                 (float(imp[0]), float(imp[1])),
                                 cur.pose, cur.pos, cur.facing,
                                 prev.pose, prev.pos, dt_prev)
                self._ragdoll_sims.append(sim)
                # the character continues from wherever it came to rest
                pelvis = sim.frames[-1][sim.names.index("pelvis")]
                wx = sim.origin[0] + pelvis[0] * sim.facing
                self.segments.append(LocoSegment(t1, t1, "teleport",
                                                 (wx, 0.0), (wx, 0.0)))
                self.segments.sort(key=lambda s: s.t0)
        finally:
            self._capturing = False
        return self._ragdoll_sims

    # ----------------------------------------------------------- the sample

    def state(self, t: float, resolve_pos=None) -> LocoState:
        if not self._capturing and self.ragdolls:
            from ..chars.rig import blend as pose_blend
            for sim in self._ensure_ragdolls():
                if sim.t0 <= t <= sim.t1:
                    pose, pos = sim.pose_at(t)
                    return LocoState(pos=pos, facing=sim.facing, pose=pose,
                                     phase=0.0)
                if sim.t1 < t <= sim.t1 + sim.recover:
                    u = (t - sim.t1) / sim.recover
                    u = u * u * (3 - 2 * u)
                    self._capturing = True
                    try:
                        base = self.state(t, resolve_pos)
                    finally:
                        self._capturing = False
                    # ragdoll pose is relative to the frozen origin; express
                    # the base pose there too, then blend
                    dx = (base.pos[0] - sim.origin[0]) * sim.facing
                    dy = base.pos[1] - sim.origin[1]
                    shifted = base.pose.copy()
                    shifted.root = (shifted.root[0] + dx, shifted.root[1] + dy)
                    mixed = pose_blend(sim.final_pose, shifted, u)
                    return LocoState(pos=sim.origin, facing=sim.facing,
                                     pose=mixed, phase=base.phase)
        st = self._loco_state(t)
        pose = st.pose
        root_extra = [0.0, 0.0, 0.0]

        for inst in self.actions:
            if inst.t0 <= t <= inst.t1:
                self._apply_action(pose, root_extra, inst, t)

        for say in self.says:
            if say.t0 <= t <= say.t1:
                self._apply_say(pose, say, t)

        for (e0, e1, expr) in self.emotes:
            if e0 <= t <= e1:
                ramp = min(0.4, (e1 - e0) * 0.3)
                w = min(1.0, (t - e0) / max(ramp, 1e-9),
                        (e1 - t) / max(ramp, 1e-9))
                pose.morphs.update(apply_expression(pose.morphs, expr,
                                                    clamp(w, 0.0, 1.0)))

        for (l0, l1, target) in self.looks:
            if l0 <= t <= l1:
                ramp = min(0.3, (l1 - l0) * 0.3)
                w = clamp(min((t - l0) / max(ramp, 1e-9),
                              (l1 - t) / max(ramp, 1e-9), 1.0), 0.0, 1.0)
                self._apply_look(pose, target, t, w, resolve_pos)

        for (t0, keys) in self.pose_tracks:
            end = t0 + max((float(k.get("t", 0.0)) for k in keys), default=0.0)
            if t0 <= t <= end + 0.5:
                self._apply_pose_track(pose, t0, keys, t)

        # blinks (unless a morph already closes the eyes)
        if pose.morphs.get("blink", 0.0) < 0.5:
            for bt in self.blinks:
                if bt <= t <= bt + 0.16:
                    u = (t - bt) / 0.16
                    pose.morphs["blink"] = math.sin(u * math.pi)
                    break

        pose.root = (pose.root[0] + root_extra[0], pose.root[1] + root_extra[1])
        pose.root_angle += root_extra[2]
        st.pose = pose
        return st

    def say_captions(self) -> List[SayInstance]:
        return self.says


class ObjProgram:
    """Object motion: position, rotation, part channels, visibility."""

    def __init__(self, placement: Placement, obj_type,
                 directions: List[Direction], scene: Scene):
        self.placement = placement
        self.obj_type = obj_type
        self.pos = Track(placement.at)
        self.angle = Track(0.0)
        self.opacity = Track(1.0)
        self.parts: Dict[str, Track] = {}
        init = placement.params.get("part_state")
        if isinstance(init, dict):
            for k, v in init.items():
                self.parts[str(k)] = Track(float(v))
        self.spins: List[Tuple[float, Optional[float], str, float]] = []
        # (t0, t1, part, rpm)

        for d in directions:
            p = d.params
            over = float(p.get("over", 0.0) or 0.0)
            if d.until is not None and over == 0.0:
                over = max(d.until - d.t, 0.0)
            ez = str(p.get("ease", "in_out"))
            if d.verb == "move":
                to = p.get("to")
                if isinstance(to, (list, tuple)) and len(to) == 2:
                    self.pos.hold(d.t)
                    self.pos.add(d.t + max(over, 0.001), (float(to[0]), float(to[1])), ez)
            elif d.verb == "spin":
                part = self._part_for(d, "spin")
                if part is None:
                    continue
                if "rpm" in p:
                    self.spins.append((d.t, d.until, part, float(p["rpm"])))
                elif "to" in p:
                    tr = self.parts.setdefault(part, Track(0.0))
                    tr.hold(d.t)
                    tr.add(d.t + max(over, 0.001), float(p["to"]), ez)
            elif d.verb in ("hinge", "slide"):
                part = self._part_for(d, d.verb)
                if part is None:
                    continue
                tr = self.parts.setdefault(part, Track(0.0))
                tr.hold(d.t)
                tr.add(d.t + max(over, 0.3), float(p.get("to", 0.0)), ez)
            elif d.verb == "show":
                fade = float(p.get("fade", 0.0) or 0.0)
                self.opacity.hold(d.t)
                self.opacity.add(d.t + max(fade, 0.001), 1.0, "linear")
            elif d.verb == "hide":
                fade = float(p.get("fade", 0.0) or 0.0)
                self.opacity.hold(d.t)
                self.opacity.add(d.t + max(fade, 0.001), 0.0, "linear")
            elif d.verb == "bounce":
                h = float(p.get("height", 0.5))
                times = int(p.get("times", 3))
                span = max(over, 0.001) if over else 1.0
                base = self.pos.sample(d.t)
                self.pos.hold(d.t)
                steps = max(times * 8, 8)
                for i in range(1, steps + 1):
                    u = i / steps
                    y = abs(math.sin(u * times * math.pi)) * h * (1.0 - u * 0.5)
                    self.pos.add(d.t + u * span, (base[0], base[1] + y), "linear")
            elif d.verb == "orbit":
                c = p.get("center", [0, 1])
                r = float(p.get("radius", 1.0))
                rpm = float(p.get("rpm", 10.0))
                span = max(over, 0.001) if over else (d.until - d.t if d.until else 4.0)
                base = self.pos.sample(d.t)
                self.pos.hold(d.t)
                steps = max(int(span * 12), 8)
                for i in range(1, steps + 1):
                    u = i / steps
                    ang = u * span * rpm / 60.0 * 2 * math.pi
                    self.pos.add(d.t + u * span,
                                 (float(c[0]) + math.cos(ang) * r,
                                  float(c[1]) + math.sin(ang) * r), "linear")
            elif d.verb == "fall":
                h = float(p.get("height", 0.0))
                base = self.pos.sample(d.t)
                target_y = float(p.get("to_y", 0.0))
                start_y = base[1] + h if h else base[1]
                drop = max(start_y - target_y, 0.0)
                dur = math.sqrt(2 * drop / 9.8) if drop > 0 else 0.001
                self.pos.hold(d.t)
                steps = max(int(dur * 30), 4)
                for i in range(1, steps + 1):
                    u = i / steps
                    y = start_y - 0.5 * 9.8 * (u * dur) ** 2
                    self.pos.add(d.t + u * dur, (base[0], max(y, target_y)), "linear")
                bounce_h = drop * 0.12
                if bounce_h > 0.02:
                    for i in range(1, 9):
                        u = i / 8.0
                        y = target_y + math.sin(u * math.pi) * bounce_h
                        self.pos.add(d.t + dur + u * dur * 0.5, (base[0], y), "linear")

    def _part_for(self, d: Direction, kind: str) -> Optional[str]:
        part = d.params.get("part")
        if part is not None:
            return str(part)
        if self.obj_type is None:
            return None
        kinds = [n for n, k in self.obj_type.articulated.items() if k == kind]
        return kinds[0] if len(kinds) == 1 else None

    def position(self, t: float) -> Tuple[float, float]:
        p = self.pos.sample(t)
        return (float(p[0]), float(p[1]))

    def part_state(self, t: float) -> Dict[str, float]:
        out = {k: float(tr.sample(t)) for k, tr in self.parts.items()}
        for (t0, t1, part, rpm) in self.spins:
            if t < t0:
                continue
            end = min(t, t1) if t1 is not None else t
            out[part] = out.get(part, 0.0) + (end - t0) * rpm * 6.0  # deg
        return out

    def opacity_at(self, t: float) -> float:
        return float(self.opacity.sample(t))
