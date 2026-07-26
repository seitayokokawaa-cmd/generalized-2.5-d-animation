"""Faces: eyes that blink and look, brows, and a viseme-driven mouth.

Built in the "face frame": +X = the direction the character faces, +Y = up,
origin at head center, everything scaled by head radius R.

Morph channels (all 0..1 unless noted):
    blink        1 = eyes closed
    gaze_x/gaze_y  -1..1, iris look direction
    mouth_open   jaw open amount
    mouth_wide   stretch (grin/ee)
    mouth_round  purse (oo)
    smile        -1..1 (frown..smile)
    brow_raise   0..1 lifts brows
    brow_angry   0..1 angles brows in
"""
from __future__ import annotations

import math
from typing import Dict, Optional

from ..core.color import RGBA, lighten
from ..draw.canvas import (Shape, Stroke, path_capsule, path_circle,
                           path_ellipse, path_line)
from ..scene.graph import Node

# viseme -> (open, wide, round)
VISEMES: Dict[str, tuple] = {
    "rest": (0.0, 0.0, 0.0),
    "M":    (0.0, 0.1, 0.0),
    "A":    (0.85, 0.35, 0.1),
    "I":    (0.3, 0.9, 0.0),
    "U":    (0.35, 0.0, 0.95),
    "E":    (0.5, 0.6, 0.0),
    "O":    (0.7, 0.1, 0.8),
}

EXPRESSIONS: Dict[str, Dict[str, float]] = {
    "neutral":   {},
    "happy":     {"smile": 0.9, "brow_raise": 0.25},
    "sad":       {"smile": -0.8, "brow_raise": 0.55, "brow_sad": 1.0},
    "angry":     {"smile": -0.5, "brow_angry": 1.0},
    "surprised": {"smile": 0.1, "brow_raise": 1.0, "mouth_open": 0.5, "mouth_round": 0.6},
    "scared":    {"smile": -0.6, "brow_raise": 0.9, "mouth_open": 0.35, "mouth_wide": 0.5},
    "disgusted": {"smile": -0.7, "brow_angry": 0.5},
    "tired":     {"blink": 0.55, "smile": -0.2},
    "wink":      {"wink": 1.0, "smile": 0.6},
}


def _eye(n: Node, cx: float, cy: float, r: float, m: Dict[str, float],
         iris_color: RGBA, skin: RGBA, near: bool) -> None:
    open_amt = 1.0 - float(m.get("blink", 0.0))
    if near and m.get("wink", 0.0) > 0.5:
        open_amt = 0.0
    gaze_x = float(m.get("gaze_x", 0.0)) * r * 0.35
    gaze_y = float(m.get("gaze_y", 0.0)) * r * 0.25
    if open_amt <= 0.06:
        # closed: a gentle lash line
        n.add(Shape(path=path_line([(cx - r, cy), (cx + r, cy)]),
                    stroke=Stroke(paint=(0.1, 0.08, 0.08, 1.0), width=r * 0.22)))
        return
    ry = r * 1.15 * open_amt
    n.add(Shape(path=path_ellipse(cx, cy - ry + ry, r, ry),
                fill=(1.0, 1.0, 1.0, 1.0)))
    n.add(Shape(path=path_circle(cx + gaze_x, cy + gaze_y, r * 0.52),
                fill=iris_color))
    n.add(Shape(path=path_circle(cx + gaze_x, cy + gaze_y, r * 0.24),
                fill=(0.05, 0.05, 0.08, 1.0)))
    n.add(Shape(path=path_circle(cx + gaze_x + r * 0.14, cy + gaze_y + r * 0.16, r * 0.1),
                fill=(1.0, 1.0, 1.0, 0.9)))
    # upper lid when partially closed
    if open_amt < 0.94:
        lid_h = ry * (1.0 - open_amt) * 1.35
        n.add(Shape(path=path_ellipse(cx, cy + ry - lid_h / 2 + ry * 0.15, r * 1.05, max(lid_h, ry * 0.1)),
                    fill=skin))


