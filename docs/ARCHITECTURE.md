# MotionForge Architecture

This is the detailed technical design. It is the contract every module is built against.

## 1. Determinism contract

The entire pipeline is a pure function: `render(screenplay_bytes) -> mp4_bytes`.

Rules enforced everywhere:

1. **No wall clock, no unseeded randomness.** One `numpy.random.Generator(PCG64(seed))`
   derived from `meta.seed` (default 0). Subsystems get *named substreams*
   (`rng.stream("weather")`, `rng.stream("blink:asha")`) so adding one feature never
   perturbs another's random sequence.
2. **Fixed timestep.** Simulation (physics, particles) steps at exactly 120 Hz internally,
   sampled at frame times. Frame `i` is at `t = i / fps` exactly (rational, not float
   accumulation).
3. **CPU-only rasterization** (cairo). No GPU, no thread-order-dependent blending. Frames may
   render in parallel across processes because each frame is an independent pure function.
4. **Bit-exact encode.** ffmpeg runs with `-fflags +bitexact -flags:v +bitexact
   -flags:a +bitexact -map_metadata -1` and fixed timestamps.

## 2. Coordinate system & 2.5D model

- World units: **meters**. X → right, **Y → up**, ground plane at `y = 0`.
  (Screen-space flip happens only inside the camera projection.)
- **Depth planes**: every placed entity lives on a plane with a depth value `z ≥ 0`
  (0 = camera plane). Named shortcuts: `fg = -2`, `near = 0`, `mid = 6`, `far = 20`,
  `sky = 200`, or any number via `depth: 12.5`.
- **Parallax projection.** Camera has `(x, y, zoom)`. For an entity at depth `z`, the
  perspective factor is `k = D / (D + z)` with reference distance `D = 10`:
  - screen position = `(world_xy - camera_xy * k) * zoom * ppm * k` (+ frame center)
  - scale on screen is multiplied by `k`, so far objects are smaller *and* drift slower —
    true parallax from a single 2D transform. `fg` (z<0) moves faster than the action.
- Draw order: planes back-to-front by `z`; within a plane, explicit `layer` then placement order.

## 3. Package layout

