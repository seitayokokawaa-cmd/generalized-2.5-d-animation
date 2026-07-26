"""Generate SPEC.md: the complete MotionForge language reference.

Everything is pulled live from the schema tables and runtime registries,
so this document can never drift from the implementation. An LLM given
only this document can author valid screenplays.
"""
from __future__ import annotations

from typing import List

from ..dsl import schema


def _table(fields: List[schema.Field]) -> str:
    out = ["| key | type | default | meaning |", "|---|---|---|---|"]
    for (k, ty, df, doc) in fields:
        out.append(f"| `{k}` | {ty} | {df} | {doc} |")
    return "\n".join(out)


EXAMPLE = '''```yaml
motionforge: 1
meta: {title: "The Gift", resolution: [1280, 720], fps: 30, seed: 7}
palette: {roof: "#a33b2a"}

characters:
  mira:  {body: human, height: 1.6, skin: "#c68642",
          hair: {style: bun, color: "#1a1208"},
          outfit: {top: "#c9483b", bottom: "#3a4666"}}
  rex:   {body: quadruped, species: dog, size: 0.5}

assets:                       # optional custom objects; built-ins need no decl
  kite:
    size: [0.8, 1.0]
    parts:
      - {name: sail, shape: polygon, points: [[0,1],[0.4,0.5],[0,0],[-0.4,0.5]],
         fill: "#e8b93a"}
      - {name: tail, shape: line, points: [[0,0],[ -0.2,-0.5]], stroke: {color: "#fff", width: 0.02}}

scenes:
  - id: meadow
    duration: 12
    background: {sky: day, ground: grass, weather: none}
    camera: {follow: {char: mira, zoom: 1.2}}
    place:
      - {char: mira, at: [-4, 0], depth: near}
      - {char: rex, at: [-5.5, 0], depth: near}
      - {obj: tree, id: bigtree, at: [4, 0], depth: mid, scale: 1.3}
      - {obj: ball, id: ball1, at: [-1, 0], depth: near}
    timeline:
      - {t: 0.5, char: mira, do: walk, to: [-1.5, 0], until: 3.0}
      - {t: 1.0, char: rex, do: run, to: [-2.5, 0], until: 2.5}
      - {t: 3.2, char: mira, do: pickup, obj: ball1}
      - {t: 4.5, char: mira, say: "Fetch!", until: 5.5}
      - {t: 5.6, char: mira, do: throw, obj: ball1, to: [3.5, 0.3]}
      - {t: 6.0, char: rex, do: run, to: [3.0, 0], until: 7.5}
      - {t: 8.0, char: mira, do: laugh, until: 9.5}
      - {t: 9.0, camera: {zoom: 1.6, over: 2.0}}
    captions:
      - {t: 0.2, until: 2.2, text: "One sunny morning", style: lower_third}

audio:
  music: {mood: happy, volume: 0.6}
  sfx: [{t: 0.5, sound: birdsong}]
```'''


