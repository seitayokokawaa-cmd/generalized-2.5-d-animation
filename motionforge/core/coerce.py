"""Tolerant coercion for user-supplied values on rendering paths.

The validator reports wrong types with line numbers; these helpers make the
render path never crash on them — bad values fall back to sane defaults.
"""
from __future__ import annotations

import math
from typing import Any, Optional, Tuple


def fnum(value: Any, default: float, lo: Optional[float] = None,
         hi: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    v = float(value)
    if not math.isfinite(v):
        return default
    if lo is not None and v < lo:
        v = lo
    if hi is not None and v > hi:
        v = hi
    return v


def fvec2(value: Any, default: Tuple[float, float]) -> Tuple[float, float]:
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(c, (int, float)) and not isinstance(c, bool)
                    and math.isfinite(float(c)) for c in value)):
        return (float(value[0]), float(value[1]))
    return default


def is_vec2(value: Any) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(c, (int, float)) and not isinstance(c, bool)
                    and math.isfinite(float(c)) for c in value))