```
motionforge/
  cli.py                # argparse CLI: check / frame / storyboard / render / spec / auto
  core/                 # zero-dependency kernel
    vec.py              #   Vec2, lerp, angles
    transform.py        #   2D affine (compose, invert, apply)
    color.py            #   parse #hex / named / hsl; mix; day-night grade ramps
    ease.py             #   linear, in, out, in_out, bounce, elastic, spring, hold, step
    rng.py              #   seeded PCG64 with named substreams
    errors.py           #   MFError(code, where, message, suggestion) — the ONE error type
  dsl/
    loader.py           #   YAML → dict with per-node line/col marks (ruamel-style tracking)
    schema.py           #   typed field specs; every field documented (feeds spec generator)
    parser.py           #   dict → typed Production IR
    validator.py        #   deep checks; emits MFError list (never raises mid-way)
  scene/
    graph.py            #   Node(transform, children, draw_ops), flatten to draw list
    world.py            #   compiled Production: scenes, entities, tracks, resolve(t)
    camera.py           #   keyed pan/zoom + follow-with-lag mode; projection math
  draw/
    canvas.py           #   backend-agnostic draw API (paths, fills, strokes, groups, alpha)
    cairo_backend.py    #   the one concrete backend (cairocffi)
    text.py             #   harfbuzz shaping → freetype outlines → path draw ops
    fonts.py            #   font resolver: script coverage detection, priority list, env override
  assets/
    shapes.py           #   primitive part shapes: rect, circle, ellipse, polygon, path(SVG-like),
                        #   capsule, star, arc, trapezoid, gear, blob
    builder.py          #   part tree from declarative dicts: pivot, articulation (hinge/spin/slide),
                        #   fill/stroke/gradient, symmetry helpers
    library.py          #   built-in object catalog (house, tree, car, windmill, crane, table, …)
  chars/
    rig.py              #   Skeleton: bones w/ length, pivot, parent; pose = {bone: angle}+root
    ik.py               #   analytic 2-bone IK (arm, leg) with elbow/knee direction hint
    bodies/             #   template builders: human.py, quadruped.py, bird.py, fish.py, blob.py
    face.py             #   eyes (blink lids, pupil gaze), brows, mouth visemes (A I U E O M rest),
                        #   expression morphs (smile, frown, angry, sad, surprise)
    style.py            #   skin/hair/outfit/species coloring; proportion presets (child, tall, heavy)
  motion/
    tracks.py           #   Track = sorted keyframes on any channel; sampling w/ easing
    gait.py             #   procedural locomotion: phase-locked steps, IK foot plant (zero slide),
                        #   modes: walk run sneak march limp jump climb swim fly hover
    actions.py          #   action clip registry + parameterized clip definitions (DATA, not code)
    blend.py            #   layered blending with body-part masks (upper/lower/face/all)
    attach.py           #   parenting: hand-holds, mounts (ride/sit), hand-off, throw ballistics
    ragdoll.py          #   verlet points+rods per rig, ground/box collision, capture→sim→recover
    custom.py           #   screenplay-supplied per-bone keyframe tables
  fx/
    sky.py              #   gradient skies, sun/moon position, stars, clouds (seeded, parametric)
    weather.py          #   rain/snow/fog particle fields (seeded, tiled for camera moves)
    transitions.py      #   cut, fade, dissolve, wipe, iris
    grade.py            #   day/night/dusk mood color grading applied at composite time
  audio/
    synth.py            #   numpy oscillators, envelopes, filters, noise, simple reverb
    music.py            #   mood library (pastoral, tense, happy, sad, epic, mystery) as note
                        #   patterns rendered deterministically
    sfx.py              #   footstep, door, whoosh, splash, crash, birdsong, rain bed, …
    mix.py              #   timeline mixer → stereo float32 → WAV
  render/
    frames.py           #   frame loop: resolve world at t → draw list → canvas
    parallel.py         #   process pool over frame ranges (deterministic assembly order)
    encode.py           #   pipe RGB24 to bundled ffmpeg; mux WAV; bitexact flags
  spec/
    generate.py         #   walks schema + action registry + asset catalog + music/sfx lists
                        #   → single SPEC.md an LLM reads to learn the whole language
  ai/
    autopilot.py        #   idea → LLM writes screenplay → check → errors fed back → repeat
                        #   → render; provider-agnostic (Anthropic API or any OpenAI-compatible)
```

## 4. The screenplay language (DSL)

One YAML file. Top-level keys:

```yaml
motionforge: 1                   # language version (required)
meta:
  title: "The Windmill"
  resolution: [1280, 720]        # default 1280x720
  fps: 30                        # default 30
  seed: 7                        # determinism seed, default 0

palette:                         # optional named colors usable anywhere a color is
  brick: "#b5502a"

assets:                          # user-defined object types (see §5); built-ins need no decl
  cart: { parts: [ ... ] }

characters:
  asha:  { body: human, height: 1.6, skin: "#c68642", hair: {style: bun, color: "#222"},
           outfit: {top: "#d33", bottom: "#334"} }
  rex:   { body: quadruped, species: dog, size: 0.5, color: "#a86" }

scenes:
  - id: dawn
    duration: 8.0                # seconds (required)
    background: { sky: dawn, weather: rain, ground: {kind: grass, color: "#3a5"} }
    transition_in: {type: fade, dur: 1.0}
    camera:                      # keys OR follow
      keys:
        - {t: 0, x: 0, y: 1.2, zoom: 1.0}
        - {t: 6, x: 4, zoom: 1.4, ease: in_out}
    place:                       # initial layout
      - {char: asha, at: [-3, 0], depth: near, facing: right}
      - {obj: windmill, id: mill, at: [8, 0], depth: far, scale: 1.4, tint: "#dcb"}
    timeline:                    # the heart: time-ordered directions
      - {t: 0.5, char: asha, do: walk, to: [2, 0], until: 4.0}
      - {t: 1.0, obj: mill, part: blades, spin: {rpm: 6}}
      - {t: 2.0, char: asha, say: "বৃষ্টি আসছে!", until: 3.8}     # lip-sync + subtitle
      - {t: 4.2, char: asha, do: point, at_target: mill}
      - {t: 5.0, char: asha, do: pickup, obj: basket, hand: right}
      - {t: 6.0, char: asha, ragdoll: {impulse: [2, 3], until: 7.2, recover: 0.8}}
      - {t: 6.0, sfx: thunder}
    captions:
      - {t: 0.0, until: 2.0, text: "Chapter One", style: title}

audio:
  music: {mood: pastoral, volume: 0.7}
```

