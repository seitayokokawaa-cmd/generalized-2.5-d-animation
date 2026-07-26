"""YAML loading with per-node line numbers and duplicate-key detection.

Returns plain dict/list/scalar structures, except mappings and sequences are
MarkedDict/MarkedList subclasses carrying `.line` (1-based) so every later
error can point at the exact screenplay line.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

import yaml

from ..core.errors import Report


class MarkedDict(dict):
    line: int = 0


class MarkedList(list):
    line: int = 0


class _Loader(yaml.SafeLoader):
    pass


def _construct_yaml_map(loader: _Loader, node):
    data = MarkedDict()
    data.line = node.start_mark.line + 1
    yield data
    seen = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in seen:
            raise yaml.MarkedYAMLError(
                problem=f"duplicate key '{key}' (first used on line {seen[key]})",
                problem_mark=key_node.start_mark,
            )
        seen[key] = key_node.start_mark.line + 1
        data[key] = loader.construct_object(value_node, deep=False)


def _construct_yaml_seq(loader: _Loader, node):
    data = MarkedList()
    data.line = node.start_mark.line + 1
    yield data
    data.extend(loader.construct_object(child, deep=False) for child in node.value)


_Loader.add_constructor("tag:yaml.org,2002:map", _construct_yaml_map)
_Loader.add_constructor("tag:yaml.org,2002:seq", _construct_yaml_seq)


def line_of(node: Any, fallback: int = 0) -> int:
    return getattr(node, "line", fallback)


def load_text(text: str) -> Tuple[Optional[Any], Report]:
    """Parse YAML text. Returns (data, report); data is None on syntax error."""
    report = Report()
    try:
        data = yaml.load(text, Loader=_Loader)
    except yaml.YAMLError as e:
        line = 0
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
        problem = getattr(e, "problem", None) or str(e)
        report.add(
            "E100", "screenplay file", f"YAML syntax error: {problem}",
            "fix the YAML syntax at this line — check indentation, colons and quotes",
            line=line,
        )
        return None, report
    if data is None:
        report.add("E101", "screenplay file", "the file is empty",
                   "start with: motionforge: 1, then meta:, characters:, scenes:")
        return None, report
    if not isinstance(data, dict):
        report.add("E102", "screenplay file",
                   f"the top level must be a mapping, got {type(data).__name__}",
                   "the screenplay starts with top-level keys like 'motionforge:', 'scenes:'")
        return None, report
    return data, report


def load_file(path: str) -> Tuple[Optional[Any], Report]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        report = Report()
        report.add("E103", "screenplay file", f"cannot read '{path}': {e.strerror}",
                   "check the file path")
        return None, report
    return load_text(text)
