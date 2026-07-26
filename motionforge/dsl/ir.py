"""The typed intermediate representation (IR) a screenplay parses into.

The parser guarantees types and defaults; deeper semantic checks live in the
validator. Subsystems (assets, characters, motion, fx, audio) interpret the
`params`/`raw` payloads that are specific to them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Meta:
    title: str = ""
    resolution: Tuple[int, int] = (1280, 720)
    fps: int = 30
    seed: int = 0


@dataclass
class ObjectDef:
    """A user-defined (or library) object type; assets.builder interprets `raw`."""
    name: str
    raw: Dict[str, Any]
    line: int = 0


@dataclass
class CharacterDef:
    name: str
    body: str = "human"          # human | quadruped | bird | fish | blob
    params: Dict[str, Any] = field(default_factory=dict)
    line: int = 0


@dataclass
class Placement:
    kind: str                    # 'char' | 'obj'
    name: str                    # character name or object type
    id: str                      # instance id (defaults to name)
    at: Tuple[float, float] = (0.0, 0.0)
    depth: float = 0.0
    facing: str = "right"
    scale: float = 1.0
    flip: bool = False
    tint: Optional[Any] = None
    layer: int = 0
    params: Dict[str, Any] = field(default_factory=dict)
    line: int = 0


@dataclass
class Direction:
    """One timeline entry, normalized: subject + verb + params."""
    t: float
    subject_kind: str            # 'char' | 'obj' | 'camera' | 'sfx' | 'world'
    subject: str                 # instance id ('' for camera/sfx/world)
    verb: str                    # walk/say/ragdoll/spin/hinge/move/zoom/play/...
    until: Optional[float] = None
    params: Dict[str, Any] = field(default_factory=dict)
    where: str = ""
    line: int = 0

    @property
    def end(self) -> float:
        return self.until if self.until is not None else self.t


@dataclass
class Caption:
    t: float
    until: float
    text: str
    style: str = "caption"       # title | subtitle | lower_third | caption
    params: Dict[str, Any] = field(default_factory=dict)
    line: int = 0


@dataclass
class CameraSpec:
    keys: List[Dict[str, Any]] = field(default_factory=list)
    follow: Optional[Dict[str, Any]] = None
    line: int = 0


@dataclass
class Scene:
    id: str
    duration: float
    background: Dict[str, Any] = field(default_factory=dict)
    transition_in: Optional[Dict[str, Any]] = None
    transition_out: Optional[Dict[str, Any]] = None
    camera: CameraSpec = field(default_factory=CameraSpec)
    place: List[Placement] = field(default_factory=list)
    timeline: List[Direction] = field(default_factory=list)
    captions: List[Caption] = field(default_factory=list)
    line: int = 0
    start_time: float = 0.0      # filled in by parser: absolute start in the film


@dataclass
class AudioSpec:
    music: Optional[Dict[str, Any]] = None
    sfx: List[Dict[str, Any]] = field(default_factory=list)
    line: int = 0


@dataclass
class Production:
    meta: Meta = field(default_factory=Meta)
    palette: Dict[str, str] = field(default_factory=dict)
    assets: Dict[str, ObjectDef] = field(default_factory=dict)
    characters: Dict[str, CharacterDef] = field(default_factory=dict)
    scenes: List[Scene] = field(default_factory=list)
    audio: AudioSpec = field(default_factory=AudioSpec)

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.scenes)

    def scene_at(self, t: float) -> Optional[Tuple[Scene, float]]:
        """Return (scene, local_time) for absolute film time t."""
        acc = 0.0
        for s in self.scenes:
            if t < acc + s.duration or s is self.scenes[-1]:
                return s, min(max(t - acc, 0.0), s.duration)
            acc += s.duration
        return None
