"""
Plan builder service — weekly plan construction and week management helpers.

Extracted from ``learning/routes.py`` to centralise plan building logic
that is used across dashboard, plan history, and week advancement endpoints.
"""
from __future__ import annotations

import re
from uuid import UUID

from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name
from app.models.entities import ChapterProgression, Task

# ── Constants ────────────────────────────────────────────────────────

COMPLETION_THRESHOLD = 0.60
"""60% score required to pass a chapter test."""

MAX_CHAPTER_ATTEMPTS = 2
"""Maximum number of test attempts per chapter before forced advancement."""

TIMELINE_MIN_WEEKS = 14
"""Minimum allowed timeline length."""

TIMELINE_MAX_WEEKS = 28
"""Maximum allowed timeline length."""


# ── Chapter helpers ──────────────────────────────────────────────────

def chapter_info(chapter_number: int) -> dict:
    """Return syllabus chapter dict for *chapter_number*, or a stub if not found."""
    for ch in SYLLABUS_CHAPTERS:
        if ch["number"] == chapter_number:
            return ch
    return {"number": chapter_number, "title": f"Chapter {chapter_number}", "subtopics": []}


def chapter_number_from_label(chapter_label: str | None) -> int | None:
    """Extract the integer chapter number from a label like 'Chapter 5', or None."""
    match = re.search(r"(\d+)", str(chapter_label or ""))
    if not match:
        return None
    return int(match.group(1))


def chapter_is_completed(status: str | None) -> bool:
    """Check whether a chapter status string indicates completion."""
    return str(status or "").startswith("completed")


# ── Mastery & ability helpers ────────────────────────────────────────

def mastery_band(score: float) -> str:
    """Map a 0–1 mastery score to a categorical band (mastered/proficient/developing/beginner)."""
    if score >= 0.80:
        return "mastered"
    if score >= 0.60:
        return "proficient"
    if score >= 0.40:
        return "developing"
    return "beginner"


def tone_for_ability(ability: float) -> dict:
    """Derive tone/pace/depth/examples config from learner ability (0–1)."""
    if ability < 0.4:
        return {"tone": "simple_supportive", "pace": "slow", "depth": "foundational", "examples": 3}
    if ability < 0.7:
        return {"tone": "clear_structured", "pace": "balanced", "depth": "standard", "examples": 2}
    return {"tone": "concise_challenging", "pace": "fast", "depth": "advanced", "examples": 1}


def bucket(value: float, scale: int = 10) -> int:
    """Clamp *value* (0–1) to an integer bucket [0, *scale*] for cache keying."""
    return max(0, min(scale, int(round(float(value or 0.0) * scale))))


# ── Plan building helpers ────────────────────────────────────────────

def remaining_chapter_numbers(progressions: list[ChapterProgression]) -> list[int]:
    """Return sorted list of chapter numbers that have not yet been completed."""
    completed = {
        chapter_number_from_label(p.chapter)
        for p in progressions
        if chapter_is_completed(p.status)
    }
    return [
        int(ch["number"])
        for ch in SYLLABUS_CHAPTERS
        if int(ch["number"]) not in completed
    ]


def build_replanned_weeks(*, current_week: int, total_weeks: int, remaining_chapters: list[int]) -> list[dict]:
    """Build a list of week dicts for the replanned schedule from *current_week* onward."""
    weeks: list[dict] = []
    for offset, week_number in enumerate(range(1, max(1, int(total_weeks)) + 1), start=0):
        if week_number < current_week:
            continue
        chapter_index = week_number - current_week
        if chapter_index < len(remaining_chapters):
            chapter_number = remaining_chapters[chapter_index]
            ch_info = chapter_info(chapter_number)
            weeks.append(
                {
                    "week": week_number,
                    "chapter": chapter_display_name(chapter_number),
                    "focus": ch_info["title"],
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


def merge_replanned_future(
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
    future = build_replanned_weeks(
        current_week=current_week,
        total_weeks=total_weeks,
        remaining_chapters=remaining_chapters,
    )
    return preserved + future


def build_week_tasks_for_chapter(*, learner_id: UUID, week_number: int, chapter_number: int) -> list[Task]:
    """Create Task objects for all subtopics + chapter test for a given chapter/week."""
    chapter_key = chapter_display_name(chapter_number)
    ch_info = chapter_info(chapter_number)
    subtopics = ch_info.get("subtopics", [])
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
            title=f"Chapter Test: {ch_info['title']}",
            sort_order=sort,
            status="pending",
            is_locked=False,
            proof_policy={"type": "test_score", "threshold": COMPLETION_THRESHOLD, "chapter_level": True},
        )
    )
    return tasks
