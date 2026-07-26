"""The action library: named, parameterized performances.

An action is a pure function  f(u, params, rig) -> (angles, morphs, root_delta)
where u is normalized time (0..1 for one-shots; may exceed 1 for loops —
use u % 1 for the cycle). `angles` are pose deviations layered over whatever
the character is otherwise doing, restricted to the action's body mask.
root_delta = (dx, dy, dangle) moves the whole body (sit, jump, lie...).

The registry (ACTIONS) feeds the spec generator, so every action and its
parameters are always documented automatically.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from ..chars.bodies.base import CharacterRig

Angles = Dict[str, float]
Morphs = Dict[str, float]
RootDelta = Tuple[float, float, float]
ActionFn = Callable[[float, dict, CharacterRig], Tuple[Angles, Morphs, RootDelta]]

ZERO: RootDelta = (0.0, 0.0, 0.0)


@dataclass
class ActionDef:
    name: str
    fn: ActionFn
    dur: float                 # natural duration in seconds (until: overrides)
    loop: bool                 # loops while active vs plays once and holds
    mask: str                  # full | upper | arms | arm | head | face | lower
    doc: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    suppresses_locomotion: bool = False   # sit/lie/kneel replace standing


ACTIONS: Dict[str, ActionDef] = {}


def action(name: str, dur: float, loop: bool, mask: str, doc: str = "",
           params: Optional[Dict[str, str]] = None,
           suppresses_locomotion: bool = False):
    def deco(fn: ActionFn) -> ActionFn:
        ACTIONS[name] = ActionDef(name=name, fn=fn, dur=dur, loop=loop,
                                  mask=mask, doc=doc, params=params or {},
                                  suppresses_locomotion=suppresses_locomotion)
        return fn
    return deco


def _side(params: dict) -> str:
    s = str(params.get("hand", params.get("side", "near")))
    return "far" if s in ("far", "left", "back") else "near"


def _osc(u: float, times: float = 1.0) -> float:
    """Sine oscillation completing `times` cycles over u in 0..1."""
    return math.sin(u * times * 2 * math.pi)


def _rise(u: float, frac: float = 0.2) -> float:
    """0->1 ramp over the first `frac`, 1->0 over the last `frac` (hold middle)."""
    if u < frac:
        x = u / frac
    elif u > 1.0 - frac:
        x = (1.0 - u) / frac
    else:
        x = 1.0
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ gestures

@action("wave", 1.6, True, "arm", "wave hello/goodbye",
        {"hand": "near|far", "times": "waves per loop (default 2)"})
def act_wave(u, p, rig):
    s = _side(p)
    w = _osc(u, float(p.get("times", 2.0)))
    return ({f"uarm_{s}": 150.0, f"farm_{s}": 35.0 + w * 25.0,
             f"hand_{s}": w * 10.0},
            {"smile": 0.5, "brow_raise": 0.3}, ZERO)


@action("point", 1.2, False, "arm", "extend an arm to point",
        {"hand": "near|far", "up": "degrees above horizontal (default 0)"})
def act_point(u, p, rig):
    s = _side(p)
    k = _rise(u, 0.25)
    up = float(p.get("up", 0.0))
    return ({f"uarm_{s}": (90.0 + up) * k, f"farm_{s}": 0.0, f"hand_{s}": 0.0},
            {}, ZERO)


@action("clap", 1.0, True, "arms", "applaud", {"times": "claps per loop (default 2)"})
def act_clap(u, p, rig):
    w = abs(_osc(u, float(p.get("times", 2.0))))
    return ({"uarm_near": 95.0 + w * 12.0, "farm_near": 35.0 - w * 25.0,
             "uarm_far": 85.0 - w * 12.0, "farm_far": 45.0 - w * 25.0},
            {"smile": 0.6}, ZERO)


@action("nod", 1.0, True, "head", "nod yes")
def act_nod(u, p, rig):
    return ({"head": _osc(u, 2.0) * 14.0 - 6.0}, {}, ZERO)


@action("shake_head", 1.0, True, "head", "shake no")
def act_shake(u, p, rig):
    return ({"head": _osc(u, 3.0) * 8.0, "neck": -_osc(u, 3.0) * 4.0}, {}, ZERO)


@action("bow", 2.0, False, "upper", "bow politely", {"deep": "0..1 (default 0.6)"})
def act_bow(u, p, rig):
    k = _rise(u, 0.3) * float(p.get("deep", 0.6))
    return ({"spine": -55.0 * k, "neck": -15.0 * k,
             "uarm_near": 20.0 * k, "uarm_far": -20.0 * k}, {}, ZERO)


@action("shrug", 1.4, False, "upper", "who knows?")
def act_shrug(u, p, rig):
    k = _rise(u, 0.3)
    return ({"uarm_near": 35.0 * k, "farm_near": 95.0 * k,
             "uarm_far": -35.0 * k, "farm_far": -95.0 * k,
             "head": 8.0 * k},
            {"brow_raise": 0.8 * k, "smile": -0.2 * k}, ZERO)


@action("salute", 1.5, False, "arm", "military salute", {"hand": "near|far"})
def act_salute(u, p, rig):
    s = _side(p)
    k = _rise(u, 0.25)
    return ({f"uarm_{s}": 140.0 * k, f"farm_{s}": 115.0 * k}, {}, ZERO)


@action("think", 2.5, True, "upper", "hand to chin, pondering")
def act_think(u, p, rig):
    sway = _osc(u, 0.5) * 2.0
    return ({"uarm_near": 55.0, "farm_near": 120.0, "hand_near": 20.0,
             "head": -6.0 + sway, "neck": 4.0},
            {"gaze_x": 0.4, "gaze_y": 0.6, "brow_raise": 0.35}, ZERO)


@action("facepalm", 1.8, False, "upper", "despair, hand to face")
def act_facepalm(u, p, rig):
    k = _rise(u, 0.25)
    return ({"uarm_near": 130.0 * k, "farm_near": 110.0 * k,
             "head": -18.0 * k, "neck": -6.0 * k},
            {"blink": 0.8 * k, "smile": -0.5 * k}, ZERO)


@action("stretch", 2.0, False, "upper", "arms up, big stretch")
def act_stretch(u, p, rig):
    k = _rise(u, 0.35)
    return ({"uarm_near": 165.0 * k, "uarm_far": -165.0 * k,
             "farm_near": 10.0 * k, "farm_far": -10.0 * k,
             "spine": 6.0 * k, "head": 10.0 * k},
            {"blink": 0.6 * k, "mouth_open": 0.4 * k}, ZERO)


@action("look_around", 2.4, True, "head", "scan the surroundings")
def act_look_around(u, p, rig):
    w = _osc(u, 1.0)
    return ({"head": w * 6.0, "neck": w * 3.0},
            {"gaze_x": w * 0.9, "brow_raise": 0.2}, ZERO)


# ------------------------------------------------------------------ emotions

@action("laugh", 1.2, True, "upper", "hearty laugh")
def act_laugh(u, p, rig):
    sh = abs(_osc(u, 3.0))
    return ({"head": 12.0 - sh * 5.0, "chest": sh * 3.0, "spine": 3.0,
             "uarm_near": 15.0, "uarm_far": -15.0},
            {"smile": 1.0, "mouth_open": 0.45 + sh * 0.3, "blink": 0.5,
             "brow_raise": 0.4}, ZERO)


@action("cry", 2.0, True, "upper", "weeping, hands to eyes")
def act_cry(u, p, rig):
    sh = abs(_osc(u, 2.5)) * 3.0
    return ({"uarm_near": 120.0, "farm_near": 118.0,
             "head": -14.0 - sh, "neck": -5.0, "spine": -6.0, "chest": sh},
            {"smile": -0.9, "brow_sad": 1.0, "brow_raise": 0.5, "blink": 0.7,
             "mouth_open": 0.25}, ZERO)


@action("cheer", 1.2, True, "upper", "arms up in triumph")
def act_cheer(u, p, rig):
    w = abs(_osc(u, 1.0))
    return ({"uarm_near": 155.0 + w * 12.0, "uarm_far": -155.0 - w * 12.0,
             "farm_near": 15.0, "farm_far": -15.0, "head": 10.0},
            {"smile": 1.0, "mouth_open": 0.5, "brow_raise": 0.7}, ZERO)


@action("mourn", 3.0, True, "upper", "grief: bowed head, hand to chest")
def act_mourn(u, p, rig):
    sway = _osc(u, 0.5)
    return ({"head": -22.0 + sway * 2.0, "neck": -8.0, "spine": -10.0,
             "uarm_near": 55.0, "farm_near": 95.0},
            {"smile": -0.7, "brow_sad": 1.0, "blink": 0.6, "gaze_y": -0.6}, ZERO)


# ------------------------------------------------------------------ postures

@action("sit", 1.0, True, "full", "sit on a chair/edge at seat height",
        {"seat": "seat height in m (default 0.45)"}, suppresses_locomotion=True)
def act_sit(u, p, rig):
    k = _rise(min(u, 1.0), 0.9) if u < 1.0 else 1.0
    seat = float(p.get("seat", 0.45))
    leg = rig.height * 0.48
    drop = (rig.hip_height - seat) * k
    return ({"thigh_near": 85.0 * k, "shin_near": -80.0 * k, "foot_near": -5.0 * k,
             "thigh_far": 80.0 * k, "shin_far": -78.0 * k, "foot_far": -4.0 * k,
             "uarm_near": 25.0 * k, "farm_near": 25.0 * k,
             "uarm_far": -25.0 * k, "farm_far": -25.0 * k,
             "spine": -4.0 * k},
            {}, (0.0, -drop, 0.0))


@action("sit_ground", 1.2, True, "full", "sit on the ground, knees up",
        suppresses_locomotion=True)
def act_sit_ground(u, p, rig):
    k = _rise(min(u, 1.0), 0.9) if u < 1.0 else 1.0
    drop = (rig.hip_height - rig.height * 0.09) * k
    return ({"thigh_near": 118.0 * k, "shin_near": -128.0 * k, "foot_near": 8.0 * k,
             "thigh_far": 112.0 * k, "shin_far": -124.0 * k, "foot_far": 8.0 * k,
             "uarm_near": 55.0 * k, "farm_near": 55.0 * k,
             "uarm_far": -50.0 * k, "farm_far": -50.0 * k,
             "spine": -10.0 * k},
            {}, (0.0, -drop, 0.0))


@action("kneel", 1.2, True, "full", "down on one knee", suppresses_locomotion=True)
def act_kneel(u, p, rig):
    k = _rise(min(u, 1.0), 0.9) if u < 1.0 else 1.0
    drop = (rig.hip_height - rig.height * 0.3) * k
    return ({"thigh_near": 95.0 * k, "shin_near": -95.0 * k, "foot_near": 0.0,
             "thigh_far": -25.0 * k, "shin_far": -95.0 * k, "foot_far": -60.0 * k,
             "spine": -3.0 * k},
            {}, (0.0, -drop, 0.0))


@action("lie_down", 1.6, True, "full", "lie on the back",
        suppresses_locomotion=True)
def act_lie(u, p, rig):
    k = _rise(min(u, 1.0), 0.9) if u < 1.0 else 1.0
    drop = (rig.hip_height - rig.height * 0.08) * k
    return ({"thigh_near": 8.0 * k, "thigh_far": -6.0 * k,
             "shin_near": -6.0 * k, "shin_far": 4.0 * k,
             "uarm_near": 10.0 * k, "uarm_far": -10.0 * k,
             "head": -8.0 * k, "neck": -4.0 * k},
            {}, (0.0, -drop, 90.0 * k))


@action("sleep", 1.6, True, "full", "lie down and sleep", suppresses_locomotion=True)
def act_sleep(u, p, rig):
    angles, morphs, root = act_lie(min(u, 1.0), p, rig)
    k = _rise(min(u, 1.0), 0.9) if u < 1.0 else 1.0
    morphs = dict(morphs, blink=k, smile=0.15 * k)
    return angles, morphs, root


@action("pray", 2.0, True, "upper", "hands together, head bowed")
def act_pray(u, p, rig):
    k = _rise(min(u, 1.0), 0.4) if u < 1.0 else 1.0
    return ({"uarm_near": 70.0 * k, "farm_near": 85.0 * k,
             "uarm_far": 60.0 * k, "farm_far": 95.0 * k,
             "head": -16.0 * k, "neck": -6.0 * k},
            {"blink": 0.9 * k}, ZERO)


# ------------------------------------------------------------------ physical

@action("jump_joy", 0.9, True, "full", "happy little hops")
def act_jump_joy(u, p, rig):
    c = u % 1.0
    h = max(0.0, math.sin(c * math.pi)) ** 2 * rig.height * 0.12
    k = math.sin(c * math.pi)
    return ({"uarm_near": 140.0 * k, "uarm_far": -140.0 * k,
             "thigh_near": 15.0 * k, "shin_near": -25.0 * k,
             "thigh_far": 12.0 * k, "shin_far": -22.0 * k},
            {"smile": 0.9, "mouth_open": 0.35}, (0.0, h, 0.0))


@action("dance", 2.0, True, "full", "groove: sway, steps, alternating arms")
def act_dance(u, p, rig):
    w = _osc(u, 2.0)
    v = _osc(u, 1.0)
    bounce = abs(_osc(u, 4.0)) * rig.height * 0.02
    return ({"uarm_near": 90.0 + w * 60.0, "farm_near": 40.0 + w * 20.0,
             "uarm_far": -90.0 + w * 60.0, "farm_far": -40.0 + w * 20.0,
             "spine": v * 6.0, "head": -v * 6.0,
             "thigh_near": 8.0 + w * 6.0, "shin_near": -12.0,
             "thigh_far": -8.0 - w * 6.0, "shin_far": 10.0},
            {"smile": 0.8}, (0.0, bounce, v * 2.0))


@action("punch", 0.7, True, "upper", "jab-cross punches", {"hand": "near|far"})
def act_punch(u, p, rig):
    c = (u % 1.0)
    k = math.sin(min(c * 2.0, 1.0) * math.pi)
    s = _side(p)
    o = "far" if s == "near" else "near"
    sign = 1.0 if s == "near" else -1.0
    guard = 85.0 if o == "near" else -85.0
    return ({f"uarm_{s}": 95.0 * k, f"farm_{s}": (25.0 - 25.0 * k),
             f"uarm_{o}": -sign * 35.0, f"farm_{o}": guard,
             "spine": -8.0 * k, "chest": -4.0 * k},
            {"brow_angry": 0.8}, ZERO)


@action("kick", 0.9, True, "lower", "front kick", {"side": "near|far"})
def act_kick(u, p, rig):
    c = u % 1.0
    k = math.sin(min(c * 1.6, 1.0) * math.pi)
    s = _side(p)
    return ({f"thigh_{s}": 85.0 * k, f"shin_{s}": -30.0 * k + 25.0 * k,
             "spine": -6.0 * k},
            {"brow_angry": 0.6}, ZERO)


@action("push", 1.6, True, "upper", "push something ahead")
def act_push(u, p, rig):
    w = _osc(u, 1.0) * 6.0
    return ({"uarm_near": 80.0 + w, "farm_near": 15.0,
             "uarm_far": 75.0 + w, "farm_far": 20.0,
             "spine": -14.0, "chest": -4.0},
            {}, ZERO)


@action("carry", 1.0, True, "arms", "hold something in front with both hands")
def act_carry(u, p, rig):
    return ({"uarm_near": 55.0, "farm_near": 55.0,
             "uarm_far": 50.0, "farm_far": 60.0}, {}, ZERO)


@action("eat", 1.4, True, "upper", "bring food to the mouth", {"hand": "near|far"})
def act_eat(u, p, rig):
    c = u % 1.0
    k = math.sin(c * math.pi)
    s = _side(p)
    return ({f"uarm_{s}": 40.0 + 60.0 * k, f"farm_{s}": 60.0 + 55.0 * k,
             "head": -4.0 * k},
            {"mouth_open": 0.5 * max(0.0, math.sin((c - 0.35) * math.pi * 2))},
            ZERO)


@action("dig", 1.6, True, "full", "shovel the ground")
def act_dig(u, p, rig):
    c = u % 1.0
    k = math.sin(c * math.pi)
    return ({"uarm_near": 45.0 + 35.0 * k, "farm_near": 30.0,
             "uarm_far": 30.0 + 35.0 * k, "farm_far": 40.0,
             "spine": -18.0 - 14.0 * k, "thigh_near": 12.0, "shin_near": -18.0,
             "thigh_far": -8.0, "shin_far": -10.0},
            {}, (0.0, -rig.height * 0.02 * k, 0.0))


@action("hammer", 1.0, True, "upper", "strike downward repeatedly", {"hand": "near|far"})
def act_hammer(u, p, rig):
    c = u % 1.0
    k = math.sin(c * math.pi)
    s = _side(p)
    return ({f"uarm_{s}": 130.0 * k, f"farm_{s}": 40.0 * (1 - k) + 10.0,
             "spine": -6.0 * (1 - k)},
            {}, ZERO)


@action("hug", 2.5, True, "arms",
        "wrap arms forward — stand partners facing each other about 0.5 m apart")
def act_hug(u, p, rig):
    k = _rise(min(u, 1.0), 0.35) if u < 1.0 else 1.0
    return ({"uarm_near": 75.0 * k, "farm_near": 65.0 * k,
             "uarm_far": 88.0 * k, "farm_far": 50.0 * k,
             "head": 4.0 * k},
            {"smile": 0.6 * k, "blink": 0.5 * k}, ZERO)


@action("handshake", 1.6, True, "arm", "offer/shake hands", {"hand": "near|far"})
def act_handshake(u, p, rig):
    s = _side(p)
    w = _osc(u, 2.0) * 6.0
    return ({f"uarm_{s}": 70.0 + w * 0.5, f"farm_{s}": 20.0 + w}, {}, ZERO)


# --------------------------------------------------- interaction companions

@action("reach_down", 0.9, False, "full", "bend and reach toward the ground",
        {"hand": "near|far"})
def act_reach_down(u, p, rig):
    k = math.sin(min(u, 1.0) * math.pi)     # down and back up
    s = _side(p)
    return ({f"uarm_{s}": -35.0 * k, f"farm_{s}": 5.0,
             "spine": -38.0 * k, "chest": -10.0 * k, "head": 12.0 * k,
             "thigh_near": 28.0 * k, "shin_near": -42.0 * k,
             "thigh_far": 22.0 * k, "shin_far": -38.0 * k},
            {"gaze_y": -0.7 * k}, (0.0, -rig.height * 0.06 * k, 0.0))


@action("reach_forward", 1.0, False, "arm", "extend a hand forward (give/catch)",
        {"hand": "near|far"})
def act_reach_forward(u, p, rig):
    k = _rise(u, 0.3)
    s = _side(p)
    return ({f"uarm_{s}": 75.0 * k, f"farm_{s}": 8.0 * k}, {}, ZERO)


@action("windup_throw", 0.7, False, "upper", "wind up and hurl", {"hand": "near|far"})
def act_windup_throw(u, p, rig):
    s = _side(p)
    if u < 0.5:                              # windup back
        k = u / 0.5
        return ({f"uarm_{s}": (140.0 + 30.0 * k), f"farm_{s}": 60.0 * k,
                 "spine": 8.0 * k, "chest": 4.0 * k}, {}, ZERO)
    k = (u - 0.5) / 0.5                      # release forward
    return ({f"uarm_{s}": 170.0 - 95.0 * k, f"farm_{s}": 60.0 - 55.0 * k,
             "spine": 8.0 - 22.0 * k, "chest": 4.0 - 8.0 * k},
            {}, ZERO)


@action("hold_item", 1.0, True, "arm", "carry something at the side",
        {"hand": "near|far"})
def act_hold_item(u, p, rig):
    s = _side(p)
    return ({f"uarm_{s}": 14.0, f"farm_{s}": 22.0}, {}, ZERO)
