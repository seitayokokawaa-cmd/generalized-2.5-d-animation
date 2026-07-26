# MotionForge

**A complete 2.5D animation studio that turns a single written screenplay into a finished
animated MP4 film.** No drawing. No manual animating. No coding. Deterministic: the same
screenplay produces the exact same video, every time.

```bash
pip install -r requirements.txt
python -m motionforge.cli render examples/windmill_dawn.yaml -o film.mp4
```

## What it does

- **Any object** — describe houses, vehicles, windmills, cranes, furniture as declarative
  part trees (or use the 25-object built-in library); moving parts (hinged doors, spinning
  wheels and blades, sliding hooks) included; reuse, resize, recolor, flip, and place at any
  depth with true parallax.
- **Real characters** — humans, quadrupeds (dog, cat, horse, elephant, …), birds, fish, and
  blob creatures with faces that blink, look, emote, and lip-sync; perfect proportions at
  any height, build, or age.
- **Every kind of motion** — a gait engine whose planted feet are world-locked by
  construction (sliding is mathematically impossible): walk, run, sneak, march, limp, jump,
  climb, swim, fly; 35+ ready-made performances (wave, sit, dance, laugh, cry, hug, fight,
  mourn, …); object interaction (pick up, carry, hand over, throw, catch, ride, sit on);
  deterministic verlet **ragdoll physics** with recovery; and raw frame-by-frame pose
  tracks for anything else.
- **Cinematography** — keyed pans/zooms and tracking shots, fades/dissolves/wipes/iris,
  animated skies (sun, moon, stars, clouds), rain/snow/fog, day-night mood grading, titles
  and subtitles in any language and script (Bengali, Arabic, Chinese verified — proper
  HarfBuzz shaping).
- **Sound** — procedural mood music (8 moods) and 16 sound effects, with footsteps synced
  to actual foot plants, creaks on hinges, whooshes on throws, thumps on ragdoll impacts,
  and weather ambience — mixed and muxed into the MP4 automatically.

## Made for AI authorship

```bash
python -m motionforge.cli spec                 # the complete language, generated live
python -m motionforge.cli check film.yaml      # every problem, with line + fix advice
python -m motionforge.cli frame film.yaml -t 3.2 -o f.png     # single-frame preview
python -m motionforge.cli storyboard film.yaml                # frame-grid overview
python -m motionforge.cli render film.yaml -o film.mp4        # the film
python -m motionforge.cli auto "a fox learns to fly" -o film.mp4   # fully automatic
```

`auto` runs the full loop with an LLM (set `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY` +
`OPENAI_BASE_URL` for any compatible provider): write → check → fix → render, no human
involvement. Validation errors are written in plain, specific language
(`unknown character 'ahsa' — did you mean 'asha'?`) so models fix them in one round.

## The screenplay language (taste)

```yaml
motionforge: 1
meta: {title: "The Gift", seed: 7}
characters:
  mira: {body: human, height: 1.6, hair: {style: bun}, outfit: {top: "#c9483b"}}
  rex:  {body: quadruped, species: dog, size: 0.5}
scenes:
  - id: meadow
    duration: 12
    background: {sky: dawn, ground: grass, weather: rain}
    camera: {follow: {char: mira, zoom: 1.2}}
    place:
      - {char: mira, at: [-4, 0], depth: near}
      - {obj: windmill, id: mill, at: [8, 0], depth: far}
    timeline:
      - {t: 0.2, obj: mill, part: blades, spin: {rpm: 8}}
      - {t: 0.5, char: mira, do: walk, to: [2, 0], until: 4.0}
      - {t: 4.5, char: mira, say: "বৃষ্টি আসছে!", until: 6.0}
      - {t: 7.0, char: mira, ragdoll: {impulse: [2, 3], until: 8.5, recover: 0.8}}
      - {t: 9.0, world: {sky: night, over: 2}}
audio: {music: {mood: pastoral, volume: 0.7}}
```

Run `python -m motionforge.cli spec` for the complete reference — every action, object,
shape, sound, and rule, generated from the implementation so it is always current.

## Determinism

Frames are pure functions of `(screenplay, time)`: seeded RNG substreams, fixed-timestep
physics, CPU-only vector rasterization (cairo), and bit-exact ffmpeg flags. Renders run
in parallel across all cores and still produce identical output.

## Requirements

Python ≥ 3.10, system `libcairo` (preinstalled on most Linux; `apt install libcairo2`
otherwise), and fonts for the scripts you use (Noto/FreeSans/WenQuanYi cover most —
override with `MOTIONFORGE_FONT_DIR`). ffmpeg is bundled via `imageio-ffmpeg`.

## Project docs

- [docs/PLAN.md](docs/PLAN.md) — milestone tracker (all core milestones complete)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — full technical design
- `examples/` — checked, rendering screenplays to learn from
- `tests/` — determinism, foot-lock invariant, validator, physics suites
