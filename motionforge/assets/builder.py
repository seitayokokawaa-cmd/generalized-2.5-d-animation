"""Compile declarative object definitions into instantiable ObjectTypes.

An object is a tree of parts. Each part is either a shape or a group
(with `parts:` children). Parts can articulate:

    articulate: spin    continuous rotation about `at` (the pivot)
    articulate: hinge   keyed rotation about `at`
    articulate: slide   keyed translation along `axis` (default [1, 0])

Articulated parts are addressed by name from the timeline. The compiled
type builds a scene-graph Node given a part-state dict {part_name: value}.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..core import color as colors
from ..core.errors import Report, did_you_mean
from ..core.transform import IDENTITY, Mat, about, chain, rotation, scaling, translation
from ..draw.canvas import Gradient, Shape, Stroke
from ..scene.graph import Node
from .shapes import SHAPES

_PART_KEYS = ("name", "shape", "at", "angle", "scale", "flip", "fill", "stroke",
              "opacity", "articulate", "axis", "parts", "mirror")


@dataclass
class Part:
    name: str
    segs: Optional[list] = None                 # leaf shape
    children: List["Part"] = field(default_factory=list)
    at: Tuple[float, float] = (0.0, 0.0)
    angle: float = 0.0
    scale: Tuple[float, float] = (1.0, 1.0)
    fill: Optional[Any] = None
    stroke: Optional[Stroke] = None
    opacity: float = 1.0
    articulate: str = ""                        # '' | spin | hinge | slide
    axis: Tuple[float, float] = (1.0, 0.0)


@dataclass
class ObjectType:
    name: str
    root: List[Part]
    size: Tuple[float, float] = (1.0, 1.0)
    articulated: Dict[str, str] = field(default_factory=dict)   # part -> kind

    def node(self, part_state: Optional[Dict[str, float]] = None,
             tint: Optional[Any] = None, palette: Optional[dict] = None) -> Node:
        state = part_state or {}
        tint_rgba = None
        if tint is not None:
            try:
                tint_rgba = colors.parse(tint, palette)
            except ValueError:
                tint_rgba = None      # validator reports it; draw untinted
        root = Node(name=self.name)
        for part in self.root:
            root.children.append(self._build(part, state, tint_rgba))
        return root

    def _paint(self, paint, tint_rgba):
        if paint is None or tint_rgba is None:
            return paint
        if isinstance(paint, Gradient):
            return Gradient(kind=paint.kind,
                            stops=[(o, colors.tint(c, tint_rgba, 0.85)) for o, c in paint.stops],
                            p0=paint.p0, p1=paint.p1, r0=paint.r0, r1=paint.r1)
        return colors.tint(paint, tint_rgba, 0.85)

    def _build(self, part: Part, state: Dict[str, float], tint_rgba) -> Node:
        m = chain(translation(part.at[0], part.at[1]),
                  rotation(part.angle),
                  scaling(part.scale[0], part.scale[1]))
        value = state.get(part.name, 0.0) if part.name else 0.0
        if part.articulate in ("spin", "hinge") and value:
            m = chain(m, rotation(float(value)))
        elif part.articulate == "slide" and value:
            m = chain(m, translation(part.axis[0] * float(value),
                                     part.axis[1] * float(value)))
        n = Node(transform=m, opacity=part.opacity, name=part.name)
        if part.segs is not None:
            n.add(Shape(path=part.segs,
                        fill=self._paint(part.fill, tint_rgba),
                        stroke=(Stroke(paint=self._paint(part.stroke.paint, tint_rgba),
                                       width=part.stroke.width, cap=part.stroke.cap,
                                       join=part.stroke.join, dash=part.stroke.dash)
                                if part.stroke else None)))
        for c in part.children:
            n.children.append(self._build(c, state, tint_rgba))
        return n


def _parse_paint(spec, palette, where: str, report: Optional[Report]):
    if spec is None:
        return None
    if isinstance(spec, dict) and ("stops" in spec or "gradient" in spec):
        from ..core.coerce import fnum, fvec2
        kind = str(spec.get("gradient", "linear"))
        stops_raw = spec.get("stops", [])
        if not isinstance(stops_raw, list):
            stops_raw = []
        stops = []
        for i, st in enumerate(stops_raw):
            if isinstance(st, (list, tuple)) and len(st) == 2:
                off, col = st
            else:
                off, col = (i / max(len(stops_raw) - 1, 1), st)
            off = fnum(off, i / max(len(stops_raw) - 1, 1), lo=0.0, hi=1.0)
            try:
                stops.append((off, colors.parse(col, palette)))
            except ValueError as e:
                if report:
                    report.add("E130", where, str(e), "")
                stops.append((off, (0.5, 0.5, 0.5, 1.0)))
        return Gradient(kind=kind, stops=stops,
                        p0=fvec2(spec.get("from"), (0.0, 0.0)),
                        p1=fvec2(spec.get("to"), (0.0, 1.0)),
                        r0=fnum(spec.get("r0", 0.0), 0.0, lo=0.0),
                        r1=fnum(spec.get("r1", 1.0), 1.0, lo=0.0))
    try:
        return colors.parse(spec, palette)
    except ValueError as e:
        if report:
            report.add("E130", where, str(e),
                       "use #hex, a palette name, or a built-in color name")
        return (0.5, 0.5, 0.5, 1.0)


def _parse_part(raw: dict, idx: int, where: str, palette: dict,
                report: Optional[Report]) -> Optional[Part]:
    w = f"{where} > parts[{idx}]"
    if not isinstance(raw, dict):
        if report:
            report.add("E131", w, f"a part must be a mapping, got {raw!r}",
                       "e.g. {shape: rect, w: 1, h: 2, fill: brick}")
        return None
    unknown = [k for k in raw if k not in _PART_KEYS and k not in _shape_param_keys(raw)]
    # shape params are free-form per shape; only flag keys when there is no shape
    from ..core.coerce import fnum, fvec2, is_vec2

    def bad(field: str, value) -> None:
        if report:
            report.add("E134", w, f"'{field}' must be a number, got {value!r}",
                       "using the default instead")

    part = Part(name=str(raw.get("name", "")))
    at = raw.get("at", (0.0, 0.0))
    if at != (0.0, 0.0) and not is_vec2(at):
        bad("at", at)
    part.at = fvec2(at, (0.0, 0.0))
    if "angle" in raw and not isinstance(raw["angle"], (int, float)):
        bad("angle", raw["angle"])
    part.angle = fnum(raw.get("angle", 0.0), 0.0)
    sc = raw.get("scale", 1.0)
    if isinstance(sc, (int, float)) and not isinstance(sc, bool):
        part.scale = (float(sc), float(sc))
    elif is_vec2(sc):
        part.scale = (float(sc[0]), float(sc[1]))
    elif sc != 1.0:
        bad("scale", sc)
    if raw.get("flip"):
        part.scale = (-part.scale[0], part.scale[1])
    part.opacity = fnum(raw.get("opacity", 1.0), 1.0, lo=0.0, hi=1.0)
    part.articulate = str(raw.get("articulate", ""))
    if part.articulate and part.articulate not in ("spin", "hinge", "slide"):
        if report:
            report.add("E132", w, f"unknown articulation '{part.articulate}'",
                       "use spin, hinge, or slide")
        part.articulate = ""
    part.axis = fvec2(raw.get("axis"), (1.0, 0.0))

    if "parts" in raw:
        for i, child in enumerate(raw.get("parts") or []):
            cp = _parse_part(child, i, w, palette, report)
            if cp:
                part.children.append(cp)
        if raw.get("mirror"):
            for i, child in enumerate(list(part.children)):
                mirrored = _mirror_part(child)
                part.children.append(mirrored)
    elif "shape" in raw:
        shape_name = str(raw["shape"])
        entry = SHAPES.get(shape_name)
        if entry is None:
            if report:
                report.add("E133", w, f"unknown shape '{shape_name}'",
                           did_you_mean(shape_name, list(SHAPES)))
            return None
        try:
            part.segs = entry[0](raw)
        except (ValueError, KeyError, TypeError, IndexError) as e:
            if report:
                report.add("E134", w, f"bad parameters for shape '{shape_name}': {e}",
                           f"expected: {entry[1]}")
            return None
    else:
        if report:
            report.add("E135", w, "a part needs either shape: or parts:",
                       "give it a shape (see the Shapes catalog) or child parts")
        return None

    part.fill = _parse_paint(raw.get("fill"), palette, w, report)
    stroke_spec = raw.get("stroke")
    if stroke_spec is not None:
        if isinstance(stroke_spec, dict):
            paint = _parse_paint(stroke_spec.get("color", "#000"), palette, w, report)
            part.stroke = Stroke(paint=paint,
                                 width=fnum(stroke_spec.get("width", 0.03), 0.03,
                                            lo=0.0))
        else:
            part.stroke = Stroke(paint=_parse_paint(stroke_spec, palette, w, report),
                                 width=0.03)
    if part.fill is None and part.stroke is None and part.segs is not None:
        part.fill = (0.5, 0.5, 0.5, 1.0)
    return part


def _mirror_part(p: Part) -> Part:
    return Part(name=(p.name + "_m") if p.name else "",
                segs=p.segs, children=[_mirror_part(c) for c in p.children],
                at=(-p.at[0], p.at[1]), angle=-p.angle,
                scale=(-p.scale[0], p.scale[1]),
                fill=p.fill, stroke=p.stroke, opacity=p.opacity,
                articulate=p.articulate, axis=(-p.axis[0], p.axis[1]))


def _shape_param_keys(raw: dict) -> tuple:
    return tuple(k for k in raw if k not in _PART_KEYS)


def compile_object(name: str, raw: Dict[str, Any], palette: Optional[dict] = None,
                   report: Optional[Report] = None) -> ObjectType:
    where = f"asset '{name}'"
    palette = palette or {}
    parts_raw = raw.get("parts")
    parts: List[Part] = []
    if not isinstance(parts_raw, list) or not parts_raw:
        if report:
            report.add("E136", where, "an object definition needs a parts: list",
                       "add parts: [{shape: rect, w: 1, h: 1, fill: gray}]")
    else:
        for i, praw in enumerate(parts_raw):
            p = _parse_part(praw, i, where, palette, report)
            if p:
                parts.append(p)
    from ..core.coerce import fvec2
    size = fvec2(raw.get("size"), (1.0, 1.0))
    obj = ObjectType(name=name, root=parts, size=size)

    def collect(ps: List[Part]) -> None:
        for p in ps:
            if p.articulate and p.name:
                obj.articulated[p.name] = p.articulate
            collect(p.children)
    collect(parts)
    return obj
