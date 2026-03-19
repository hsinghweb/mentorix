"""
Learning API: content delivery, test generation, task completion, weekly cycle, dashboard.

This module provides the student-facing learning endpoints that drive the core
weekly cycle after onboarding is complete.
"""
from __future__ import annotations

import json
import logging
import math
import random
import re
import asyncio
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_provider import get_llm_provider
from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger
from app.core.settings import settings
from app.core.timeline import (
    TIMELINE_TZ,
    build_week_timeline_item,
    canonical_today,
    estimate_completion_date,
    format_week_label,
    scheduled_completion_date,
    week_bounds_from_plan,
)
from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name
from app.mcp.client import execute_mcp
from app.mcp.contracts import MCPRequest
from app.memory.cache import redis_client
from app.memory.database import get_db
from app.agents.decision_logger import log_agent_decision
from app.services.agent_dispatch import (
    dispatch_assessment,
    dispatch_reflection,
    dispatch_interventions,
    record_timeline_event,
    record_timeline_reflection,
)
from app.models.entities import (
    AgentDecision,
    AssessmentResult,
    ChapterProgression,
    EmbeddingChunk,
    LearnerProfile,
    LearnerProfileSnapshot,
    RevisionQueueItem,
    SubsectionProgression,
    Task,
    TaskAttempt,
    WeeklyForecast,
    WeeklyPlan,
    WeeklyPlanVersion,
)
router = APIRouter(prefix="/learning", tags=["learning"])
logger = get_domain_logger(__name__, DOMAIN_COMPLIANCE)

COMPLETION_THRESHOLD = 0.60  # 60%
MAX_CHAPTER_ATTEMPTS = 2
TIMELINE_MIN_WEEKS = 14
TIMELINE_MAX_WEEKS = 28
CONTENT_PROMPT_VERSION = "v2"
TEST_PROMPT_VERSION = "v2"


from app.services.shared_helpers import generate_text_with_mcp as _generate_text_with_mcp  # noqa: E402



# â”€â”€ Pydantic models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Pydantic models extracted to learning/schemas.py
from app.api.learning.schemas import (  # noqa: E402
    CompleteReadingRequest,
    CompleteReadingResponse,
    ContentRequest,
    ContentResponse,
    DashboardResponse,
    ExplainQuestionRequest,
    ExplainQuestionResponse,
    GenerateTestResponse,
    SourceChapterResponse,
    SourceSectionResponse,
    SubsectionContentRequest,
    SubmitTestRequest,
    SubmitTestResponse,
    TestAnswer,
    TestQuestion,
    WeekCompleteResponse,
)


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _chapter_info(chapter_number: int) -> dict:
    """Return syllabus chapter dict for *chapter_number*, or a stub if not found."""
    for ch in SYLLABUS_CHAPTERS:
        if ch["number"] == chapter_number:
            return ch
    return {"number": chapter_number, "title": f"Chapter {chapter_number}", "subtopics": []}


def _mastery_band(score: float) -> str:
    """Map a 0–1 mastery score to a categorical band (mastered/proficient/developing/beginner)."""
    if score >= 0.80:
        return "mastered"
    if score >= 0.60:
        return "proficient"
    if score >= 0.40:
        return "developing"
    return "beginner"


def _tone_for_ability(ability: float) -> dict:
    """Derive tone/pace/depth/examples config from learner ability (0–1)."""
    if ability < 0.4:
        return {"tone": "simple_supportive", "pace": "slow", "depth": "foundational", "examples": 3}
    if ability < 0.7:
        return {"tone": "clear_structured", "pace": "balanced", "depth": "standard", "examples": 2}
    return {"tone": "concise_challenging", "pace": "fast", "depth": "advanced", "examples": 1}


def _bucket(value: float, scale: int = 10) -> int:
    """Clamp *value* (0–1) to an integer bucket [0, *scale*] for cache keying."""
    return max(0, min(scale, int(round(float(value or 0.0) * scale))))


def _profile_snapshot_key(profile: LearnerProfile, chapter_key: str) -> str:
    """Build a compact snapshot key from cognitive depth + chapter mastery for content cache."""
    cog = _bucket(profile.cognitive_depth or 0.5)
    mastery = _bucket((profile.concept_mastery or {}).get(chapter_key, 0.5))
    return f"c{cog}m{mastery}"


def _section_content_cache_key(section_id: str, tone: str, profile_snapshot: str) -> str:
    """Build a stable content-cache key for a section. Tone/snapshot are accepted for API compat but ignored."""
    _ = tone
    _ = profile_snapshot
    # Stable key so generated section content is reused across subsequent requests.
    return f"{section_id}::pv={CONTENT_PROMPT_VERSION}::stable"


def _chapter_test_cache_key(chapter_base: str, difficulty: str, profile_snapshot: str) -> str:
    """Build a stable cache key for chapter-final tests. Difficulty/snapshot accepted for compat."""
    _ = difficulty
    _ = profile_snapshot
    # Stable key so chapter-final tests are reused unless regenerate=true.
    return f"{chapter_base}::pv={TEST_PROMPT_VERSION}::stable"


def _estimate_read_seconds(content: str, ability: float = 0.5) -> int:
    """
    Estimate minimum reading time from content length.
    Rule: estimate by words / human reading speed, then clamp to configured bounds.
    Default bounds: 1 to 5 minutes.
    """
    min_seconds = max(30, int(getattr(settings, "reading_min_seconds", 60) or 60))
    max_seconds = max(min_seconds, int(getattr(settings, "reading_max_seconds", 300) or 300))
    wpm = max(80.0, float(getattr(settings, "reading_estimate_wpm", 150) or 150))
    words = len(re.findall(r"\b\w+\b", str(content or "")))
    if words <= 0:
        return min_seconds
    _ = ability  # kept in signature for compatibility with existing call sites
    estimated = int(math.ceil((words / wpm) * 60.0))
    return max(min_seconds, min(max_seconds, estimated))


def _clamp_read_seconds(value: int | float | None) -> int:
    """Clamp a raw reading-time value to the configured [min, max] seconds range."""
    min_seconds = max(30, int(getattr(settings, "reading_min_seconds", 60) or 60))
    max_seconds = max(min_seconds, int(getattr(settings, "reading_max_seconds", 300) or 300))
    try:
        raw = int(value or 0)
    except Exception:
        raw = min_seconds
    return max(min_seconds, min(max_seconds, raw))


def _profile_onboarding_date(profile: LearnerProfile):
    """Return the learner's onboarding date, falling back to today if unset."""
    return profile.onboarding_date or canonical_today()


def _chapter_is_completed(status: str | None) -> bool:
    """Check whether a chapter status string indicates completion."""
    return str(status or "").startswith("completed")


def _extract_week_start_overrides(plan_payload: dict | None) -> dict:
    """Extract the `week_start_overrides` dict from a plan payload, or return empty dict."""
    if not isinstance(plan_payload, dict):
        return {}
    overrides = plan_payload.get("week_start_overrides")
    return overrides if isinstance(overrides, dict) else {}


def _chapter_number_from_label(chapter_label: str | None) -> int | None:
    """Extract the integer chapter number from a label like 'Chapter 5', or None."""
    match = re.search(r"(\d+)", str(chapter_label or ""))
    if not match:
        return None
    return int(match.group(1))


def _remaining_chapter_numbers(progressions: list[ChapterProgression]) -> list[int]:
    """Return sorted list of chapter numbers that have not yet been completed."""
    completed = {
        _chapter_number_from_label(p.chapter)
        for p in progressions
        if _chapter_is_completed(p.status)
    }
    return [
        int(ch["number"])
        for ch in SYLLABUS_CHAPTERS
        if int(ch["number"]) not in completed
    ]


def _build_replanned_weeks(*, current_week: int, total_weeks: int, remaining_chapters: list[int]) -> list[dict]:
    """Build a list of week dicts for the replanned schedule from *current_week* onward."""
    weeks: list[dict] = []
    for offset, week_number in enumerate(range(1, max(1, int(total_weeks)) + 1), start=0):
        if week_number < current_week:
            continue
        chapter_index = week_number - current_week
        if chapter_index < len(remaining_chapters):
            chapter_number = remaining_chapters[chapter_index]
            chapter_info = _chapter_info(chapter_number)
            weeks.append(
                {
                    "week": week_number,
                    "chapter": chapter_display_name(chapter_number),
                    "focus": chapter_info["title"],
                }
            )
        else:
            weeks.append(
                {
                    "week": week_number,
                    "chapter": "Revision",
                    "focus": "mixed revision and weak-topic reinforcement",
                }
            )
    return weeks


def _merge_replanned_future(
    existing_weeks: list[dict],
    *,
    current_week: int,
    total_weeks: int,
    remaining_chapters: list[int],
) -> list[dict]:
    """Preserve past weeks from *existing_weeks* and rebuild future from *remaining_chapters*."""
    preserved = [
        {"week": int(entry.get("week")), "chapter": entry.get("chapter"), "focus": entry.get("focus")}
        for entry in existing_weeks
        if isinstance(entry.get("week"), int) and int(entry.get("week")) < current_week
    ]
    future = _build_replanned_weeks(
        current_week=current_week,
        total_weeks=total_weeks,
        remaining_chapters=remaining_chapters,
    )
    return preserved + future


def _build_week_tasks_for_chapter(*, learner_id: UUID, week_number: int, chapter_number: int) -> list[Task]:
    chapter_key = chapter_display_name(chapter_number)
    chapter_info = _chapter_info(chapter_number)
    subtopics = chapter_info.get("subtopics", [])
    tasks: list[Task] = []
    sort = 0
    for subtopic in subtopics:
        sort += 1
        tasks.append(
            Task(
                learner_id=learner_id,
                week_number=week_number,
                chapter=chapter_key,
                task_type="read",
                title=f"Read: {subtopic['id']} {subtopic['title']}",
                sort_order=sort,
                status="pending",
                is_locked=False,
                proof_policy={"type": "reading_time", "min_seconds": 120, "section_id": subtopic["id"]},
            )
        )
        sort += 1
        tasks.append(
            Task(
                learner_id=learner_id,
                week_number=week_number,
                chapter=chapter_key,
                task_type="test",
                title=f"Test: {subtopic['id']} {subtopic['title']}",
                sort_order=sort,
                status="pending",
                is_locked=False,
                proof_policy={"type": "section_test", "threshold": COMPLETION_THRESHOLD, "section_id": subtopic["id"]},
            )
        )
    sort += 1
    tasks.append(
        Task(
            learner_id=learner_id,
            week_number=week_number,
            chapter=chapter_key,
            task_type="test",
            title=f"Chapter Test: {chapter_info['title']}",
            sort_order=sort,
            status="pending",
            is_locked=False,
            proof_policy={"type": "test_score", "threshold": COMPLETION_THRESHOLD, "chapter_level": True},
        )
    )
    return tasks


async def _apply_dynamic_reading_requirement(
    db: AsyncSession,
    learner_id: UUID,
    task_id: UUID | None,
    required_seconds: int,
) -> None:
    if not task_id:
        return
    task = (await db.execute(
        select(Task).where(Task.id == task_id, Task.learner_id == learner_id, Task.task_type == "read")
    )).scalar_one_or_none()
    if not task:
        return
    required_seconds = _clamp_read_seconds(required_seconds)
    policy = dict(task.proof_policy or {})
    policy["min_seconds"] = int(required_seconds)
    # Keep a denormalized minutes value for backward compatibility in older consumers.
    policy["min_reading_minutes"] = max(1, int(math.ceil(required_seconds / 60.0)))
    task.proof_policy = policy
    await db.flush()


def _normalized_question_text(text: str) -> str:
    """Normalize question text for de-dup checks."""
    txt = re.sub(r"\\\(|\\\)|\\\[|\\\]", " ", str(text or ""))
    txt = re.sub(r"[^a-zA-Z0-9]+", " ", txt).strip().lower()
    return re.sub(r"\s+", " ", txt)


def _looks_like_math_fragment(fragment: str) -> bool:
    s = str(fragment or "").strip()
    if not s:
        return False
    if any(ch in s for ch in ["\\", "^", "_", "=", "+", "-", "*", "/", "Ã—", "Ã·", "<", ">"]):
        return True
    if re.fullmatch(r"[a-zA-Z]\d*", s):
        return True
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return True
    if re.fullmatch(r"[a-zA-Z0-9]+\s*(?:[+\-*/=]\s*[a-zA-Z0-9]+)+", s):
        return True
    return False


