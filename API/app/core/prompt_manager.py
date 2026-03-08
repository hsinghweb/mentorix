"""
Prompt Manager — unified prompt loading with caching and fallback chain.

All generation modules should load prompts through ``prompt_manager.get()``.
Supports language-aware prompt selection and an audit utility.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
_cache: dict[str, str] = {}


def _ensure_prompt_dir() -> None:
    _PROMPT_DIR.mkdir(parents=True, exist_ok=True)


def get(
    name: str,
    *,
    language: str = "en",
    fallback: str | None = None,
) -> str:
    """
    Load a prompt template by name.

    Lookup order:
      1. ``prompts/{name}.{language}.txt``
      2. ``prompts/{name}.txt``
      3. ``fallback`` string argument

    Results are cached in-memory; call ``reload()`` to clear.
    """
    _ensure_prompt_dir()
    cache_key = f"{name}:{language}"
    if cache_key in _cache:
        return _cache[cache_key]

    # Language-specific file first
    lang_path = _PROMPT_DIR / f"{name}.{language}.txt"
    if lang_path.exists():
        content = lang_path.read_text(encoding="utf-8").strip()
        _cache[cache_key] = content
        return content

    # Generic fallback
    generic_path = _PROMPT_DIR / f"{name}.txt"
    if generic_path.exists():
        content = generic_path.read_text(encoding="utf-8").strip()
        _cache[cache_key] = content
        return content

    if fallback is not None:
        _cache[cache_key] = fallback
        return fallback

    logger.warning("Prompt '%s' not found (language=%s)", name, language)
    return ""


def reload() -> None:
    """Clear the prompt cache so next ``get()`` re-reads from disk."""
    _cache.clear()
    logger.info("Prompt cache cleared")


def audit() -> dict[str, Any]:
    """
    Scan prompt directory and report status of known prompt slots.

    Returns dict with 'found', 'missing' lists and 'total' count.
    """
    _ensure_prompt_dir()
    found: list[str] = []
    for p in _PROMPT_DIR.glob("*.txt"):
        found.append(p.stem)
    return {
        "prompt_dir": str(_PROMPT_DIR),
        "found": sorted(set(found)),
        "total": len(set(found)),
    }
