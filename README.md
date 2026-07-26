# MotionForge

**A complete 2.5D animation studio that turns a single written screenplay into a finished
animated MP4 film.** No drawing. No manual animating. No coding. Deterministic: the same
screenplay produces the exact same video, every time.

```
motionforge render examples/windmill.yaml -o windmill.mp4
```

- **Any object** — describe houses, vehicles, windmills, cranes, furniture in declarative
  YAML; moving parts (doors, wheels, blades) included; reuse, resize, recolor, flip, place
  at any depth with true parallax.
- **Real characters** — humans, animals, birds, fish with faces that blink, look, emote,
  and lip-sync; perfect proportions in every frame.
- **Every kind of motion** — foot-locked walking/running/flying/swimming, a rich action
  library (wave, dance, hug, fight, mourn…), object interaction (pick up, carry, throw,
  catch, ride), deterministic ragdoll physics, and frame-by-frame custom motion in plain text.
- **Cinematography** — pans, zooms, tracking shots, fades, weather, day/night, titles and
  subtitles in any language and script (Bengali, Arabic, Chinese…), music and sound effects.
- **Made for AI authorship** — `motionforge spec` emits the whole language in one document;
  `motionforge check` reports problems in plain, fixable language; `motionforge frame` shows
  single-frame previews; `motionforge auto "story idea"` runs the full write→check→fix→render
  loop with an LLM, no human involvement.

## Install

```bash
pip install -r requirements.txt      # needs system libcairo (preinstalled on most Linux)
python -m motionforge --help
```

## Status

Under active construction — see [docs/PLAN.md](docs/PLAN.md) for the milestone tracker and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full technical design.