def generate_spec() -> str:
    from ..assets.catalog import Catalog
    from ..assets.library import LIBRARY
    from ..assets.shapes import SHAPES
    from ..audio.music import MOODS
    from ..audio.sfx import SFX
    from ..chars.face import EXPRESSIONS
    from ..chars.style import HAIR_STYLES, SPECIES_COLORS
    from ..core.color import NAMED
    from ..dsl.ir import Production
    from ..fx.grade import MOODS as GRADE_MOODS
    from ..fx.sky import SKIES
    from ..motion.actions import ACTIONS
    from ..motion.gait import GAITS

    L: List[str] = []
    add = L.append
    add("# MotionForge Screenplay Language — Complete Reference")
    add("")
    add("MotionForge turns one YAML screenplay into a finished 2.5D animated MP4 "
        "film — deterministically: the same file always produces the same video. "
        "This document is generated from the implementation and is always current. "
        "It is everything you need to author films.")
    add("")
    add("## Workflow for AI authors")
    add("")
    add("1. Write a screenplay (format below). 2. Run `motionforge check film.yaml` — "
        "it reports *every* problem with the line number, what is wrong, and how to "
        "fix it. 3. Fix and re-check until clean. 4. Preview single moments with "
        "`motionforge frame film.yaml -t 3.2 -o f.png` or an overview with "
        "`motionforge storyboard film.yaml`. 5. Render with "
        "`motionforge render film.yaml -o film.mp4`.")
    add("")
    add("## Coordinates & staging")
    add("")
    add("- World units are **meters**. X grows to the right, Y grows **up**, the "
        "ground is at y=0. Characters and objects sit on the ground at y=0.")
    add("- At zoom 1 the camera sees about 12.8 m across; keep the action within "
        "roughly x = -6..6 of the camera, or move the camera.")
    add("- `depth` gives true parallax: `fg` (in front of the action), `near` "
        "(the action plane), `mid` (≈6 m back), `far` (≈20 m), `sky` (backdrop), "
        "or any number of meters. Far things are smaller, higher on screen, and "
        "pan slower — automatically.")
    add("- Characters face right by default; they turn automatically when walking.")
    add("")
    add("## Top-level structure")
    add("")
    add(_table(schema.TOP))
    add("")
    add("### meta")
    add(_table(schema.META))
    add("")
    add("### characters — each entry is a name -> definition")
    add(_table(schema.CHARACTER))
    add(f"\nHair styles: {', '.join(HAIR_STYLES)}. "
        f"Known species looks: {', '.join(sorted(SPECIES_COLORS))} "
        "(any other string gets a generic look).")
    add("")
    add("### scenes — a list, played in order")
    add(_table(schema.SCENE))
    add("")
    add("#### background")
    add(_table(schema.BACKGROUND))
    add(f"\nSky presets: {', '.join(SKIES)} (or any color). "
        f"Grade moods: {', '.join(GRADE_MOODS)}. "
        "Weather kinds: rain, snow, fog, none (or {kind, intensity: 0..1}).")
    add("")
    add("#### place — initial layout")
    add(_table(schema.PLACE))
    add("")
    add("#### camera")
    add("Either keyed moves or follow mode:")
    add(_table(schema.CAMERA_KEY))
    add("\nfollow mode:")
    add(_table(schema.CAMERA_FOLLOW))
    add("\nA timeline entry `{t: 4, camera: {zoom: 2, x: 3, over: 1.5, ease: in_out}}` "
        "moves the camera mid-scene.")
    add("")
    add("#### captions")
    add(_table(schema.CAPTION))
    add("\nAny language and script works — Bengali, Arabic, Chinese, etc. are "
        "shaped correctly. `say:` directions add subtitles automatically.")
    add("")
    add("## The timeline — directions")
    add("")
    add("Each entry: `{t: <sec>, <subject>, <verb>, ...params, until: <sec>}`. "
        "Common keys:")
    add(_table(schema.TIMELINE_COMMON))
    add("")
    add("### Character verbs")
    add("")
    add("**Movement** (needs `to: [x, y]`; `until:` sets the arrival time — feet "
        "never slide, the last step lands exactly on target):")
    add("")
    for name, g in GAITS.items():
        add(f"- `do: {name}` — max comfortable speed ≈ "
            f"{g['max_speed']:.1f} m/s per meter of character height")
    add("- `do: jump` — crouch, ballistic arc to `to:`, landing absorb")
    add("- `do: climb` — ladder-style climb (mostly vertical `to:`)")
    add("- `do: swim` / `do: fly` — horizontal glide; birds flap, fish wiggle")
    add("")
    add("**Special keys** (instead of `do:`):")
    add("")
    for k, doc in schema.CHAR_VERBS.items():
        if k != "do":
            add(f"- `{k}:` — {doc}")
    add(f"\nExpressions for `emote:`: {', '.join(EXPRESSIONS)}.")
    add("")
    add("**Actions catalog** (`do: <name>`; loops run until `until:`, one-shots "
        "auto-end; parameters listed):")
    add("")
    for name in sorted(ACTIONS):
        a = ACTIONS[name]
        params = "; ".join(f"{k}: {v}" for k, v in a.params.items())
        loop = "loops" if a.loop else f"one-shot ≈{a.dur:.1f}s"
        add(f"- `{name}` — {a.doc} ({loop}, affects {a.mask}"
            + (f"; params: {params}" if params else "") + ")")
    add("")
    add("**Interactions** (character + object):")
    add("")
    add("- `{char: a, do: pickup, obj: ball1, hand: near|far}` — bends, grabs; "
        "the object follows the hand from then on")
    add("- `{char: a, do: drop, obj: ball1}` — releases; the object falls")
    add("- `{char: a, do: give, obj: ball1, to_char: b}` — hands it over")
    add("- `{char: a, do: throw, obj: ball1, to: [x, y]}` — ballistic arc to the target")
    add("- `{char: b, do: catch, obj: ball1}` — snatches it from flight (throw first!)")
    add("- `{char: a, do: ride|sit_on, obj: cart1, offset: [x,y]?}` then "
        "`{char: a, do: dismount}` — sit on / move with an object")
    add("")
    add("**Custom motion** — raw keyframes when nothing above fits:")
    add("")
    add("```yaml")
    add("- {t: 2, char: mira, pose_track: [")
    add("     {t: 0.0, bones: {head: -20, uarm_near: 90}},")
    add("     {t: 0.5, bones: {head: 15, uarm_near: 160}, morphs: {smile: 1}}]}")
    add("```")
    add("Bones: pelvis, spine, chest, neck, head, uarm/farm/hand_near|far, "
        "thigh/shin/foot_near|far (quadrupeds: *_near_front etc.). Angles are "
        "degrees, deviations from the natural pose. Morphs: blink, gaze_x/gaze_y, "
        "mouth_open/wide/round, smile, brow_raise/angry/sad.")
    add("")
    add("**Physics** — `{t: 5, char: a, ragdoll: {impulse: [3, 4], until: 6.5, "
        "recover: 0.8}}`: the character goes limp, tumbles deterministically, "
        "then gets back up where it landed.")
    add("")
    add("### Object verbs")
    add("")
    for k, doc in schema.OBJ_VERBS.items():
        add(f"- `{k}:` — {doc}")
    add("")
    add("### World verbs (change the environment mid-scene)")
    add("")
    add("`{t: 3, world: {sky: night, over: 2}}`, "
        "`{t: 3, world: {weather: rain, intensity: 0.8, over: 2}}`, "
        "`{t: 3, world: {mood: tense}}`")
    add("")
    add("### Sound")
    add("")
    add("`{t: 2, sfx: thunder}` in a timeline, or film-level `audio:` :")
    add(_table(schema.AUDIO))
    add(f"\nMusic moods: {', '.join(MOODS)}.")
    add("\nSounds: " + ", ".join(f"`{n}` ({d[1]})" for n, d in sorted(SFX.items())))
    add("\nFootsteps, door creaks, throw whooshes, catch pops, ragdoll thumps and "
        "rain/wind ambience are added automatically — do not script them.")
    add("")
    add("## Objects")
    add("")
    add("### Built-in library (place with `obj: <name>`; no declaration needed)")
    add("")
    cat = Catalog(Production())
    for name in sorted(LIBRARY):
        obj = cat.get(name)
        parts = ""
        if obj and obj.articulated:
            parts = " — moving parts: " + ", ".join(
                f"{p} ({k})" for p, k in obj.articulated.items())
        size = LIBRARY[name].get("size", [1, 1])
        add(f"- `{name}` ({size[0]}×{size[1]} m){parts}")
    add("")
    add("### Custom objects (assets:)")
    add("")
    add("An object is a tree of parts. Each part: a `shape:` with its parameters, "
        "or a group with `parts:`. Options per part: `name, at: [x,y], angle, "
        "scale, flip, fill, stroke: {color, width}, opacity, articulate: "
        "spin|hinge|slide, axis: [x,y]` (for slide), `mirror: true` on a group "
        "duplicates children mirrored. Fills can be colors or gradients "
        "`{gradient: linear|radial, stops: [c1, c2], from: [x,y], to: [x,y]}`. "
        "Objects should sit on y=0 and be sized in meters.")
    add("")
    add("Shapes:")
    add("")
    for name, (fn, doc) in sorted(SHAPES.items()):
        add(f"- `{name}` — {doc}")
    add("")
    add("Colors: `#rgb`, `#rrggbb`, `#rrggbbaa`, palette names, or built-ins: "
        + ", ".join(sorted(NAMED)) + ".")
    add("")
    add("## Authoring checklist (the validator enforces these)")
    add("")
    add("- Every scene needs a unique `id` and a `duration`.")
    add("- Place every character/object you direct; reference them by their "
        "instance `id` (defaults to the name).")
    add("- `until` must be after `t`; keep directions inside the scene duration.")
    add("- One direction = one subject + one verb; split combined moves.")
    add("- Don't overlap two movements of the same character; sequence them.")
    add("- Give walks realistic time (~1.2 m/s walking, ~3 m/s running).")
    add("- `catch` needs an earlier `throw`; interactions need placed objects.")
    add("- Speak lines with `say:` — lip sync + subtitles are automatic.")
    add("")
    add("## Complete example")
    add("")
    add(EXAMPLE)
    add("")
    return "\n".join(L)