def _normalize_generated_math_markdown(text: str) -> str:
    """
    Normalize weak math formatting from LLM output for better frontend rendering.
    Example: "( a )" -> "\\(a\\)", "( 1 = 10 - 3 \\times 3 )" -> "\\(1 = 10 - 3 \\times 3\\)".
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
            # Keep existing LaTeX math blocks untouched to avoid delimiter corruption.
            parts.append(chunk)
            continue
        normalized = re.sub(r"\(\s*([^()\n]{1,120})\s*\)", repl, chunk)
        normalized = re.sub(r"\(\s+", "(", normalized)
        normalized = re.sub(r"\s+\)", ")", normalized)
        parts.append(normalized)
    return "".join(parts)


def _repair_broken_latex_delimiters(text: str) -> str:
    """
    Repair common malformed inline delimiters seen in model output:
    - \\( ... \\\\) -> \\( ... \\)
    - \\sqrt{2}\\\\) -> \\(\\sqrt{2}\\)
    - Unbalanced \\( without closing \\) on a line -> append closing \\)
    """
    raw = str(text or "")
    if not raw:
        return raw

    fixed = raw
    fixed = fixed.replace("\\\\(", "\\(").replace("\\\\)", "\\)")
    fixed = fixed.replace("\\\\[", "\\[").replace("\\\\]", "\\]")

    # Broken inline closer inside an inline block.
    fixed = re.sub(r"\\\((.*?)\\\\\)", r"\\(\1\\)", fixed, flags=re.DOTALL)

    # Bare latex fragment ending with broken closer: \sqrt{2}\\) -> \(\sqrt{2}\)
    def _wrap_bare_fragment(m: re.Match) -> str:
        prefix = m.group(1)
        body = (m.group(2) or "").replace("\\\\)", "")
        return prefix + "\\(" + body + "\\)"

    fixed = re.sub(
        r"(^|[\s,;:([{\-])((?:\\[A-Za-z]+(?:\{[^{}]*\}|[A-Za-z0-9._^+\-])*)+)\\\\\)",
        _wrap_bare_fragment,
        fixed,
    )

    # Line-level balancing for unmatched inline openers.
    balanced: list[str] = []
    for line in fixed.splitlines():
        open_count = line.count(r"\(")
        close_count = line.count(r"\)")
        if open_count > close_count:
            line = line + (r"\)" * (open_count - close_count))
        balanced.append(line)
    return "\n".join(balanced)


def _split_math_blocks(text: str) -> list[tuple[bool, str]]:
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


def _repair_unwrapped_math_fragments(text: str) -> str:
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
            r"(?<!\\\()(?<![A-Za-z0-9_])([A-Za-z0-9_]+\s*/\s*[A-Za-z0-9_]+)(?![A-Za-z0-9_])(?!\\\))",
            wrap_fraction,
            repaired,
        )

        def wrap_expr(m: re.Match) -> str:
            expr = m.group(0).strip()
            if expr.startswith("\\(") and expr.endswith("\\)"):
                return expr
            return f"\\({expr}\\)"
        repaired = re.sub(
            r"(?<!\\\()(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*\s*(?:=|\+|-|\*|/|\^|Ã—|Ã·|<|>)\s*[A-Za-z0-9_\\][A-Za-z0-9_\\\s+\-*/^Ã—Ã·<>{}]*)",
            wrap_expr,
            repaired,
        )
        repaired = re.sub(
            r"(?<!\\\()(?<![A-Za-z0-9_])([A-Za-z]\s+divides\s+[A-Za-z0-9_\\^{}]+)",
            wrap_expr,
            repaired,
            flags=re.IGNORECASE,
        )

        out.append(repaired)
    return "".join(out)


def _count_unwrapped_math_like(text: str) -> int:
    count = 0
    for is_math, chunk in _split_math_blocks(text):
        if is_math:
            continue
        count += len(re.findall(r"\(\s*[a-zA-Z0-9_\\^{}=+\-*/Ã—Ã·<>\s]{1,80}\s*\)", chunk))
        count += len(re.findall(r"(?<!\\\()([A-Za-z0-9_]+\s*/\s*[A-Za-z0-9_]+)(?!\\\))", chunk))
        count += len(re.findall(r"(?<!\\\()([A-Za-z]\s+divides\s+[A-Za-z0-9_\\^{}]+)", chunk, flags=re.IGNORECASE))
        count += len(re.findall(r"(?<!\\\()([A-Za-z][A-Za-z0-9_]*\s*(?:=|\+|-|\*|/|\^|Ã—|Ã·)\s*[A-Za-z0-9_\\][A-Za-z0-9_\\\s+\-*/^Ã—Ã·{}]*)", chunk))
    return count


async def _enforce_math_format(text: str, provider=None, allow_second_pass: bool = True) -> str:
    prefixed = _repair_broken_latex_delimiters(text)
    repaired = _repair_unwrapped_math_fragments(_normalize_generated_math_markdown(prefixed))
    unresolved = _count_unwrapped_math_like(repaired)
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
            fixed = _repair_unwrapped_math_fragments(
                _normalize_generated_math_markdown(_repair_broken_latex_delimiters(llm_text.strip()))
            )
            unresolved_fixed = _count_unwrapped_math_like(fixed)
            logger.info(
                "event=math_format_second_pass unresolved_before=%s unresolved_after=%s",
                unresolved,
                unresolved_fixed,
            )
            return fixed if unresolved_fixed <= unresolved else repaired
    except Exception as exc:
        logger.warning("Math format second pass failed: %s", exc)
    return repaired


def _format_math_for_display(text: str) -> str:
    """Deterministic pass for cached/review/fallback text shown in UI."""
    prefixed = _repair_broken_latex_delimiters(str(text or ""))
    return _repair_unwrapped_math_fragments(_normalize_generated_math_markdown(prefixed))


async def _format_mcq_item_math(item: dict, provider=None) -> dict:
    """Apply reading-content math formatting to MCQ stem + options."""
    if not isinstance(item, dict):
        return item
    stem_task = _enforce_math_format(
        str(item.get("q", "")),
        provider=provider,
        allow_second_pass=False,
    )
    raw_options = item.get("options", [])
    option_tasks = []
    if isinstance(raw_options, list):
        option_tasks = [
            _enforce_math_format(str(opt), provider=provider, allow_second_pass=False)
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


def _sanitize_question_payload(question: dict) -> dict:
    """Normalize prompt/options for KaTeX rendering in all test UI surfaces."""
    if not isinstance(question, dict):
        return question
    raw_options = question.get("options", [])
    options = []
    if isinstance(raw_options, list):
        options = [_format_math_for_display(str(o)) for o in raw_options]
    return {
        **question,
        "prompt": _format_math_for_display(str(question.get("prompt", ""))),
        "options": options,
    }


def _is_near_duplicate(candidate: str, existing: list[str], threshold: float = 0.9) -> bool:
    return any(SequenceMatcher(a=candidate, b=prev).ratio() >= threshold for prev in existing)


_QUESTION_STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "into", "this", "which", "about", "using", "what",
    "when", "where", "your", "their", "there", "these", "those", "chapter", "class", "cbse", "math",
    "mathematics", "choose", "following", "statement", "correct", "option", "best", "most",
}


def _keyword_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z]{3,}", str(text or "").lower())
    return {t for t in tokens if t not in _QUESTION_STOPWORDS}


def _question_looks_relevant(prompt: str, chapter_name: str, topic_titles: list[str]) -> bool:
    q_tokens = _keyword_tokens(prompt)
    if not q_tokens:
        return False
    source_tokens = _keyword_tokens(chapter_name)
    for topic in topic_titles or []:
        source_tokens |= _keyword_tokens(topic)
    # Require at least one meaningful topic/chapter keyword overlap.
    if q_tokens & source_tokens:
        return True
    # Math-heavy prompts can still be relevant even without direct keyword overlap.
    return bool(re.search(r"[=+\-*/^]|\\frac|\\sqrt|ratio|equation|factor|multiple|polynomial", prompt, flags=re.IGNORECASE))


def _has_valid_options(options: list) -> bool:
    if not isinstance(options, list) or len(options) < 4:
        return False
    normalized = [re.sub(r"\s+", " ", str(opt or "").strip().lower()) for opt in options]
    normalized = [opt for opt in normalized if opt]
    return len(normalized) >= 4 and len(set(normalized[:4])) == 4


def _dedupe_generated_questions(
    raw_items: list[dict],
    target_count: int,
    *,
    chapter_name: str = "",
    topic_titles: list[str] | None = None,
) -> tuple[list[dict], int]:
    """Drop exact/normalized/near-duplicate question stems from LLM output."""
    out: list[dict] = []
    seen_norm: list[str] = []
    duplicates_removed = 0
    for item in raw_items:
        if not isinstance(item, dict):
            duplicates_removed += 1
            continue
        q = str(item.get("q", "")).strip()
        options = item.get("options", [])
        if not q or not _has_valid_options(options):
            duplicates_removed += 1
            continue
        if chapter_name and not _question_looks_relevant(q, chapter_name, topic_titles or []):
            duplicates_removed += 1
            continue
        norm = _normalized_question_text(q)
        if not norm:
            duplicates_removed += 1
            continue
        if norm in seen_norm or _is_near_duplicate(norm, seen_norm):
            duplicates_removed += 1
            continue
        seen_norm.append(norm)
        out.append(item)
        if len(out) >= target_count:
            break
    return out, duplicates_removed


def _reading_content_is_high_quality(content: str, chapter_name: str, topic_titles: list[str] | None = None) -> bool:
    text = str(content or "").strip()
    if not text:
        return False
    words = re.findall(r"\b\w+\b", text)
    if len(words) < 45:
        return False
    low_quality_markers = [
        "correct definition",
        "incorrect variant",
        "select the statement that best matches",
        "which concept is central",
    ]
    lowered = text.lower()
    if any(marker in lowered for marker in low_quality_markers):
        return False
    topic_titles = topic_titles or []
    if not _keyword_tokens(" ".join(topic_titles) + " " + chapter_name):
        return True
    return bool(_keyword_tokens(text) & _keyword_tokens(" ".join(topic_titles) + " " + chapter_name))


def _question_set_is_high_quality(
    questions: list[TestQuestion],
    *,
    chapter_name: str,
    topic_titles: list[str] | None = None,
    min_count: int,
) -> bool:
    if len(questions) < min_count:
        return False
    prompts = [str(q.prompt or "") for q in questions]
    normalized = [_normalized_question_text(p) for p in prompts]
    if len(set(normalized)) < len(normalized):
        return False
    lowered = " ".join(prompts).lower()
    if "correct definition" in lowered or "incorrect variant" in lowered:
        return False
    relevant_count = 0
    for q in questions:
        if _question_looks_relevant(str(q.prompt or ""), chapter_name, topic_titles or []):
            relevant_count += 1
    return relevant_count >= max(min_count - 1, int(0.8 * len(questions)))


async def _pending_subsection_tasks_for_final_test(
    db: AsyncSession,
    learner_id: UUID,
    chapter_number: int,
    chapter: str,
) -> tuple[int, list[str]]:
    """
    Return pending subsection task count/list for the chapter's final test week.
    If no chapter-level task exists, treat as unblocked for ad-hoc generation.
    """
    final_task = (await db.execute(
        select(Task).where(
            Task.learner_id == learner_id,
            Task.chapter == chapter,
            Task.task_type == "test",
            Task.proof_policy["chapter_level"].as_boolean() == True,
        ).order_by(Task.week_number.asc(), Task.sort_order.asc(), Task.created_at.asc())
    )).scalars().first()
    if final_task is None:
        # Fallback gate when no final-task row exists: enforce subsection progression completeness.
        await _ensure_subsection_rows(db, learner_id, chapter_number)
        rows = (await db.execute(
            select(SubsectionProgression.section_id, SubsectionProgression.section_title, SubsectionProgression.status)
            .where(
                SubsectionProgression.learner_id == learner_id,
                SubsectionProgression.chapter == chapter,
            )
        )).all()
        pending = [
            f"{sid} {title}"
            for sid, title, status in rows
            if str(status) != "completed"
        ]
        return len(pending), pending

    week_number = int(final_task.week_number)
    pending_rows = (await db.execute(
        select(Task.title).where(
            Task.learner_id == learner_id,
            Task.chapter == chapter,
            Task.week_number == week_number,
            Task.task_type.in_(["read", "test"]),
            Task.proof_policy["section_id"].is_not(None),
            Task.status != "completed",
        ).order_by(Task.sort_order.asc(), Task.created_at.asc())
    )).scalars().all()
    pending_tasks = [str(t) for t in pending_rows if isinstance(t, str)]
    return len(pending_tasks), pending_tasks


async def _get_profile(db: AsyncSession, learner_id: UUID) -> LearnerProfile:
    profile = (await db.execute(
        select(LearnerProfile).where(LearnerProfile.learner_id == learner_id)
    )).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found. Complete onboarding first.")
    return profile


async def _get_plan(db: AsyncSession, learner_id: UUID) -> WeeklyPlan | None:
    return (await db.execute(
        select(WeeklyPlan)
        .where(WeeklyPlan.learner_id == learner_id)
        .order_by(desc(WeeklyPlan.generated_at))
    )).scalars().first()


async def _retrieve_chapter_chunks(db: AsyncSession, chapter_number: int, top_k: int = 5, section_id: str | None = None) -> list[str]:
    """Retrieve embedded chunks for a specific chapter (or section) from pgvector."""
    try:
        stmt = (
            select(EmbeddingChunk)
            .where(EmbeddingChunk.chapter_number == chapter_number)
        )
        if section_id is not None:
            stmt = stmt.where(EmbeddingChunk.section_id == section_id)
        stmt = stmt.limit(top_k * 3)
        rows = (await db.execute(stmt)).scalars().all()
        if not rows:
            # Fallback: get any chunks for this chapter
            stmt = select(EmbeddingChunk).where(
                EmbeddingChunk.chapter_number == chapter_number
            ).limit(top_k)
            rows = (await db.execute(stmt)).scalars().all()
        return [r.content for r in rows[:top_k]] if rows else []
    except Exception as exc:
        logger.warning("Chunk retrieval failed for chapter %s section %s: %s", chapter_number, section_id, exc)
        return []


async def _get_canonical_section_context(
    db: AsyncSession,
    chapter_number: int,
    section_id: str,
    section_title: str,
    *,
    top_k: int = 8,
) -> str:
    """
    Deterministic subsection source fetch:
    1) canonical_sections Mongo cache
    2) DB chunks filtered by exact chapter+section_id, then persisted in canonical_sections
    """
    from app.memory.content_cache import get_canonical_section, save_canonical_section

    cached = get_canonical_section(chapter_number, section_id)
    if cached and isinstance(cached.get("source_text"), str) and cached.get("source_text"):
        return str(cached["source_text"])

    stmt = (
        select(EmbeddingChunk.content)
        .where(
            EmbeddingChunk.chapter_number == chapter_number,
            EmbeddingChunk.section_id == section_id,
        )
        .limit(top_k * 2)
    )
    rows = (await db.execute(stmt)).scalars().all()
    text_parts = [str(r).strip() for r in rows if isinstance(r, str) and r.strip()]
    if text_parts:
        source_text = "\n\n".join(text_parts[:top_k])
        save_canonical_section(chapter_number, section_id, section_title, source_text)
        return source_text
    return ""


# â”€â”€ In-memory test store (for simplicity; keyed by test_id) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_test_store: dict[str, dict] = {}


# â”€â”€ ENDPOINTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# 1. Get reading content for a chapter
@router.post("/content", response_model=ContentResponse)
async def get_reading_content(payload: ContentRequest, db: AsyncSession = Depends(get_db)):
    """Generate reading content for a chapter, adapted to student's ability."""
    from app.memory.content_cache import get_cached_content, save_content_cache

    profile = await _get_profile(db, payload.learner_id)
    ch_info = _chapter_info(payload.chapter_number)
    chapter_name = ch_info["title"]
    subtopics = [s["title"] for s in ch_info.get("subtopics", []) if "Summary" not in s["title"] and "Introduction" not in s["title"]]

    # Determine ability and tone
    ability = profile.cognitive_depth or 0.5
    mastery = (profile.concept_mastery or {}).get(chapter_display_name(payload.chapter_number), 0.5)
    combined_ability = (ability + mastery) / 2
    tone_config = _tone_for_ability(combined_ability)
    cache_section_id = "__chapter__"
    if payload.regenerate:
        logger.info(
            "event=regenerate_triggered kind=chapter_content learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            cache_section_id,
        )

    if not payload.regenerate:
        cached = get_cached_content(str(payload.learner_id), payload.chapter_number, cache_section_id)
        if cached and cached.get("content"):
            cached_content = str(cached.get("content") or "")
            if not _reading_content_is_high_quality(cached_content, chapter_name, subtopics):
                logger.warning(
                    "event=cache_quality_reject kind=chapter_content learner_id=%s chapter=%s",
                    payload.learner_id,
                    payload.chapter_number,
                )
            else:
                required_read_seconds = _clamp_read_seconds(
                    cached.get("required_read_seconds")
                    or _estimate_read_seconds(cached_content, combined_ability)
                )
                await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
                await db.commit()
                logger.info(
                    "event=cache_hit kind=chapter_content learner_id=%s chapter=%s section=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    cache_section_id,
                )
                return ContentResponse(
                    chapter_number=payload.chapter_number,
                    chapter_title=chapter_name,
                    content=_format_math_for_display(cached_content),
                    source="cached",
                    tone=str(cached.get("tone") or tone_config["tone"]),
                    examples_count=tone_config["examples"],
                    required_read_seconds=required_read_seconds,
                )
        logger.info(
            "event=cache_miss kind=chapter_content learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            cache_section_id,
        )

    # Retrieve NCERT chunks
    chunks = await _retrieve_chapter_chunks(db, payload.chapter_number, top_k=6)
    context = "\n\n".join(chunks[:5]) if chunks else ""

    if not context:
        # No embeddings available for this chapter â€” provide a structured fallback
        content = (
            f"# {chapter_name}\n\n"
            f"This chapter covers the following topics:\n\n"
            + "\n".join(f"- {s}" for s in subtopics) + "\n\n"
            f"**Note:** Detailed NCERT content for this chapter is not yet embedded. "
            f"Please refer to the NCERT textbook for Chapter {payload.chapter_number}."
        )
        required_read_seconds = _estimate_read_seconds(content, combined_ability)
        await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
        await db.commit()
        return ContentResponse(
            chapter_number=payload.chapter_number,
            chapter_title=chapter_name,
            content=_format_math_for_display(content),
            source="fallback",
            tone=tone_config["tone"],
            examples_count=0,
            required_read_seconds=required_read_seconds,
        )

    # Generate with LLM
    subtopic_list = "\n".join(f"- {s}" for s in subtopics)
    prompt = (
        f"You are a friendly math tutor teaching a Class 10 CBSE student.\n"
        f"Generate a clear, well-structured reading lesson for:\n\n"
        f"Chapter: {chapter_name}\n"
        f"Subtopics to cover:\n{subtopic_list}\n\n"
        f"Tone: {tone_config['tone']}\n"
        f"Pace: {tone_config['pace']}\n"
        f"Depth: {tone_config['depth']}\n"
        f"Include {tone_config['examples']} solved examples.\n\n"
        f"Use ONLY the following NCERT curriculum content as your source. "
        f"Do not add any information outside of this:\n\n"
        f"{context}\n\n"
        f"Formatting rules (strict):\n"
        f"- Use clean Markdown headings and bullets.\n"
        f"- Write ALL math as LaTeX inline math using \\\\( ... \\\\).\n"
        f"- NEVER write math as plain parenthesized text like ( a ) or ( p/q ).\n"
        f"- Good: \\\\(a\\\\), \\\\((p/q)\\\\), \\\\(17 = 5 \\\\times 3 + 2\\\\).\n"
        f"- Keep notation consistent and student-readable.\n"
        f"Keep the language appropriate for a 15-16 year old student.\n"
    )
    strict_prompt = (
        prompt
        + "\nQuality constraints:\n"
          "- Do not use generic placeholders.\n"
          "- Explain concepts logically with step-by-step reasoning.\n"
          "- Include at least one concrete solved example and one short practice check.\n"
          "- Ensure each paragraph teaches a distinct point.\n"
    )

    try:
        provider = get_llm_provider(role="content_generator")
        for attempt, candidate_prompt in enumerate([prompt, strict_prompt], start=1):
            llm_text, _ = await _generate_text_with_mcp(candidate_prompt, role="content_generator")
            if not llm_text or len(llm_text.strip()) <= 50:
                continue
            generated_content = await _enforce_math_format(llm_text.strip(), provider=provider)
            if not _reading_content_is_high_quality(generated_content, chapter_name, subtopics):
                logger.warning(
                    "event=reading_quality_reject kind=chapter_content learner_id=%s chapter=%s attempt=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    attempt,
                )
                continue
            required_read_seconds = _estimate_read_seconds(generated_content, combined_ability)
            save_content_cache(
                str(payload.learner_id),
                payload.chapter_number,
                cache_section_id,
                chapter_name,
                generated_content,
                tone_config["tone"],
                required_read_seconds=required_read_seconds,
            )
            await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
            await db.commit()
            return ContentResponse(
                chapter_number=payload.chapter_number,
                chapter_title=chapter_name,
                content=_format_math_for_display(generated_content),
                source="llm",
                tone=tone_config["tone"],
                examples_count=tone_config["examples"],
                required_read_seconds=required_read_seconds,
            )
    except Exception as exc:
        logger.warning("LLM content generation failed: %s", exc)

    # Fallback: use RAG chunks directly
    content = (
        f"# {chapter_name}\n\n"
        f"## Key Concepts\n\n{context}\n\n"
        f"*Content sourced from NCERT textbook.*"
    )
    required_read_seconds = _estimate_read_seconds(content, combined_ability)
    await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
    await db.commit()
    return ContentResponse(
        chapter_number=payload.chapter_number,
        chapter_title=chapter_name,
        content=_format_math_for_display(content),
        source="rag_only",
        tone=tone_config["tone"],
        examples_count=0,
        required_read_seconds=required_read_seconds,
    )


