"""Interactions: pick up, carry, drop, give, throw, catch, ride, sit on.

Compiled per scene from the character programs' interaction commands.
Everything stays a pure function of t: held objects follow the carrying
hand's FK; thrown objects fly a closed-form ballistic arc; riders follow
their mounts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..chars.rig import FK
from ..core.vec import clamp
from ..dsl.ir import Direction

GRAB_DELAY = 0.45      # seconds after a pickup command before the hand closes
G = -9.8


@dataclass
class Hold:
    t0: float
    t1: float                      # inf until something releases it
    char_id: str
    hand: str                      # 'near' | 'far'
    grip: Tuple[float, float]


@dataclass
class Flight:
    t0: float
    target: Tuple[float, float]
    duration: float                # chosen flight time
    release_from: Tuple[str, str]  # (char_id, hand) to fetch launch point


@dataclass
class Mount:
    t0: float
    t1: float
    obj_id: str
    offset: Tuple[float, float]


class SceneLinks:
    """All cross-entity attachment state for one compiled scene."""

    def __init__(self, entities: Dict[str, Any]):
        # entities: id -> Entity (with .program, .obj_type, .placement)
        self.entities = entities
        self.holds: Dict[str, List[Hold]] = {}
        self.flights: Dict[str, List[Flight]] = {}
        self.mounts: Dict[str, List[Mount]] = {}
        self._flight_cache: Dict[Tuple[str, int], Tuple[Tuple[float, float], Tuple[float, float]]] = {}

        cmds: List[Tuple[Direction, str]] = []
        for eid, ent in entities.items():
            prog = ent.program
            for d in getattr(prog, "attach_cmds", []):
                cmds.append((d, eid))
        cmds.sort(key=lambda cd: cd[0].t)

        for d, char_id in cmds:
            p = d.params
            obj_id = str(p.get("obj", ""))
            hand = "far" if str(p.get("hand", "near")) in ("far", "left") else "near"
            if d.verb == "pickup":
                grip = p.get("grip")
                ent = entities.get(obj_id)
                if not (isinstance(grip, (list, tuple)) and len(grip) == 2):
                    size = ent.obj_type.size if ent is not None and ent.obj_type else (0.4, 0.4)
                    grip = (0.0, size[1] * 0.55)
                self._end_open_hold(obj_id, d.t + GRAB_DELAY)
                self.holds.setdefault(obj_id, []).append(
                    Hold(d.t + GRAB_DELAY, math.inf, char_id, hand,
                         (float(grip[0]), float(grip[1]))))
            elif d.verb == "drop":
                self._end_open_hold(obj_id, d.t)
                self.flights.setdefault(obj_id, []).append(
                    Flight(d.t, (math.nan, 0.0), 0.0, (char_id, hand)))
            elif d.verb == "give":
                to_char = str(p.get("to_char", p.get("to", "")))
                t_mid = d.t + (max((d.until or d.t + 1.0) - d.t, 0.4)) * 0.5
                self._end_open_hold(obj_id, t_mid)
                other_hand = "near"
                self.holds.setdefault(obj_id, []).append(
                    Hold(t_mid, math.inf, to_char, other_hand,
                         self._last_grip(obj_id)))
            elif d.verb == "throw":
                to = p.get("to", [0.0, 0.0])
                target = (float(to[0]), float(to[1])) if isinstance(to, (list, tuple)) else (0.0, 0.0)
                t_rel = d.t + 0.35
                self._end_open_hold(obj_id, t_rel)
                self.flights.setdefault(obj_id, []).append(
                    Flight(t_rel, target, 0.0, (char_id, hand)))
            elif d.verb == "catch":
                # take over from the object's active flight (or just hold it)
                self.holds.setdefault(obj_id, []).append(
                    Hold(d.t, math.inf, char_id, hand, self._last_grip(obj_id)))
                # truncate the flight at the catch moment
                for fl in self.flights.get(obj_id, []):
                    if fl.t0 < d.t and (fl.duration == 0.0 or fl.t0 + fl.duration > d.t):
                        fl.duration = min(fl.duration or (d.t - fl.t0), d.t - fl.t0) or (d.t - fl.t0)
            elif d.verb in ("ride", "sit_on", "mount"):
                ent = entities.get(obj_id)
                off = p.get("offset")
                if not (isinstance(off, (list, tuple)) and len(off) == 2):
                    size = ent.obj_type.size if ent is not None and ent.obj_type else (1.0, 1.0)
                    off = (0.0, size[1] * (0.55 if d.verb == "ride" else 0.45))
                t1 = d.until if d.until is not None else math.inf
                self.mounts.setdefault(char_id, []).append(
                    Mount(d.t, t1, obj_id, (float(off[0]), float(off[1]))))
            elif d.verb in ("dismount", "stand"):
                for m in self.mounts.get(char_id, []):
                    if m.t1 == math.inf and m.t0 < d.t:
                        m.t1 = d.t

        # riders continue from where their mount ends, not their old spot
        for char_id, mounts in self.mounts.items():
            ent = entities.get(char_id)
            for m in mounts:
                if m.t1 == math.inf or ent is None or ent.program is None:
                    continue
                obj = entities.get(m.obj_id)
                if obj is None or obj.program is None:
                    continue
                ox, _oy = obj.program.position(m.t1)
                if hasattr(ent.program, "insert_teleport"):
                    ent.program.insert_teleport(m.t1, (ox + m.offset[0], 0.0))

    def _end_open_hold(self, obj_id: str, t: float) -> None:
        for h in self.holds.get(obj_id, []):
            if h.t1 == math.inf and h.t0 < t:
                h.t1 = t

    def _last_grip(self, obj_id: str) -> Tuple[float, float]:
        holds = self.holds.get(obj_id, [])
        if holds:
            return holds[-1].grip
        ent = self.entities.get(obj_id)
        size = ent.obj_type.size if ent is not None and ent.obj_type else (0.4, 0.4)
        return (0.0, size[1] * 0.55)

    # ------------------------------------------------------------- queries

    def hand_state(self, char_id: str, t: float) -> Tuple[Tuple[float, float], float, float]:
        """(hand world pos, hand world angle deg, facing) for the near hand.
        Internal helper via _hand for a specific hand."""
        return self._hand(char_id, "near", t)

    def _hand(self, char_id: str, hand: str, t: float):
        ent = self.entities.get(char_id)
        if ent is None or ent.rig is None or ent.program is None:
            return ((0.0, 0.0), 0.0, 1.0)
        st = ent.program.state(t)
        rig = ent.rig
        arm = rig.arms.get(hand) or next(iter(rig.arms.values()), None)
        fk = FK(rig.skeleton, st.pose)
        if arm is None:
            p = fk.tip_point(rig.head_bone)
            ang = 0.0
        else:
            p = fk.tip_point(arm.end)
            ang = fk.world_angle(arm.end)
        scale = ent.placement.scale
        wx = st.pos[0] + p[0] * st.facing * scale
        wy = st.pos[1] + p[1] * scale
        return ((wx, wy), ang, st.facing)

    def held_by(self, obj_id: str, t: float) -> Optional[Hold]:
        for h in self.holds.get(obj_id, []):
            if h.t0 <= t < h.t1:
                return h
        return None

    def flight_pos(self, obj_id: str, t: float) -> Optional[Tuple[float, float, float]]:
        """(x, y, spin_deg) if the object is in free flight (or at rest after one)."""
        best: Optional[Flight] = None
        for fl in self.flights.get(obj_id, []):
            if fl.t0 <= t and (best is None or fl.t0 > best.t0):
                # a later hold (catch/pickup) hides the flight
                h = self.held_by(obj_id, t)
                if h is not None and h.t0 > fl.t0:
                    continue
                best = fl
        if best is None:
            return None
        key = (obj_id, int(best.t0 * 1000))
        if key not in self._flight_cache:
            p_r, _ang, facing = self._hand(best.release_from[0],
                                           "near", max(best.t0 - 1e-3, 0.0))
            if math.isnan(best.target[0]):     # drop: straight down
                target = (p_r[0] + 0.15 * facing, 0.1)
                T = math.sqrt(max(2 * (p_r[1] - target[1]) / -G, 0.02))
            else:
                target = best.target
                dist = math.hypot(target[0] - p_r[0], target[1] - p_r[1])
                T = clamp(dist * 0.16, 0.45, 1.3)
            self._flight_cache[key] = (p_r, target)
            best.duration = best.duration or T
        p_r, target = self._flight_cache[key]
        T = best.duration or 0.6
        tau = t - best.t0
        if tau >= T:
            return (target[0], target[1], 360.0 * T)
        v0x = (target[0] - p_r[0]) / T
        v0y = (target[1] - p_r[1] - 0.5 * G * T * T) / T
        x = p_r[0] + v0x * tau
        y = p_r[1] + v0y * tau + 0.5 * G * tau * tau
        return (x, y, 360.0 * tau)

    def mount_of(self, char_id: str, t: float) -> Optional[Mount]:
        for m in self.mounts.get(char_id, []):
            if m.t0 <= t < m.t1:
                return m
        return None
