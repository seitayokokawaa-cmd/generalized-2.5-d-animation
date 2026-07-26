"""Deterministic randomness with named substreams.

Every subsystem that needs randomness asks for a *named* stream:

    rng = MFRandom(seed=7)
    blink = rng.stream("blink:asha")

Streams are independent: adding a new consumer never changes the sequence any
existing consumer sees, so renders stay stable as features are added.
"""
from __future__ import annotations

import hashlib

import numpy as np


class MFRandom:
    def __init__(self, seed: int = 0):
        self.seed = int(seed)

    def stream(self, name: str) -> np.random.Generator:
        digest = hashlib.sha256(f"{self.seed}:{name}".encode()).digest()
        child_seed = int.from_bytes(digest[:8], "little")
        return np.random.Generator(np.random.PCG64(child_seed))

    def uniform(self, name: str, lo: float, hi: float, n: int | None = None):
        return self.stream(name).uniform(lo, hi, n)