def _brow(n: Node, cx: float, cy: float, w: float, m: Dict[str, float],
          color: RGBA, inner_sign: float) -> None:
    raise_amt = float(m.get("brow_raise", 0.0)) * w * 0.6
    angry = float(m.get("brow_angry", 0.0))
    sad = float(m.get("brow_sad", 0.0))
    tilt = (angry * -0.5 + sad * 0.4) * inner_sign
    y = cy + raise_amt
    x0, y0 = cx - w / 2, y - tilt * w / 2
    x1, y1 = cx + w / 2, y + tilt * w / 2
    n.add(Shape(path=path_line([(x0, y0), (x1, y1)]),
                stroke=Stroke(paint=color, width=w * 0.28)))


def _mouth(n: Node, cx: float, cy: float, R: float, m: Dict[str, float],
           skin: RGBA) -> None:
    open_amt = float(m.get("mouth_open", 0.0))
    wide = float(m.get("mouth_wide", 0.0))
    rnd = float(m.get("mouth_round", 0.0))
    smile = float(m.get("smile", 0.0))
    dark = (0.25, 0.08, 0.09, 1.0)
    lip = lighten(skin, -0.18)
    if open_amt > 0.06:
        w = R * (0.30 + 0.28 * wide - 0.12 * rnd)
        h = R * (0.10 + 0.38 * open_amt)
        if rnd > 0.5:
            w = R * (0.16 + 0.1 * open_amt)
        n.add(Shape(path=path_ellipse(cx, cy - h + h, w, h), fill=dark))
        if open_amt > 0.45 and rnd < 0.6:
            n.add(Shape(path=path_ellipse(cx, cy + h * 0.45, w * 0.7, h * 0.28),
                        fill=(1.0, 1.0, 1.0, 1.0)))   # teeth
    else:
        w = R * (0.34 + 0.22 * wide)
        curve = smile * R * 0.16
        pts = []
        steps = 8
        for i in range(steps + 1):
            u = i / steps
            x = cx - w / 2 + w * u
            y = cy + (math.sin(u * math.pi) - 0.6) * curve
            pts.append((x, y))
        n.add(Shape(path=path_line(pts),
                    stroke=Stroke(paint=lip, width=R * 0.07)))


def face_node(R: float, morphs: Dict[str, float], style: dict) -> Node:
    """Facial features for a head of radius R (head disc itself drawn by the body)."""
    n = Node(name="face")
    skin: RGBA = style.get("skin_rgba", (0.88, 0.68, 0.41, 1.0))
    iris: RGBA = style.get("eyes_rgba", (0.13, 0.14, 0.17, 1.0))
    brow: RGBA = style.get("brow_rgba", (0.15, 0.11, 0.08, 1.0))
    m = morphs
    er = R * 0.21
    # far eye then near eye (near = +X, the facing side)
    _eye(n, -R * 0.16, R * 0.10, er * 0.92, m, iris, skin, near=False)
    _eye(n, R * 0.42, R * 0.10, er, m, iris, skin, near=True)
    _brow(n, -R * 0.16, R * 0.42, R * 0.36, m, brow, inner_sign=1.0)
    _brow(n, R * 0.42, R * 0.44, R * 0.4, m, brow, inner_sign=-1.0)
    # nose: subtle wedge on the facing side
    n.add(Shape(path=path_line([(R * 0.68, R * 0.02), (R * 0.78, -R * 0.12),
                                 (R * 0.62, -R * 0.18)]),
                stroke=Stroke(paint=lighten(skin, -0.14), width=R * 0.055)))
    _mouth(n, R * 0.38, -R * 0.5, R, m, skin)
    return n


def apply_expression(morphs: Dict[str, float], name: str,
                     amount: float = 1.0) -> Dict[str, float]:
    out = dict(morphs)
    for k, v in EXPRESSIONS.get(name, {}).items():
        out[k] = out.get(k, 0.0) + (v - out.get(k, 0.0)) * amount
    return out
