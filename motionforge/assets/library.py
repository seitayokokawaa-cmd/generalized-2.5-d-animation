"""Built-in object catalog.

Every entry is a declarative definition in exactly the user-facing format
(see builder.py), so the catalog is self-documenting: the spec generator
lists names, sizes and articulated parts straight from this data.

All objects sit on the ground (y=0), sized in meters, facing right.
"""
from __future__ import annotations

from typing import Any, Dict

LIBRARY: Dict[str, Dict[str, Any]] = {

    # ------------------------------------------------------------ primitives
    "box": {
        "size": [1, 1],
        "parts": [{"name": "body", "shape": "rect", "w": 1, "h": 1, "fill": "wood"}],
    },
    "ball": {
        "size": [0.6, 0.6],
        "parts": [{"name": "body", "shape": "circle", "r": 0.3,
                   "fill": {"gradient": "radial", "stops": ["#e86a5e", "#b23a30"],
                            "from": [-0.08, 0.38], "to": [0, 0.3], "r1": 0.42}}],
    },
    "crate": {
        "size": [1, 1],
        "parts": [
            {"shape": "rect", "w": 1, "h": 1, "fill": "#b98c4a"},
            {"shape": "rect", "w": 1, "h": 0.12, "at": [0, 0.44], "fill": "#8a6534"},
            {"shape": "rect", "w": 0.12, "h": 1, "at": [-0.44, 0], "fill": "#8a6534"},
            {"shape": "rect", "w": 0.12, "h": 1, "at": [0.44, 0], "fill": "#8a6534"},
        ],
    },

    # ------------------------------------------------------------ vegetation
    "tree": {
        "size": [2.4, 3.2],
        "parts": [
            {"name": "trunk", "shape": "trapezoid", "w1": 0.42, "w2": 0.28, "h": 1.4,
             "fill": "#7a5230"},
            {"name": "crown", "shape": "blob", "at": [0, 1.1],
             "points": [[0, 2.0], [0.9, 1.6], [1.2, 0.8], [0.7, 0.2],
                        [0, 0.0], [-0.7, 0.2], [-1.2, 0.8], [-0.9, 1.6]],
             "fill": {"gradient": "linear", "stops": ["#5eab52", "#3c7f38"],
                      "from": [0, 2.0], "to": [0, 0]}},
        ],
    },
    "pine": {
        "size": [1.8, 3.4],
        "parts": [
            {"name": "trunk", "shape": "rect", "w": 0.26, "h": 0.9, "fill": "#6e4a28"},
            {"shape": "triangle", "w": 1.8, "h": 1.4, "at": [0, 0.7], "fill": "#2f6e46"},
            {"shape": "triangle", "w": 1.4, "h": 1.2, "at": [0, 1.6], "fill": "#357a4d"},
            {"shape": "triangle", "w": 1.0, "h": 1.0, "at": [0, 2.4], "fill": "#3c8654"},
        ],
    },
    "bush": {
        "size": [1.4, 0.9],
        "parts": [
            {"shape": "blob", "points": [[0, 0.85], [0.55, 0.6], [0.7, 0.2], [0.3, 0],
                                          [-0.3, 0], [-0.7, 0.2], [-0.55, 0.6]],
             "fill": "#4f9247"},
        ],
    },
    "flower": {
        "size": [0.3, 0.55],
        "parts": [
            {"name": "stem", "shape": "rect", "w": 0.04, "h": 0.4, "fill": "#3c7f38"},
            {"name": "head", "shape": "star", "r": 0.14, "inner": 0.08, "points_n": 6,
             "at": [0, 0.28], "fill": "#e86aa6"},
            {"shape": "circle", "r": 0.05, "cy": 0, "at": [0, 0.42], "fill": "gold"},
        ],
    },
    "rock": {
        "size": [1.0, 0.6],
        "parts": [{"shape": "blob", "points": [[-0.5, 0], [-0.4, 0.35], [0, 0.55],
                                                [0.35, 0.4], [0.5, 0]],
                   "fill": {"gradient": "linear", "stops": ["#a8a8a0", "#7c7c74"],
                            "from": [0, 0.55], "to": [0, 0]}}],
    },

    # ------------------------------------------------------------ buildings
    "house": {
        "size": [4.4, 3.9],
        "parts": [
            {"name": "wall", "shape": "rect", "w": 4.0, "h": 2.4, "fill": "cream"},
            {"name": "roof", "shape": "triangle", "w": 4.6, "h": 1.5, "at": [0, 2.4],
             "fill": "brick"},
            {"name": "door", "shape": "rect", "w": 0.8, "h": 1.6, "at": [1.1, 0],
             "articulate": "hinge", "fill": "#7a5230"},
            {"name": "knob", "shape": "circle", "r": 0.05, "cy": 0, "at": [0.85, 0.9],
             "fill": "gold"},
            {"name": "window", "shape": "rect", "w": 0.9, "h": 0.9, "at": [-1.1, 1.0],
             "fill": "#bfe3f2", "stroke": {"color": "#5a4a38", "width": 0.06}},
        ],
    },
    "barn": {
        "size": [5.4, 4.6],
        "parts": [
            {"shape": "rect", "w": 5.0, "h": 2.8, "fill": "#b0492f"},
            {"shape": "trapezoid", "w1": 5.4, "w2": 2.6, "h": 1.6, "at": [0, 2.8],
             "fill": "#8a3524"},
            {"name": "door", "shape": "rect", "w": 1.6, "h": 2.0, "at": [0, 0],
             "articulate": "hinge", "fill": "#7a5230",
             "stroke": {"color": "#5a3a20", "width": 0.06}},
            {"shape": "rect", "w": 1.0, "h": 0.8, "at": [0, 3.0], "fill": "#f5eeda"},
        ],
    },
    "windmill": {
        "size": [3.2, 7.6],
        "parts": [
            {"name": "tower", "shape": "trapezoid", "w1": 2.4, "w2": 1.2, "h": 6.2,
             "fill": "#d8cfc0"},
            {"shape": "rect", "w": 0.8, "h": 1.4, "fill": "#6e4a28"},
            {"name": "cap", "shape": "arc", "r": 0.75, "a0": 0, "a1": 180,
             "at": [0, 6.2], "fill": "#8a3524"},
            {"name": "blades", "at": [0, 6.4], "articulate": "spin", "parts": [
                {"shape": "capsule", "w": 0.3, "h": 2.6, "angle": 0, "fill": "#f0ede6",
                 "stroke": {"color": "#b8b2a4", "width": 0.04}},
                {"shape": "capsule", "w": 0.3, "h": 2.6, "angle": 90, "fill": "#f0ede6",
                 "stroke": {"color": "#b8b2a4", "width": 0.04}},
                {"shape": "capsule", "w": 0.3, "h": 2.6, "angle": 180, "fill": "#f0ede6",
                 "stroke": {"color": "#b8b2a4", "width": 0.04}},
                {"shape": "capsule", "w": 0.3, "h": 2.6, "angle": 270, "fill": "#f0ede6",
                 "stroke": {"color": "#b8b2a4", "width": 0.04}},
                {"shape": "circle", "r": 0.22, "cy": 0, "fill": "#6e4a28"},
            ]},
        ],
    },
    "tower": {
        "size": [2.2, 6.5],
        "parts": [
            {"shape": "rect", "w": 2.0, "h": 5.4, "fill": "stone"},
            {"shape": "trapezoid", "w1": 2.4, "w2": 0.3, "h": 1.1, "at": [0, 5.4],
             "fill": "#5d7085"},
            {"shape": "rect", "w": 0.5, "h": 0.8, "at": [0, 3.8], "fill": "#2c3540"},
        ],
    },

    # ------------------------------------------------------------ furniture
    "table": {
        "size": [1.8, 0.95],
        "parts": [
            {"shape": "rect", "w": 1.8, "h": 0.1, "at": [0, 0.85], "fill": "wood"},
            {"shape": "rect", "w": 0.12, "h": 0.85, "at": [-0.75, 0], "fill": "#8a6534"},
            {"shape": "rect", "w": 0.12, "h": 0.85, "at": [0.75, 0], "fill": "#8a6534"},
        ],
    },
    "chair": {
        "size": [0.6, 1.0],
        "parts": [
            {"shape": "rect", "w": 0.6, "h": 0.08, "at": [0, 0.45], "fill": "wood"},
            {"shape": "rect", "w": 0.1, "h": 0.45, "at": [-0.24, 0], "fill": "#8a6534"},
            {"shape": "rect", "w": 0.1, "h": 0.45, "at": [0.24, 0], "fill": "#8a6534"},
            {"shape": "rect", "w": 0.1, "h": 0.55, "at": [-0.24, 0.5], "fill": "#8a6534"},
            {"shape": "rect", "w": 0.55, "h": 0.4, "at": [-0.03, 0.7], "fill": "wood"},
        ],
    },
    "bench": {
        "size": [1.6, 0.85],
        "parts": [
            {"shape": "rect", "w": 1.6, "h": 0.08, "at": [0, 0.42], "fill": "wood"},
            {"shape": "rect", "w": 0.1, "h": 0.42, "at": [-0.65, 0], "fill": "#6e5433"},
            {"shape": "rect", "w": 0.1, "h": 0.42, "at": [0.65, 0], "fill": "#6e5433"},
            {"shape": "rect", "w": 1.6, "h": 0.3, "at": [0, 0.62], "fill": "wood"},
        ],
    },
    "lamp_post": {
        "size": [0.7, 3.2],
        "parts": [
            {"shape": "trapezoid", "w1": 0.35, "w2": 0.15, "h": 0.25, "fill": "#333a42"},
            {"shape": "rect", "w": 0.1, "h": 2.6, "at": [0, 0.2], "fill": "#333a42"},
            {"name": "lamp", "shape": "circle", "r": 0.22, "cy": 0, "at": [0, 2.95],
             "fill": {"gradient": "radial", "stops": ["#fff2c0", "#e8b93a"],
                      "from": [0, 2.95], "to": [0, 2.95], "r1": 0.24}},
            {"shape": "arc", "r": 0.28, "a0": 0, "a1": 180, "at": [0, 3.02],
             "fill": "#333a42"},
        ],
    },
    "sign": {
        "size": [1.0, 1.8],
        "parts": [
            {"shape": "rect", "w": 0.1, "h": 1.3, "fill": "#8a6534"},
            {"shape": "rect", "w": 1.0, "h": 0.5, "round": 0.08, "at": [0, 1.25],
             "fill": "#e8d9a8", "stroke": {"color": "#8a6534", "width": 0.05}},
        ],
    },
    "fence": {
        "size": [2.4, 1.0],
        "parts": [
            {"shape": "rect", "w": 0.1, "h": 1.0, "at": [-1.1, 0], "fill": "#b8a47e"},
            {"shape": "rect", "w": 0.1, "h": 1.0, "at": [0, 0], "fill": "#b8a47e"},
            {"shape": "rect", "w": 0.1, "h": 1.0, "at": [1.1, 0], "fill": "#b8a47e"},
            {"shape": "rect", "w": 2.4, "h": 0.12, "at": [0, 0.65], "fill": "#c8b48c"},
            {"shape": "rect", "w": 2.4, "h": 0.12, "at": [0, 0.25], "fill": "#c8b48c"},
        ],
    },
    "well": {
        "size": [1.6, 1.9],
        "parts": [
            {"shape": "rect", "w": 1.4, "h": 0.7, "fill": "stone"},
            {"shape": "rect", "w": 0.1, "h": 1.3, "at": [-0.6, 0.5], "fill": "#8a6534"},
            {"shape": "rect", "w": 0.1, "h": 1.3, "at": [0.6, 0.5], "fill": "#8a6534"},
            {"shape": "triangle", "w": 1.7, "h": 0.5, "at": [0, 1.6], "fill": "brick"},
            {"name": "crank", "shape": "rect", "w": 0.9, "h": 0.08, "at": [0, 1.15],
             "articulate": "spin", "fill": "#6e4a28"},
        ],
    },

    # ------------------------------------------------------------ vehicles
    "car": {
        "size": [3.4, 1.5],
        "parts": [
            {"name": "body", "shape": "rect", "w": 3.2, "h": 0.6, "round": 0.2,
             "at": [0, 0.35], "fill": "#c93b30"},
            {"name": "cabin", "shape": "trapezoid", "w1": 1.9, "w2": 1.2, "h": 0.55,
             "at": [-0.1, 0.95], "fill": "#c93b30"},
            {"shape": "trapezoid", "w1": 0.75, "w2": 0.55, "h": 0.42, "at": [-0.5, 0.98],
             "fill": "#bfe3f2"},
            {"shape": "trapezoid", "w1": 0.75, "w2": 0.55, "h": 0.42, "at": [0.35, 0.98],
             "fill": "#bfe3f2"},
            {"name": "wheel_back", "at": [-1.05, 0.32], "articulate": "spin", "parts": [
                {"shape": "circle", "r": 0.32, "cy": 0, "fill": "#22262b"},
                {"shape": "circle", "r": 0.16, "cy": 0, "fill": "#9aa2ad"},
                {"shape": "rect", "w": 0.26, "h": 0.05, "fill": "#5a626d"},
            ]},
            {"name": "wheel_front", "at": [1.05, 0.32], "articulate": "spin", "parts": [
                {"shape": "circle", "r": 0.32, "cy": 0, "fill": "#22262b"},
                {"shape": "circle", "r": 0.16, "cy": 0, "fill": "#9aa2ad"},
                {"shape": "rect", "w": 0.26, "h": 0.05, "fill": "#5a626d"},
            ]},
        ],
    },
    "cart": {
        "size": [2.2, 1.3],
        "parts": [
            {"shape": "trapezoid", "w1": 2.0, "w2": 1.6, "h": 0.6, "at": [0, 0.5],
             "fill": "#a5793f", "flip": False},
            {"shape": "rect", "w": 1.1, "h": 0.08, "at": [-1.35, 0.62], "angle": 12,
             "fill": "#8a6534"},
            {"name": "wheel", "at": [0.3, 0.42], "articulate": "spin", "parts": [
                {"shape": "circle", "r": 0.42, "cy": 0, "fill": "#6e4a28"},
                {"shape": "circle", "r": 0.34, "cy": 0, "fill": "#8a6534"},
                {"shape": "rect", "w": 0.66, "h": 0.06, "fill": "#5a3a20"},
                {"shape": "rect", "w": 0.06, "h": 0.66, "at": [0, -0.33], "fill": "#5a3a20"},
            ]},
        ],
    },
    "boat": {
        "size": [2.8, 2.6],
        "parts": [
            {"name": "hull", "shape": "polygon",
             "points": [[-1.4, 0.7], [1.4, 0.7], [1.0, 0.0], [-1.0, 0.0]],
             "fill": "#7a5230"},
            {"name": "mast", "shape": "rect", "w": 0.08, "h": 1.8, "at": [0, 0.7],
             "fill": "#5a3a20"},
            {"name": "sail", "shape": "polygon",
             "points": [[0.06, 0.9], [0.06, 2.4], [1.1, 1.0]], "fill": "#f0ede6"},
        ],
    },
    "crane": {
        "size": [3.0, 6.0],
        "parts": [
            {"shape": "rect", "w": 2.2, "h": 0.5, "fill": "#d9a521"},
            {"shape": "rect", "w": 0.5, "h": 4.2, "at": [-0.5, 0.5], "fill": "#d9a521"},
            {"name": "arm", "at": [-0.5, 4.6], "articulate": "hinge", "parts": [
                {"shape": "rect", "w": 3.6, "h": 0.32, "at": [1.5, -0.16], "fill": "#e8b93a"},
                {"name": "hook", "at": [3.1, -0.2], "articulate": "slide",
                 "axis": [0, -1], "parts": [
                     {"shape": "rect", "w": 0.05, "h": 1.2, "at": [0, -1.2], "fill": "#444"},
                     {"shape": "arc", "r": 0.18, "a0": 180, "a1": 360, "at": [0, -1.25],
                      "fill": "#666"},
                 ]},
            ]},
        ],
    },

    # ------------------------------------------------------------ misc
    "flag": {
        "size": [1.4, 2.6],
        "parts": [
            {"name": "pole", "shape": "rect", "w": 0.06, "h": 2.5, "fill": "#b8bcc2"},
            {"name": "cloth", "shape": "polygon",
             "points": [[0.03, 2.45], [1.25, 2.2], [0.03, 1.9]], "fill": "#d92626"},
        ],
    },
    "cloud": {
        "size": [2.6, 1.0],
        "parts": [
            {"shape": "blob", "points": [[-1.2, 0.2], [-0.7, 0.75], [0, 0.95],
                                          [0.7, 0.7], [1.2, 0.25], [0.6, 0],
                                          [-0.6, 0]],
             "fill": "#ffffffee"},
        ],
    },
    "mountain": {
        "size": [8.0, 4.5],
        "parts": [
            {"shape": "triangle", "w": 8.0, "h": 4.5, "fill": "#7d8a99"},
            {"shape": "polygon", "points": [[-0.9, 3.4], [0, 4.5], [0.9, 3.4],
                                             [0.45, 3.0], [0, 3.35], [-0.45, 3.0]],
             "fill": "#eef3f8"},
        ],
    },
    "bridge": {
        "size": [6.0, 2.2],
        "parts": [
            {"shape": "rect", "w": 6.0, "h": 0.35, "at": [0, 1.3], "fill": "stone"},
            {"shape": "arc", "r": 1.3, "a0": 0, "a1": 180, "at": [0, 0], "fill": "stone"},
            {"shape": "arc", "r": 1.05, "a0": 0, "a1": 180, "at": [0, 0], "fill": "#87ceeb"},
            {"shape": "rect", "w": 6.0, "h": 0.12, "at": [0, 1.85], "fill": "#7c7c74"},
            {"shape": "rect", "w": 0.1, "h": 0.55, "at": [-2.6, 1.3], "fill": "#7c7c74"},
            {"shape": "rect", "w": 0.1, "h": 0.55, "at": [2.6, 1.3], "fill": "#7c7c74"},
        ],
    },
}