**Design rules for the DSL** (so LLMs succeed):

- Every reference is by **name**; every unknown name error includes a did-you-mean.
- Times are seconds within the scene. `until` > `t` always; validator enforces.
- Everything has a sane default; a 5-line screenplay must render something reasonable.
- No nesting deeper than ~3 levels in common cases; flat time-ordered `timeline`.
- The schema module is the single source of truth: parser, validator, and the generated
  SPEC.md all derive from it, so documentation can never go stale.

## 5. Assets: declarative parametric objects

An object is a **tree of parts**. Each part: a shape primitive (or sub-group), local
transform, pivot, paint, optional **articulation**:

```yaml
assets:
  windmill:
    size: [3, 8]                       # logical bounding size in meters
    parts:
      - {name: tower, shape: trapezoid, w1: 2.2, w2: 1.2, h: 6.5, fill: brick}
      - name: blades
        pivot: [0, 6.9]                # articulation pivot in object space
        articulate: spin               # spin | hinge | slide
        parts:
          - {shape: capsule, w: 0.3, h: 3.2, angle: 0,   fill: "#eee"}
          - {shape: capsule, w: 0.3, h: 3.2, angle: 90,  fill: "#eee"}
          - {shape: capsule, w: 0.3, h: 3.2, angle: 180, fill: "#eee"}
          - {shape: capsule, w: 0.3, h: 3.2, angle: 270, fill: "#eee"}
```

Placement supports `scale`, `flip`, `tint` (recolor), `depth`, `layer`. Articulated parts are
addressed from the timeline: `{obj: mill, part: blades, spin: {rpm: 6}}` or
`{obj: barn, part: door, hinge: {to: 95, over: 0.6, ease: out}}`.

Built-in library objects are defined in exactly the same declarative form (they live in
`assets/library.py` as data), so the catalog in SPEC.md is generated, and users override or
extend freely.

## 6. Characters & rigs

- `Skeleton`: named bones with parent, length, base angle. Humanoid: pelvis, spine, chest,
  neck, head, L/R upper_arm, forearm, hand, thigh, shin, foot. Quadruped/bird/fish variants.
- A **Pose** is `{bone_name: local_angle}` + root position/orientation + morph dict
  (face + secondary). Poses blend linearly (angles via shortest arc).
- **Template bodies** generate vector part shapes sized from the skeleton, so any `height`,
  `build`, or `species` keeps proportions exact in every frame by construction.
- **Faces**: eye whites+iris (gaze target), eyelids (blink cycle from named rng stream),
  brows (expression), mouth = viseme set {rest, M, A, I, U, E, O} + emotion morphs.
  `say:` maps text → syllable-ish viseme sequence (deterministic from text) for lip sync;
  captions show the spoken line as a subtitle.

## 7. Motion

Priority-layered channels, later layers override/blend by mask:

