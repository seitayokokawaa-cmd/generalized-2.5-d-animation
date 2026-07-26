"""Shared helpers for the MotionForge test suite."""
from __future__ import annotations

import textwrap

from motionforge.dsl.parser import parse_text
from motionforge.dsl.validator import validate
from motionforge.scene.world import World


def compile_production(yaml_text: str):
    """Parse + validate a screenplay string -> (production_or_None, report)."""
    prod, report = parse_text(textwrap.dedent(yaml_text))
    if prod is not None:
        validate(prod, report)
    return prod, report


def compile_ok(yaml_text: str):
    """Compile a screenplay that must be error-free; return the Production."""
    prod, report = compile_production(yaml_text)
    assert prod is not None, "parse failed:\n" + report.format()
    assert report.ok, "expected a clean screenplay, got:\n" + report.format()
    return prod


def make_world(yaml_text: str) -> World:
    return World(compile_ok(yaml_text))


def error_codes(yaml_text: str):
    """All error/warning codes reported for a screenplay string."""
    _prod, report = compile_production(yaml_text)
    return {e.code for e in report.items}
