"""Minimal provider-agnostic LLM client (no SDK dependencies).

Uses the Anthropic API when ANTHROPIC_API_KEY is set, otherwise any
OpenAI-compatible endpoint via OPENAI_API_KEY (+ OPENAI_BASE_URL).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Dict, List, Optional

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"


class LLMError(RuntimeError):
    pass


def complete(messages: List[Dict[str, str]], system: str,
             model: Optional[str] = None, max_tokens: int = 8000) -> str:
    """messages: [{role: user|assistant, content: str}] -> assistant text."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _anthropic(messages, system, model, max_tokens)
    if os.environ.get("OPENAI_API_KEY"):
        return _openai(messages, system, model, max_tokens)
    raise LLMError(
        "no LLM credentials found — set ANTHROPIC_API_KEY (recommended) or "
        "OPENAI_API_KEY (+ optional OPENAI_BASE_URL for compatible providers)")


def _post(url: str, headers: Dict[str, str], payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:500]
        raise LLMError(f"LLM API error {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"cannot reach the LLM API: {e.reason}") from None


def _anthropic(messages, system, model, max_tokens) -> str:
    data = _post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": os.environ["ANTHROPIC_API_KEY"],
         "anthropic-version": "2023-06-01"},
        {"model": model or os.environ.get("MOTIONFORGE_MODEL",
                                          DEFAULT_ANTHROPIC_MODEL),
         "system": system, "messages": messages, "max_tokens": max_tokens})
    parts = data.get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def _openai(messages, system, model, max_tokens) -> str:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    data = _post(
        f"{base.rstrip('/')}/chat/completions",
        {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        {"model": model or os.environ.get("MOTIONFORGE_MODEL", DEFAULT_OPENAI_MODEL),
         "messages": [{"role": "system", "content": system}] + messages,
         "max_tokens": max_tokens})
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        raise LLMError(f"unexpected LLM response shape: {str(data)[:300]}") from None
