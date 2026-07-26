"""Schema tables: every recognized key, its type, default, and documentation.

This module is the single source of truth for the shape of the language.
The parser uses it to reject unknown keys with did-you-mean suggestions, and
the spec generator walks it to produce the always-current SPEC.md.

Each entry: (key, type_label, default_label, doc)
"""
from __future__ import annotations

from typing import Dict, List, Tuple

Field = Tuple[str, str, str, str]

TOP: List[Field] = [
    ("motionforge", "int", "required", "language version; always 1"),
    ("meta", "map", "{}", "film metadata: title, resolution, fps, seed"),
    ("palette", "map of name->color", "{}", "named colors usable anywhere a color is"),
    ("assets", "map of name->object def", "{}", "custom object types (built-ins need no declaration)"),
    ("characters", "map of name->character def", "{}", "the cast"),
    ("scenes", "list of scene", "required", "the film, in order"),
    ("audio", "map", "{}", "music and standalone sound effects"),
]

META: List[Field] = [
    ("title", "string", "''", "film title (also usable as an automatic title card)"),
    ("resolution", "[width, height]", "[1280, 720]", "output pixel size"),
    ("fps", "int", "30", "frames per second (12-60)"),
    ("seed", "int", "0", "determinism seed; same seed + screenplay = identical video"),
]

CHARACTER: List[Field] = [
    ("body", "string", "human", "body template: human, quadruped, bird, fish, blob"),
    ("height", "number (m)", "1.7", "standing height in meters (human) or body length"),
    ("size", "number (m)", "template default", "overall size for non-human bodies"),
    ("build", "string", "normal", "slim, normal, heavy, muscular"),
    ("age", "string", "adult", "child, teen, adult, elder (adjusts proportions)"),
    ("species", "string", "''", "for quadruped/bird/fish: dog, cat, horse, crow, goldfish, ..."),
    ("skin", "color", "template default", "skin / fur / feather / scale base color"),
    ("hair", "map {style, color}", "{}", "hair: style = none, short, bun, long, ponytail, curly"),
    ("outfit", "map {top, bottom, shoes, hat}", "{}", "clothing colors; omit for none"),
    ("color", "color", "''", "shorthand: overall body color (animals)"),
    ("eyes", "color", "#20242c", "iris color"),
]

SCENE: List[Field] = [
    ("id", "string", "required", "unique scene name"),
    ("duration", "number (s)", "required", "scene length in seconds"),
    ("background", "map", "{sky: day}", "sky, weather, ground, backdrop objects"),
    ("transition_in", "map {type, dur}", "cut", "fade, dissolve, wipe, iris or cut"),
    ("transition_out", "map {type, dur}", "cut", "applied at the end of the scene"),
    ("camera", "map {keys | follow}", "static", "camera movement (see camera section)"),
    ("place", "list", "[]", "initial layout of characters and objects"),
    ("timeline", "list", "[]", "time-ordered directions (the heart of the scene)"),
    ("captions", "list", "[]", "titles / subtitles / lower thirds"),
]

BACKGROUND: List[Field] = [
    ("sky", "string", "day", "day, dawn, dusk, night, storm, or a color"),
    ("weather", "string or map", "none", "rain, snow, fog, or {kind, intensity 0-1}"),
    ("ground", "string, color or map", "grass", "grass, dirt, sand, stone, snow, water, road, none, or {kind, color, y}"),
    ("mood", "string", "neutral", "color grade: neutral, warm, cold, night, dream, tense"),
]

PLACE: List[Field] = [
    ("char", "string", "-", "character name to place (use exactly one of char/obj)"),
    ("obj", "string", "-", "object type to place (built-in or from assets:)"),
    ("id", "string", "defaults to name", "instance id used by the timeline"),
    ("at", "[x, y]", "[0, 0]", "world position in meters (y=0 is the ground)"),
    ("depth", "name or number", "near", "fg, near, mid, far, sky, or meters into the scene"),
    ("facing", "string", "right", "left or right"),
    ("scale", "number", "1.0", "uniform resize"),
    ("flip", "bool", "false", "mirror horizontally"),
    ("tint", "color", "none", "recolor the whole object toward this color"),
    ("layer", "int", "0", "draw order within the same depth (higher = in front)"),
    ("part_state", "map part->value", "{}", "initial articulated part angles/offsets"),
]

