"""
Learning API: content delivery, test generation, task completion, weekly cycle, dashboard.

This module provides the student-facing learning endpoints that drive the core
weekly cycle after onboarding is complete.
"""
from __future__ import annotations

import json
import logging
import random
import re
from difflib import SequenceMatcher
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_provider import get_llm_provider
from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger
from app.core.settings import settings
from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name
from app.memory.cache import redis_client
from app.memory.database import get_db
from app.agents.decision_logger import log_agent_decision
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


# ── Pydantic models ──────────────────────────────────────────────────────────

class ContentRequest(BaseModel):
    learner_id: UUID
    chapter_number: int = Field(ge=1, le=14)
    regenerate: bool = False


class ContentResponse(BaseModel):
    chapter_number: int
    chapter_title: str
    content: str
    source: str  # "llm" | "rag_only" | "fallback"
    tone: str
    examples_count: int


class TestQuestion(BaseModel):
    question_id: str
    prompt: str
    options: list[str]
    chapter_number: int


class GenerateTestResponse(BaseModel):
    learner_id: str
    week_number: int
    chapter: str
    test_id: str | None = None
    questions: list[TestQuestion] = Field(default_factory=list)
    time_limit_minutes: int = 20
    source: str = "llm"
    blocked: bool = False
    reason_code: str | None = None
    pending_tasks: list[str] = Field(default_factory=list)


class TestAnswer(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=3)


class SubmitTestRequest(BaseModel):
    learner_id: UUID
    test_id: str
    answers: list[TestAnswer]
    task_id: UUID | None = None


class SubmitTestResponse(BaseModel):
    learner_id: str
    chapter: str
    score: float
    correct: int
    total: int
    passed: bool
    attempt_number: int
    max_attempts: int
    decision: str  # "chapter_completed" | "retry" | "move_on_revision"
    message: str
    question_results: list[dict] = Field(default_factory=list)


class CompleteReadingRequest(BaseModel):
    learner_id: UUID
    task_id: UUID
    time_spent_seconds: int = Field(ge=0)


class SubsectionContentRequest(BaseModel):
    learner_id: UUID
    chapter_number: int = Field(ge=1, le=14)
    section_id: str  # e.g. "1.2", "3.3.1"
    regenerate: bool = False  # True = force LLM call, ignore cache


class PracticeGenerateRequest(BaseModel):
    learner_id: UUID
    chapter_number: int = Field(ge=1, le=14)
    section_id: str
    regenerate: bool = False


class CompleteReadingResponse(BaseModel):
    task_id: str
    accepted: bool
    reason: str


class WeekCompleteResponse(BaseModel):
    learner_id: str
    completed_week: int
    new_week: int
    plan_updated: bool
    chapters_completed: list[str]
    revision_chapters: list[str]
    message: str


class DashboardResponse(BaseModel):
    learner_id: str
    student_name: str
    diagnostic_score: float | None
    math_9_percent: int | None
    selected_weeks: int | None
    suggested_weeks: int | None
    current_week: int
    total_weeks: int
    overall_completion_percent: float
    overall_mastery_percent: float
    rough_plan: list[dict]
    chapter_status: list[dict]
    chapter_confidence: list[dict]
    current_week_tasks: list[dict]
    revision_queue: list[dict]


class ExplainQuestionRequest(BaseModel):
    learner_id: UUID
    test_id: str
    question_id: str
    selected_index: int | None = None
    regenerate: bool = False


class ExplainQuestionResponse(BaseModel):
    learner_id: str
    test_id: str
    question_id: str
    chapter_number: int
    chapter: str
    section_id: str | None = None
    explanation: str
    source: str  # "cached" | "llm" | "fallback"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chapter_info(chapter_number: int) -> dict:
    for ch in SYLLABUS_CHAPTERS:
        if ch["number"] == chapter_number:
            return ch
    return {"number": chapter_number, "title": f"Chapter {chapter_number}", "subtopics": []}


def _mastery_band(score: float) -> str:
    if score >= 0.80:
        return "mastered"
    if score >= 0.60:
        return "proficient"
    if score >= 0.40:
        return "developing"
    return "beginner"


def _tone_for_ability(ability: float) -> dict:
    if ability < 0.4:
        return {"tone": "simple_supportive", "pace": "slow", "depth": "foundational", "examples": 3}
    if ability < 0.7:
        return {"tone": "clear_structured", "pace": "balanced", "depth": "standard", "examples": 2}
    return {"tone": "concise_challenging", "pace": "fast", "depth": "advanced", "examples": 1}


