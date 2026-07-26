"""The autopilot: story idea in, finished film out, no human in the loop.

    motionforge auto "a fox learns to fly" -o film.mp4

Loop: LLM writes a screenplay from the generated SPEC -> `check` validates ->
plain-language errors go back to the LLM -> repeat until clean -> render.
"""
from __future__ import annotations

import re
import sys
from typing import List, Optional

from ..core.errors import Report
from ..dsl.parser import parse_text
from ..dsl.validator import validate
from ..spec.generate import generate_spec
from .llm import LLMError, complete

SYSTEM = """You are a screenwriter-director for MotionForge, a deterministic \
2.5D animation studio. You write complete screenplays in MotionForge YAML.

Rules:
- Reply with ONE fenced yaml block containing the complete screenplay, and \
nothing else outside the fence.
- Aim for a 20-45 second film with 2-4 scenes, a clear little story arc, \
expressive acting (emote, say, actions), at least one camera move, captions \
for title/mood, music, and staging that uses depth (near/mid/far).
- When you receive a validation report, fix EVERY listed problem and reply \
with the full corrected screenplay in one yaml block again.

The complete language reference follows.

"""


def _extract_yaml(text: str) -> Optional[str]:
    m = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    if text.strip().startswith("motionforge"):
        return text
    return None


def autopilot(idea: str, output: str = "film.mp4", model: Optional[str] = None,
              max_rounds: int = 6, keep: bool = False) -> int:
    spec = generate_spec()
    system = SYSTEM + spec
    messages: List[dict] = [{"role": "user", "content":
                             f"Write a MotionForge screenplay for this idea:\n\n{idea}"}]
    screenplay = None
    for round_i in range(1, max_rounds + 1):
        print(f"[auto] round {round_i}: asking the model...", file=sys.stderr)
        try:
            reply = complete(messages, system, model)
        except LLMError as e:
            print(f"[auto] {e}", file=sys.stderr)
            return 2
        text = _extract_yaml(reply)
        if text is None:
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content":
                          "Reply with the complete screenplay in one ```yaml fence."}]
            continue
        prod, report = parse_text(text)
        if prod is not None:
            validate(prod, report)
        if prod is not None and report.ok:
            screenplay = text
            break
        print(f"[auto] {len(report.errors)} problem(s); sending them back",
              file=sys.stderr)
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content":
                      "The validator found these problems — fix all of them and "
                      "send the full corrected screenplay:\n\n" + report.format()}]
    if screenplay is None:
        print(f"[auto] gave up after {max_rounds} rounds — the last report:",
              file=sys.stderr)
        return 3

    if keep:
        path = re.sub(r"\.mp4$", "", output) + ".yaml"
        with open(path, "w", encoding="utf-8") as f:
            f.write(screenplay)
        print(f"[auto] screenplay saved to {path}", file=sys.stderr)

    prod, report = parse_text(screenplay)
    if report.warnings:
        print(report.format(), file=sys.stderr)
    from ..render.encode import render_video
    print("[auto] rendering...", file=sys.stderr)
    render_video(prod, output)
    print(f"[auto] wrote {output} ({prod.duration:.1f}s)", file=sys.stderr)
    return 0