CAMERA_KEY: List[Field] = [
    ("t", "number (s)", "0", "time of this camera key within the scene"),
    ("x", "number (m)", "previous", "camera center x in world meters"),
    ("y", "number (m)", "previous", "camera center y (1.0 ≈ eye height)"),
    ("zoom", "number", "previous", "1 = default framing; 2 = twice as close"),
    ("ease", "string", "in_out", "easing from the previous key"),
]

CAMERA_FOLLOW: List[Field] = [
    ("char", "string", "required", "character (or object id) to track"),
    ("lag", "number (s)", "0.3", "smoothing; 0 = rigid lock"),
    ("zoom", "number", "1.0", "zoom while following"),
    ("offset", "[x, y]", "[0, 1]", "framing offset from the subject in meters"),
]

# Timeline direction keys.  A direction = subject + one verb key + parameters.
TIMELINE_COMMON: List[Field] = [
    ("t", "number (s)", "required", "when the direction begins, in seconds from scene start"),
    ("until", "number (s)", "verb default", "when it ends (must be greater than t)"),
    ("ease", "string", "verb default", "easing for movements"),
]

CHAR_VERBS: Dict[str, str] = {
    "do":         "perform a named action: walk, run, wave, sit, dance, ... (see Actions catalog)",
    "say":        "speak a line: lip-sync + subtitle. Params: 'text' is the value; voice: {pitch}",
    "ragdoll":    "go limp with physics. Value: {impulse: [x,y], until, recover}",
    "pose_track": "raw frame-by-frame motion: list of {t, bones: {bone: angle}, root: [x,y]}",
    "look":       "aim the eyes/head. Value: target id, [x,y], or 'camera'",
    "emote":      "facial expression: neutral, happy, sad, angry, surprised, scared, disgusted",
    "face":       "turn to face 'left', 'right', or a target id",
    "at":         "teleport instantly to [x, y] (no walking)",
}

OBJ_VERBS: Dict[str, str] = {
    "spin":   "rotate continuously: {rpm} or {to, over} — often with part:",
    "hinge":  "swing a part around its pivot: {to: degrees, over: seconds}",
    "slide":  "slide a part along its axis: {to: meters, over: seconds}",
    "move":   "move to a new position: {to: [x,y], over | until, ease}",
    "orbit":  "circle around a point: {center: [x,y], radius, rpm}",
    "bounce": "bounce in place or along a path: {height, times, over}",
    "fall":   "drop under gravity until ground/height: {height | onto}",
    "shatter":"break into pieces and scatter (seeded, deterministic)",
    "show":   "make visible (optionally {fade: seconds})",
    "hide":   "make invisible (optionally {fade: seconds})",
    "tint":   "recolor over time: {to: color, over: seconds}",
}

WORLD_VERBS: Dict[str, str] = {
    "weather": "change weather: rain, snow, fog, none or {kind, intensity, over}",
    "sky":     "change sky: day, dawn, dusk, night, storm or a color, {over: seconds}",
    "mood":    "change color grade over time",
}

CAPTION: List[Field] = [
    ("t", "number (s)", "required", "when the caption appears"),
    ("until", "number (s)", "required", "when it disappears"),
    ("text", "string", "required", "the text — any language and script"),
    ("style", "string", "caption", "title, subtitle, lower_third, caption"),
    ("pos", "string or [x,y]", "style default", "top, center, bottom, or 0-1 screen coords"),
    ("color", "color", "style default", "text color"),
    ("bg", "color", "style default", "background pill/bar color (or 'none')"),
    ("size", "number", "style default", "font size in pixels at 720p scale"),
    ("fade", "number (s)", "0.25", "fade in/out duration"),
]

AUDIO: List[Field] = [
    ("music", "map {mood, volume, start}", "none", "background music for the whole film"),
    ("sfx", "list of {t, sound, volume}", "[]", "film-level one-shot sounds (scene sfx go in timelines)"),
]

MUSIC_MOODS = ["pastoral", "happy", "tense", "sad", "epic", "mystery", "lullaby", "march"]

DEPTH_NAMES: Dict[str, float] = {
    "fg": -2.0, "near": 0.0, "mid": 6.0, "far": 20.0, "sky": 200.0,
}


def allowed_keys(fields: List[Field]) -> List[str]:
    return [f[0] for f in fields]