def _bucket(value: float, scale: int = 10) -> int:
    return max(0, min(scale, int(round(float(value or 0.0) * scale))))


def _profile_snapshot_key(profile: LearnerProfile, chapter_key: str) -> str:
    cog = _bucket(profile.cognitive_depth or 0.5)
    mastery = _bucket((profile.concept_mastery or {}).get(chapter_key, 0.5))
    return f"c{cog}m{mastery}"


def _section_content_cache_key(section_id: str, tone: str, profile_snapshot: str) -> str:
    return f"{section_id}::pv={CONTENT_PROMPT_VERSION}::tone={tone}::p={profile_snapshot}"


def _chapter_test_cache_key(chapter_base: str, difficulty: str, profile_snapshot: str) -> str:
    return f"{chapter_base}::pv={TEST_PROMPT_VERSION}::difficulty={difficulty}::p={profile_snapshot}"


def _normalized_question_text(text: str) -> str:
    """Normalize question text for de-dup checks."""
    txt = re.sub(r"\\\(|\\\)|\\\[|\\\]", " ", str(text or ""))
    txt = re.sub(r"[^a-zA-Z0-9]+", " ", txt).strip().lower()
    return re.sub(r"\s+", " ", txt)


def _is_near_duplicate(candidate: str, existing: list[str], threshold: float = 0.9) -> bool:
    return any(SequenceMatcher(a=candidate, b=prev).ratio() >= threshold for prev in existing)


def _dedupe_generated_questions(raw_items: list[dict], target_count: int) -> tuple[list[dict], int]:
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
        if not q or not isinstance(options, list) or len(options) < 4:
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


