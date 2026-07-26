"""Motion-layer validation: verbs, timing feasibility, interaction wiring."""
from __future__ import annotations

from typing import Dict, List

from ..chars.face import EXPRESSIONS
from ..core.errors import Report, did_you_mean
from ..dsl.ir import Production, Scene
from ..dsl.schema import CHAR_VERBS
from .actions import ACTIONS
from .gait import GAITS

LOCO = set(GAITS) | {"jump", "climb", "swim", "fly"}
INTERACTIONS = {"pickup", "drop", "give", "throw", "catch", "ride", "sit_on",
                "mount", "dismount", "stand"}
SPECIAL = set(CHAR_VERBS) | {"teleport"}


def char_verb_names() -> List[str]:
    return sorted(set(ACTIONS) | LOCO | INTERACTIONS |
                  (SPECIAL - {"do", "at"}))


def validate_motion(production: Production, report: Report) -> None:
    from ..audio.music import MOODS
    from ..audio.sfx import SFX

    for scene in production.scenes:
        chars = {p.id for p in scene.place if p.kind == "char"}
        objs = {p.id for p in scene.place if p.kind == "obj"}
        heights: Dict[str, float] = {}
        for p in scene.place:
            if p.kind == "char" and p.name in production.characters:
                params = production.characters[p.name].params
                heights[p.id] = float(params.get("height", params.get("size", 1.7)))

        loco_windows: Dict[str, List[tuple]] = {}
        throws: Dict[str, List[float]] = {}

        for d in scene.timeline:
            if d.subject_kind != "char":
                if d.subject_kind == "sfx":
                    name = str(d.params.get("sound", ""))
                    if name not in SFX:
                        report.add("E501", d.where, f"unknown sound '{name}'",
                                   did_you_mean(name, list(SFX)), d.line)
                continue

            verb = d.verb
            known = verb in ACTIONS or verb in LOCO or verb in INTERACTIONS \
                or verb in SPECIAL
            if not known:
                report.add("E220", d.where,
                           f"'{verb}' is not a known action or movement",
                           did_you_mean(verb, char_verb_names()) +
                           " (run `motionforge spec` for the full catalog)",
                           d.line)
                continue

            if verb in LOCO:
                to = d.params.get("to")
                if not (isinstance(to, (list, tuple)) and len(to) == 2):
                    report.add("E221", d.where,
                               f"'{verb}' needs a destination: to: [x, y]",
                               "e.g. {char: name, do: %s, to: [3, 0], until: 4.0}" % verb,
                               d.line)
                    continue
                end = d.until if d.until is not None else d.t + 1.0
                loco_windows.setdefault(d.subject, []).append((d.t, end, verb, to, d))

            if verb == "emote":
                expr = str(d.params.get("expression", ""))
                if expr not in EXPRESSIONS:
                    report.add("E502", d.where, f"unknown expression '{expr}'",
                               did_you_mean(expr, list(EXPRESSIONS)), d.line)

            if verb in ("pickup", "drop", "throw", "catch"):
                obj = d.params.get("obj")
                if obj is None:
                    report.add("E223", d.where, f"'{verb}' needs obj: <object id>",
                               "name an object placed in this scene", d.line)
                elif str(obj) not in objs:
                    report.add("E223", d.where,
                               f"'{verb}' references unknown object '{obj}'",
                               did_you_mean(str(obj), list(objs)), d.line)
                if verb == "throw":
                    throws.setdefault(str(obj), []).append(d.t)
                if verb == "catch":
                    obj_s = str(obj)
                    if not any(tt < d.t for tt in throws.get(obj_s, [])):
                        report.add("E340", d.where,
                                   f"'{d.subject}' catches '{obj_s}' but nothing was thrown before t={d.t}",
                                   "add a throw direction earlier, or use pickup",
                                   d.line)
            if verb == "give":
                to_char = str(d.params.get("to_char", d.params.get("to", "")))
                if to_char not in chars:
                    report.add("E223", d.where,
                               f"give: receiving character '{to_char}' is not in this scene",
                               did_you_mean(to_char, list(chars)) +
                               " (use to_char: <name>)", d.line)
            if verb in ("ride", "sit_on", "mount"):
                obj = str(d.params.get("obj", ""))
                if obj not in objs:
                    report.add("E223", d.where,
                               f"'{verb}' references unknown object '{obj}'",
                               did_you_mean(obj, list(objs)), d.line)

        # overlapping locomotion + speed sanity (positions chain like the compiler's)
        start_at = {p.id: p.at for p in scene.place}
        for cid, wins in loco_windows.items():
            wins.sort(key=lambda w: w[0])
            H = heights.get(cid, 1.7)
            pos = start_at.get(cid, (0.0, 0.0))
            prev_end = -1.0
            for (t0, t1, verb, to, d) in wins:
                if t0 < prev_end - 1e-6:
                    report.add("E310", d.where,
                               f"'{cid}' is told to {verb} at t={t0} while still moving "
                               f"(previous movement ends at t={prev_end})",
                               "start this after the previous movement ends, or "
                               "shorten the previous one", d.line)
                prev_end = max(prev_end, t1)
                if verb in GAITS and t1 > t0:
                    import math
                    dist = math.hypot(float(to[0]) - pos[0], float(to[1]) - pos[1])
                    speed = dist / (t1 - t0)
                    max_v = GAITS[verb]["max_speed"] * H * 1.4
                    if speed > max_v:
                        faster = "run" if verb != "run" else "a longer time window"
                        report.add("W402", d.where,
                                   f"{cid} would need {speed:.1f} m/s to {verb} "
                                   f"{dist:.1f} m in {t1 - t0:.1f}s (max ~{max_v:.1f})",
                                   f"increase until:, shorten the distance, or use {faster}",
                                   d.line)
                pos = (float(to[0]), float(to[1]))


def validate_audio(production: Production, report: Report) -> None:
    from ..audio.music import MOODS
    from ..audio.sfx import SFX
    music = production.audio.music
    if music:
        mood = str(music.get("mood", "pastoral"))
        if mood not in MOODS:
            report.add("E503", "audio > music", f"unknown music mood '{mood}'",
                       did_you_mean(mood, list(MOODS)), production.audio.line)
    for i, s in enumerate(production.audio.sfx or []):
        if isinstance(s, dict):
            name = str(s.get("sound", ""))
            if name not in SFX:
                report.add("E501", f"audio > sfx[{i}]", f"unknown sound '{name}'",
                           did_you_mean(name, list(SFX)), production.audio.line)