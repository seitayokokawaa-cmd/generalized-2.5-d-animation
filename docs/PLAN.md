# MotionForge — Build Plan & Progress Tracker

MotionForge is a **deterministic 2.5D animation studio**: one screenplay file in → one polished
MP4 out. Same screenplay, same video, every time. No drawing, no manual animating, no coding
required by the author — human or AI.

This document is the living roadmap. Each milestone is a small, pushed commit (or a few), so
progress can be tracked commit-by-commit.

## Technology decisions (made after probing the environment)

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best ecosystem for deterministic CPU pipelines; AI-friendly |
| Rasterizer | **cairocffi** (system libcairo) | High-quality anti-aliased vector rendering, pure CPU → deterministic, installable with plain `pip` (no compiler, no root) |
| Video encode | **imageio-ffmpeg** (bundled static ffmpeg) | Zero system deps; H.264 MP4 with `+bitexact` flags for reproducible bytes |
| Complex text | **uharfbuzz + freetype-py** | Proper shaping for Bengali, Arabic, Chinese; glyph outlines drawn as vector paths |
| Screenplay format | **YAML DSL** (strict schema) | Human- and LLM-writable, line-precise error reporting |
| Physics | Fixed-timestep verlet (pure Python/numpy) | Bit-deterministic ragdolls, no external engine |
| Audio | numpy procedural synthesis | Deterministic music + SFX, no asset downloads |
| Randomness | Single seeded PCG64 stream per render | Rain, blinks, crowd jitter all reproducible |

**Determinism contract:** no wall clock, no unseeded RNG, no GPU, no network at render time.
Frames are pure functions of `(screenplay, time)`.

## Architecture at a glance

```
screenplay.yaml ─▶ dsl (parse+validate) ─▶ compiled Production
                                             │
                    ┌────────────────────────┼─────────────────────┐
                    ▼                        ▼                     ▼
              scene graph              motion system           audio synth
        (assets, chars, camera,   (gait/IK, actions, ragdoll,  (music, SFX)
         depth planes, FX)         attach, custom tracks)          │
                    └────────────┬───────────┘                     │
                                 ▼                                 ▼
                        frame renderer (cairo) ──▶ ffmpeg mux ◀── WAV mix
                                 │
                                 ▼
                             final MP4
```

Full design: [ARCHITECTURE.md](ARCHITECTURE.md).

## Milestones

- [x] **M0 — Plan & scaffold**: this plan, architecture doc, package skeleton, tooling config
- [x] **M1 — Core kernel**: vec/transform/color math, easing curves, seeded RNG, YAML parser
      with line-number tracking, schema types, plain-language error framework
- [x] **M2 — Renderer**: cairo backend, scene graph, depth planes with true parallax, camera
      (pan/zoom/follow), `motionforge frame` PNG previews
- [x] **M3 — Text engine**: harfbuzz shaping, font resolver, titles/subtitles/lower-thirds in
      any script (Bengali, Arabic, Chinese verified)
- [x] **M4 — Asset system**: declarative part-based objects (shapes, pivots, articulated
      parts), built-in library, user-defined objects, reuse/resize/recolor/flip at any depth
- [x] **M5 — Characters**: skeleton rigs, analytic 2-bone IK, template bodies (human,
      quadruped, bird, fish, blob) with proportion-safe scaling, faces (blink, gaze, brows,
      lip-sync visemes)
- [x] **M6 — Motion**: foot-locked gait engine (walk/run/sneak/jump/climb/swim/fly),
      keyframed action library (wave, sit, dance, hug, fight, mourn, …), body-mask blending,
      frame-by-frame custom pose tracks
- [x] **M7 — Interaction & physics**: pick up / carry / hand-off / throw / catch, ride, sit,
      door hinges & wheels, deterministic verlet ragdoll with recovery
- [x] **M8 — Cinematography FX**: fades/dissolves, rain/snow/fog, skies with sun/moon/clouds,
      day/night grading
- [x] **M9 — Audio & encode**: procedural music moods, SFX (footsteps auto-synced to gait),
      WAV mix, parallel frame rendering, bit-exact MP4 encode
- [x] **M10 — AI authorship**: deep validator with fixable plain-language errors,
      `motionforge spec` (always-current language doc generated from code),
      `motionforge auto` (LLM write→check→fix→render loop)
- [x] **M11 — Ship**: example screenplays, pytest suite (determinism, foot-lock invariant,
      validator coverage), adversarial review pass, golden end-to-end renders, final README

All milestones complete. The adversarial review (two independent lenses, all findings
reproduced before fixing) closed: a ragdoll lazy-compile determinism break, diagonal-path
overshoot, wrong-hand throws, releases swallowed inside the grab window, the trailing-foot
catch-up step, and ~20 crash-on-bad-input paths now covered by tolerant coercion + new
validator rules. Final state: 93 tests green; 3 example films check clean and render to
MP4 faster than realtime.

## CLI surface (target)

```
motionforge check   screenplay.yaml            # validate, plain-language report
motionforge frame   screenplay.yaml -t 3.2     # single-frame PNG preview
motionforge storyboard screenplay.yaml         # grid of key frames
motionforge render  screenplay.yaml -o out.mp4 # full film
motionforge spec                               # emit complete language reference for LLMs
motionforge auto    "a fox learns to fly" -o film.mp4   # fully automatic authorship
```
