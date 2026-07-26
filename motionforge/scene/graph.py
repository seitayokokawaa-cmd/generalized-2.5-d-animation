"""Scene graph: nested nodes of shapes, flattened to a device draw list."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..core.transform import IDENTITY, Mat, compose
from ..draw.canvas import Shape


@dataclass
class Node:
    transform: Mat = IDENTITY
    shapes: List[Shape] = field(default_factory=list)      # local-space shapes
    children: List["Node"] = field(default_factory=list)
    opacity: float = 1.0
    visible: bool = True
    name: str = ""

    def child(self, **kw) -> "Node":
        n = Node(**kw)
        self.children.append(n)
        return n

    def add(self, shape: Shape) -> "Node":
        self.shapes.append(shape)
        return self


def flatten(node: Node, parent: Mat = IDENTITY, alpha: float = 1.0,
            out: Optional[List[Shape]] = None) -> List[Shape]:
    """Compose transforms/opacity down the tree into a flat, ordered Shape list."""
    if out is None:
        out = []
    if not node.visible or node.opacity <= 0.0:
        return out
    m = compose(parent, node.transform)
    a = alpha * node.opacity
    for s in node.shapes:
        out.append(Shape(path=s.path, fill=s.fill, stroke=s.stroke,
                         transform=compose(m, s.transform), alpha=s.alpha * a,
                         operator=s.operator))
    for c in node.children:
        flatten(c, m, a, out)
    return out
