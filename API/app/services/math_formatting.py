"""
Math formatting service — deterministic and LLM-backed LaTeX repair.

Extracted from ``learning/routes.py`` to improve separation of concerns.
All math formatting helpers live here and are imported as needed by
both learning and onboarding route modules.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.core.settings import settings
from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger

logger = get_domain_logger(__name__, DOMAIN_COMPLIANCE)


# ── Internal helpers ─────────────────────────────────────────────────

def _split_math_blocks(text: str) -> list[tuple[bool, str]]:
    """Split *text* into (is_math, chunk) pairs by LaTeX delimiters."""
    parts: list[tuple[bool, str]] = []
    cursor = 0
    for m in re.finditer(r"(\\\(.+?\\\)|\\\[.+?\\\])", text, flags=re.DOTALL):
        if m.start() > cursor:
            parts.append((False, text[cursor:m.start()]))
        parts.append((True, m.group(0)))
        cursor = m.end()
    if cursor < len(text):
        parts.append((False, text[cursor:]))
    return parts


def _looks_like_math_fragment(fragment: str) -> bool:
    """Heuristic check whether *fragment* is likely a math expression."""
    s = str(fragment or "").strip()
    if not s:
        return False
    if any(ch in s for ch in ["\\", "^", "_", "=", "+", "-", "*", "/", "\u00d7", "\u00f7", "<", ">"]):
        return True
    if re.fullmatch(r"[a-zA-Z]\d*", s):
        return True
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return True
    if re.fullmatch(r"[a-zA-Z0-9]+\s*(?:[+\-*/=]\s*[a-zA-Z0-9]+)+", s):
        return True
    return False


# ── Public API ───────────────────────────────────────────────────────

def normalize_generated_math_markdown(text: str) -> str:
    """
    Normalize weak math formatting from LLM output for better frontend rendering.
    Example: ``( a )`` → ``\\(a\\)``.
    """
    raw = str(text or "")
    if not raw:
        return raw

    def repl(m: re.Match) -> str:
        inner = (m.group(1) or "").strip()
        if not _looks_like_math_fragment(inner):
            return m.group(0)
        if inner.startswith("\\(") and inner.endswith("\\)"):
            return m.group(0)
        compact = re.sub(r"\s+", " ", inner)
        return f"\\({compact}\\)"

    parts: list[str] = []
    for is_math, chunk in _split_math_blocks(raw):
        if is_math:
            parts.append(chunk)
            continue
        normalized = re.sub(r"\(\s*([^()\n]{1,120})\s*\)", repl, chunk)
        normalized = re.sub(r"\(\s+", "(", normalized)
        normalized = re.sub(r"\s+\)", ")", normalized)
        parts.append(normalized)
    return "".join(parts)


def repair_broken_latex_delimiters(text: str) -> str:
    """
    Repair common malformed inline delimiters seen in model output:
    - ``\\\\( ... \\\\\\\\)`` → ``\\\\( ... \\\\)``
    - Unbalanced ``\\\\(`` without closing ``\\\\)`` on a line → append closing.
    """
    raw = str(text or "")
    if not raw:
        return raw

    fixed = raw
    fixed = fixed.replace("\\\\(", "\\(").replace("\\\\)", "\\)")
    fixed = fixed.replace("\\\\[", "\\[").replace("\\\\]", "\\]")
    fixed = re.sub(r"\\\((.*?)\\\\\)", r"\\(\1\\)", fixed, flags=re.DOTALL)

    def _wrap_bare_fragment(m: re.Match) -> str:
        prefix = m.group(1)
        body = (m.group(2) or "").replace("\\\\)", "")
        return prefix + "\\(" + body + "\\)"

    fixed = re.sub(
        r"(^|[\s,;:([{\-])((?:\\[A-Za-z]+(?:\{[^{}]*\}|[A-Za-z0-9._^+\-])*)+)\\\\\\)",
        _wrap_bare_fragment,
        fixed,
    )

    balanced: list[str] = []
    for line in fixed.splitlines():
        open_count = line.count(r"\(")
        close_count = line.count(r"\)")
        if open_count > close_count:
            line = line + (r"\)" * (open_count - close_count))
        balanced.append(line)
    return "\n".join(balanced)


def repair_unwrapped_math_fragments(text: str) -> str:
    """Wrap common bare math expressions in LaTeX inline delimiters."""
    fragments = _split_math_blocks(text)
    out: list[str] = []
    for is_math, chunk in fragments:
        if is_math:
            out.append(chunk)
            continue

        repaired = chunk

        def wrap_fraction(m: re.Match) -> str:
            expr = m.group(0).strip()
            return f"\\({expr}\\)"
        repaired = re.sub(
            r"(?<!\\\\\\()(?<![A-Za-z0-9_])([A-Za-z0-9_]+\s*/\s*[A-Za-z0-9_]+)(?![A-Za-z0-9_])(?!\\\\\\))",
            wrap_fraction,
            repaired,
        )

        def wrap_expr(m: re.Match) -> str:
            expr = m.group(0).strip()
            if expr.startswith("\\(") and expr.endswith("\\)"):
                return expr
            return f"\\({expr}\\)"
        repaired = re.sub(
            r"(?<!\\\\\\()(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*\s*(?:=|\+|-|\*|/|\^|\u00d7|\u00f7|<|>)\s*[A-Za-z0-9_\\\\][A-Za-z0-9_\\\\\s+\-*/^\u00d7\u00f7<>{}]*)",
            wrap_expr,
            repaired,
        )
        repaired = re.sub(
            r"(?<!\\\\\\()(?<![A-Za-z0-9_])([A-Za-z]\s+divides\s+[A-Za-z0-9_\\\\^{}]+)",
            wrap_expr,
            repaired,
            flags=re.IGNORECASE,
        )

        out.append(repaired)
    return "".join(out)


def count_unwrapped_math_like(text: str) -> int:
    """Count remaining unwrapped math-like expressions in *text*."""
    count = 0
    for is_math, chunk in _split_math_blocks(text):
        if is_math:
            continue
        count += len(re.findall(r"\(\s*[a-zA-Z0-9_\\\\^{}=+\-*/\u00d7\u00f7<>\s]{1,80}\s*\)", chunk))
        count += len(re.findall(r"(?<!\\\\\\()([A-Za-z0-9_]+\s*/\s*[A-Za-z0-9_]+)(?!\\\\\\))", chunk))
        count += len(re.findall(r"(?<!\\\\\\()([A-Za-z]\s+divides\s+[A-Za-z0-9_\\\\^{}]+)", chunk, flags=re.IGNORECASE))
        count += len(re.findall(r"(?<!\\\\\\()([A-Za-z][A-Za-z0-9_]*\s*(?:=|\+|-|\*|/|\^|\u00d7|\u00f7)\s*[A-Za-z0-9_\\\\][A-Za-z0-9_\\\\\s+\-*/^\u00d7\u00f7{}]*)", chunk))
    return count


async def enforce_math_format(text: str, provider: Any = None, allow_second_pass: bool = True) -> str:
    """Full pipeline: repair delimiters → normalize → repair unwrapped → optional LLM second pass."""
    prefixed = repair_broken_latex_delimiters(text)
    repaired = repair_unwrapped_math_fragments(normalize_generated_math_markdown(prefixed))
    unresolved = count_unwrapped_math_like(repaired)
    if unresolved <= 0:
        return repaired

    logger.warning("event=math_format_unresolved stage=deterministic count=%s", unresolved)
    if not allow_second_pass or not settings.math_format_fix_second_pass_enabled or provider is None:
        return repaired

    fix_prompt = (
        "Rewrite the following educational content with STRICT formatting rules.\n"
        "Keep meaning unchanged.\n"
        "Rules:\n"
        "- Every mathematical expression MUST be wrapped in LaTeX inline delimiters \\\\( ... \\\\).\n"
        "- Do not use plain parenthesized math like ( a ) or ( p/q ).\n"
        "- Keep markdown structure intact.\n\n"
        "Content:\n"
        f"{repaired}"
    )
    try:
        llm_text, _ = await provider.generate(fix_prompt)
        if llm_text and llm_text.strip():
            fixed = repair_unwrapped_math_fragments(
                normalize_generated_math_markdown(repair_broken_latex_delimiters(llm_text.strip()))
            )
            unresolved_fixed = count_unwrapped_math_like(fixed)
            logger.info(
                "event=math_format_second_pass unresolved_before=%s unresolved_after=%s",
                unresolved,
                unresolved_fixed,
            )
            return fixed if unresolved_fixed <= unresolved else repaired
    except Exception as exc:
        logger.warning("Math format second pass failed: %s", exc)
    return repaired


def format_math_for_display(text: str) -> str:
    """Deterministic pass for cached/review/fallback text shown in UI."""
    prefixed = repair_broken_latex_delimiters(str(text or ""))
    return repair_unwrapped_math_fragments(normalize_generated_math_markdown(prefixed))


async def format_mcq_item_math(item: dict, provider: Any = None) -> dict:
    """Apply reading-content math formatting to MCQ stem + options."""
    if not isinstance(item, dict):
        return item
    stem_task = enforce_math_format(
        str(item.get("q", "")),
        provider=provider,
        allow_second_pass=False,
    )
    raw_options = item.get("options", [])
    option_tasks = []
    if isinstance(raw_options, list):
        option_tasks = [
            enforce_math_format(str(opt), provider=provider, allow_second_pass=False)
            for opt in raw_options
        ]
    if option_tasks:
        results = await asyncio.gather(stem_task, *option_tasks)
        stem = results[0]
        options = [str(v) for v in results[1:]]
    else:
        stem = await stem_task
        options = []
    return {
        **item,
        "q": stem,
        "options": options if options else ["A", "B", "C", "D"],
    }


def sanitize_question_payload(question: dict) -> dict:
    """Normalize prompt/options for KaTeX rendering in all test UI surfaces."""
    if not isinstance(question, dict):
        return question
    raw_options = question.get("options", [])
    options = []
    if isinstance(raw_options, list):
        options = [format_math_for_display(str(o)) for o in raw_options]
    return {
        **question,
        "prompt": format_math_for_display(str(question.get("prompt", ""))),
        "options": options,
    }
