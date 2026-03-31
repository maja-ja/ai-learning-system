"""
Task-based model routing:
- cheap tier: brainstorming / topic seed list
- quality tier: explanation / knowledge decoding / handout generation
"""

from __future__ import annotations

import os
from typing import Literal, Dict

TaskTier = Literal["cheap", "quality"]
Provider = Literal["gemini", "claude"]


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def resolve_provider(tier: TaskTier = "quality") -> Provider:
    """
    Priority:
      1) AI_PROVIDER_<TIER>
      2) AI_PROVIDER
      3) auto -> claude if key exists else gemini
    """
    raw = _env(f"AI_PROVIDER_{tier.upper()}", _env("AI_PROVIDER", "auto")).lower()
    if raw in ("claude", "anthropic"):
        return "claude"
    if raw in ("gemini", "google"):
        return "gemini"
    # auto/default fallback
    if _env("ANTHROPIC_API_KEY"):
        return "claude"
    return "gemini"


def resolve_gemini_model(tier: TaskTier = "quality") -> str:
    if tier == "cheap":
        return _env("GEMINI_MODEL_CHEAP", _env("GEMINI_MODEL", "gemini-2.5-flash"))
    return _env("GEMINI_MODEL_QUALITY", _env("GEMINI_MODEL", "gemini-2.5-flash"))


def resolve_claude_model(tier: TaskTier = "quality") -> str:
    if tier == "cheap":
        return _env("CLAUDE_MODEL_CHEAP", _env("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"))
    return _env("CLAUDE_MODEL_QUALITY", _env("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"))


def resolve_task_config(task: str, tier: TaskTier = "quality") -> Dict[str, str]:
    provider = resolve_provider(tier=tier)
    if provider == "claude":
        return {"provider": provider, "model": resolve_claude_model(tier=tier), "tier": tier, "task": task}
    return {"provider": provider, "model": resolve_gemini_model(tier=tier), "tier": tier, "task": task}
