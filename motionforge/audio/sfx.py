"""Procedural sound effects. Every entry documents itself for the spec."""
from __future__ import annotations

from typing import Callable, Dict, Tuple

import numpy as np

from ..core.rng import MFRandom
from . import synth
from .synth import SR


def _env(n: int, a=0.005, d=0.1, s=0.0, r=0.05) -> np.ndarray:
    return synth.adsr(n, a, d, s, r)


def sfx_footstep(rng, ground: str = "grass") -> np.ndarray:
    base = {"grass": 300, "dirt": 240, "sand": 200, "stone": 700, "road": 650,
            "snow": 180, "wood": 500, "water": 350}.get(ground, 300)
    nz = synth.noise(0.09, rng)
    nz = synth.lowpass(nz, base + float(rng.uniform(-40, 40)))
    return (nz * _env(len(nz), 0.002, 0.06, 0.0, 0.03) * 0.8).astype(np.float32)


def sfx_thunder(rng) -> np.ndarray:
    nz = synth.noise(2.6, rng)
    low = synth.lowpass(nz, 90)
    mid = synth.lowpass(nz, 300) * 0.4
    x = (low + mid) * synth.adsr(len(nz), 0.01, 1.8, 0.12, 0.8)
    return synth.soft_clip(x * 2.2, 1.4) * 0.9


def sfx_door_creak(rng) -> np.ndarray:
    f = np.linspace(320, 180, int(0.7 * SR)) * (1 + 0.05 * np.sin(
        np.linspace(0, 40, int(0.7 * SR))))
    x = synth.osc(f, 0.7, "saw") * 0.12
    x += synth.lowpass(synth.noise(0.7, rng), 800) * 0.05
    return (x * _env(len(x), 0.05, 0.4, 0.3, 0.2)).astype(np.float32)


def sfx_whoosh(rng) -> np.ndarray:
    nz = synth.noise(0.5, rng)
    x = synth.lowpass(nz, 1200) - synth.lowpass(nz, 250)
    env = np.sin(np.linspace(0, np.pi, len(x))) ** 2
    return (x * env * 0.7).astype(np.float32)


def sfx_splash(rng) -> np.ndarray:
    nz = synth.noise(0.7, rng)
    x = synth.lowpass(nz, 1600) - synth.lowpass(nz, 300)
    return (x * _env(len(x), 0.004, 0.35, 0.1, 0.25) * 0.8).astype(np.float32)


def sfx_crash(rng) -> np.ndarray:
    nz = synth.noise(1.1, rng)
    x = synth.lowpass(nz, 2400)
    x += synth.osc(np.linspace(180, 60, len(x)) , 1.1, "sine") * 0.3
    return synth.soft_clip(x * _env(len(x), 0.002, 0.5, 0.05, 0.5) * 1.6, 1.3) * 0.85


def sfx_thump(rng) -> np.ndarray:
    x = synth.osc(np.linspace(120, 45, int(0.28 * SR)), 0.28, "sine")
    x += synth.lowpass(synth.noise(0.28, rng), 200) * 0.5
    return (x * _env(len(x), 0.002, 0.16, 0.0, 0.1) * 0.9).astype(np.float32)


def sfx_pop(rng) -> np.ndarray:
    x = synth.osc(np.linspace(600, 300, int(0.06 * SR)), 0.06, "sine")
    return (x * _env(len(x), 0.001, 0.04, 0.0, 0.02) * 0.6).astype(np.float32)


def sfx_ding(rng) -> np.ndarray:
    x = synth.note(1320, 0.9, "sine", vol=0.4, a=0.002, d=0.5, s=0.15, r=0.3,
                   harmonics=3)
    return x


def sfx_boing(rng) -> np.ndarray:
    f = 300 * 2 ** (-np.linspace(0, 1.2, int(0.5 * SR)))
    x = synth.osc(f * (1 + 0.15 * np.sin(np.linspace(0, 60, len(f)))), 0.5, "sine")
    return (x * _env(len(x), 0.002, 0.3, 0.1, 0.15) * 0.6).astype(np.float32)