# 2. Generate a chapter test
@router.post("/test/generate", response_model=GenerateTestResponse)
async def generate_chapter_test(payload: ContentRequest, db: AsyncSession = Depends(get_db)):
    """Generate an MCQ test for a chapter using NCERT embeddings + LLM."""
    from app.memory.content_cache import get_cached_test, save_test_cache

    profile = await _get_profile(db, payload.learner_id)
    plan = await _get_plan(db, payload.learner_id)
    week_number = plan.current_week if plan else 1
    ch_info = _chapter_info(payload.chapter_number)
    chapter_name = ch_info["title"]
    chapter_key = chapter_display_name(payload.chapter_number)
    combined_ability = (
        float(profile.cognitive_depth or 0.5)
        + float((profile.concept_mastery or {}).get(chapter_key, 0.5))
    ) / 2.0
    difficulty = "foundational" if combined_ability < 0.4 else ("standard" if combined_ability < 0.7 else "advanced")
    profile_snapshot = _profile_snapshot_key(profile, chapter_key)
    cache_section_id = _chapter_test_cache_key("__chapter__", difficulty, profile_snapshot)
    if payload.regenerate:
        logger.info(
            "event=regenerate_triggered kind=chapter_test learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            cache_section_id,
        )

    if not payload.regenerate:
        cached = get_cached_test(str(payload.learner_id), payload.chapter_number, cache_section_id)
        if cached:
            cached_questions = [
                _sanitize_question_payload(q)
                for q in (cached.get("questions") or [])
                if isinstance(q, dict)
            ]
            cached_as_models = [TestQuestion(**q) for q in cached_questions]
            topic_titles = [s.get("title", "") for s in ch_info.get("subtopics", []) if isinstance(s, dict)]
            if not _question_set_is_high_quality(
                cached_as_models,
                chapter_name=chapter_name,
                topic_titles=topic_titles,
                min_count=8,
            ):
                logger.warning(
                    "event=cache_quality_reject kind=chapter_test learner_id=%s chapter=%s",
                    payload.learner_id,
                    payload.chapter_number,
                )
            else:
                logger.info(
                    "event=cache_hit kind=chapter_test learner_id=%s chapter=%s section=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    cache_section_id,
                )
                _test_store[cached["test_id"]] = {
                    "learner_id": str(payload.learner_id),
                    "chapter_number": payload.chapter_number,
                    "chapter": chapter_key,
                    "chapter_level": True,
                    "section_id": None,
                    "questions": cached_questions,
                    "answer_key": cached["answer_key"],
                    "created_at": cached.get("created_at", datetime.now(timezone.utc).isoformat()),
                }
                return GenerateTestResponse(
                    learner_id=str(payload.learner_id),
                    week_number=week_number,
                    chapter=chapter_key,
                    test_id=cached["test_id"],
                    questions=cached_as_models,
                    time_limit_minutes=20,
                    source="cached",
                )
        logger.info(
            "event=cache_miss kind=chapter_test learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            cache_section_id,
        )

    # Pre-generation gate: do not spend tokens for final test when subsection tasks are pending.
    pending_count, pending_tasks = await _pending_subsection_tasks_for_final_test(
        db,
        payload.learner_id,
        payload.chapter_number,
        chapter_key,
    )
    if pending_count > 0:
        logger.warning(
            "event=final_test_generation_blocked reason=pending_subsection_tasks learner=%s chapter=%s pending_count=%s pending_tasks=%s",
            payload.learner_id,
            chapter_key,
            pending_count,
            pending_tasks[:5],
        )
        return GenerateTestResponse(
            learner_id=str(payload.learner_id),
            week_number=week_number,
            chapter=chapter_key,
            source="blocked",
            blocked=True,
            reason_code="pending_subsection_tasks",
            pending_tasks=pending_tasks[:8],
        )

    # Retrieve chunks for question generation
    chunks = await _retrieve_chapter_chunks(db, payload.chapter_number, top_k=5)
    context = "\n\n".join(chunks[:4]) if chunks else ""

    test_id = str(uuid4())[:12]
    questions: list[TestQuestion] = []
    answer_key: dict[str, int] = {}

    if context:
        prompt = (
            f"You are a math test generator for Class 10 CBSE.\n"
            f"Generate exactly 10 multiple-choice questions for:\n"
            f"Chapter: {chapter_name}\n\n"
            f"Use ONLY the following NCERT content:\n{context}\n\n"
            f"Rules:\n"
            f"- All 10 question stems MUST be unique.\n"
            f"- Do NOT repeat or lightly paraphrase the same stem.\n"
            f"- Cover different ideas/skills from the chapter.\n"
            f"Format: Return a JSON array of 10 objects, each with:\n"
            f'  {{"q": "question text", "options": ["A", "B", "C", "D"], "correct": 0}}\n'
            f"where correct is 0-3 (index of correct option).\n"
            f"Use \\\\( \\\\) for inline LaTeX math.\n"
            f"Return ONLY the JSON array, no other text.\n"
        )
        strict_prompt = (
            prompt
            + "\nQuality constraints:\n"
              "- Questions must be solvable and logically correct.\n"
              "- Avoid generic placeholders.\n"
              "- Ensure each question tests a distinct concept or skill.\n"
              "- Keep options plausible but only one clearly correct.\n"
        )

        try:
            provider = get_llm_provider(role="content_generator")
            topic_titles = [s.get("title", "") for s in ch_info.get("subtopics", []) if isinstance(s, dict)]
            for attempt, candidate_prompt in enumerate([prompt, strict_prompt], start=1):
                questions = []
                answer_key = {}
                llm_text, _ = await _generate_text_with_mcp(candidate_prompt, role="content_generator")
                if not llm_text:
                    continue
                text = llm_text.strip()
                start = text.find("[")
                end = text.rfind("]") + 1
                if start < 0 or end <= start:
                    continue
                parsed = json.loads(text[start:end])
                formatted_parsed: list[dict] = []
                for item in parsed:
                    if isinstance(item, dict):
                        formatted_parsed.append(await _format_mcq_item_math(item, provider=provider))
                deduped, duplicates_removed = _dedupe_generated_questions(
                    formatted_parsed,
                    target_count=10,
                    chapter_name=chapter_name,
                    topic_titles=topic_titles,
                )
                for i, item in enumerate(deduped):
                    qid = f"t_{test_id}_q{i+1}"
                    options = item.get("options", ["A", "B", "C", "D"])
                    correct = int(item.get("correct", 0))
                    if correct < 0 or correct >= len(options):
                        correct = 0
                    questions.append(TestQuestion(
                        question_id=qid,
                        prompt=item.get("q", f"Question {i+1}"),
                        options=options,
                        chapter_number=payload.chapter_number,
                    ))
                    answer_key[qid] = correct
                if _question_set_is_high_quality(
                    questions,
                    chapter_name=chapter_name,
                    topic_titles=topic_titles,
                    min_count=8,
                ):
                    logger.info(
                        "event=test_generation_diagnostics kind=chapter requested=%s unique_count=%s duplicates_removed=%s chapter=%s attempt=%s",
                        10,
                        len(questions),
                        duplicates_removed,
                        payload.chapter_number,
                        attempt,
                    )
                    break
                logger.warning(
                    "event=test_quality_reject kind=chapter learner_id=%s chapter=%s attempt=%s unique_count=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    attempt,
                    len(questions),
                )
        except Exception as exc:
            logger.warning("LLM test generation failed: %s", exc)

    # Refill missing unique slots with deterministic fallback stems.
    subtopics = [s["title"] for s in ch_info.get("subtopics", [])
                 if "Summary" not in s["title"] and "Introduction" not in s["title"]]
    fallback_templates = [
        "[Q{n}] Which statement is true for '{topic}'?",
        "[Q{n}] Solve and choose the best answer related to '{topic}'.",
        "[Q{n}] Which method should be applied first in a '{topic}' problem?",
        "[Q{n}] Identify the incorrect claim about '{topic}'.",
    ]
    while len(questions) < 10:
        i = len(questions)
        qid = f"t_{test_id}_q{i+1}"
        topic = subtopics[i % len(subtopics)] if subtopics else chapter_name
        prompt_text = fallback_templates[i % len(fallback_templates)].format(n=i + 1, topic=topic)
        if _is_near_duplicate(_normalized_question_text(prompt_text), [_normalized_question_text(q.prompt) for q in questions]):
            prompt_text = f"[Q{i+1}] Apply a core concept from '{topic}' to select the correct option."
        questions.append(TestQuestion(
            question_id=qid,
            prompt=prompt_text,
            options=[
                f"A correct concept/application of {topic}",
                f"A partially correct but flawed statement on {topic}",
                f"A common misconception about {topic}",
                f"An unrelated statement not valid for {topic}",
            ],
            chapter_number=payload.chapter_number,
        ))
        answer_key[qid] = 0

    # Safety fallback if generation returned very low quality.
    if len(questions) < 5:
        questions = []
        answer_key = {}
        for i in range(10):
            qid = f"t_{test_id}_q{i+1}"
            topic = subtopics[i % len(subtopics)] if subtopics else chapter_name
            fallback_stem = fallback_templates[i % len(fallback_templates)].format(n=i + 1, topic=topic)
            questions.append(TestQuestion(
                question_id=qid,
                prompt=fallback_stem,
                options=[
                    f"A correct concept/application of {topic}",
                    f"A partially correct but flawed statement on {topic}",
                    f"A common misconception about {topic}",
                    f"An unrelated statement not valid for {topic}",
                ],
                chapter_number=payload.chapter_number,
            ))
            answer_key[qid] = 0

    # Store test for scoring
    questions_dicts = [_sanitize_question_payload(q.model_dump()) for q in questions]
    _test_store[test_id] = {
        "learner_id": str(payload.learner_id),
        "chapter_number": payload.chapter_number,
        "chapter": chapter_key,
        "chapter_level": True,
        "section_id": None,
        "questions": questions_dicts,
        "answer_key": answer_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    response_questions = [TestQuestion(**q) for q in questions_dicts]
    save_test_cache(
        str(payload.learner_id),
        payload.chapter_number,
        cache_section_id,
        chapter_name,
        test_id,
        questions_dicts,
        answer_key,
    )

    return GenerateTestResponse(
        learner_id=str(payload.learner_id),
        week_number=week_number,
        chapter=chapter_key,
        test_id=test_id,
        questions=response_questions,
        time_limit_minutes=20,
        source="llm",
    )


# 3. Submit test answers
@router.post("/test/submit", response_model=SubmitTestResponse)
async def submit_chapter_test(payload: SubmitTestRequest, db: AsyncSession = Depends(get_db)):
    """Score section/chapter tests, enforce subsection-first gating, and update progression."""
    test_data = _test_store.get(payload.test_id)
    if not test_data:
        raise HTTPException(status_code=404, detail="Test not found or expired.")

    answer_key = test_data["answer_key"]
    chapter = test_data["chapter"]
    section_id = test_data.get("section_id")
    chapter_level = bool(test_data.get("chapter_level", False))
    chapter_number = int(test_data.get("chapter_number") or 1)

    question_results: list[dict] = []
    answer_map = {a.question_id: a.selected_index for a in payload.answers}

    correct = 0
    total = len(answer_key)
    questions = test_data.get("questions", [])
    question_meta = {
        str(q.get("question_id")): q
        for q in questions
        if isinstance(q, dict) and q.get("question_id")
    }
    for ans in payload.answers:
        expected = answer_key.get(ans.question_id)
        if expected is not None and ans.selected_index == expected:
            correct += 1
    for qid, expected in answer_key.items():
        selected = answer_map.get(qid)
        q = question_meta.get(qid, {})
        options = [_format_math_for_display(str(o)) for o in (q.get("options", []) or [])]
        question_results.append(
            {
                "question_id": qid,
                "prompt": _format_math_for_display(str(q.get("prompt", ""))),
                "options": options,
                "selected_index": selected,
                "correct_index": expected,
                "is_correct": selected == expected if selected is not None else False,
            }
        )

    score = correct / max(total, 1)
    passed = score >= COMPLETION_THRESHOLD
    selected_task_id = payload.task_id
    attempt_number = 1
    max_attempts = MAX_CHAPTER_ATTEMPTS
    accepted_attempt = passed

    if section_id and not chapter_level:
        chapter_key = chapter_display_name(chapter_number)
        await _ensure_subsection_rows(db, payload.learner_id, chapter_number)
        sp = (await db.execute(
            select(SubsectionProgression).where(
                SubsectionProgression.learner_id == payload.learner_id,
                SubsectionProgression.chapter == chapter_key,
                SubsectionProgression.section_id == section_id,
            )
        )).scalar_one_or_none()
        if not sp:
            raise HTTPException(status_code=404, detail="Subsection progression not found.")

        sp.attempt_count += 1
        sp.last_score = score
        if score > sp.best_score:
            sp.best_score = score

        if passed:
            sp.status = "completed" if sp.reading_completed else "test_done"
            decision = "section_completed"
            message = (
                f"Section {section_id} passed: {correct}/{total} ({score*100:.0f}%). "
                f"{'Subsection complete.' if sp.reading_completed else 'Complete reading to finish this subsection.'}"
            )
            if not selected_task_id:
                selected_task_id = (await db.execute(
                    select(Task.id).where(
                        Task.learner_id == payload.learner_id,
                        Task.chapter == chapter,
                        Task.task_type == "test",
                        Task.status != "completed",
                        Task.proof_policy["section_id"].as_string() == section_id,
                    ).order_by(Task.sort_order.asc(), Task.created_at.asc())
                )).scalar_one_or_none()
            if selected_task_id:
                task = (await db.execute(select(Task).where(Task.id == selected_task_id))).scalar_one_or_none()
                if task and task.status != "completed":
                    task.status = "completed"
                    task.completed_at = datetime.now(timezone.utc)
        else:
            sp.status = "reading_done" if sp.reading_completed else "in_progress"
            decision = "section_retry"
            message = (
                f"Section {section_id}: {correct}/{total} ({score*100:.0f}%). "
                f"Retry this subsection test to reach {COMPLETION_THRESHOLD*100:.0f}%."
            )
        attempt_number = sp.attempt_count
        max_attempts = 999
    else:
        final_task_week = None
        if selected_task_id:
            selected_task = (await db.execute(
                select(Task).where(
                    Task.id == selected_task_id,
                    Task.learner_id == payload.learner_id,
                )
            )).scalar_one_or_none()
            if selected_task:
                final_task_week = int(selected_task.week_number)
        if final_task_week is None:
            final_task = (await db.execute(
                select(Task).where(
                    Task.learner_id == payload.learner_id,
                    Task.chapter == chapter,
                    Task.task_type == "test",
                    Task.proof_policy["chapter_level"].as_boolean() == True,
                ).order_by(Task.week_number.asc(), Task.sort_order.asc(), Task.created_at.asc())
            )).scalars().first()
            if final_task is not None:
                final_task_week = int(final_task.week_number)
                if selected_task_id is None:
                    selected_task_id = final_task.id
        if final_task_week is None:
            plan = await _get_plan(db, payload.learner_id)
            final_task_week = int(plan.current_week if plan else 1)

        pending_section_tasks = (await db.execute(
            select(func.count(Task.id)).where(
                Task.learner_id == payload.learner_id,
                Task.chapter == chapter,
                Task.week_number == final_task_week,
                Task.task_type.in_(["read", "test"]),
                Task.proof_policy["section_id"].is_not(None),
                Task.status != "completed",
            )
        )).scalar_one()
        if int(pending_section_tasks or 0) > 0:
            pending_rows = (await db.execute(
                select(Task.title).where(
                    Task.learner_id == payload.learner_id,
                    Task.chapter == chapter,
                    Task.week_number == final_task_week,
                    Task.task_type.in_(["read", "test"]),
                    Task.proof_policy["section_id"].is_not(None),
                    Task.status != "completed",
                ).order_by(Task.sort_order.asc(), Task.created_at.asc()).limit(5)
            )).scalars().all()
            logger.warning(
                "event=final_test_submit_failed reason=pending_subsection_tasks learner=%s chapter=%s week=%s pending_tasks=%s test_id=%s",
                payload.learner_id,
                chapter,
                final_task_week,
                pending_rows,
                payload.test_id,
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Complete all subsection read/test tasks before attempting final chapter test. "
                    f"Pending: {', '.join(pending_rows) if pending_rows else 'subsection tasks'}"
                ),
            )

        cp = (await db.execute(
            select(ChapterProgression).where(
                ChapterProgression.learner_id == payload.learner_id,
                ChapterProgression.chapter == chapter,
            )
        )).scalar_one_or_none()
        if not cp:
            cp = ChapterProgression(
                learner_id=payload.learner_id,
                chapter=chapter,
                attempt_count=0,
                best_score=0.0,
                last_score=0.0,
                status="not_started",
            )
            db.add(cp)
            await db.flush()

        cp.attempt_count += 1
        cp.last_score = score
        if score > cp.best_score:
            cp.best_score = score
        already_completed = cp.status.startswith("completed")

        if not already_completed:
            if passed:
                cp.status = "completed_first_attempt" if cp.attempt_count == 1 else "completed"
                decision = "chapter_completed"
                message = f"Congratulations! You scored {correct}/{total} ({score*100:.0f}%). Chapter completed!"
            elif cp.attempt_count >= MAX_CHAPTER_ATTEMPTS:
                cp.status = "completed"
                cp.revision_queued = True
                decision = "move_on_revision"
                message = (
                    f"You scored {correct}/{total} ({score*100:.0f}%). "
                    f"After {cp.attempt_count} attempts, we are moving on and queuing revision."
                )
                existing_rev = (await db.execute(
                    select(RevisionQueueItem).where(
                        RevisionQueueItem.learner_id == payload.learner_id,
                        RevisionQueueItem.chapter == chapter,
                    )
                )).scalar_one_or_none()
                if not existing_rev:
                    db.add(RevisionQueueItem(
                        learner_id=payload.learner_id,
                        chapter=chapter,
                        status="pending",
                        priority=2,
                        reason=f"Failed to reach {COMPLETION_THRESHOLD*100:.0f}% after {MAX_CHAPTER_ATTEMPTS} attempts",
                    ))
            else:
                cp.status = "in_progress"
                remaining = MAX_CHAPTER_ATTEMPTS - cp.attempt_count
                decision = "retry"
                message = (
                    f"You scored {correct}/{total} ({score*100:.0f}%). "
                    f"You need {COMPLETION_THRESHOLD*100:.0f}% to pass. {remaining} attempt(s) left."
                )
        else:
            decision = "practice_retake"
            message = f"Practice retake: {correct}/{total} ({score*100:.0f}%). Best {cp.best_score*100:.0f}%."

        attempt_number = cp.attempt_count
        accepted_attempt = passed or cp.attempt_count >= MAX_CHAPTER_ATTEMPTS
        if not selected_task_id:
            selected_task_id = (await db.execute(
                select(Task.id).where(
                    Task.learner_id == payload.learner_id,
                    Task.chapter == chapter,
                    Task.task_type == "test",
                    Task.proof_policy["chapter_level"].as_boolean() == True,
                ).order_by(Task.sort_order.asc(), Task.created_at.asc())
            )).scalar_one_or_none()
        if not already_completed and accepted_attempt and selected_task_id:
            task = (await db.execute(select(Task).where(Task.id == selected_task_id))).scalar_one_or_none()
            if task and task.status != "completed":
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)

    db.add(AssessmentResult(
        learner_id=payload.learner_id,
        concept=f"{chapter}:{section_id}" if section_id and not chapter_level else chapter,
        score=score,
        error_type="none" if passed else "below_threshold",
    ))

    profile = await _get_profile(db, payload.learner_id)
    mastery = dict(profile.concept_mastery or {})
    mastery[chapter] = max(mastery.get(chapter, 0.0), score)
    profile.concept_mastery = mastery

    if not selected_task_id:
        selected_task_id = (await db.execute(
            select(Task.id).where(
                Task.learner_id == payload.learner_id,
                Task.chapter == chapter,
                Task.task_type == "test",
            ).order_by(desc(Task.created_at))
        )).scalar_one_or_none()
    if not selected_task_id:
        logger.info(
            "event=ad_hoc_test_submit learner=%s chapter=%s test_id=%s section_id=%s chapter_level=%s",
            payload.learner_id,
            chapter,
            payload.test_id,
            section_id,
            chapter_level,
        )
    else:
        db.add(TaskAttempt(
            task_id=selected_task_id,
            learner_id=payload.learner_id,
            proof_payload={
                "score": score,
                "correct": correct,
                "total": total,
                "test_id": payload.test_id,
                "attempt": attempt_number,
                "section_id": section_id,
                "chapter_level": chapter_level,
            },
            accepted=accepted_attempt,
            reason=decision,
        ))
    try:
        await log_agent_decision(
            db=db,
            learner_id=payload.learner_id,
            agent_name="evaluation",
            decision_type=decision,
            chapter=chapter,
            section_id=section_id,
            input_snapshot={
                "test_id": payload.test_id,
                "answers_count": len(payload.answers),
                "chapter_level": chapter_level,
            },
            output_payload={
                "score": score,
                "correct": correct,
                "total": total,
                "passed": passed,
                "attempt_number": attempt_number,
            },
            confidence=round(score, 4),
            reasoning=message,
        )
    except Exception:
        pass

    await db.commit()

    try:
        await redis_client.delete(f"learning:dashboard:{payload.learner_id}")
    except Exception:
        pass

    # ── Agent dispatch (fire-and-forget) ─────────────────────────────
    # Wire agents into the main learning flow per audit §3/§13.
    learner_str = str(payload.learner_id)
    try:
        await dispatch_assessment(
            learner_id=learner_str,
            chapter=chapter,
            section_id=section_id,
            score=score,
            correct=correct,
            total=total,
            question_results=question_results,
        )
        await dispatch_reflection(
            learner_id=learner_str,
            chapter=chapter,
            score=score,
            passed=passed,
            attempt_number=attempt_number,
            decision=decision,
        )
        # Record to LearnerMemoryTimeline
        event_type = "win" if passed else "mistake"
        record_timeline_event(
            learner_id=learner_str,
            event_type=event_type,
            content=f"{chapter} {'section ' + section_id if section_id and not chapter_level else 'final'}: {correct}/{total} ({score*100:.0f}%)",
            metadata={"chapter": chapter, "section_id": section_id, "score": score, "attempt": attempt_number},
        )
        # On chapter completion, add reflection and run interventions
        if chapter_level and (passed or attempt_number >= MAX_CHAPTER_ATTEMPTS):
            record_timeline_reflection(
                learner_id=learner_str,
                trigger="final_test_completed",
                summary=f"{chapter} completed: {score*100:.0f}% on attempt {attempt_number}. Decision: {decision}",
            )
            await dispatch_interventions(learner_id=learner_str, db_session=db)
    except Exception:
        pass  # agent dispatch must never break the main flow

    return SubmitTestResponse(
        learner_id=str(payload.learner_id),
        chapter=chapter,
        score=score,
        correct=correct,
        total=total,
        passed=passed,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        decision=decision,
        message=message,
        question_results=question_results,
    )