```
base pose → locomotion (gait) → action clips (masked) → custom tracks → attach solve
                                                       → ragdoll (takes over whole body)
```

- **Gait engine** — locomotion is computed from a **path** (`to:` waypoints + `until:` time):
  speed profile eased at both ends; step phase advances with distance traveled; each foot
  alternates *plant* (world-locked via 2-bone IK — mathematically zero slide) and *swing*
  (bezier arc to the next plant point, predicted from current speed). Body bob, lean, arm
  swing derive from phase. Modes change stride length, duty cycle, posture: walk, run,
  sneak, march, limp; jump/climb/swim/fly are related generators sharing the API.
- **Actions** are data: keyframe tables on rig channels with a duration, loopable flag,
  body mask, and parameters (e.g. `wave: {hand: left, times: 3}`). Registry auto-feeds
  SPEC.md.
- **Ragdoll**: on trigger, current pose → verlet particles (joints) + distance rods (bones)
  + angular limits; ground plane & obstacle collision; runs at 120 Hz fixed step; on
  `recover`, final ragdoll pose blends back into the animation stack over the given time.
- **Attach**: objects can be parented to a hand/mount bone with grip offset; `handoff`
  reparents between characters at time t; `throw` detaches with initial velocity and flies
  ballistically (same fixed-step integrator); `catch` re-attaches when trajectories meet
  (validator checks feasibility and reports exact correction if not).
- **Custom motion**: `{char: asha, pose_track: [{t: 0, bones: {head: -20}}, ...]}` — raw
  declarative frame-by-frame control for anything not covered.

## 8. Cameras, captions, FX

- Camera: keyed `(x, y, zoom)` with easing, or `follow: {char: asha, lag: 0.4, frame: [x_off, y_off]}`.
  Zoom is depth-aware (projection handles parallax shift correctly while zooming).
- Captions: styles `title`, `subtitle`, `lower_third`, `caption`; any script via harfbuzz
  (RTL handled by shaper + bidi para direction); background pill/bar options; safe-area layout.
- Transitions between scenes: `cut | fade | dissolve | wipe | iris` with duration.
- Weather/sky per scene with intensity; particles are seeded and tiled in camera space so
  panning never shows edges.

## 9. Audio

- Music moods are note-pattern programs (tempo, scale, chord loop, instrument voices)
  rendered by the numpy synth — deterministic samples.
- SFX events from timeline (`sfx: thunder`) plus **auto-SFX**: every gait foot-plant emits a
  footstep matched to ground kind; door hinges creak; ragdoll impacts thump (velocity-scaled).
- Mixer assembles stereo 44.1 kHz float, soft-limits, writes WAV; ffmpeg muxes into the MP4.

## 10. Validation & AI loop

- `check` returns ALL problems at once (not fail-fast), each as:
  `code | where (scene/index/line) | message | suggestion`, e.g.
  `E204 scene 'dawn' timeline[3] (line 41): unknown character 'ahsa' — did you mean 'asha'?`
- Classes: schema/type errors, unknown references, timing (until ≤ t, overlap of
  incompatible actions on one body mask, direction past scene end), spatial (teleport:
  consecutive commands imply >X m instantaneous move; unreachable catch), resource
  (unknown action/mood/sfx with catalog list).
- `spec` generates the complete language document from schema + registries: an LLM needs
  only this one document to author valid screenplays.
- `auto`: prompt(SPEC + idea) → screenplay → `check` → errors appended to conversation →
  LLM revises (bounded retries) → optional preview-frame critique → `render`.

## 11. Testing strategy

- **Determinism**: render frame N twice (and across process-pool boundaries) → identical PNG bytes.
- **Foot-lock invariant**: during plant phase, foot world-x variance < 1e-6 m.
- **Proportion invariant**: bone screen-length ratios constant across frames/zoom.
- **Validator**: table-driven bad screenplays → expected error codes.
- **Golden examples**: every example screenplay must `check` clean and render.