# ── In-memory test store (for simplicity; keyed by test_id) ─────────────────
_test_store: dict[str, dict] = {}


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

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
            logger.info(
                "event=cache_hit kind=chapter_content learner_id=%s chapter=%s section=%s",
                payload.learner_id,
                payload.chapter_number,
                cache_section_id,
            )
            return ContentResponse(
                chapter_number=payload.chapter_number,
                chapter_title=chapter_name,
                content=str(cached["content"]),
                source="cached",
                tone=str(cached.get("tone") or tone_config["tone"]),
                examples_count=tone_config["examples"],
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
        # No embeddings available for this chapter — provide a structured fallback
        content = (
            f"# {chapter_name}\n\n"
            f"This chapter covers the following topics:\n\n"
            + "\n".join(f"- {s}" for s in subtopics) + "\n\n"
            f"**Note:** Detailed NCERT content for this chapter is not yet embedded. "
            f"Please refer to the NCERT textbook for Chapter {payload.chapter_number}."
        )
        return ContentResponse(
            chapter_number=payload.chapter_number,
            chapter_title=chapter_name,
            content=content,
            source="fallback",
            tone=tone_config["tone"],
            examples_count=0,
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
        f"Format the output in clean Markdown with headers, bullet points, "
        f"and LaTeX math notation using \\\\( \\\\) for inline math.\n"
        f"Keep the language appropriate for a 15-16 year old student.\n"
    )

    try:
        provider = get_llm_provider(role="content_generator")
        llm_text, _ = await provider.generate(prompt)
        if llm_text and len(llm_text.strip()) > 50:
            save_content_cache(
                str(payload.learner_id),
                payload.chapter_number,
                cache_section_id,
                chapter_name,
                llm_text.strip(),
                tone_config["tone"],
            )
            return ContentResponse(
                chapter_number=payload.chapter_number,
                chapter_title=chapter_name,
                content=llm_text.strip(),
                source="llm",
                tone=tone_config["tone"],
                examples_count=tone_config["examples"],
            )
    except Exception as exc:
        logger.warning("LLM content generation failed: %s", exc)

    # Fallback: use RAG chunks directly
    content = (
        f"# {chapter_name}\n\n"
        f"## Key Concepts\n\n{context}\n\n"
        f"*Content sourced from NCERT textbook.*"
    )
    return ContentResponse(
        chapter_number=payload.chapter_number,
        chapter_title=chapter_name,
        content=content,
        source="rag_only",
        tone=tone_config["tone"],
        examples_count=0,
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
                "questions": cached.get("questions", []),
                "answer_key": cached["answer_key"],
                "created_at": cached.get("created_at", datetime.now(timezone.utc).isoformat()),
            }
            return GenerateTestResponse(
                learner_id=str(payload.learner_id),
                week_number=week_number,
                chapter=chapter_key,
                test_id=cached["test_id"],
                questions=[TestQuestion(**q) for q in cached["questions"]],
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

        try:
            provider = get_llm_provider(role="content_generator")
            llm_text, _ = await provider.generate(prompt)
            if llm_text:
                # Parse JSON from LLM response
                text = llm_text.strip()
                # Try to extract JSON array
                start = text.find("[")
                end = text.rfind("]") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(text[start:end])
                    deduped, duplicates_removed = _dedupe_generated_questions(parsed, target_count=10)
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
                    logger.info(
                        "event=test_generation_diagnostics kind=chapter requested=%s unique_count=%s duplicates_removed=%s chapter=%s",
                        10,
                        len(questions),
                        duplicates_removed,
                        payload.chapter_number,
                    )
        except Exception as exc:
            logger.warning("LLM test generation failed: %s", exc)

    # Refill missing unique slots with deterministic fallback stems.
    subtopics = [s["title"] for s in ch_info.get("subtopics", [])
                 if "Summary" not in s["title"] and "Introduction" not in s["title"]]
    while len(questions) < 10:
        i = len(questions)
        qid = f"t_{test_id}_q{i+1}"
        topic = subtopics[i % len(subtopics)] if subtopics else chapter_name
        prompt_text = f"[Q{i+1}] Which of the following best describes a key concept in '{topic}'?"
        if _is_near_duplicate(_normalized_question_text(prompt_text), [_normalized_question_text(q.prompt) for q in questions]):
            prompt_text = f"[Q{i+1}] Identify the most accurate statement about '{topic}'."
        questions.append(TestQuestion(
            question_id=qid,
            prompt=prompt_text,
            options=[
                f"Correct definition of {topic}",
                f"Incorrect variant A of {topic}",
                f"Incorrect variant B of {topic}",
                f"Unrelated concept",
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
            questions.append(TestQuestion(
                question_id=qid,
                prompt=f"[Q{i+1}] Which of the following best describes a key concept in '{topic}'?",
                options=[
                    f"Correct definition of {topic}",
                    f"Incorrect variant A of {topic}",
                    f"Incorrect variant B of {topic}",
                    f"Unrelated concept",
                ],
                chapter_number=payload.chapter_number,
            ))
            answer_key[qid] = 0

    # Store test for scoring
    _test_store[test_id] = {
        "learner_id": str(payload.learner_id),
        "chapter_number": payload.chapter_number,
        "chapter": chapter_key,
        "chapter_level": True,
        "section_id": None,
        "questions": [q.model_dump() for q in questions],
        "answer_key": answer_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_test_cache(
        str(payload.learner_id),
        payload.chapter_number,
        cache_section_id,
        chapter_name,
        test_id,
        [q.model_dump() for q in questions],
        answer_key,
    )

    return GenerateTestResponse(
        learner_id=str(payload.learner_id),
        week_number=week_number,
        chapter=chapter_key,
        test_id=test_id,
        questions=questions,
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
        options = q.get("options", [])
        question_results.append(
            {
                "question_id": qid,
                "prompt": q.get("prompt"),
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
            return ExplainQuestionResponse(
                learner_id=str(payload.learner_id),
                test_id=payload.test_id,
                question_id=payload.question_id,
                chapter_number=chapter_number,
                chapter=chapter,
                section_id=section_id,
                explanation=str(cached["explanation"]),
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

    options = question.get("options", [])
    prompt = (
        "You are a Class 10 CBSE math tutor.\n"
        "Explain the question outcome in a concise and clear way.\n"
        "Use ONLY the NCERT source context below.\n\n"
        f"Chapter: {chapter_number}\n"
        f"Section: {section_id or 'chapter-level final'}\n"
        f"Question: {question.get('prompt', '')}\n"
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
            provider = get_llm_provider(role="content_generator")
            llm_text, _ = await provider.generate(prompt)
            if llm_text and llm_text.strip():
                explanation = llm_text.strip()
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
            f"Correct answer: **{correct_text}**\n\n"
            f"Your choice: **{chosen_text}**\n\n"
            "Review the related concept from the section and retry a similar problem."
        )

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
    MIN_READING_SECONDS = 180  # 3 minutes minimum

    task = (await db.execute(
        select(Task).where(Task.id == payload.task_id, Task.learner_id == payload.learner_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.task_type != "read":
        raise HTTPException(status_code=400, detail="This endpoint is for reading tasks only.")
    if task.status == "completed":
        return CompleteReadingResponse(task_id=str(task.id), accepted=True, reason="Already completed.")

    if payload.time_spent_seconds < MIN_READING_SECONDS:
        return CompleteReadingResponse(
            task_id=str(task.id),
            accepted=False,
            reason=f"Please spend at least {MIN_READING_SECONDS // 60} minutes reading before completing.",
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
    return CompleteReadingResponse(task_id=str(task.id), accepted=True, reason="Reading completed! ✅")


# ── SUBSECTION ENDPOINTS ─────────────────────────────────────────────────────

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
                await db.commit()
            return {
                "chapter_number": payload.chapter_number,
                "section_id": payload.section_id,
                "section_title": cached.get("section_title", section_title),
                "content": cached["content"],
                "source": "cached",
                "tone": cached.get("tone", "normal"),
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
        return {
            "chapter_number": payload.chapter_number,
            "section_id": payload.section_id,
            "section_title": section_title,
            "content": (
                f"# {section_title}\n\n"
                f"**Note:** NCERT content for section {payload.section_id} is not yet embedded. "
                f"Please refer to the NCERT textbook for Chapter {payload.chapter_number}."
            ),
            "source": "fallback",
            "tone": tone_config["tone"],
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
        f"Format the output in clean Markdown with headers, bullet points, "
        f"and LaTeX math notation using \\\\( \\\\) for inline math.\n"
        f"Keep the language appropriate for a 15-16 year old student.\n"
    )

    try:
        provider = get_llm_provider(role="content_generator")
        llm_text, _ = await provider.generate(prompt)
        if llm_text and len(llm_text.strip()) > 50:
            # Mark reading done for this subsection
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

            generated_content = llm_text.strip()
            # Save to cache
            save_content_cache(
                str(payload.learner_id), payload.chapter_number, cache_section_id,
                section_title, generated_content, tone_config["tone"],
            )
            return {
                "chapter_number": payload.chapter_number,
                "section_id": payload.section_id,
                "section_title": section_title,
                "content": generated_content,
                "source": "llm",
                "tone": tone_config["tone"],
            }
    except Exception as exc:
        logger.warning("LLM section content generation failed: %s", exc)

    return {
        "chapter_number": payload.chapter_number,
        "section_id": payload.section_id,
        "section_title": section_title,
        "content": f"# {section_title}\n\n## Key Concepts\n\n{context}\n\n*Content sourced from NCERT textbook.*",
        "source": "rag_only",
        "tone": tone_config["tone"],
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
                "questions": cached.get("questions", []),
                "answer_key": cached["answer_key"],
                "created_at": cached.get("created_at", datetime.now(timezone.utc).isoformat()),
            }
            return {
                "learner_id": str(payload.learner_id),
                "chapter": chapter_key,
                "section_id": payload.section_id,
                "section_title": cached.get("section_title", section_title),
                "test_id": cached["test_id"],
                "questions": cached["questions"],
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

        try:
            provider = get_llm_provider(role="content_generator")
            llm_text, _ = await provider.generate(prompt)
            if llm_text:
                text = llm_text.strip()
                start = text.find("[")
                end = text.rfind("]") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(text[start:end])
                    deduped, duplicates_removed = _dedupe_generated_questions(parsed, target_count=5)
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
                    logger.info(
                        "event=test_generation_diagnostics kind=section requested=%s unique_count=%s duplicates_removed=%s chapter=%s section=%s",
                        5,
                        len(questions),
                        duplicates_removed,
                        payload.chapter_number,
                        payload.section_id,
                    )
        except Exception as exc:
            logger.warning("LLM section test generation failed: %s", exc)

    # Refill missing unique slots with deterministic fallback stems.
    while len(questions) < 5:
        i = len(questions)
        qid = f"st_{test_id}_q{i+1}"
        prompt_text = f"[Q{i+1}] Which concept is central to '{section_title}'?"
        if _is_near_duplicate(_normalized_question_text(prompt_text), [_normalized_question_text(q.prompt) for q in questions]):
            prompt_text = f"[Q{i+1}] Select the statement that best matches '{section_title}'."
        questions.append(TestQuestion(
            question_id=qid,
            prompt=prompt_text,
            options=[
                f"Correct definition of {section_title}",
                f"Incorrect variant A",
                f"Incorrect variant B",
                f"Unrelated concept",
            ],
            chapter_number=payload.chapter_number,
        ))
        answer_key[qid] = 0

    _test_store[test_id] = {
        "learner_id": str(payload.learner_id),
        "chapter_number": payload.chapter_number,
        "chapter": chapter_key,
        "section_id": payload.section_id,
        "chapter_level": False,
        "questions": [q.model_dump() for q in questions],
        "answer_key": answer_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    questions_dicts = [q.model_dump() for q in questions]
    save_test_cache(
        str(payload.learner_id), payload.chapter_number, payload.section_id,
        section_title, test_id, questions_dicts, answer_key,
    )

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


@router.post("/practice/generate")
async def generate_practice(payload: PracticeGenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate practice set for a subsection (alias over section test generation)."""
    section_payload = SubsectionContentRequest(
        learner_id=payload.learner_id,
        chapter_number=payload.chapter_number,
        section_id=payload.section_id,
        regenerate=payload.regenerate,
    )
    result = await generate_section_test(section_payload, db)
    if isinstance(result, dict):
        result["practice"] = True
    return result

# 5. Check if week is complete and advance
@router.post("/week/advance", response_model=WeekCompleteResponse)
async def advance_week(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Check if all tasks for current week are done, then create next week."""
    profile = await _get_profile(db, learner_id)
    plan = await _get_plan(db, learner_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found. Complete onboarding first.")

    current_week = plan.current_week

    # Check if all tasks for current week are completed
    tasks = (await db.execute(
        select(Task).where(
            Task.learner_id == learner_id,
            Task.week_number == current_week,
        )
    )).scalars().all()

    incomplete = [t for t in tasks if t.status != "completed"]
    if incomplete:
        raise HTTPException(
            status_code=400,
            detail=f"Week {current_week} has {len(incomplete)} incomplete task(s). Complete all tasks first.",
        )

    # Determine which chapters were completed this week (rough_plan or weeks)
    plan_payload = plan.plan_payload or {}
    raw_weeks = plan_payload.get("rough_plan", []) or plan_payload.get("weeks", [])
    week_chapters = [e.get("chapter", "") for e in raw_weeks if e.get("week") == current_week]

    completed_chapters = []
    revision_chapters = []
    for ch in week_chapters:
        cp = (await db.execute(
            select(ChapterProgression).where(
                ChapterProgression.learner_id == learner_id,
                ChapterProgression.chapter == ch,
            )
        )).scalar_one_or_none()
        if cp:
            if cp.revision_queued:
                revision_chapters.append(ch)
            if cp.status == "completed":
                completed_chapters.append(ch)

    # Update profile snapshot
    db.add(LearnerProfileSnapshot(
        learner_id=learner_id,
        reason=f"week_{current_week}_complete",
        payload={
            "week": current_week,
            "mastery": dict(profile.concept_mastery or {}),
            "cognitive_depth": profile.cognitive_depth,
        },
    ))

    # Recalculate plan: update forecast
    new_week = current_week + 1
    plan.current_week = new_week

    # Recalculate total weeks based on remaining chapters
    all_progressions = (await db.execute(
        select(ChapterProgression).where(ChapterProgression.learner_id == learner_id)
    )).scalars().all()
    completed_count = sum(1 for p in all_progressions if p.status == "completed")
    remaining_chapters = 14 - completed_count

    # Dynamic pacing
    selected = profile.selected_timeline_weeks or 14
    if remaining_chapters <= 0:
        plan.total_weeks = current_week
    else:
        estimated_total = current_week + remaining_chapters
        plan.total_weeks = max(selected, estimated_total)

    # Create next week plan entry (rough_plan is source of truth from onboarding)
    weeks_list = list(plan_payload.get("rough_plan", []) or plan_payload.get("weeks", []))
    next_chapter_number = None
    for ch_data in SYLLABUS_CHAPTERS:
        ch_key = chapter_display_name(ch_data["number"])
        cp = None
        for p in all_progressions:
            if p.chapter == ch_key:
                cp = p
                break
        if cp is None or cp.status != "completed":
            next_chapter_number = ch_data["number"]
            break

    if next_chapter_number:
        next_ch_key = chapter_display_name(next_chapter_number)
        next_ch_info = _chapter_info(next_chapter_number)

        # Check if this week entry already exists
        existing_week = any(e.get("week") == new_week for e in weeks_list)
        if not existing_week:
            weeks_list.append({
                "week": new_week,
                "chapter": next_ch_key,
                "focus": next_ch_info["title"],
            })
            plan.plan_payload = {**plan_payload, "rough_plan": weeks_list, "weeks": weeks_list}

        # Create tasks for new week
        existing_tasks = (await db.execute(
            select(Task).where(
                Task.learner_id == learner_id,
                Task.week_number == new_week,
            )
        )).scalars().all()
        if not existing_tasks:
            subtopics = next_ch_info.get("subtopics", [])
            sort = 0
            for st in subtopics:
                sort += 1
                # Reading task for every subsection
                db.add(Task(
                    learner_id=learner_id,
                    week_number=new_week,
                    chapter=next_ch_key,
                    task_type="read",
                    title=f"Read: {st['id']} {st['title']}",
                    sort_order=sort,
                    status="pending",
                    is_locked=False,
                    proof_policy={"type": "reading_time", "min_seconds": 120, "section_id": st["id"]},
                ))
                # Test task for every subsection, including Summary.
                sort += 1
                db.add(Task(
                    learner_id=learner_id,
                    week_number=new_week,
                    chapter=next_ch_key,
                    task_type="test",
                    title=f"Test: {st['id']} {st['title']}",
                    sort_order=sort,
                    status="pending",
                    is_locked=False,
                    proof_policy={"type": "section_test", "threshold": COMPLETION_THRESHOLD, "section_id": st["id"]},
                ))
            # Final chapter-level test (unlocked after all subsections done)
            sort += 1
            db.add(Task(
                learner_id=learner_id,
                week_number=new_week,
                chapter=next_ch_key,
                task_type="test",
                title=f"📋 Chapter Test: {next_ch_info['title']}",
                sort_order=sort,
                status="pending",
                is_locked=False,
                proof_policy={"type": "test_score", "threshold": COMPLETION_THRESHOLD, "chapter_level": True},
            ))

    # Create plan version
    db.add(WeeklyPlanVersion(
        weekly_plan_id=plan.id,
        learner_id=learner_id,
        version_number=(current_week + 1),
        current_week=new_week,
        plan_payload=plan.plan_payload,
        reason=f"week_{current_week}_completed",
    ))

    # Forecast entry
    db.add(WeeklyForecast(
        learner_id=learner_id,
        week_number=new_week,
        selected_timeline_weeks=selected,
        recommended_timeline_weeks=profile.recommended_timeline_weeks or selected,
        current_forecast_weeks=plan.total_weeks,
        timeline_delta_weeks=plan.total_weeks - selected,
        pacing_status="ahead" if plan.total_weeks < selected else ("behind" if plan.total_weeks > selected else "on_track"),
        reason=f"week_{current_week}_complete_advance",
    ))

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
                "total_weeks": plan.total_weeks,
                "timeline_delta_weeks": plan.total_weeks - selected,
                "pacing_status": "ahead" if plan.total_weeks < selected else ("behind" if plan.total_weeks > selected else "on_track"),
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
        message += "You've completed all chapters! 🎉"

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
    if plan and plan.plan_payload:
        raw = plan.plan_payload.get("rough_plan", []) or plan.plan_payload.get("weeks", [])
        cw = plan.current_week or 1
        for entry in raw:
            w = entry.get("week", 0)
            rough_plan.append({
                "week": w,
                "chapter": entry.get("chapter"),
                "focus": entry.get("focus"),
                "status": "completed" if w < cw else ("current" if w == cw else "upcoming"),
            })

    # Current week tasks
    current_week = plan.current_week if plan else 1
    tasks = (await db.execute(
        select(Task).where(
            Task.learner_id == learner_id,
            Task.week_number == current_week,
        ).order_by(Task.sort_order)
    )).scalars().all()

    current_tasks = []
    for t in tasks:
        policy = t.proof_policy or {}
        current_tasks.append({
            "task_id": str(t.id),
            "chapter": t.chapter,
            "task_type": t.task_type,
            "title": t.title,
            "status": t.status,
            "is_locked": t.is_locked,
            "section_id": policy.get("section_id"),
            "chapter_level": policy.get("chapter_level", False),
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
        current_week=current_week,
        total_weeks=plan.total_weeks if plan else 14,
        overall_completion_percent=round(overall_completion, 1),
        overall_mastery_percent=round(overall_mastery, 1),
        rough_plan=rough_plan,
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
@router.get("/plan/history/{learner_id}")
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


@router.get("/plan-history/{learner_id}")
async def get_plan_history_alias(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Alias endpoint for plan history."""
    return await get_plan_history(learner_id, db)


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

