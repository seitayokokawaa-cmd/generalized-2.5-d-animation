"""Deterministic math primitives: interpolation, easing, springs, seeded RNG,
and 2D affine transforms.

Everything here is pure and reproducible: no wall clocks, no global random
state. All randomness in MotionForge flows through :class:`DetRandom`,
seeded by hashing the screenplay content plus a stable key path, so the same
screenplay always produces the exact same film.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

TAU = math.tau


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def inv_lerp(a: float, b: float, x: float) -> float:
    if a == b:
        return 0.0
    return (x - a) / (b - a)


def remap(x: float, a0: float, a1: float, b0: float, b1: float) -> float:
    return lerp(b0, b1, clamp01(inv_lerp(a0, a1, x)))


def smoothstep(t: float) -> float:
    t = clamp01(t)
    return t * t * (3.0 - 2.0 * t)


def smootherstep(t: float) -> float:
    t = clamp01(t)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


# ---------------------------------------------------------------------------
# Easing curves (all map [0,1] -> [0,1])
# ---------------------------------------------------------------------------

def ease_linear(t: float) -> float:
    return clamp01(t)


def ease_in(t: float) -> float:
    t = clamp01(t)
    return t * t


def ease_out(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_out(t: float) -> float:
    return smoothstep(t)


def ease_out_back(t: float) -> float:
    t = clamp01(t)
    c1, c3 = 1.70158, 2.70158
    u = t - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


def ease_out_elastic(t: float) -> float:
    t = clamp01(t)
    if t in (0.0, 1.0):
        return t
    c4 = TAU / 3.0
    return math.pow(2.0, -10.0 * t) * math.sin((t * 10.0 - 0.75) * c4) + 1.0


def ease_out_bounce(t: float) -> float:
    t = clamp01(t)
    n1, d1 = 7.5625, 2.75
    if t < 1.0 / d1:
        return n1 * t * t
    if t < 2.0 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


EASING = {
    "linear": ease_linear,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease": ease_in_out,
    "ease_in_out": ease_in_out,
    "back": ease_out_back,
    "elastic": ease_out_elastic,
    "bounce": ease_out_bounce,
}


def eased(name: str, t: float) -> float:
    return EASING.get(name, ease_in_out)(t)


# ---------------------------------------------------------------------------
# Envelope: smooth attack/release window for layering animation clips
# ---------------------------------------------------------------------------

def envelope(t: float, duration: float, attack: float = 0.25, release: float = 0.3) -> float:
    """0→1→0 weight over a clip of `duration` seconds; smooth on both ends."""
    if duration <= 0.0 or t <= 0.0 or t >= duration:
        return 0.0
    attack = min(attack, duration * 0.5)
    release = min(release, duration * 0.5)
    w = 1.0
    if t < attack:
        w = smoothstep(t / attack)
    if t > duration - release:
        w = min(w, smoothstep((duration - t) / release))
    return w


# ---------------------------------------------------------------------------
# Angles
# ---------------------------------------------------------------------------

def wrap_angle(a: float) -> float:
    """Wrap to (-pi, pi]."""
    a = math.fmod(a + math.pi, TAU)
    if a <= 0.0:
        a += TAU
    return a - math.pi


def lerp_angle(a: float, b: float, t: float) -> float:
    return a + wrap_angle(b - a) * t


# ---------------------------------------------------------------------------
# Critically damped spring (smooth camera follow without overshoot)
# ---------------------------------------------------------------------------

def spring_track(pos: float, vel: float, target: float, halflife: float, dt: float) -> tuple[float, float]:
    """Advance a critically damped spring one step; returns (pos, vel).

    `halflife` is the time for the remaining distance to roughly halve —
    an intuitive smoothing knob.
    """
    if halflife <= 1e-6:
        return target, 0.0
    omega = 2.0 * 0.6931472 / halflife
    x = pos - target
    exp = math.exp(-omega * dt)
    new_x = (x + (vel + omega * x) * dt) * exp
    new_v = (vel - (vel + omega * x) * omega * dt) * exp
    return target + new_x, new_v


# ---------------------------------------------------------------------------
# Deterministic randomness
# ---------------------------------------------------------------------------

def stable_hash(*keys: object) -> int:
    """A cross-platform stable 64-bit hash of the given key path."""
    text = "\x1f".join(str(k) for k in keys)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class DetRandom(random.Random):
    """Deterministic RNG namespaced by a key path.

    DetRandom(seed, "scene3", "rain") always yields the same sequence for
    the same screenplay seed, independent of call order elsewhere.
    """

    def __init__(self, *keys: object):
        super().__init__(stable_hash(*keys))


def hash_noise(*keys: object) -> float:
    """A single deterministic float in [0,1) from a key path. Cheap, stateless."""
    return (stable_hash(*keys) % (1 << 53)) / float(1 << 53)


def value_noise_1d(x: float, *keys: object) -> float:
    """Smooth deterministic 1D value noise in [0,1); period-free, stateless."""
    x0 = math.floor(x)
    t = smoothstep(x - x0)
    a = hash_noise(*keys, int(x0))
    b = hash_noise(*keys, int(x0) + 1)
    return lerp(a, b, t)


def fbm_1d(x: float, octaves: int = 3, *keys: object) -> float:
    """Fractal noise in [0,1): layered value noise for organic wobble."""
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for octave in range(octaves):
        total += amp * value_noise_1d(x * freq, *keys, octave)
        norm += amp
        amp *= 0.5
        freq *= 2.03
    return total / norm


# ---------------------------------------------------------------------------
# 2D affine transform (row-major: [a c e; b d f; 0 0 1])
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Mat2D:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @staticmethod
    def identity() -> "Mat2D":
        return Mat2D()

    @staticmethod
    def translate(tx: float, ty: float) -> "Mat2D":
        return Mat2D(1.0, 0.0, 0.0, 1.0, tx, ty)

    @staticmethod
    def scale(sx: float, sy: float | None = None) -> "Mat2D":
        if sy is None:
            sy = sx
        return Mat2D(sx, 0.0, 0.0, sy, 0.0, 0.0)

    @staticmethod
    def rotate(theta: float) -> "Mat2D":
        c, s = math.cos(theta), math.sin(theta)
        return Mat2D(c, s, -s, c, 0.0, 0.0)

    @staticmethod
    def trs(tx: float, ty: float, theta: float = 0.0, sx: float = 1.0, sy: float | None = None) -> "Mat2D":
        if sy is None:
            sy = sx
        c, s = math.cos(theta), math.sin(theta)
        return Mat2D(c * sx, s * sx, -s * sy, c * sy, tx, ty)

    def __matmul__(self, other: "Mat2D") -> "Mat2D":
        """self @ other: apply `other` first, then `self`."""
        return Mat2D(
            self.a * other.a + self.c * other.b,
            self.b * other.a + self.d * other.b,
            self.a * other.c + self.c * other.d,
            self.b * other.c + self.d * other.d,
            self.a * other.e + self.c * other.f + self.e,
            self.b * other.e + self.d * other.f + self.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def apply_vec(self, x: float, y: float) -> tuple[float, float]:
        """Transform a direction (ignores translation)."""
        return (self.a * x + self.c * y, self.b * x + self.d * y)

    def apply_many(self, pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        a, b, c, d, e, f = self.a, self.b, self.c, self.d, self.e, self.f
        return [(a * x + c * y + e, b * x + d * y + f) for x, y in pts]


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(bx - ax, by - ay)


def two_bone_ik(
    root: tuple[float, float],
    target: tuple[float, float],
    len1: float,
    len2: float,
    bend: float = 1.0,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Analytic two-bone IK. Returns (joint, end) positions.

    `bend` = +1 bends the middle joint to one side, -1 to the other
    (e.g. knees bend backward, elbows forward). If the target is out of
    reach, the chain stretches straight toward it — never glitches.
    """
    rx, ry = root
    tx, ty = target
    dx, dy = tx - rx, ty - ry
    d = math.hypot(dx, dy)
    reach = len1 + len2
    if d < 1e-9:
        return (rx + len1, ry), (rx + len1 - len2, ry)
    if d >= reach - 1e-9:
        ux, uy = dx / d, dy / d
        joint = (rx + ux * len1, ry + uy * len1)
        end = (rx + ux * min(d, reach), ry + uy * min(d, reach))
        return joint, end
    # Law of cosines for the middle joint.
    a = (len1 * len1 - len2 * len2 + d * d) / (2.0 * d)
    h = math.sqrt(max(0.0, len1 * len1 - a * a)) * (1.0 if bend >= 0 else -1.0)
    ux, uy = dx / d, dy / d
    joint = (rx + ux * a - uy * h, ry + uy * a + ux * h)
    return joint, (tx, ty)