@router.post("/test/question/explain", response_model=ExplainQuestionResponse)
async def explain_test_question(payload: ExplainQuestionRequest, db: AsyncSession = Depends(get_db)):
    """Return grounded explanation for a single test question (cache-first)."""
    from app.memory.content_cache import get_cached_explanation, save_explanation_cache

    test_data = _test_store.get(payload.test_id)
    if not test_data:
        raise HTTPException(status_code=404, detail="Test not found or expired.")

    chapter_number = int(test_data.get("chapter_number") or 1)
    chapter = str(test_data.get("chapter") or chapter_display_name(chapter_number))
    section_id = test_data.get("section_id")

    if not payload.regenerate:
        cached = get_cached_explanation(str(payload.learner_id), payload.test_id, payload.question_id)
        if cached and cached.get("explanation"):
            logger.info(
                "event=cache_hit kind=question_explain learner_id=%s test_id=%s question_id=%s",
                payload.learner_id,
                payload.test_id,
                payload.question_id,
            )
            await log_agent_decision(
                db=db,
                learner_id=payload.learner_id,
                agent_name="assessment",
                decision_type="question_explained",
                chapter=chapter,
                section_id=section_id,
                input_snapshot={"mode": "cached", "question_id": payload.question_id},
                output_payload={"source": "cached"},
            )
            await db.commit()
            return ExplainQuestionResponse(
                learner_id=str(payload.learner_id),
                test_id=payload.test_id,
                question_id=payload.question_id,
                chapter_number=chapter_number,
                chapter=chapter,
                section_id=section_id,
                explanation=_format_math_for_display(str(cached["explanation"])),
                source="cached",
            )
        logger.info(
            "event=cache_miss kind=question_explain learner_id=%s test_id=%s question_id=%s",
            payload.learner_id,
            payload.test_id,
            payload.question_id,
        )

    question_items = test_data.get("questions", [])
    question = None
    for q in question_items:
        if isinstance(q, dict) and q.get("question_id") == payload.question_id:
            question = q
            break
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in test.")
    logger.info(
        "event=explain_requested learner_id=%s test_id=%s question_id=%s regenerate=%s",
        payload.learner_id,
        payload.test_id,
        payload.question_id,
        payload.regenerate,
    )

    answer_key = test_data.get("answer_key", {})
    correct_index = answer_key.get(payload.question_id)
    selected_index = payload.selected_index
    if selected_index is None:
        # Best-effort fallback for callers that omit selected option.
        selected_index = -1

    ch_info = _chapter_info(chapter_number)
    section_title = section_id or ch_info["title"]
    if section_id:
        for s in ch_info.get("subtopics", []):
            if s.get("id") == section_id:
                section_title = s.get("title", section_id)
                break

    context = ""
    if section_id:
        context = await _get_canonical_section_context(
            db,
            chapter_number,
            str(section_id),
            str(section_title),
            top_k=6,
        )
    if not context:
        chunks = await _retrieve_chapter_chunks(db, chapter_number, top_k=5)
        context = "\n\n".join(chunks[:4]) if chunks else ""

    formatted_question = _format_math_for_display(str(question.get("prompt", "")))
    options = [_format_math_for_display(str(o)) for o in (question.get("options", []) or [])]
    prompt = (
        "You are a Class 10 CBSE math tutor.\n"
        "Explain the question outcome in a concise and clear way.\n"
        "Use ONLY the NCERT source context below.\n\n"
        f"Chapter: {chapter_number}\n"
        f"Section: {section_id or 'chapter-level final'}\n"
        f"Question: {formatted_question}\n"
        f"Options: {json.dumps(options, ensure_ascii=True)}\n"
        f"Student selected index: {selected_index}\n"
        f"Correct index: {correct_index}\n\n"
        f"NCERT source context:\n{context}\n\n"
        "Output format (Markdown):\n"
        "1) Correct answer\n"
        "2) Why this is correct\n"
        "3) Why student's choice is wrong (if wrong)\n"
        "4) One quick remediation tip\n"
    )

    explanation = ""
    source = "fallback"
    if context:
        try:
            llm_text, _ = await _generate_text_with_mcp(prompt, role="content_generator")
            if llm_text and llm_text.strip():
                provider = get_llm_provider(role="content_generator")
                explanation = _format_math_for_display(
                    await _enforce_math_format(llm_text.strip(), provider=provider)
                )
                source = "llm"
        except Exception as exc:
            logger.warning("Question explain generation failed: %s", exc)

    if not explanation:
        correct_text = (
            options[int(correct_index)]
            if isinstance(correct_index, int) and 0 <= int(correct_index) < len(options)
            else "See solution key"
        )
        chosen_text = (
            options[int(selected_index)]
            if isinstance(selected_index, int) and 0 <= int(selected_index) < len(options)
            else "No option selected"
        )
        explanation = (
            f"Correct answer: **{_format_math_for_display(str(correct_text))}**\n\n"
            f"Your choice: **{_format_math_for_display(str(chosen_text))}**\n\n"
            "Review the related concept from the section and retry a similar problem."
        )

    explanation = _format_math_for_display(explanation)

    save_explanation_cache(
        str(payload.learner_id),
        payload.test_id,
        payload.question_id,
        {
            "chapter_number": chapter_number,
            "chapter": chapter,
            "section_id": section_id,
            "explanation": explanation,
        },
    )
    await log_agent_decision(
        db=db,
        learner_id=payload.learner_id,
        agent_name="assessment",
        decision_type="question_explained",
        chapter=chapter,
        section_id=section_id,
        input_snapshot={"mode": "generated" if source == "llm" else "fallback", "question_id": payload.question_id},
        output_payload={"source": source},
    )
    await db.commit()

    return ExplainQuestionResponse(
        learner_id=str(payload.learner_id),
        test_id=payload.test_id,
        question_id=payload.question_id,
        chapter_number=chapter_number,
        chapter=chapter,
        section_id=section_id,
        explanation=explanation,
        source=source,
    )
