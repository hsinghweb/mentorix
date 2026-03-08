"""
Generation Reliability Guards — shared helpers for JSON extraction, validation
gates, and bounded retry with reason codes.

Used by content/test/reading generation endpoints to block invalid or
low-quality outputs from reaching the UI.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# JSON extraction / cleanup
# -------------------------------------------------------------------

def extract_json(raw: str) -> Any:
    """
    Robustly extract JSON from LLM output.

    Handles:
      - Markdown fenced code blocks (```json ... ```)
      - Leading/trailing prose before/after JSON
      - Single quotes → double quotes fallback
    """
    if not raw:
        return None

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    fence_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    match = fence_pattern.search(raw)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Find first { or [ and extract
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = raw.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(raw[start:], start=start):
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start : i + 1])
                except json.JSONDecodeError:
                    break

    # Last resort: single-quote replacement
    try:
        return json.loads(raw.replace("'", '"'))
    except json.JSONDecodeError:
        return None


# -------------------------------------------------------------------
# Validation gates
# -------------------------------------------------------------------

class ValidationResult:
    def __init__(self, valid: bool, reason: str = "ok"):
        self.valid = valid
        self.reason = reason

    def __bool__(self) -> bool:
        return self.valid


def validate_format(data: Any, *, required_keys: set[str] | None = None) -> ValidationResult:
    """Check that data is a dict (or list of dicts) with required keys."""
    if data is None:
        return ValidationResult(False, "null_output")
    items = data if isinstance(data, list) else [data]
    if not items:
        return ValidationResult(False, "empty_output")
    if required_keys:
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                return ValidationResult(False, f"item_{idx}_not_dict")
            missing = required_keys - set(item.keys())
            if missing:
                return ValidationResult(False, f"item_{idx}_missing_keys:{missing}")
    return ValidationResult(True)


def validate_no_duplicates(items: list[dict], key: str) -> ValidationResult:
    """Check that no two items share the same value for ``key``."""
    seen: set[str] = set()
    for item in items:
        val = str(item.get(key, "")).strip().lower()
        if not val:
            continue
        if val in seen:
            return ValidationResult(False, f"duplicate_{key}:{val[:60]}")
        seen.add(val)
    return ValidationResult(True)


def validate_not_placeholder(items: list[dict], text_key: str) -> ValidationResult:
    """Reject items that look like placeholder/template text."""
    placeholders = {"lorem", "placeholder", "sample text", "todo", "tbd", "xxx"}
    for item in items:
        text = str(item.get(text_key, "")).strip().lower()
        if any(p in text for p in placeholders):
            return ValidationResult(False, f"placeholder_detected:{text[:60]}")
    return ValidationResult(True)


# -------------------------------------------------------------------
# Bounded retry with reason codes
# -------------------------------------------------------------------

async def generate_with_guards(
    generate_func,
    *,
    required_keys: set[str] | None = None,
    dedup_key: str | None = None,
    text_key: str | None = None,
    max_attempts: int = 3,
) -> tuple[Any, list[dict]]:
    """
    Call ``generate_func`` up to ``max_attempts`` times, applying validation
    gates after each attempt.

    Returns (parsed_data, attempt_log).
    """
    attempt_log: list[dict] = []

    for attempt in range(1, max_attempts + 1):
        try:
            raw = await generate_func()
            data = extract_json(raw) if isinstance(raw, str) else raw

            # Gate 1: format
            fmt_check = validate_format(data, required_keys=required_keys)
            if not fmt_check:
                attempt_log.append({"attempt": attempt, "rejected": True, "reason": fmt_check.reason})
                continue

            items = data if isinstance(data, list) else [data]

            # Gate 2: duplicates
            if dedup_key:
                dup_check = validate_no_duplicates(items, dedup_key)
                if not dup_check:
                    attempt_log.append({"attempt": attempt, "rejected": True, "reason": dup_check.reason})
                    continue

            # Gate 3: placeholder content
            if text_key:
                placeholder_check = validate_not_placeholder(items, text_key)
                if not placeholder_check:
                    attempt_log.append({"attempt": attempt, "rejected": True, "reason": placeholder_check.reason})
                    continue

            attempt_log.append({"attempt": attempt, "rejected": False, "reason": "accepted"})
            return data, attempt_log

        except Exception as exc:
            attempt_log.append({"attempt": attempt, "rejected": True, "reason": f"exception:{exc}"})

    # All attempts failed — return None with full log
    logger.warning("Generation guards: all %d attempts failed", max_attempts)
    return None, attempt_log