def sfx_birdsong(rng) -> np.ndarray:
    out = synth.silence(1.6)
    t0 = 0.0
    for _ in range(int(rng.integers(3, 6))):
        dur = float(rng.uniform(0.08, 0.2))
        f0 = float(rng.uniform(2200, 3800))
        f = f0 + np.sin(np.linspace(0, float(rng.uniform(20, 60)), int(dur * SR))) * 300
        chirp = synth.osc(f, dur, "sine") * _env(int(dur * SR), 0.01, dur * 0.5, 0.2, 0.05)
        i0 = int(t0 * SR)
        n = min(len(chirp), len(out) - i0)
        if n > 0:
            out[i0:i0 + n] += chirp[:n] * 0.35
        t0 += dur + float(rng.uniform(0.05, 0.25))
    return out


def sfx_wind(rng) -> np.ndarray:
    nz = synth.noise(4.0, rng)
    x = synth.lowpass(nz, 400)
    mod = 0.5 + 0.5 * np.sin(np.linspace(0, 5.5, len(x)))
    return (x * mod * 0.35).astype(np.float32)


def sfx_rain_bed(rng) -> np.ndarray:
    nz = synth.noise(4.0, rng)
    x = synth.lowpass(nz, 3000) - synth.lowpass(nz, 350)
    return (x * 0.30).astype(np.float32)


def sfx_knock(rng) -> np.ndarray:
    out = synth.silence(0.8)
    for i in range(3):
        x = synth.osc(np.linspace(220, 130, int(0.08 * SR)), 0.08, "sine")
        x = (x + synth.lowpass(synth.noise(0.08, rng), 500) * 0.5)
        x *= _env(len(x), 0.001, 0.06, 0.0, 0.02)
        i0 = int(i * 0.22 * SR)
        out[i0:i0 + len(x)] += x * 0.8
    return out


def sfx_bell(rng) -> np.ndarray:
    x = synth.note(660, 2.2, "sine", vol=0.35, a=0.002, d=1.4, s=0.1, r=0.6,
                   harmonics=4)
    return x


def sfx_cheer_crowd(rng) -> np.ndarray:
    nz = synth.noise(2.2, rng)
    x = synth.lowpass(nz, 1200) - synth.lowpass(nz, 300)
    mod = 0.6 + 0.4 * np.sin(np.linspace(0, 18, len(x)))
    return (x * mod * synth.adsr(len(x), 0.3, 0.8, 0.5, 0.8) * 0.5).astype(np.float32)


SFX: Dict[str, Tuple[Callable, str]] = {
    "footstep":   (sfx_footstep, "one soft step (auto-played by walking)"),
    "thunder":    (sfx_thunder, "rolling thunder clap"),
    "door_creak": (sfx_door_creak, "hinged door creak (auto-played by hinge)"),
    "whoosh":     (sfx_whoosh, "fast swish (auto-played by throw)"),
    "splash":     (sfx_splash, "water splash"),
    "crash":      (sfx_crash, "breaking crash"),
    "thump":      (sfx_thump, "heavy soft impact (auto-played by ragdoll)"),
    "pop":        (sfx_pop, "small pop (auto-played by catch)"),
    "ding":       (sfx_ding, "bright ding"),
    "boing":      (sfx_boing, "cartoon bounce"),
    "birdsong":   (sfx_birdsong, "songbird chirps"),
    "wind":       (sfx_wind, "wind gust bed"),
    "rain_bed":   (sfx_rain_bed, "rain ambience (auto-played by rain)"),
    "knock":      (sfx_knock, "three knocks"),
    "bell":       (sfx_bell, "church-ish bell"),
    "cheer_crowd": (sfx_cheer_crowd, "crowd cheering swell"),
}


def build(name: str, rng: MFRandom, key: str = "", **kw) -> np.ndarray:
    fn, _doc = SFX[name]
    return fn(rng.stream(f"sfx:{name}:{key}"), **kw)
