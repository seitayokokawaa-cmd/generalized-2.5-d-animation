"""Procedural background music: mood programs rendered deterministically.

A mood defines tempo, scale, chord loop and voicing; the melody is a seeded
random walk, so the same screenplay seed always yields the same track.
"""
from __future__ import annotations

import numpy as np

from ..core.rng import MFRandom
from . import synth
from .synth import SR

# midi note number -> frequency
def _hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12.0)


# mood: (bpm, root_midi, mode intervals, chord degrees loop, brightness)
MOODS = {
    "pastoral": (92, 62, [0, 2, 4, 5, 7, 9, 11], [0, 3, 5, 4], 0.7),
    "happy":    (122, 60, [0, 2, 4, 5, 7, 9, 11], [0, 4, 5, 3], 0.9),
    "sad":      (68, 57, [0, 2, 3, 5, 7, 8, 10], [0, 5, 2, 6], 0.35),
    "tense":    (100, 55, [0, 1, 3, 5, 7, 8, 10], [0, 0, 5, 6], 0.3),
    "epic":     (108, 55, [0, 2, 4, 5, 7, 9, 11], [0, 6, 3, 4], 0.8),
    "mystery":  (84, 58, [0, 2, 4, 6, 8, 10], [0, 2, 4, 1], 0.4),
    "lullaby":  (76, 64, [0, 2, 4, 5, 7, 9, 11], [0, 3, 4, 0], 0.6),
    "march":    (116, 57, [0, 2, 4, 5, 7, 9, 11], [0, 0, 4, 4], 0.75),
}


def render_music(mood: str, duration: float, rng: MFRandom,
                 volume: float = 0.7) -> np.ndarray:
    """Stereo (n, 2) float32 music bed for the whole film."""
    bpm, root, mode, chords, bright = MOODS.get(mood, MOODS["pastoral"])
    beat = 60.0 / bpm
    bar = beat * 4
    n = int(duration * SR)
    out = np.zeros((n, 2), dtype=np.float32)
    r = rng.stream(f"music:{mood}")

    def scale_note(degree: int, octave: int = 0) -> float:
        return _hz(root + mode[degree % len(mode)] + 12 * (octave + degree // len(mode)))

    t = 0.0
    bar_i = 0
    while t < duration:
        deg = chords[bar_i % len(chords)]
        # pad chord: root, third, fifth — soft sines
        for k, dv in enumerate((0, 2, 4)):
            f = scale_note(deg + dv, 0)
            clip = synth.note(f, bar * 1.02, "sine", vol=0.05 + 0.02 * bright,
                              a=0.4, d=0.3, s=0.8, r=0.6, harmonics=2)
            synth.mix_into(out, clip, t, pan=(k - 1) * 0.3, vol=1.0)
        # bass on 1 and 3
        for b in (0, 2):
            f = scale_note(deg, -1) / 2
            clip = synth.note(f, beat * 1.6, "triangle", vol=0.14,
                              a=0.01, d=0.1, s=0.5, r=0.3)
            synth.mix_into(out, synth.lowpass(clip, 300), t + b * beat, pan=0.0)
        # melody: seeded walk on 8ths, rests ~35%
        mel_deg = deg + 7
        for e in range(8):
            if float(r.uniform(0, 1)) < 0.38:
                continue
            step = int(r.integers(-2, 3))
            mel_deg = int(np.clip(mel_deg + step, deg + 4, deg + 12))
            f = scale_note(mel_deg, 0)
            dur_n = beat * (0.45 if e % 2 else 0.9)
            wave = "triangle" if bright > 0.5 else "sine"
            clip = synth.note(f, dur_n, wave, vol=0.10 + 0.05 * bright,
                              a=0.015, d=0.1, s=0.55, r=0.12, harmonics=2)
            synth.mix_into(out, clip, t + e * beat / 2,
                           pan=float(r.uniform(-0.25, 0.25)))
        # march/epic percussion
        if mood in ("march", "epic"):
            pr = rng.stream(f"perc:{bar_i}")
            for b in range(4):
                nz = synth.noise(0.09, pr) * synth.adsr(int(0.09 * SR), 0.001, 0.06, 0.0, 0.02)
                nz = synth.highpass(nz, 900) * (0.20 if b % 2 == 0 else 0.10)
                synth.mix_into(out, nz.astype(np.float32), t + b * beat)
        t += bar
        bar_i += 1
    # gentle fade at the very end
    fade_n = min(int(1.2 * SR), n)
    out[n - fade_n:] *= np.linspace(1, 0, fade_n, dtype=np.float32)[:, None]
    return (out * volume).astype(np.float32)
