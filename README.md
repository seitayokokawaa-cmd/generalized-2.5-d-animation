# MotionForge

A complete 2.5D animation studio that turns **one written screenplay** into a finished,
polished MP4 film — no drawing, no manual animating, no coding by the author.
The same screenplay always produces the exact same video.

Built for AI authorship: any LLM can learn the entire screenplay language from one
generated document (`motionforge spec`), validate its work with plain-language error
reports (`motionforge validate`), look at single frames (`motionforge preview`), and
even drive the whole write→check→fix→render loop automatically (`motionforge auto`).

## Quick start

```bash
pip install -e .
motionforge render examples/village_morning.yaml -o village.mp4
```

## Commands

| Command | What it does |
| --- | --- |
| `motionforge render play.yaml -o out.mp4` | Render a screenplay to a finished MP4 (video + music + SFX). |
| `motionforge validate play.yaml` | Check a screenplay and report every problem in plain, specific language. |
| `motionforge preview play.yaml -t 12.5 -o frame.png` | Render the single frame at t=12.5s. |
| `motionforge spec` | Print the complete, always-up-to-date screenplay language reference. |
| `motionforge auto "a fox learns to fly" -o film.mp4` | Let an LLM write, validate, fix, and render the film automatically. |

Full documentation lives in the generated spec: run `motionforge spec > SPEC.md`.
