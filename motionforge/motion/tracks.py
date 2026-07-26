"""Keyframe tracks: the universal animation primitive.

A Track holds (time, value, ease) keys in time order and samples by
interpolating between neighbors with the *destination* key's easing.
Values can be floats, vec2 tuples, or anything the lerp function handles.
"""
from __future__ import annotations

from bisect import bisect_right
from typing import Any, Callable, List, Optional, Tuple

from ..core import ease as easing
from ..core.vec import angle_lerp, lerp, vlerp


def _lerp_any(a: Any, b: Any, t: float) -> Any:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return lerp(float(a), float(b), t)
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return tuple(lerp(float(x), float(y), t) for x, y in zip(a, b))
    return b if t >= 1.0 else a


class Track:
    __slots__ = ("keys", "lerp_fn")

    def __init__(self, initial: Any = None, t0: float = 0.0,
                 lerp_fn: Callable[[Any, Any, float], Any] = _lerp_any):
        self.keys: List[Tuple[float, Any, str]] = []
        self.lerp_fn = lerp_fn
        if initial is not None:
            self.keys.append((t0, initial, "linear"))

    def add(self, t: float, value: Any, ease: str = "in_out") -> None:
        """Append a key; keys must be added in non-decreasing time order."""
        if self.keys and t < self.keys[-1][0]:
            # keep determinism: clamp to last time rather than reorder silently
            t = self.keys[-1][0]
        self.keys.append((t, value, ease))

    def hold(self, t: float) -> None:
        """Anchor the current value at time t (so a later key eases from here)."""
        if self.keys:
            self.add(t, self.sample(t), "linear")

    def last_time(self) -> float:
        return self.keys[-1][0] if self.keys else 0.0

    def last_value(self) -> Any:
        return self.keys[-1][1] if self.keys else None

    def sample(self, t: float) -> Any:
        keys = self.keys
        if not keys:
            return None
        if t <= keys[0][0]:
            return keys[0][1]
        if t >= keys[-1][0]:
            return keys[-1][1]
        # find segment: last key with time <= t
        times = [k[0] for k in keys]
        i = bisect_right(times, t) - 1
        t0, v0, _ = keys[i]
        t1, v1, ez = keys[i + 1]
        if t1 <= t0:
            return v1
        u = (t - t0) / (t1 - t0)
        u = easing.EASES.get(ez, easing.in_out)(u)
        return self.lerp_fn(v0, v1, u)


def angle_track(initial: float = 0.0, t0: float = 0.0) -> Track:
    return Track(initial, t0, lerp_fn=lambda a, b, t: angle_lerp(float(a), float(b), t))