# 4. Complete reading task
@router.post("/reading/complete", response_model=CompleteReadingResponse)
async def complete_reading(payload: CompleteReadingRequest, db: AsyncSession = Depends(get_db)):
    """Mark a reading task as complete if minimum time threshold is met."""
    task = (await db.execute(
        select(Task).where(Task.id == payload.task_id, Task.learner_id == payload.learner_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.task_type != "read":
        raise HTTPException(status_code=400, detail="This endpoint is for reading tasks only.")
    if task.status == "completed":
        return CompleteReadingResponse(task_id=str(task.id), accepted=True, reason="Already completed.")

    policy = dict(task.proof_policy or {})
    required_seconds = int(policy.get("min_seconds") or 0)
    if required_seconds <= 0 and policy.get("min_reading_minutes") is not None:
        try:
            required_seconds = int(float(policy.get("min_reading_minutes")) * 60)
        except Exception:
            required_seconds = 0
    if required_seconds <= 0:
        required_seconds = 60  # default minimum: 1 minute

    if payload.time_spent_seconds < required_seconds:
        return CompleteReadingResponse(
            task_id=str(task.id),
            accepted=False,
            reason=f"Please spend at least {max(1, int(math.ceil(required_seconds / 60.0)))} minutes reading before completing.",
        )

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    section_id = (task.proof_policy or {}).get("section_id")
    if section_id:
        match = (task.chapter or "").split(" ")
        chapter_number = int(match[-1]) if match and match[-1].isdigit() else None
        if chapter_number:
            await _ensure_subsection_rows(db, payload.learner_id, chapter_number)
            sp = (await db.execute(
                select(SubsectionProgression).where(
                    SubsectionProgression.learner_id == payload.learner_id,
                    SubsectionProgression.chapter == task.chapter,
                    SubsectionProgression.section_id == section_id,
                )
            )).scalar_one_or_none()
            if sp:
                sp.reading_completed = True
                if sp.status in ("not_started", "in_progress"):
                    sp.status = "reading_done"
                if sp.status == "test_done":
                    sp.status = "completed"

    db.add(TaskAttempt(
        task_id=task.id,
        learner_id=payload.learner_id,
        proof_payload={"time_spent_seconds": payload.time_spent_seconds},
        accepted=True,
        reason="reading_time_met",
    ))
    await db.commit()

    try:
        await redis_client.delete(f"learning:dashboard:{payload.learner_id}")
    except Exception:
        pass
    return CompleteReadingResponse(task_id=str(task.id), accepted=True, reason="Reading completed! âœ…")


# â”€â”€ SUBSECTION ENDPOINTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _ensure_subsection_rows(db: AsyncSession, learner_id: UUID, chapter_number: int):
    """Lazily create SubsectionProgression rows for all subsections of a chapter."""
    ch_info = _chapter_info(chapter_number)
    chapter_key = chapter_display_name(chapter_number)
    subtopics = list(ch_info.get("subtopics", []))

    existing = (await db.execute(
        select(SubsectionProgression.section_id).where(
            SubsectionProgression.learner_id == learner_id,
            SubsectionProgression.chapter == chapter_key,
        )
    )).scalars().all()
    existing_ids = set(existing)

    for s in subtopics:
        if s["id"] not in existing_ids:
            db.add(SubsectionProgression(
                learner_id=learner_id,
                chapter=chapter_key,
                section_id=s["id"],
                section_title=s["title"],
                status="not_started",
            ))
    if subtopics and len(existing_ids) < len(subtopics):
        await db.flush()


@router.get("/chapter/{chapter_number}/sections/{learner_id}")
async def get_chapter_sections(chapter_number: int, learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return per-subsection progress for a chapter."""
    await _ensure_subsection_rows(db, learner_id, chapter_number)
    chapter_key = chapter_display_name(chapter_number)
    ch_info = _chapter_info(chapter_number)

    rows = (await db.execute(
        select(SubsectionProgression).where(
            SubsectionProgression.learner_id == learner_id,
            SubsectionProgression.chapter == chapter_key,
        )
    )).scalars().all()

    sections = []
    for r in rows:
        sections.append({
            "section_id": r.section_id,
            "section_title": r.section_title,
            "status": r.status,
            "best_score": round(r.best_score, 2),
            "last_score": round(r.last_score, 2),
            "attempt_count": r.attempt_count,
            "reading_completed": r.reading_completed,
            "mastery_band": _mastery_band(r.best_score),
        })

    return {
        "chapter_number": chapter_number,
        "chapter_key": chapter_key,
        "chapter_title": ch_info["title"],
        "sections": sections,
    }


@router.get("/source-section/{chapter_number}/{section_id}", response_model=SourceSectionResponse)
async def get_source_section_content(
    chapter_number: int,
    section_id: str,
    learner_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return the original NCERT-grounded subsection content used for adaptive generation."""
    ch_info = _chapter_info(chapter_number)
    section_title = section_id
    for item in ch_info.get("subtopics", []):
        if item["id"] == section_id:
            section_title = item["title"]
            break

    stmt = (
        select(EmbeddingChunk.content)
        .where(
            EmbeddingChunk.chapter_number == chapter_number,
            EmbeddingChunk.section_id == section_id,
        )
        .order_by(EmbeddingChunk.chunk_index.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    text_parts = [str(row).strip() for row in rows if isinstance(row, str) and str(row).strip()]
    if not text_parts:
        raise HTTPException(status_code=404, detail="NCERT source content not found for this section.")

    source_content = "\n\n".join(text_parts)
    if learner_id is not None:
        await log_agent_decision(
            db=db,
            learner_id=learner_id,
            agent_name="content",
            decision_type="source_section_requested",
            chapter=chapter_display_name(chapter_number),
            section_id=section_id,
            input_snapshot={"chapter_number": chapter_number, "section_id": section_id},
            output_payload={"chunk_count": len(text_parts), "section_title": section_title},
        )
        await db.commit()

    return SourceSectionResponse(
        chapter_number=chapter_number,
        chapter_title=ch_info["title"],
        section_id=section_id,
        section_title=section_title,
        source_content=_format_math_for_display(source_content),
        chunk_count=len(text_parts),
    )


@router.get("/source-chapter/{chapter_number}", response_model=SourceChapterResponse)
async def get_source_chapter_content(
    chapter_number: int,
    learner_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return the original chapter-grounded NCERT content used for chapter-level reading."""
    ch_info = _chapter_info(chapter_number)
    stmt = (
        select(EmbeddingChunk.content)
        .where(EmbeddingChunk.chapter_number == chapter_number)
        .order_by(EmbeddingChunk.chunk_index.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    text_parts = [str(row).strip() for row in rows if isinstance(row, str) and str(row).strip()]
    if not text_parts:
        raise HTTPException(status_code=404, detail="NCERT source content not found for this chapter.")

    source_content = "\n\n".join(text_parts)
    if learner_id is not None:
        await log_agent_decision(
            db=db,
            learner_id=learner_id,
            agent_name="content",
            decision_type="source_chapter_requested",
            chapter=chapter_display_name(chapter_number),
            input_snapshot={"chapter_number": chapter_number},
            output_payload={"chunk_count": len(text_parts), "chapter_title": ch_info["title"]},
        )
        await db.commit()

    return SourceChapterResponse(
        chapter_number=chapter_number,
        chapter_title=ch_info["title"],
        source_content=_format_math_for_display(source_content),
        chunk_count=len(text_parts),
    )


@router.post("/content/section")
async def get_section_content(payload: SubsectionContentRequest, db: AsyncSession = Depends(get_db)):
    """Generate reading content for a specific subsection, grounded on section-level chunk."""
    from app.memory.content_cache import get_cached_content, save_content_cache

    profile = await _get_profile(db, payload.learner_id)
    ch_info = _chapter_info(payload.chapter_number)
    chapter_name = ch_info["title"]

    # Find section title
    section_title = payload.section_id
    for s in ch_info.get("subtopics", []):
        if s["id"] == payload.section_id:
            section_title = s["title"]
            break

    # Determine ability and tone (used for adaptive prompt + profile-aware cache key).
    ability = profile.cognitive_depth or 0.5
    chapter_key = chapter_display_name(payload.chapter_number)
    mastery = (profile.concept_mastery or {}).get(chapter_key, 0.5)
    combined_ability = (ability + mastery) / 2
    tone_config = _tone_for_ability(combined_ability)
    profile_snapshot = _profile_snapshot_key(profile, chapter_key)
    cache_section_id = _section_content_cache_key(payload.section_id, tone_config["tone"], profile_snapshot)

    # Check cache first (unless regenerate requested)
    if payload.regenerate:
        logger.info(
            "event=regenerate_triggered kind=section_content learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            cache_section_id,
        )
    if not payload.regenerate:
        cached = get_cached_content(str(payload.learner_id), payload.chapter_number, cache_section_id)
        if cached:
            cached_content = str(cached.get("content") or "")
            if not _reading_content_is_high_quality(cached_content, chapter_name, [section_title]):
                logger.warning(
                    "event=cache_quality_reject kind=section_content learner_id=%s chapter=%s section=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    payload.section_id,
                )
            else:
                required_read_seconds = _clamp_read_seconds(
                    cached.get("required_read_seconds")
                    or _estimate_read_seconds(str(cached.get("content") or ""), combined_ability)
                )
                logger.info(
                    "event=cache_hit kind=section_content learner_id=%s chapter=%s section=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    cache_section_id,
                )
                logger.info("Serving cached content for %s section %s", payload.chapter_number, payload.section_id)
                # Still mark reading done
                await _ensure_subsection_rows(db, payload.learner_id, payload.chapter_number)
                sp = (await db.execute(
                    select(SubsectionProgression).where(
                        SubsectionProgression.learner_id == payload.learner_id,
                        SubsectionProgression.chapter == chapter_key,
                        SubsectionProgression.section_id == payload.section_id,
                    )
                )).scalar_one_or_none()
                if sp and not sp.reading_completed:
                    sp.reading_completed = True
                    if sp.status == "not_started":
                        sp.status = "reading_done"
                await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
                await log_agent_decision(
                    db=db,
                    learner_id=payload.learner_id,
                    agent_name="content",
                    decision_type="section_content_served",
                    chapter=chapter_key,
                    section_id=payload.section_id,
                    input_snapshot={"mode": "cached", "chapter_number": payload.chapter_number},
                    output_payload={"source": "cached", "tone": cached.get("tone", "normal")},
                )
                await db.commit()
                return {
                    "chapter_number": payload.chapter_number,
                    "section_id": payload.section_id,
                    "section_title": cached.get("section_title", section_title),
                    "content": _format_math_for_display(cached_content),
                    "source": "cached",
                    "tone": cached.get("tone", "normal"),
                    "required_read_seconds": required_read_seconds,
                }
        logger.info(
            "event=cache_miss kind=section_content learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            cache_section_id,
        )

    # Deterministic subsection source fetch from canonical store.
    context = await _get_canonical_section_context(
        db,
        payload.chapter_number,
        payload.section_id,
        section_title,
        top_k=6,
    )

    if not context:
        # Try chapter-level fallback
        chunks = await _retrieve_chapter_chunks(db, payload.chapter_number, top_k=5)
        context = "\n\n".join(chunks[:4]) if chunks else ""

    if not context:
        fallback_content = (
            f"# {section_title}\n\n"
            f"**Note:** NCERT content for section {payload.section_id} is not yet embedded. "
            f"Please refer to the NCERT textbook for Chapter {payload.chapter_number}."
        )
        required_read_seconds = _estimate_read_seconds(fallback_content, combined_ability)
        await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
        await log_agent_decision(
            db=db,
            learner_id=payload.learner_id,
            agent_name="content",
            decision_type="section_content_served",
            chapter=chapter_key,
            section_id=payload.section_id,
            input_snapshot={"mode": "fallback", "chapter_number": payload.chapter_number},
            output_payload={"source": "fallback", "tone": tone_config["tone"]},
        )
        await db.commit()
        return {
            "chapter_number": payload.chapter_number,
            "section_id": payload.section_id,
            "section_title": section_title,
            "content": _format_math_for_display(fallback_content),
            "source": "fallback",
            "tone": tone_config["tone"],
            "required_read_seconds": required_read_seconds,
        }

    prompt = (
        f"You are a friendly math tutor teaching a Class 10 CBSE student.\n"
        f"Generate a clear, well-structured reading lesson for:\n\n"
        f"Chapter: {chapter_name}\n"
        f"Section: {payload.section_id} - {section_title}\n\n"
        f"Tone: {tone_config['tone']}\n"
        f"Pace: {tone_config['pace']}\n"
        f"Depth: {tone_config['depth']}\n"
        f"Include {tone_config['examples']} solved examples.\n\n"
        f"Use ONLY the following NCERT curriculum content as your source. "
        f"Do not add any information outside of this:\n\n"
        f"{context}\n\n"
        f"Formatting rules (strict):\n"
        f"- Use clean Markdown headings and bullets.\n"
        f"- Write ALL math as LaTeX inline math using \\\\( ... \\\\).\n"
        f"- NEVER write math as plain parenthesized text like ( a ) or ( p/q ).\n"
        f"- Good: \\\\(a\\\\), \\\\((p/q)\\\\), \\\\(17 = 5 \\\\times 3 + 2\\\\).\n"
        f"- Keep notation consistent and student-readable.\n"
        f"Keep the language appropriate for a 15-16 year old student.\n"
    )
    strict_prompt = (
        prompt
        + "\nQuality constraints:\n"
          "- Do not use generic template text.\n"
          "- Explain the section with logical progression from concept to example.\n"
          "- Include at least one section-specific solved example.\n"
          "- Avoid repetitive statements.\n"
    )

    try:
        provider = get_llm_provider(role="content_generator")
        for attempt, candidate_prompt in enumerate([prompt, strict_prompt], start=1):
            llm_text, _ = await _generate_text_with_mcp(candidate_prompt, role="content_generator")
            if not llm_text or len(llm_text.strip()) <= 50:
                continue
            generated_content = await _enforce_math_format(llm_text.strip(), provider=provider)
            if not _reading_content_is_high_quality(generated_content, chapter_name, [section_title]):
                logger.warning(
                    "event=reading_quality_reject kind=section_content learner_id=%s chapter=%s section=%s attempt=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    payload.section_id,
                    attempt,
                )
                continue
            # Mark reading done only after quality gate passes.
            await _ensure_subsection_rows(db, payload.learner_id, payload.chapter_number)
            sp = (await db.execute(
                select(SubsectionProgression).where(
                    SubsectionProgression.learner_id == payload.learner_id,
                    SubsectionProgression.chapter == chapter_key,
                    SubsectionProgression.section_id == payload.section_id,
                )
            )).scalar_one_or_none()
            if sp and not sp.reading_completed:
                sp.reading_completed = True
                if sp.status == "not_started":
                    sp.status = "reading_done"
                await db.commit()
            required_read_seconds = _estimate_read_seconds(generated_content, combined_ability)
            # Save to cache
            save_content_cache(
                str(payload.learner_id), payload.chapter_number, cache_section_id,
                section_title, generated_content, tone_config["tone"], required_read_seconds=required_read_seconds,
            )
            await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
            await log_agent_decision(
                db=db,
                learner_id=payload.learner_id,
                agent_name="content",
                decision_type="section_content_served",
                chapter=chapter_key,
                section_id=payload.section_id,
                input_snapshot={"mode": "generated", "chapter_number": payload.chapter_number, "tone": tone_config["tone"]},
                output_payload={"source": "llm", "required_read_seconds": required_read_seconds},
            )
            await db.commit()
            return {
                "chapter_number": payload.chapter_number,
                "section_id": payload.section_id,
                "section_title": section_title,
                "content": _format_math_for_display(generated_content),
                "source": "llm",
                "tone": tone_config["tone"],
                "required_read_seconds": required_read_seconds,
            }
    except Exception as exc:
        logger.warning("LLM section content generation failed: %s", exc)

    rag_content = f"# {section_title}\n\n## Key Concepts\n\n{context}\n\n*Content sourced from NCERT textbook.*"
    required_read_seconds = _estimate_read_seconds(rag_content, combined_ability)
    await _apply_dynamic_reading_requirement(db, payload.learner_id, payload.task_id, required_read_seconds)
    await log_agent_decision(
        db=db,
        learner_id=payload.learner_id,
        agent_name="content",
        decision_type="section_content_served",
        chapter=chapter_key,
        section_id=payload.section_id,
        input_snapshot={"mode": "rag_only", "chapter_number": payload.chapter_number},
        output_payload={"source": "rag_only", "required_read_seconds": required_read_seconds},
    )
    await db.commit()
    return {
        "chapter_number": payload.chapter_number,
        "section_id": payload.section_id,
        "section_title": section_title,
        "content": _format_math_for_display(rag_content),
        "source": "rag_only",
        "tone": tone_config["tone"],
        "required_read_seconds": required_read_seconds,
    }


@router.post("/test/section/generate")
async def generate_section_test(payload: SubsectionContentRequest, db: AsyncSession = Depends(get_db)):
    """Generate MCQ test for a specific subsection."""
    from app.memory.content_cache import get_cached_test, save_test_cache

    ch_info = _chapter_info(payload.chapter_number)
    chapter_name = ch_info["title"]
    chapter_key = chapter_display_name(payload.chapter_number)

    section_title = payload.section_id
    for s in ch_info.get("subtopics", []):
        if s["id"] == payload.section_id:
            section_title = s["title"]
            break

    # Check cache first (unless regenerate requested)
    if payload.regenerate:
        logger.info(
            "event=regenerate_triggered kind=section_test learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            payload.section_id,
        )
    if not payload.regenerate:
        cached = get_cached_test(str(payload.learner_id), payload.chapter_number, payload.section_id)
        if cached:
            cached_questions = [
                _sanitize_question_payload(q)
                for q in (cached.get("questions") or [])
                if isinstance(q, dict)
            ]
            cached_as_models = [TestQuestion(**q) for q in cached_questions]
            if not _question_set_is_high_quality(
                cached_as_models,
                chapter_name=chapter_name,
                topic_titles=[section_title],
                min_count=4,
            ):
                logger.warning(
                    "event=cache_quality_reject kind=section_test learner_id=%s chapter=%s section=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    payload.section_id,
                )
            else:
                logger.info(
                    "event=cache_hit kind=section_test learner_id=%s chapter=%s section=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    payload.section_id,
                )
                logger.info("Serving cached test for %s section %s", payload.chapter_number, payload.section_id)
                # Re-register in _test_store for scoring
                _test_store[cached["test_id"]] = {
                    "learner_id": str(payload.learner_id),
                    "chapter_number": payload.chapter_number,
                    "chapter": chapter_key,
                    "section_id": payload.section_id,
                    "chapter_level": False,
                    "questions": cached_questions,
                    "answer_key": cached["answer_key"],
                    "created_at": cached.get("created_at", datetime.now(timezone.utc).isoformat()),
                }
                await log_agent_decision(
                    db=db,
                    learner_id=payload.learner_id,
                    agent_name="assessment",
                    decision_type="section_test_generated",
                    chapter=chapter_key,
                    section_id=payload.section_id,
                    input_snapshot={"mode": "cached", "chapter_number": payload.chapter_number},
                    output_payload={"source": "cached", "question_count": len(cached_questions)},
                )
                await db.commit()
                return {
                    "learner_id": str(payload.learner_id),
                    "chapter": chapter_key,
                    "section_id": payload.section_id,
                    "section_title": cached.get("section_title", section_title),
                    "test_id": cached["test_id"],
                    "questions": cached_questions,
                    "time_limit_minutes": 10,
                    "source": "cached",
                }
        logger.info(
            "event=cache_miss kind=section_test learner_id=%s chapter=%s section=%s",
            payload.learner_id,
            payload.chapter_number,
            payload.section_id,
        )

    # Deterministic subsection source fetch from canonical store.
    context = await _get_canonical_section_context(
        db,
        payload.chapter_number,
        payload.section_id,
        section_title,
        top_k=6,
    )

    if not context:
        chunks = await _retrieve_chapter_chunks(db, payload.chapter_number, top_k=5)
        context = "\n\n".join(chunks[:4]) if chunks else ""

    test_id = str(uuid4())[:12]
    questions: list[TestQuestion] = []
    answer_key: dict[str, int] = {}

    if context:
        prompt = (
            f"You are a math test generator for Class 10 CBSE.\n"
            f"Generate exactly 5 multiple-choice questions for:\n"
            f"Chapter: {chapter_name}\n"
            f"Section: {payload.section_id} - {section_title}\n\n"
            f"Use ONLY the following NCERT content:\n{context}\n\n"
            f"Rules:\n"
            f"- All 5 question stems MUST be unique.\n"
            f"- Do NOT repeat or lightly paraphrase the same stem.\n"
            f"- Cover distinct points from this section.\n"
            f"Format: Return a JSON array of 5 objects, each with:\n"
            f'  {{"q": "question text", "options": ["A", "B", "C", "D"], "correct": 0}}\n'
            f"where correct is 0-3 (index of correct option).\n"
            f"Use \\\\( \\\\) for inline LaTeX math.\n"
            f"Return ONLY the JSON array, no other text.\n"
        )
        strict_prompt = (
            prompt
            + "\nQuality constraints:\n"
              "- Questions must be directly tied to this section.\n"
              "- Avoid generic placeholders and repeated stems.\n"
              "- Ensure each question tests a different concept from the section.\n"
              "- Options must be meaningful and non-repetitive.\n"
        )

        try:
            provider = get_llm_provider(role="content_generator")
            for attempt, candidate_prompt in enumerate([prompt, strict_prompt], start=1):
                questions = []
                answer_key = {}
                llm_text, _ = await _generate_text_with_mcp(candidate_prompt, role="content_generator")
                if not llm_text:
                    continue
                text = llm_text.strip()
                start = text.find("[")
                end = text.rfind("]") + 1
                if start < 0 or end <= start:
                    continue
                parsed = json.loads(text[start:end])
                formatted_parsed: list[dict] = []
                for item in parsed:
                    if isinstance(item, dict):
                        formatted_parsed.append(await _format_mcq_item_math(item, provider=provider))
                deduped, duplicates_removed = _dedupe_generated_questions(
                    formatted_parsed,
                    target_count=5,
                    chapter_name=chapter_name,
                    topic_titles=[section_title],
                )
                for i, item in enumerate(deduped):
                    qid = f"st_{test_id}_q{i+1}"
                    options = item.get("options", ["A", "B", "C", "D"])
                    correct_idx = int(item.get("correct", 0))
                    if correct_idx < 0 or correct_idx >= len(options):
                        correct_idx = 0
                    questions.append(TestQuestion(
                        question_id=qid,
                        prompt=item.get("q", f"Question {i+1}"),
                        options=options,
                        chapter_number=payload.chapter_number,
                    ))
                    answer_key[qid] = correct_idx
                if _question_set_is_high_quality(
                    questions,
                    chapter_name=chapter_name,
                    topic_titles=[section_title],
                    min_count=4,
                ):
                    logger.info(
                        "event=test_generation_diagnostics kind=section requested=%s unique_count=%s duplicates_removed=%s chapter=%s section=%s attempt=%s",
                        5,
                        len(questions),
                        duplicates_removed,
                        payload.chapter_number,
                        payload.section_id,
                        attempt,
                    )
                    break
                logger.warning(
                    "event=test_quality_reject kind=section learner_id=%s chapter=%s section=%s attempt=%s unique_count=%s",
                    payload.learner_id,
                    payload.chapter_number,
                    payload.section_id,
                    attempt,
                    len(questions),
                )
        except Exception as exc:
            logger.warning("LLM section test generation failed: %s", exc)

    # Refill missing unique slots with deterministic fallback stems.
    section_fallback_templates = [
        "[Q{n}] Which statement is true for section '{topic}'?",
        "[Q{n}] Apply the core rule from '{topic}' to choose the correct option.",
        "[Q{n}] Which step is logically valid in a '{topic}' problem?",
        "[Q{n}] Identify the misconception related to '{topic}'.",
    ]
    while len(questions) < 5:
        i = len(questions)
        qid = f"st_{test_id}_q{i+1}"
        prompt_text = section_fallback_templates[i % len(section_fallback_templates)].format(n=i + 1, topic=section_title)
        if _is_near_duplicate(_normalized_question_text(prompt_text), [_normalized_question_text(q.prompt) for q in questions]):
            prompt_text = f"[Q{i+1}] Select the most accurate application of '{section_title}'."
        questions.append(TestQuestion(
            question_id=qid,
            prompt=prompt_text,
            options=[
                f"A correct concept/application of {section_title}",
                f"A partially correct but flawed statement on {section_title}",
                f"A common misconception about {section_title}",
                f"An unrelated statement not valid for {section_title}",
            ],
            chapter_number=payload.chapter_number,
        ))
        answer_key[qid] = 0

    questions_dicts = [_sanitize_question_payload(q.model_dump()) for q in questions]
    _test_store[test_id] = {
        "learner_id": str(payload.learner_id),
        "chapter_number": payload.chapter_number,
        "chapter": chapter_key,
        "section_id": payload.section_id,
        "chapter_level": False,
        "questions": questions_dicts,
        "answer_key": answer_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_test_cache(
        str(payload.learner_id), payload.chapter_number, payload.section_id,
        section_title, test_id, questions_dicts, answer_key,
    )
    await log_agent_decision(
        db=db,
        learner_id=payload.learner_id,
        agent_name="assessment",
        decision_type="section_test_generated",
        chapter=chapter_key,
        section_id=payload.section_id,
        input_snapshot={"mode": "generated", "chapter_number": payload.chapter_number},
        output_payload={"source": "llm", "question_count": len(questions_dicts)},
    )
    await db.commit()

    return {
        "learner_id": str(payload.learner_id),
        "chapter": chapter_key,
        "section_id": payload.section_id,
        "section_title": section_title,
        "test_id": test_id,
        "questions": questions_dicts,
        "time_limit_minutes": 10,
        "source": "llm",
    }


# 5. Check if week is complete and advance
@router.post("/week/advance", response_model=WeekCompleteResponse)
async def advance_week(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Check if all tasks for current week are done, then create the next committed week."""
    profile = await _get_profile(db, learner_id)
    plan = await _get_plan(db, learner_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found. Complete onboarding first.")

    current_week = plan.current_week
    tasks = (
        await db.execute(
            select(Task).where(
                Task.learner_id == learner_id,
                Task.week_number == current_week,
            )
        )
    ).scalars().all()

    incomplete = [t for t in tasks if t.status != "completed"]
    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"Week {current_week} has {len(incomplete)} incomplete task(s). Complete all tasks first.",
        )

    plan_payload = dict(plan.plan_payload or {})
    raw_weeks = plan_payload.get("rough_plan", []) or plan_payload.get("weeks", [])
    week_chapters = [e.get("chapter", "") for e in raw_weeks if e.get("week") == current_week]

    completed_chapters: list[str] = []
    revision_chapters: list[str] = []
    for chapter_label in week_chapters:
        cp = (
            await db.execute(
                select(ChapterProgression).where(
                    ChapterProgression.learner_id == learner_id,
                    ChapterProgression.chapter == chapter_label,
                )
            )
        ).scalar_one_or_none()
        if not cp:
            continue
        if cp.revision_queued:
            revision_chapters.append(chapter_label)
        if _chapter_is_completed(cp.status):
            completed_chapters.append(chapter_label)

    db.add(
        LearnerProfileSnapshot(
            learner_id=learner_id,
            reason=f"week_{current_week}_complete",
            payload={
                "week": current_week,
                "mastery": dict(profile.concept_mastery or {}),
                "cognitive_depth": profile.cognitive_depth,
            },
        )
    )

    new_week = current_week + 1
    plan.current_week = new_week

    all_progressions = (
        await db.execute(
            select(ChapterProgression).where(ChapterProgression.learner_id == learner_id)
        )
    ).scalars().all()
    remaining_chapter_numbers = _remaining_chapter_numbers(all_progressions)
    remaining_chapters = len(remaining_chapter_numbers)

    selected = int(profile.selected_timeline_weeks or 14)
    prior_forecast = int(profile.current_forecast_weeks or plan.total_weeks or selected)
    if remaining_chapters <= 0:
        plan.total_weeks = current_week
    else:
        workload_floor = current_week + remaining_chapters
        acceleration_credit = max(0, prior_forecast - current_week - remaining_chapters)
        plan.total_weeks = max(new_week, workload_floor - min(acceleration_credit, 1))

    onboarding_date = _profile_onboarding_date(profile)
    week_start_overrides = dict(_extract_week_start_overrides(plan_payload))
    _, current_week_end = week_bounds_from_plan(onboarding_date, current_week, week_start_overrides)
    today = canonical_today()
    early_start_applied = False
    if today <= current_week_end:
        week_start_overrides[str(new_week)] = today.isoformat()
        early_start_applied = True

    weeks_list = _merge_replanned_future(
        list(raw_weeks),
        current_week=new_week,
        total_weeks=plan.total_weeks,
        remaining_chapters=remaining_chapter_numbers,
    )
    next_chapter_number = remaining_chapter_numbers[0] if remaining_chapter_numbers else None
    pacing_status = "ahead" if plan.total_weeks < selected else ("behind" if plan.total_weeks > selected else "on_track")
    logger.info(
        "event=week_advance_replan learner=%s current_week=%s new_week=%s prev_forecast=%s new_forecast=%s selected_weeks=%s next_chapter=%s early_start_applied=%s",
        learner_id,
        current_week,
        new_week,
        prior_forecast,
        int(plan.total_weeks),
        selected,
        next_chapter_number,
        early_start_applied,
    )

    timeline_payload = dict(plan_payload.get("timeline", {}))
    timeline_payload.update(
        {
            "selected_timeline_weeks": selected,
            "recommended_timeline_weeks": profile.recommended_timeline_weeks or selected,
            "current_forecast_weeks": int(plan.total_weeks),
            "timeline_delta_weeks": int(plan.total_weeks - selected),
            "pacing_status": pacing_status,
        }
    )
    plan.plan_payload = {
        **plan_payload,
        "rough_plan": weeks_list,
        "weeks": weeks_list,
        "week_start_overrides": week_start_overrides,
        "timeline": timeline_payload,
    }

    if next_chapter_number:
        existing_tasks = (
            await db.execute(
                select(Task).where(
                    Task.learner_id == learner_id,
                    Task.week_number == new_week,
                )
            )
        ).scalars().all()
        if not existing_tasks:
            new_tasks = list(_build_week_tasks_for_chapter(
                learner_id=learner_id,
                week_number=new_week,
                chapter_number=next_chapter_number,
            ))
            if new_tasks:
                db.add_all(new_tasks)

    profile.current_forecast_weeks = int(plan.total_weeks)
    profile.timeline_delta_weeks = int(plan.total_weeks - selected)

    db.add(
        WeeklyPlanVersion(
            weekly_plan_id=plan.id,
            learner_id=learner_id,
            version_number=(current_week + 1),
            current_week=new_week,
            plan_payload=plan.plan_payload,
            reason=f"week_{current_week}_completed",
        )
    )

    db.add(
        WeeklyForecast(
            learner_id=learner_id,
            week_number=new_week,
            selected_timeline_weeks=selected,
            recommended_timeline_weeks=profile.recommended_timeline_weeks or selected,
            current_forecast_weeks=int(plan.total_weeks),
            timeline_delta_weeks=int(plan.total_weeks - selected),
            pacing_status=pacing_status,
            reason=f"week_{current_week}_complete_advance",
        )
    )

    await db.commit()
    pace_reasoning = (
        f"Week {current_week} complete; moved to week {new_week}. "
        f"Forecast is {plan.total_weeks} weeks vs selected {selected}."
    )
    try:
        await log_agent_decision(
            db=db,
            learner_id=learner_id,
            agent_name="planner",
            decision_type="pace_adjustment",
            chapter=chapter_display_name(next_chapter_number) if next_chapter_number else None,
            input_snapshot={
                "current_week": current_week,
                "new_week": new_week,
                "selected_timeline_weeks": selected,
            },
            output_payload={
                "total_weeks": int(plan.total_weeks),
                "timeline_delta_weeks": int(plan.total_weeks - selected),
                "pacing_status": pacing_status,
            },
            reasoning=pace_reasoning,
        )
        await db.commit()
    except Exception:
        pass

    message = f"Week {current_week} complete! "
    if next_chapter_number:
        message += f"Week {new_week} is ready with {_chapter_info(next_chapter_number)['title']}."
    else:
        message += "You've completed all chapters!"

    try:
        await redis_client.delete(f"learning:dashboard:{learner_id}")
    except Exception:
        pass

    return WeekCompleteResponse(
        learner_id=str(learner_id),
        completed_week=current_week,
        new_week=new_week,
        plan_updated=True,
        chapters_completed=completed_chapters,
        revision_chapters=revision_chapters,
        message=message,
    )


# 6. Dashboard
DASHBOARD_CACHE_TTL = 60  # seconds

@router.get("/dashboard/{learner_id}", response_model=DashboardResponse)
async def get_dashboard(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return complete dashboard data: plan, completion, confidence, tasks. Cached 60s in Redis."""
    cache_key = f"learning:dashboard:{learner_id}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return DashboardResponse(**data)
    except Exception:
        pass

    profile = await _get_profile(db, learner_id)
    plan = await _get_plan(db, learner_id)

    # Get student name
    from app.models.entities import StudentAuth
    auth = (await db.execute(
        select(StudentAuth).where(StudentAuth.learner_id == learner_id)
    )).scalar_one_or_none()
    student_name = auth.name if auth else "Student"

    # Chapter progressions
    progressions = (await db.execute(
        select(ChapterProgression).where(ChapterProgression.learner_id == learner_id)
    )).scalars().all()
    prog_map = {p.chapter: p for p in progressions}

    # Build chapter status and confidence lists
    chapter_status = []
    chapter_confidence = []
    completed_count = 0
    mastery_sum = 0.0

    for ch in SYLLABUS_CHAPTERS:
        ch_key = chapter_display_name(ch["number"])
        cp = prog_map.get(ch_key)
        status = cp.status if cp else "not_started"
        best_score = cp.best_score if cp else 0.0
        attempt_count = cp.attempt_count if cp else 0
        revision = cp.revision_queued if cp else False

        if status == "completed":
            completed_count += 1

        mastery_score = (profile.concept_mastery or {}).get(ch_key, 0.0)
        mastery_sum += mastery_score

        subtopics = [{"id": s["id"], "title": s["title"]} for s in ch.get("subtopics", [])]

        chapter_status.append({
            "chapter_number": ch["number"],
            "chapter_key": ch_key,
            "title": ch["title"],
            "status": status,
            "subtopics": subtopics,
        })

        chapter_confidence.append({
            "chapter_number": ch["number"],
            "chapter_key": ch_key,
            "title": ch["title"],
            "best_score": round(best_score, 2),
            "mastery_score": round(mastery_score, 2),
            "mastery_band": _mastery_band(mastery_score),
            "attempt_count": attempt_count,
            "revision_queued": revision,
        })

    overall_completion = (completed_count / 14) * 100
    overall_mastery = (mastery_sum / 14) * 100

    # Rough plan (onboarding stores as plan_payload.rough_plan)
    rough_plan = []
    onboarding_date = _profile_onboarding_date(profile)
    timeline_visualization = []
    week_start_overrides = _extract_week_start_overrides(plan.plan_payload if plan else {})
    if plan and plan.plan_payload:
        raw = plan.plan_payload.get("rough_plan", []) or plan.plan_payload.get("weeks", [])
        cw = plan.current_week or 1
        for entry in raw:
            w = entry.get("week", 0)
            if not isinstance(w, int) or w <= 0:
                continue
            # Performance: skip expensive date/timeline computations for
            # completed weeks that are far in the past (>2 weeks before current).
            if w < cw - 2:
                rough_plan.append({
                    "week": w,
                    "chapter": entry.get("chapter"),
                    "focus": entry.get("focus"),
                    "week_start_date": None,
                    "week_end_date": None,
                    "week_label": f"Week {w}",
                    "status": "completed",
                })
                continue
            week_start, week_end = week_bounds_from_plan(onboarding_date, w, week_start_overrides)
            week_label = format_week_label(w, week_start, week_end)
            rough_plan.append({
                "week": w,
                "chapter": entry.get("chapter"),
                "focus": entry.get("focus"),
                "week_start_date": week_start.isoformat(),
                "week_end_date": week_end.isoformat(),
                "week_label": week_label,
                "status": "completed" if w < cw else ("current" if w == cw else "upcoming"),
            })
            timeline_visualization.append(
                {
                    **build_week_timeline_item(
                        onboarding_date=onboarding_date,
                        week_number=w,
                        is_current=(w == cw),
                        is_past=(w < cw),
                        week_start_overrides=week_start_overrides,
                    ),
                    "chapter": entry.get("chapter"),
                    "focus": entry.get("focus"),
                }
            )

    # Current week tasks
    current_week = plan.current_week if plan else 1
    current_week_start, current_week_end = week_bounds_from_plan(onboarding_date, current_week, week_start_overrides)
    completion = estimate_completion_date(
        onboarding_date=onboarding_date,
        current_week=current_week,
        total_weeks_forecast=(profile.current_forecast_weeks or (plan.total_weeks if plan else 14)),
    )
    tasks = (await db.execute(
        select(Task).where(
            Task.learner_id == learner_id,
            Task.week_number == current_week,
        ).order_by(Task.sort_order)
    )).scalars().all()

    current_tasks = []
    for t in tasks:
        policy = t.proof_policy or {}
        min_seconds = policy.get("min_seconds")
        if not isinstance(min_seconds, int):
            try:
                min_seconds = int(float(policy.get("min_reading_minutes", 0)) * 60) if policy.get("min_reading_minutes") is not None else None
            except Exception:
                min_seconds = None
        current_tasks.append({
            "task_id": str(t.id),
            "chapter": t.chapter,
            "task_type": t.task_type,
            "title": t.title,
            "status": t.status,
            "is_locked": t.is_locked,
            "section_id": policy.get("section_id"),
            "chapter_level": policy.get("chapter_level", False),
            "min_seconds": min_seconds,
            "scheduled_day": t.scheduled_day.isoformat() if t.scheduled_day else None,
        })

    # Revision queue
    revisions = (await db.execute(
        select(RevisionQueueItem).where(
            RevisionQueueItem.learner_id == learner_id,
            RevisionQueueItem.status == "pending",
        )
    )).scalars().all()
    revision_list = [{"chapter": r.chapter, "reason": r.reason, "priority": r.priority} for r in revisions]

    response = DashboardResponse(
        learner_id=str(learner_id),
        student_name=student_name,
        diagnostic_score=profile.onboarding_diagnostic_score,
        math_9_percent=profile.math_9_percent,
        selected_weeks=profile.selected_timeline_weeks,
        suggested_weeks=profile.recommended_timeline_weeks,
        onboarding_date=onboarding_date.isoformat(),
        timeline_timezone=str(TIMELINE_TZ),
        current_week=current_week,
        current_week_label=format_week_label(current_week, current_week_start, current_week_end),
        current_week_start_date=current_week_start.isoformat(),
        current_week_end_date=current_week_end.isoformat(),
        total_weeks=plan.total_weeks if plan else 14,
        completion_estimate_date=scheduled_completion_date(
            onboarding_date=onboarding_date,
            total_weeks_forecast=(profile.current_forecast_weeks or (plan.total_weeks if plan else 14)),
            week_start_overrides=week_start_overrides,
        ).isoformat(),
        completion_estimate_date_active_pace=completion["estimated_completion_date"],
        completion_estimate_weeks_active_pace=completion["completion_estimate_weeks_active_pace"],
        overall_completion_percent=round(overall_completion, 1),
        overall_mastery_percent=round(overall_mastery, 1),
        rough_plan=rough_plan,
        timeline_visualization=timeline_visualization,
        chapter_status=chapter_status,
        chapter_confidence=chapter_confidence,
        current_week_tasks=current_tasks,
        revision_queue=revision_list,
    )
    try:
        await redis_client.set(cache_key, response.model_dump_json(), ex=DASHBOARD_CACHE_TTL)
    except Exception:
        pass
    return response


# 7. Plan history
@router.get("/plan-history/{learner_id}")
async def get_plan_history(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return all plan versions for a learner, newest first."""
    versions = (await db.execute(
        select(WeeklyPlanVersion).where(
            WeeklyPlanVersion.learner_id == learner_id
        ).order_by(desc(WeeklyPlanVersion.created_at))
    )).scalars().all()

    return {
        "learner_id": str(learner_id),
        "total_versions": len(versions),
        "versions": [
            {
                "version_number": v.version_number,
                "current_week": v.current_week,
                "reason": v.reason,
                "plan_payload": v.plan_payload,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
    }

@router.get("/confidence-trend/{learner_id}")
async def get_confidence_trend(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return recent assessment trend for charting confidence over time."""
    rows = (await db.execute(
        select(AssessmentResult).where(
            AssessmentResult.learner_id == learner_id
        ).order_by(AssessmentResult.timestamp.asc()).limit(200)
    )).scalars().all()
    points = [
        {
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "score": round(float(r.score or 0.0), 4),
            "concept": r.concept,
        }
        for r in rows
    ]
    if not points:
        return {"learner_id": str(learner_id), "points": [], "trend": "flat", "latest_score": 0.0}
    latest = points[-1]["score"]
    window = points[-5:]
    avg = sum(p["score"] for p in window) / max(1, len(window))
    trend = "up" if latest > avg + 0.02 else ("down" if latest < avg - 0.02 else "flat")
    return {
        "learner_id": str(learner_id),
        "points": points,
        "trend": trend,
        "latest_score": round(latest, 4),
    }


# 8. Agent decision history
@router.get("/decisions/{learner_id}")
async def get_agent_decisions(learner_id: UUID, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Return recent agent decisions for observability."""
    decisions = (await db.execute(
        select(AgentDecision).where(
            AgentDecision.learner_id == learner_id
        ).order_by(desc(AgentDecision.created_at)).limit(limit)
    )).scalars().all()

    return {
        "learner_id": str(learner_id),
        "total": len(decisions),
        "decisions": [
            {
                "id": str(d.id),
                "agent_name": d.agent_name,
                "decision_type": d.decision_type,
                "chapter": d.chapter,
                "section_id": d.section_id,
                "confidence": d.confidence,
                "reasoning": d.reasoning,
                "input_snapshot": d.input_snapshot,
                "output_payload": d.output_payload,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decisions
        ],
    }


