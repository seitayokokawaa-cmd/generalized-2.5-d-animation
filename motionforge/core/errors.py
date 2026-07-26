"""The single error/report framework.

Every problem MotionForge finds is an MFError with:
  code       stable identifier (E1xx schema, E2xx reference, E3xx timing,
             E4xx spatial/motion, E5xx resource, W9xx warnings)
  where      human path, e.g. "scene 'dawn' > timeline[3]"
  line       1-based line in the screenplay file (0 = unknown)
  message    what is wrong, in plain language
  suggestion how to fix it, in plain language an LLM can act on directly
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass
class MFError:
    code: str
    where: str
    message: str
    suggestion: str = ""
    line: int = 0

    @property
    def is_warning(self) -> bool:
        return self.code.startswith("W")

    def format(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        s = f"{self.code} {self.where}{loc}: {self.message}"
        if self.suggestion:
            s += f" — {self.suggestion}"
        return s


class Report:
    """Accumulates errors; validation never stops at the first problem."""

    def __init__(self) -> None:
        self.items: List[MFError] = []

    def add(self, code: str, where: str, message: str,
            suggestion: str = "", line: int = 0) -> None:
        self.items.append(MFError(code, where, message, suggestion, line))

    @property
    def errors(self) -> List[MFError]:
        return [e for e in self.items if not e.is_warning]

    @property
    def warnings(self) -> List[MFError]:
        return [e for e in self.items if e.is_warning]

    @property
    def ok(self) -> bool:
        return not self.errors

    def format(self) -> str:
        if not self.items:
            return "OK: screenplay is valid."
        lines = []
        if self.errors:
            lines.append(f"{len(self.errors)} problem(s) found:")
            lines += ["  " + e.format() for e in self.errors]
        if self.warnings:
            lines.append(f"{len(self.warnings)} warning(s):")
            lines += ["  " + w.format() for w in self.warnings]
        return "\n".join(lines)

    def to_json(self) -> list:
        return [
            {"code": e.code, "where": e.where, "line": e.line,
             "message": e.message, "suggestion": e.suggestion}
            for e in self.items
        ]


class ScreenplayError(Exception):
    """Raised when rendering is attempted on an invalid screenplay."""

    def __init__(self, report: Report):
        self.report = report
        super().__init__(report.format())


def did_you_mean(name: str, known: Sequence[str]) -> str:
    """A suggestion fragment: closest matches to a misspelled name."""
    matches = difflib.get_close_matches(str(name), list(known), n=3, cutoff=0.5)
    if matches:
        return f"did you mean {', '.join(repr(m) for m in matches)}?"
    shown = sorted(known)[:12]
    more = "" if len(known) <= 12 else f", ... ({len(known)} total)"
    return f"known names: {', '.join(map(str, shown))}{more}" if shown else "none are defined yet"
