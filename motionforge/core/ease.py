"""Easing curves. All map t in [0,1] -> [0,1] (bounce/elastic may overshoot)."""
from __future__ import annotations

import math
from typing import Callable, Dict


def linear(t: float) -> float:
    return t


def ease_in(t: float) -> float:
    return t * t


def ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def in_out(t: float) -> float:
    return 2 * t * t if t < 0.5 else 1.0 - 2 * (1.0 - t) * (1.0 - t)


def in_cubic(t: float) -> float:
    return t * t * t


def out_cubic(t: float) -> float:
    u = 1.0 - t
    return 1.0 - u * u * u


def in_out_cubic(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1.0 - 4 * (1.0 - t) ** 3


def out_bounce(t: float) -> float:
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def out_elastic(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c4 = (2 * math.pi) / 3
    return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def out_back(t: float) -> float:
    c1 = 1.70158
    c3 = c1 + 1
    u = t - 1
    return 1 + c3 * u * u * u + c1 * u * u


def hold(t: float) -> float:
    """Step at the end: value holds until the segment completes."""
    return 0.0 if t < 1.0 else 1.0


def step(t: float) -> float:
    """Step at the start: value jumps immediately."""
    return 1.0 if t > 0.0 else 0.0


EASES: Dict[str, Callable[[float], float]] = {
    "linear": linear,
    "in": ease_in,
    "out": ease_out,
    "in_out": in_out,
    "in_cubic": in_cubic,
    "out_cubic": out_cubic,
    "in_out_cubic": in_out_cubic,
    "bounce": out_bounce,
    "elastic": out_elastic,
    "back": out_back,
    "hold": hold,
    "step": step,
}


def get(name: str) -> Callable[[float], float]:
    try:
        return EASES[name]
    except KeyError:
        raise KeyError(
            f"unknown ease '{name}' — choose one of: {', '.join(sorted(EASES))}"
        ) from None
