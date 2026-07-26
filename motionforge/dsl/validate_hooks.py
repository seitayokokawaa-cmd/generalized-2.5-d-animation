"""Registry of extra validators contributed by subsystems (assets, motion, audio).

Each hook: fn(production, report) -> None. Registered at import time by the
subsystem modules; keeps the validator decoupled while reporting through the
same Report.
"""
from __future__ import annotations

from typing import Callable, List

from ..core.errors import Report

HOOKS: List[Callable] = []


def register(fn: Callable) -> Callable:
    HOOKS.append(fn)
    return fn
