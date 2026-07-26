"""Character styling: colors, hair, outfit, proportions — parsed once."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..core import color as colors
from ..core.color import RGBA, lighten

HAIR_STYLES = ["none", "short", "bun", "long", "ponytail", "curly", "spiky", "bald"]
BUILD = {"slim": 0.85, "normal": 1.0, "heavy": 1.3, "muscular": 1.15}
AGE = {  # head-size factor, height factor already applied via height param
    "child": {"head": 1.35, "limb": 0.9},
    "teen": {"head": 1.12, "limb": 0.97},
    "adult": {"head": 1.0, "limb": 1.0},
    "elder": {"head": 1.0, "limb": 0.97},
}

SPECIES_COLORS = {
    "dog": "#a8845c", "cat": "#8c8c94", "horse": "#7a4f2b", "cow": "#e8e4da",
    "pig": "#e8a8a0", "sheep": "#e8e0d0", "goat": "#c8bcaa", "rabbit": "#cfc4b8",
    "fox": "#d4713a", "wolf": "#7d838c", "bear": "#6e4a28", "lion": "#c9973e",
    "tiger": "#d9822b", "elephant": "#9a9aa2", "deer": "#b08050", "mouse": "#a8a2ac",
    "crow": "#26262e", "sparrow": "#a08058", "eagle": "#6e5433", "owl": "#a89478",
    "parrot": "#2f9e44", "duck": "#e8e4da", "chicken": "#e0d8c8", "penguin": "#2c3540",
    "goldfish": "#e8842c", "shark": "#7d8a99", "whale": "#4a5f78", "salmon": "#c97a6a",
}


def parse_style(body: str, params: Dict[str, Any],
                palette: Optional[dict] = None) -> Dict[str, Any]:
    def col(value, default: str) -> RGBA:
        if value is None:
            return colors.parse(default, palette)
        try:
            return colors.parse(value, palette)
        except ValueError:
            return colors.parse(default, palette)

    species = str(params.get("species", "") or "")
    base_default = SPECIES_COLORS.get(species, "#a8845c" if body != "human" else "#e0ac69")
    base = col(params.get("color") or params.get("skin"), base_default)

    hair = params.get("hair") or {}
    if isinstance(hair, str):
        hair = {"style": hair}
    outfit = params.get("outfit") or {}
    if isinstance(outfit, str):
        outfit = {"top": outfit}

    style: Dict[str, Any] = {
        "body": body,
        "species": species,
        "skin_rgba": base,
        "skin2_rgba": lighten(base, 0.12),           # belly / muzzle accent
        "eyes_rgba": col(params.get("eyes"), "#20242c"),
        "hair_style": str(hair.get("style", "short" if body == "human" else "none")),
        "hair_rgba": col(hair.get("color"), "#3a2a1a"),
        "brow_rgba": lighten(col(hair.get("color"), "#3a2a1a"), -0.08),
        "top_rgba": col(outfit.get("top"), "#3f6fb5"),
        "bottom_rgba": col(outfit.get("bottom"), "#41485c"),
        "shoe_rgba": col(outfit.get("shoes"), "#33302c"),
        "hat_rgba": col(outfit.get("hat"), "#00000000") if outfit.get("hat") else None,
        "has_top": "top" in outfit or body == "human",
        "has_bottom": "bottom" in outfit or body == "human",
        "build": BUILD.get(str(params.get("build", "normal")), 1.0),
        "age": AGE.get(str(params.get("age", "adult")), AGE["adult"]),
    }
    return style
