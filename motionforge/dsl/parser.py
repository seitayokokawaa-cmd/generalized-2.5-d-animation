"""Screenplay dict (from loader) -> typed Production IR, accumulating errors.

The parser is forgiving: it records every problem it can and still produces
as much IR as possible, so `check` reports everything in one pass.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..core.errors import Report, did_you_mean
from . import schema
from .ir import (AudioSpec, CameraSpec, Caption, CharacterDef, Direction, Meta,
                 ObjectDef, Placement, Production, Scene)
from .loader import line_of


class Cur:
    """A cursor over one mapping node: typed getters that log errors."""

    def __init__(self, node: Dict[str, Any], where: str, report: Report):
        self.node = node if isinstance(node, dict) else {}
        self.where = where
        self.report = report
        self.line = line_of(node)

    def err(self, code: str, message: str, suggestion: str = "", line: int = 0) -> None:
        self.report.add(code, self.where, message, suggestion, line or self.line)

    def check_keys(self, allowed: List[str], extra_ok: Tuple[str, ...] = ()) -> None:
        for k in self.node:
            if k not in allowed and k not in extra_ok:
                self.err("E110", f"unknown key '{k}'",
                         did_you_mean(k, list(allowed) + list(extra_ok)),
                         line_of(self.node, self.line))

    def has(self, key: str) -> bool:
        return key in self.node

    def raw(self, key: str, default: Any = None) -> Any:
        return self.node.get(key, default)

    def num(self, key: str, default: Optional[float] = None, required: bool = False,
            lo: Optional[float] = None, hi: Optional[float] = None) -> Optional[float]:
        if key not in self.node:
            if required:
                self.err("E111", f"missing required number '{key}'",
                         f"add {key}: <number>")
            return default
        v = self.node[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            self.err("E112", f"'{key}' must be a number, got {type(v).__name__} ({v!r})",
                     f"write {key}: 1.5 style numbers")
            return default
        v = float(v)
        if not math.isfinite(v):
            self.err("E112", f"'{key}' must be a finite number, got {v!r}",
                     "NaN and infinity are not allowed")
            return default
        if lo is not None and v < lo or hi is not None and v > hi:
            rng = f"{lo if lo is not None else '-inf'}..{hi if hi is not None else 'inf'}"
            self.err("E113", f"'{key}' = {v} is outside the allowed range {rng}",
                     f"use a value between {rng}")
            return default if default is not None else max(lo or v, min(hi or v, v))
        return v

    def integer(self, key: str, default: Optional[int] = None, required: bool = False,
                lo: Optional[int] = None, hi: Optional[int] = None) -> Optional[int]:
        v = self.num(key, None if default is None else float(default), required,
                     None if lo is None else float(lo), None if hi is None else float(hi))
        return None if v is None else int(round(v))

    def st(self, key: str, default: Optional[str] = None, required: bool = False,
           choices: Optional[List[str]] = None) -> Optional[str]:
        if key not in self.node:
            if required:
                self.err("E111", f"missing required '{key}'", f"add {key}: <text>")
            return default
        v = self.node[key]
        if not isinstance(v, str):
            v = str(v)
        if choices and v not in choices:
            self.err("E114", f"'{key}' is '{v}', which is not a recognized choice",
                     did_you_mean(v, choices))
            return default
        return v

    def boolean(self, key: str, default: bool = False) -> bool:
        v = self.node.get(key, default)
        if not isinstance(v, bool):
            self.err("E112", f"'{key}' must be true or false, got {v!r}", "")
            return default
        return v

    def vec2(self, key: str, default: Optional[Tuple[float, float]] = None,
             required: bool = False) -> Optional[Tuple[float, float]]:
        if key not in self.node:
            if required:
                self.err("E111", f"missing required position '{key}'", f"add {key}: [x, y]")
            return default
        v = self.node[key]
        if (not isinstance(v, (list, tuple)) or len(v) != 2
                or not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in v)):
            self.err("E115", f"'{key}' must be [x, y] with two numbers, got {v!r}",
                     f"write {key}: [3.0, 0]")
            return default
        return (float(v[0]), float(v[1]))

    def map(self, key: str, required: bool = False) -> Optional[Dict[str, Any]]:
        if key not in self.node:
            if required:
                self.err("E111", f"missing required section '{key}'", f"add a {key}: block")
            return None
        v = self.node[key]
        if not isinstance(v, dict):
            self.err("E116", f"'{key}' must be a mapping (indented key: value lines), got {type(v).__name__}",
                     "")
            return None
        return v

    def lst(self, key: str) -> List[Any]:
        v = self.node.get(key, [])
        if not isinstance(v, list):
            self.err("E117", f"'{key}' must be a list (lines starting with '- ')",
                     "", line_of(v, self.line))
            return []
        return v

    def sub(self, key: str, required: bool = False) -> "Cur":
        m = self.map(key, required)
        return Cur(m if m is not None else {}, f"{self.where} > {key}", self.report)


def parse_depth(value: Any, cur: Cur, key: str = "depth") -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        if value in schema.DEPTH_NAMES:
            return schema.DEPTH_NAMES[value]
        cur.err("E118", f"unknown depth '{value}'",
                did_you_mean(value, list(schema.DEPTH_NAMES)) + " (or give meters as a number)")
        return 0.0
    cur.err("E118", f"'{key}' must be a depth name or a number, got {value!r}", "")
    return 0.0


def _params_from(node: Dict[str, Any], consumed: Tuple[str, ...]) -> Dict[str, Any]:
    return {k: v for k, v in node.items() if k not in consumed}


def parse_placement(node: Any, where: str, report: Report, idx: int) -> Optional[Placement]:
    cur = Cur(node, f"{where} > place[{idx}]", report)
    if not isinstance(node, dict):
        cur.err("E116", f"each place entry must be a mapping, got {node!r}",
                "write - {char: name, at: [x, y]} or - {obj: type, at: [x, y]}")
        return None
    cur.check_keys(schema.allowed_keys(schema.PLACE))
    has_char, has_obj = cur.has("char"), cur.has("obj")
    if has_char == has_obj:
        cur.err("E120", "a place entry needs exactly one of 'char:' or 'obj:'",
                "use char: <character name> for cast, obj: <object type> for props")
        return None
    kind = "char" if has_char else "obj"
    name = str(cur.raw(kind))
    depth = parse_depth(cur.raw("depth", "near" if kind == "char" else "near"), cur)
    p = Placement(
        kind=kind, name=name, id=str(cur.raw("id", name)),
        at=cur.vec2("at", (0.0, 0.0)) or (0.0, 0.0),
        depth=depth,
        facing=cur.st("facing", "right", choices=["left", "right"]) or "right",
        scale=cur.num("scale", 1.0, lo=0.001, hi=1000.0) or 1.0,
        flip=cur.boolean("flip", False),
        tint=cur.raw("tint"),
        layer=cur.integer("layer", 0) or 0,
        params=_params_from(node, tuple(schema.allowed_keys(schema.PLACE))),
        line=line_of(node),
    )
    if kind == "char" and cur.has("part_state"):
        cur.err("E121", "'part_state' applies to objects, not characters",
                "remove it or move it to an obj: entry")
    if cur.has("part_state"):
        p.params["part_state"] = cur.raw("part_state")
    return p


_SUBJECT_KEYS = ("char", "obj", "camera", "sfx", "world")
_COMMON_KEYS = ("t", "until", "ease")


def parse_direction(node: Any, where: str, report: Report, idx: int) -> Optional[Direction]:
    w = f"{where} > timeline[{idx}]"
    cur = Cur(node, w, report)
    if not isinstance(node, dict):
        cur.err("E116", f"each timeline entry must be a mapping, got {node!r}",
                "write - {t: 1.0, char: name, do: walk, to: [x, y], until: 3.0}")
        return None
    t = cur.num("t", required=True, lo=0.0)
    if t is None:
        t = 0.0
    until = cur.num("until", None, lo=0.0)

    subjects = [k for k in _SUBJECT_KEYS if cur.has(k)]
    # char + obj together is an interaction: char is the subject, obj a parameter
    if "char" in subjects and subjects == ["char", "obj"]:
        subjects = ["char"]
    if len(subjects) != 1:
        if not subjects:
            cur.err("E122", "this direction has no subject",
                    "add one of: char: <name>, obj: <id>, camera: {...}, sfx: <sound>, world: {...}")
        else:
            cur.err("E123", f"a direction can have only one subject, found {subjects}",
                    "split this into separate timeline entries with the same t:")
        return None
    subject_key = subjects[0]

    if subject_key == "camera":
        cam = cur.raw("camera")
        if not isinstance(cam, dict):
            cur.err("E116", "'camera:' in a timeline must be a mapping like {zoom: 2, over: 1.5}", "")
            return None
        return Direction(t=t, until=until, subject_kind="camera", subject="", verb="camera",
                         params=dict(cam), where=w, line=line_of(node))

    if subject_key == "sfx":
        sound = cur.raw("sfx")
        params = _params_from(node, _COMMON_KEYS + ("sfx",))
        params["sound"] = str(sound)
        return Direction(t=t, until=until, subject_kind="sfx", subject="", verb="play",
                         params=params, where=w, line=line_of(node))

    if subject_key == "world":
        wnode = cur.raw("world")
        if not isinstance(wnode, dict):
            cur.err("E116", "'world:' must be a mapping like {weather: rain, over: 2}", "")
            return None
        verbs = [k for k in schema.WORLD_VERBS if k in wnode]
        if not verbs:
            cur.err("E124", "world direction needs one of: " + ", ".join(schema.WORLD_VERBS), "")
            return None
        params = {k: v for k, v in wnode.items()}
        return Direction(t=t, until=until, subject_kind="world", subject="", verb=verbs[0],
                         params=params, where=w, line=line_of(node))

    # char / obj directions
    subject = str(cur.raw(subject_key))
    verb_table = schema.CHAR_VERBS if subject_key == "char" else schema.OBJ_VERBS
    verbs = [k for k in verb_table if cur.has(k)]
    if len(verbs) > 1:
        cur.err("E123", f"one direction, one verb: found {verbs}",
                "split into separate timeline entries")
        return None
    if not verbs:
        known = ", ".join(sorted(verb_table))
        extra = [k for k in cur.node
                 if k not in _COMMON_KEYS and k not in _SUBJECT_KEYS]
        hint = did_you_mean(extra[0], list(verb_table)) if extra else f"choose one of: {known}"
        cur.err("E125", f"no verb found for this {subject_key} direction", hint)
        return None
    verb = verbs[0]
    vval = cur.raw(verb)

    consumed = _COMMON_KEYS + (subject_key, verb)
    if subject_key != "char":
        consumed = consumed + tuple(k for k in _SUBJECT_KEYS if k != subject_key)
    params = _params_from(node, consumed)
    if verb == "do":
        # {char: a, do: walk, to: ...} -> verb=walk, params carry the rest
        if not isinstance(vval, str):
            cur.err("E126", f"'do:' must name an action, got {vval!r}",
                    "e.g. do: walk   (see the Actions catalog in the spec)")
            return None
        verb = vval
    elif isinstance(vval, dict):
        params.update(vval)
    elif verb == "say":
        params["text"] = "" if vval is None else str(vval)
    elif verb in ("look", "face"):
        params["target"] = vval
    elif verb == "emote":
        params["expression"] = str(vval)
    elif verb == "at":
        params["to"] = vval
        verb = "teleport"
    elif verb == "pose_track":
        params["keys"] = vval
    else:
        if vval is not None and vval != {}:
            params["value"] = vval

    ease = cur.st("ease")
    if ease:
        params["ease"] = ease
    return Direction(t=t, until=until, subject_kind=subject_key, subject=subject,
                     verb=verb, params=params, where=w, line=line_of(node))


def parse_caption(node: Any, where: str, report: Report, idx: int) -> Optional[Caption]:
    cur = Cur(node, f"{where} > captions[{idx}]", report)
    if not isinstance(node, dict):
        cur.err("E116", f"each caption must be a mapping, got {node!r}",
                'write - {t: 0, until: 2, text: "Chapter One", style: title}')
        return None
    cur.check_keys(schema.allowed_keys(schema.CAPTION))
    t = cur.num("t", required=True, lo=0.0)
    until = cur.num("until", required=True, lo=0.0)
    text = cur.st("text", required=True)
    if t is None or until is None or text is None:
        return None
    style = cur.st("style", "caption",
                   choices=["title", "subtitle", "lower_third", "caption"]) or "caption"
    if cur.has("size"):
        cur.num("size", 30.0, lo=4.0, hi=400.0)
    if cur.has("fade"):
        cur.num("fade", 0.25, lo=0.0)
    pos = cur.raw("pos")
    if pos is not None and not isinstance(pos, str):
        cur.vec2("pos")
    for ckey in ("color", "bg"):
        cval = cur.raw(ckey)
        # strict check only for literal forms; palette names resolve later
        if isinstance(cval, (list, tuple)) or (isinstance(cval, str)
                                               and cval.startswith("#")):
            from ..core import color as _color
            try:
                _color.parse(cval, None)
            except ValueError as e:
                cur.err("E130", f"caption {ckey}: {e}",
                        "use #hex or a built-in color name")
    params = _params_from(node, ("t", "until", "text", "style"))
    return Caption(t=t, until=until, text=text, style=style, params=params,
                   line=line_of(node))


def parse_camera(node: Any, where: str, report: Report) -> CameraSpec:
    cur = Cur(node if isinstance(node, dict) else {}, f"{where} > camera", report)
    spec = CameraSpec(line=line_of(node))
    if node is None:
        return spec
    if not isinstance(node, dict):
        cur.err("E116", "'camera' must be a mapping with keys: or follow:", "")
        return spec
    cur.check_keys(["keys", "follow"])
    if "keys" in node and "follow" in node:
        cur.err("E127", "camera cannot both have fixed keys and follow a subject",
                "keep either keys: or follow:")
    keys = cur.lst("keys")
    for i, k in enumerate(keys):
        kc = Cur(k, f"{where} > camera > keys[{i}]", report)
        if not isinstance(k, dict):
            kc.err("E116", f"each camera key must be a mapping, got {k!r}", "")
            continue
        kc.check_keys(schema.allowed_keys(schema.CAMERA_KEY))
        kc.num("t", 0.0, lo=0.0)
        for field in ("x", "y"):
            if kc.has(field):
                kc.num(field, 0.0)
        if kc.has("zoom"):
            kc.num("zoom", 1.0, lo=0.05, hi=50.0)
        spec.keys.append(dict(k, __line__=line_of(k)))
    fol = cur.map("follow")
    if fol is not None:
        fc = Cur(fol, f"{where} > camera > follow", report)
        fc.check_keys(schema.allowed_keys(schema.CAMERA_FOLLOW) + ["obj"])
        if fc.has("zoom"):
            fc.num("zoom", 1.0, lo=0.05, hi=50.0)
        if fc.has("lag"):
            fc.num("lag", 0.3, lo=0.0)
        if fc.has("offset"):
            fc.vec2("offset", (0.0, 1.0))
        spec.follow = dict(fol)
    return spec


def parse_scene(node: Any, report: Report, idx: int) -> Optional[Scene]:
    sid = node.get("id") if isinstance(node, dict) else None
    where = f"scene '{sid}'" if sid else f"scenes[{idx}]"
    cur = Cur(node, where, report)
    if not isinstance(node, dict):
        cur.err("E116", f"each scene must be a mapping, got {node!r}", "")
        return None
    cur.check_keys(schema.allowed_keys(schema.SCENE))
    sid = cur.st("id", required=True) or f"scene{idx}"
    duration = cur.num("duration", required=True, lo=0.1, hi=3600.0)
    if duration is None:
        duration = 5.0
    bg = cur.map("background") or {}
    if bg:
        bc = Cur(bg, f"{where} > background", report)
        bc.check_keys(schema.allowed_keys(schema.BACKGROUND))
    scene = Scene(
        id=sid, duration=duration, background=dict(bg),
        transition_in=cur.map("transition_in"),
        transition_out=cur.map("transition_out"),
        camera=parse_camera(cur.raw("camera"), where, report),
        line=line_of(node),
    )
    for i, p in enumerate(cur.lst("place")):
        placement = parse_placement(p, where, report, i)
        if placement:
            scene.place.append(placement)
    for i, d in enumerate(cur.lst("timeline")):
        direction = parse_direction(d, where, report, i)
        if direction:
            scene.timeline.append(direction)
    for i, c in enumerate(cur.lst("captions")):
        caption = parse_caption(c, where, report, i)
        if caption:
            scene.captions.append(caption)
    scene.timeline.sort(key=lambda d: (d.t, d.line))
    return scene


def parse_production(data: Dict[str, Any], report: Report) -> Production:
    top = Cur(data, "screenplay", report)
    top.check_keys(schema.allowed_keys(schema.TOP))
    version = top.integer("motionforge")
    if version is None:
        top.err("E104", "missing 'motionforge: 1' at the top level",
                "add the line: motionforge: 1")
    elif version != 1:
        top.err("E105", f"unsupported language version {version}", "this build supports version 1")

    prod = Production()

    meta = top.sub("meta")
    meta.check_keys(schema.allowed_keys(schema.META))
    res = meta.raw("resolution", [1280, 720])
    if (not isinstance(res, (list, tuple)) or len(res) != 2
            or not all(isinstance(c, int) and not isinstance(c, bool) and 16 <= c <= 4096 for c in res)):
        meta.err("E115", f"'resolution' must be [width, height] ints (16..4096), got {res!r}",
                 "e.g. resolution: [1280, 720]")
        res = [1280, 720]
    elif res[0] % 2 or res[1] % 2:
        meta.err("E115", f"resolution {res[0]}x{res[1]} must use even numbers "
                 "(H.264 requirement)",
                 f"use [{res[0] + res[0] % 2}, {res[1] + res[1] % 2}]")
        res = [res[0] + res[0] % 2, res[1] + res[1] % 2]
    prod.meta = Meta(
        title=meta.st("title", "") or "",
        resolution=(int(res[0]), int(res[1])),
        fps=meta.integer("fps", 30, lo=12, hi=60) or 30,
        seed=meta.integer("seed", 0) or 0,
    )

    palette = top.map("palette") or {}
    for name, val in palette.items():
        prod.palette[str(name)] = val

    assets = top.map("assets") or {}
    for name, val in assets.items():
        if not isinstance(val, dict):
            report.add("E116", f"asset '{name}'", "an asset definition must be a mapping",
                       "give it a parts: list — see the Objects section of the spec",
                       line_of(val, line_of(assets)))
            continue
        prod.assets[str(name)] = ObjectDef(name=str(name), raw=dict(val), line=line_of(val))

    chars = top.map("characters") or {}
    for name, val in chars.items():
        w = f"character '{name}'"
        if not isinstance(val, dict):
            report.add("E116", w, "a character definition must be a mapping",
                       "e.g. {body: human, height: 1.7}", line_of(val, line_of(chars)))
            continue
        cc = Cur(val, w, report)
        cc.check_keys(schema.allowed_keys(schema.CHARACTER))
        body = cc.st("body", "human",
                     choices=["human", "quadruped", "bird", "fish", "blob"]) or "human"
        prod.characters[str(name)] = CharacterDef(
            name=str(name), body=body,
            params={k: v for k, v in val.items() if k != "body"},
            line=line_of(val),
        )

    scenes = top.lst("scenes")
    if not scenes:
        top.err("E106", "the screenplay has no scenes",
                "add a scenes: list with at least one scene (id + duration)")
    start = 0.0
    for i, s in enumerate(scenes):
        scene = parse_scene(s, report, i)
        if scene:
            scene.start_time = start
            start += scene.duration
            prod.scenes.append(scene)
    seen_ids: Dict[str, int] = {}
    for s in prod.scenes:
        if s.id in seen_ids:
            report.add("E107", f"scene '{s.id}'",
                       f"duplicate scene id (also used on line {seen_ids[s.id]})",
                       "give every scene a unique id", s.line)
        else:
            seen_ids[s.id] = s.line

    audio = top.map("audio")
    if audio is not None:
        ac = Cur(audio, "audio", report)
        ac.check_keys(schema.allowed_keys(schema.AUDIO))
        prod.audio = AudioSpec(music=ac.map("music"), sfx=ac.lst("sfx"),
                               line=line_of(audio))
    return prod


def parse_text(text: str) -> Tuple[Optional[Production], Report]:
    from .loader import load_text
    data, report = load_text(text)
    if data is None:
        return None, report
    return parse_production(data, report), report


def parse_file(path: str) -> Tuple[Optional[Production], Report]:
    from .loader import load_file
    data, report = load_file(path)
    if data is None:
        return None, report
    return parse_production(data, report), report
