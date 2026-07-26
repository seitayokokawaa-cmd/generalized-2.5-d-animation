"""The soundtrack mixer: music + scripted SFX + auto-SFX -> stereo WAV.

Auto-SFX are derived from the same compiled programs that drive the visuals,
so footsteps land exactly on foot plants and thumps on ragdoll impacts.
"""
from __future__ import annotations

import math
import wave
from typing import List, Optional, Tuple

import numpy as np

from ..core.vec import clamp
from ..motion.gait import GAITS
from ..scene.world import World
from . import sfx as sfxmod
from . import synth
from .music import render_music
from .synth import SR


def _pan_for(world: World, cs, x: float, t: float) -> float:
    cam = world.camera_state(cs, t)
    return clamp((x - cam.x) / 7.0, -0.9, 0.9)


def _ease(u: float) -> float:
    return u * u * (3 - 2 * u)


def _invert_ease(target: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _ease(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _footstep_events(world: World) -> List[Tuple[float, float, str, float]]:
    """(abs_time, world_x, ground, volume) for every foot plant."""
    events = []
    for cs in world.scenes:
        bg = cs.scene.background.get("ground", "grass")
        ground = bg.get("kind", "grass") if isinstance(bg, dict) else str(bg)
        for ent in cs.entities:
            prog = ent.program
            if prog is None or not hasattr(prog, "segments") or ent.rig is None:
                continue
            if not getattr(ent.rig, "legs", None):
                continue
            leg_chain = next(iter(ent.rig.legs.values()))
            l1 = ent.rig.skeleton.bones[leg_chain.upper].length
            l2 = ent.rig.skeleton.bones[leg_chain.lower].length
            leg = l1 + l2
            for seg in prog.segments:
                if seg.mode not in GAITS or seg.total < 1e-6 or seg.t1 <= seg.t0:
                    continue
                g = GAITS[seg.mode]
                step = g["step_h"] * leg * (0.8 if prog.is_quad else 0.55)
                n_steps = max(1, round(seg.total / step))
                step = seg.total / n_steps
                vol = {"run": 1.0, "march": 0.9, "sneak": 0.25,
                       "limp": 0.6}.get(seg.mode, 0.55)
                dur = seg.t1 - seg.t0
                for k in range(1, n_steps + 1):
                    u = _invert_ease(k * step / seg.total)
                    t_loc = seg.t0 + u * dur
                    x = seg.p0[0] + (seg.p1[0] - seg.p0[0]) * _ease(u)
                    events.append((cs.scene.start_time + t_loc, x, ground, vol))
    return events


def _ragdoll_events(world: World) -> List[Tuple[float, float]]:
    events = []
    for cs in world.scenes:
        for ent in cs.entities:
            prog = ent.program
            if prog is None or not getattr(prog, "ragdolls", None):
                continue
            for sim in prog._ensure_ragdolls():
                hit = False
                for i, frame in enumerate(sim.frames):
                    low = min(p[1] for p in frame)
                    if low < 0.09 and not hit and i > 3:
                        hit = True
                        events.append((cs.scene.start_time + sim.t0 + i / 120.0,
                                       sim.origin[0]))
                    elif low > 0.2:
                        hit = False
    return events


def build_soundtrack(world: World) -> np.ndarray:
    prod = world.production
    duration = max(prod.duration, 0.5)
    n = int(duration * SR)
    out = np.zeros((n, 2), dtype=np.float32)

    # ------------------------------------------------------------- music
    music_spec = prod.audio.music
    if music_spec:
        mood = str(music_spec.get("mood", "pastoral"))
        vol = float(music_spec.get("volume", 0.7))
        music = render_music(mood, duration, world.rng, vol)
        m = min(len(music), n)
        out[:m] += music[:m]

    # ---------------------------------------------------- scripted sfx
    def play(name: str, t_abs: float, pan: float, vol: float, key: str,
             **kw) -> None:
        if name not in sfxmod.SFX:
            return
        clip = sfxmod.build(name, world.rng, key=key, **kw)
        synth.mix_into(out, clip, t_abs, pan=pan, vol=vol)

    for i, s in enumerate(prod.audio.sfx or []):
        if isinstance(s, dict) and "sound" in s:
            play(str(s["sound"]), float(s.get("t", 0.0)), 0.0,
                 float(s.get("volume", 1.0)), key=f"film{i}")

    for cs in world.scenes:
        t0s = cs.scene.start_time
        for i, d in enumerate(cs.scene.timeline):
            if d.subject_kind == "sfx":
                play(str(d.params.get("sound", "")), t0s + d.t, 0.0,
                     float(d.params.get("volume", 1.0)), key=f"{cs.scene.id}:{i}")
            elif d.subject_kind == "obj" and d.verb == "hinge":
                ent = cs.entity(d.subject)
                x = ent.position(d.t)[0] if ent else 0.0
                play("door_creak", t0s + d.t, _pan_for(world, cs, x, d.t), 0.8,
                     key=f"h{cs.scene.id}:{i}")
        # interactions
        if cs.links is not None:
            for obj_id, flights in cs.links.flights.items():
                for fl in flights:
                    play("whoosh", t0s + fl.t0, 0.0, 0.7, key=f"th{obj_id}{fl.t0}")
            for obj_id, holds in cs.links.holds.items():
                for h in holds:
                    if h.t0 > 0.5:
                        play("pop", t0s + h.t0, 0.0, 0.4, key=f"po{obj_id}{h.t0}")
        # weather ambience, sampled per second
        if cs.weather is not None:
            t = 0.0
            while t < cs.scene.duration:
                kind, inten = cs.weather.state_at(t + 0.25)
                if kind == "rain" and inten > 0.05:
                    play("rain_bed", t0s + t, 0.0, 0.55 * inten, key="rb")
                elif kind in ("snow", "fog") and inten > 0.05:
                    play("wind", t0s + t, 0.0, 0.35 * inten, key="wd")
                t += 3.8

    # ------------------------------------------------------- auto events
    for (t_abs, x, ground, vol) in _footstep_events(world):
        cs, _ = world.scene_at(t_abs)
        play("footstep", t_abs, _pan_for(world, cs, x, t_abs - cs.scene.start_time),
             vol, key=f"fs{t_abs:.3f}", ground=ground)
    for (t_abs, x) in _ragdoll_events(world):
        cs, _ = world.scene_at(t_abs)
        play("thump", t_abs, _pan_for(world, cs, x, t_abs - cs.scene.start_time),
             0.9, key=f"rd{t_abs:.3f}")

    # --------------------------------------------------------- mastering
    out = synth.soft_clip(out, 1.0)
    peak = float(np.max(np.abs(out)) or 1.0)
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def write_wav(path: str, audio: np.ndarray) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
