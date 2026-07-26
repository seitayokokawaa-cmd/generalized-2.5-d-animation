"""Build a CharacterRig from a CharacterDef."""
from __future__ import annotations

from typing import Optional

from ..dsl.ir import CharacterDef
from .bodies.base import CharacterRig
from .style import parse_style


def make_rig(cdef: CharacterDef, palette: Optional[dict] = None) -> CharacterRig:
    style = parse_style(cdef.body, cdef.params, palette)
    if cdef.body == "human":
        from .bodies.human import build_human
        return build_human(cdef.name, cdef.params, style)
    if cdef.body == "quadruped":
        from .bodies.quadruped import build_quadruped
        return build_quadruped(cdef.name, cdef.params, style)
    if cdef.body == "bird":
        from .bodies.bird import build_bird
        return build_bird(cdef.name, cdef.params, style)
    if cdef.body == "fish":
        from .bodies.fish import build_fish
        return build_fish(cdef.name, cdef.params, style)
    from .bodies.blob import build_blob
    return build_blob(cdef.name, cdef.params, style)
