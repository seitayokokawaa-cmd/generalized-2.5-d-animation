"""Object type resolution: user assets override the built-in library."""
from __future__ import annotations

from typing import Dict, Optional

from ..core.errors import Report, did_you_mean
from ..dsl.ir import Production
from .builder import ObjectType, compile_object
from .library import LIBRARY


class Catalog:
    """Compiled object types for one production (cached)."""

    def __init__(self, production: Production, report: Optional[Report] = None):
        self.production = production
        self.report = report
        self._cache: Dict[str, ObjectType] = {}

    def known_names(self) -> list:
        return sorted(set(LIBRARY) | set(self.production.assets))

    def get(self, name: str) -> Optional[ObjectType]:
        if name in self._cache:
            return self._cache[name]
        palette = self.production.palette
        if name in self.production.assets:
            obj = compile_object(name, self.production.assets[name].raw,
                                 palette, self.report)
        elif name in LIBRARY:
            obj = compile_object(name, LIBRARY[name], palette, self.report)
        else:
            return None
        self._cache[name] = obj
        return obj


def validate_assets(production: Production, report: Report) -> None:
    catalog = Catalog(production, report)
    # compile every user asset once so definition errors surface with lines
    for name in production.assets:
        catalog.get(name)
    for scene in production.scenes:
        placed_types: Dict[str, str] = {}
        for p in scene.place:
            if p.kind != "obj":
                continue
            obj = catalog.get(p.name)
            if obj is None:
                report.add("E210", f"scene '{scene.id}'",
                           f"unknown object type '{p.name}'",
                           did_you_mean(p.name, catalog.known_names()) +
                           " (or define it under assets:)", p.line)
                continue
            placed_types[p.id] = p.name
            if p.tint is not None:
                from ..core import color as colors
                try:
                    colors.parse(p.tint, production.palette)
                except ValueError as e:
                    report.add("E130", f"scene '{scene.id}' place '{p.id}'",
                               f"tint: {e}",
                               "use #hex, a palette name, or a built-in color",
                               p.line)
            ps = p.params.get("part_state")
            if isinstance(ps, dict):
                for part in ps:
                    if part not in obj.articulated:
                        report.add("E211", f"scene '{scene.id}' place '{p.id}'",
                                   f"'{p.name}' has no articulated part '{part}'",
                                   did_you_mean(part, list(obj.articulated)) or
                                   "this object has no moving parts", p.line)
        for d in scene.timeline:
            if d.subject_kind != "obj" or d.subject not in placed_types:
                continue
            obj = catalog.get(placed_types[d.subject])
            if obj is None:
                continue
            part = d.params.get("part")
            if d.verb in ("spin", "hinge", "slide"):
                if part is None:
                    # allowed when the object has exactly one part of that kind
                    kinds = [n for n, k in obj.articulated.items() if k == d.verb]
                    if len(kinds) != 1:
                        report.add("E212", d.where,
                                   f"'{d.verb}' needs part: to say which part of "
                                   f"'{placed_types[d.subject]}' to move",
                                   f"articulated parts: {', '.join(obj.articulated) or 'none'}",
                                   d.line)
                elif str(part) not in obj.articulated:
                    report.add("E213", d.where,
                               f"'{placed_types[d.subject]}' has no articulated part '{part}'",
                               did_you_mean(str(part), list(obj.articulated)) or
                               "this object has no moving parts", d.line)
                elif obj.articulated[str(part)] != d.verb:
                    kind = obj.articulated[str(part)]
                    report.add("E214", d.where,
                               f"part '{part}' is a {kind} part, but the direction says {d.verb}",
                               f"use {kind}: instead", d.line)
