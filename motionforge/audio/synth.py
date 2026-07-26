"""Tiny deterministic synthesizer: numpy oscillators, envelopes, filters."""
from __future__ import annotations

import numpy as np

SR = 44100


def silence(dur: float) -> np.ndarray:
    return np.zeros(int(dur * SR), dtype=np.float32)


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR), dtype=np.float32) / SR


def osc(freq, dur: float, wave: str = "sine", detune: float = 0.0) -> np.ndarray:
    """freq: scalar or array (for sweeps)."""
    t = _t(dur)
    if np.isscalar(freq):
        phase = 2 * np.pi * float(freq) * (1 + detune) * t
    else:
        freq = np.asarray(freq, dtype=np.float32)
        phase = 2 * np.pi * np.cumsum(freq * (1 + detune)) / SR
    if wave == "sine":
        return np.sin(phase).astype(np.float32)
    if wave == "saw":
        return (2 * ((phase / (2 * np.pi)) % 1.0) - 1).astype(np.float32)
    if wave == "square":
        return np.sign(np.sin(phase)).astype(np.float32)
    if wave == "triangle":
        return (2 * np.abs(2 * ((phase / (2 * np.pi)) % 1.0) - 1) - 1).astype(np.float32)
    return np.sin(phase).astype(np.float32)


def noise(dur: float, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1, 1, int(dur * SR)).astype(np.float32)


def adsr(n: int, a: float = 0.01, d: float = 0.08, s: float = 0.7,
         r: float = 0.12) -> np.ndarray:
    """Envelope over n samples (times in seconds)."""
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(n - a_n - d_n - r_n, 0)
    env = np.concatenate([
        np.linspace(0, 1, max(a_n, 1), endpoint=False),
        np.linspace(1, s, max(d_n, 1), endpoint=False),
        np.full(s_n, s, dtype=np.float32),
        np.linspace(s, 0, max(r_n, 1)),
    ]).astype(np.float32)
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n]


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """One-pole lowpass y[n] = a*x[n] + (1-a)*y[n-1], vectorized in blocks."""
    w = 2 * np.pi * cutoff / SR
    a = float(np.clip(w / (w + 1), 0.001, 0.999))
    r = 1.0 - a
    xs = x.astype(np.float64)
    ys = np.empty_like(xs)
    B = 64                       # small enough that r**-B never overflows
    powers = r ** np.arange(B + 1)
    inv = 1.0 / powers[:B]
    prev = 0.0
    for i0 in range(0, len(xs), B):
        blk = xs[i0:i0 + B]
        n = len(blk)
        acc = np.cumsum(blk * inv[:n])
        yb = a * powers[:n] * acc + prev * powers[1:n + 1]
        ys[i0:i0 + B] = yb
        prev = yb[-1]
    return ys.astype(np.float32)


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    return (x - lowpass(x, cutoff)).astype(np.float32)


def note(freq: float, dur: float, wave: str = "sine", vol: float = 0.5,
         a: float = 0.01, d: float = 0.08, s: float = 0.7, r: float = 0.12,
         harmonics: int = 1) -> np.ndarray:
    x = osc(freq, dur, wave)
    for h in range(2, harmonics + 1):
        x = x + osc(freq * h, dur, wave) * (0.4 / h)
    n = len(x)
    return (x * adsr(n, a, d, s, r) * vol).astype(np.float32)


def echo(x: np.ndarray, delay: float = 0.22, feedback: float = 0.3,
         mix: float = 0.25, taps: int = 3) -> np.ndarray:
    d = int(delay * SR)
    out = x.copy().astype(np.float32)
    tap = x
    for k in range(1, taps + 1):
        shifted = np.zeros(len(x) + d * k, dtype=np.float32)
        shifted[d * k:] = tap * (feedback ** k)
        out = np.pad(out, (0, max(0, len(shifted) - len(out))))
        out[:len(shifted)] += shifted * mix
        tap = tap
    return out


def soft_clip(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    return np.tanh(x * drive).astype(np.float32)


def mix_into(target: np.ndarray, clip: np.ndarray, at: float,
             pan: float = 0.0, vol: float = 1.0) -> None:
    """Add a mono clip into a stereo (n, 2) buffer at time `at` (seconds)."""
    i0 = int(at * SR)
    if i0 >= len(target) or i0 + len(clip) <= 0:
        return
    if i0 < 0:
        clip = clip[-i0:]
        i0 = 0
    n = min(len(clip), len(target) - i0)
    if n <= 0:
        return
    pan = float(np.clip(pan, -1.0, 1.0))
    lg = np.sqrt(0.5 * (1 - pan))
    rg = np.sqrt(0.5 * (1 + pan))
    target[i0:i0 + n, 0] += clip[:n] * vol * lg
    target[i0:i0 + n, 1] += clip[:n] * vol * rg
