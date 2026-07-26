"""Semantic validation of a parsed Production.

This grows with each subsystem; every check reports plain, fixable language.
Codes: E2xx references, E3xx timing, E4xx spatial/motion, E5xx resources.
"""
from __future__ import annotations

from typing import Dict, List, Set

from ..core.errors import Report, did_you_mean
from .ir import Direction, Production, Scene


def _known_instances(scene: Scene, production: Production) -> Dict[str, str]:
    """instance id -> kind ('char' | 'obj')."""
    out: Dict[str, str] = {}
    for p in scene.place:
        out[p.id] = p.kind
    return out


def _check_scene_refs(scene: Scene, production: Production, report: Report) -> None:
    instances = _known_instances(scene, production)
    chars = [i for i, k in instances.items() if k == "char"]
    objs = [i for i, k in instances.items() if k == "obj"]

    for p in scene.place:
        if p.kind == "char" and p.name not in production.characters:
            report.add("E200", f"scene '{scene.id}'",
                       f"place uses unknown character '{p.name}'",
                       did_you_mean(p.name, list(production.characters)) +
                       " (define it under characters:)", p.line)

    seen_ids: Set[str] = set()
    for p in scene.place:
        if p.id in seen_ids:
            report.add("E201", f"scene '{scene.id}'",
                       f"two placements share the id '{p.id}'",
                       "give one of them a unique id: <name>", p.line)
        seen_ids.add(p.id)

    for d in scene.timeline:
        if d.subject_kind == "char":
            if d.subject not in instances:
                report.add("E202", d.where,
                           f"unknown character '{d.subject}' — it is not placed in this scene",
                           did_you_mean(d.subject, chars) +
                           " (add it to the scene's place: list)", d.line)
            elif instances[d.subject] != "char":
                report.add("E203", d.where,
                           f"'{d.subject}' is an object, but this direction uses char:",
                           "use obj: for objects", d.line)
        elif d.subject_kind == "obj":
            if d.subject not in instances:
                report.add("E202", d.where,
                           f"unknown object '{d.subject}' — it is not placed in this scene",
                           did_you_mean(d.subject, objs) +
                           " (add it to the scene's place: list)", d.line)
            elif instances[d.subject] != "obj":
                report.add("E203", d.where,
                           f"'{d.subject}' is a character, but this direction uses obj:",
                           "use char: for characters", d.line)


def _check_scene_timing(scene: Scene, report: Report) -> None:
    for d in scene.timeline:
        if d.until is not None and d.until <= d.t:
            report.add("E300", d.where,
                       f"'until' ({d.until}) must be after 't' ({d.t})",
                       "increase until: or remove it", d.line)
        if d.t > scene.duration + 1e-9:
            report.add("E301", d.where,
                       f"starts at t={d.t} but the scene only lasts {scene.duration}s",
                       f"reduce t: or increase the scene duration", d.line)
        elif d.end > scene.duration + 1e-9:
            report.add("W301", d.where,
                       f"runs until {d.end}s, past the scene's end at {scene.duration}s",
                       "it will be cut off at the scene end", d.line)
    for c in scene.captions:
        if c.until <= c.t:
            report.add("E300", f"scene '{scene.id}' captions",
                       f"caption 'until' ({c.until}) must be after 't' ({c.t})",
                       "increase until:", c.line)
        if c.t > scene.duration + 1e-9:
            report.add("E301", f"scene '{scene.id}' captions",
                       f"caption starts at t={c.t}, after the scene ends ({scene.duration}s)",
                       "reduce t: or lengthen the scene", c.line)


def validate(production: Production, report: Report) -> Report:
    for scene in production.scenes:
        _check_scene_refs(scene, production, report)
        _check_scene_timing(scene, report)
        cam = scene.camera
        if cam.follow is not None:
            target = cam.follow.get("char") or cam.follow.get("obj")
            ids = [p.id for p in scene.place]
            if target and str(target) not in ids:
                report.add("E202", f"scene '{scene.id}' > camera > follow",
                           f"camera follows '{target}', which is not placed in this scene",
                           did_you_mean(str(target), ids), cam.line)
    # subsystem validators (imported lazily to keep layering clean)
    from ..assets.catalog import validate_assets
    validate_assets(production, report)
    from ..motion.validate import validate_audio, validate_motion
    validate_motion(production, report)
    validate_audio(production, report)
    return report
