"""
Learning API: content delivery, test generation, task completion, weekly cycle, dashboard.

This module provides the student-facing learning endpoints that drive the core
weekly cycle after onboarding is complete.
"""
from __future__ import annotations

import json
import logging
import random
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
from app.models.entities import (
    AssessmentResult,
    ChapterProgression,
    EmbeddingChunk,
    LearnerProfile,
    LearnerProfileSnapshot,
    RevisionQueueItem,
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


# ── Pydantic models ──────────────────────────────────────────────────────────

class ContentRequest(BaseModel):
    learner_id: UUID
    chapter_number: int = Field(ge=1, le=14)


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
    test_id: str
    questions: list[TestQuestion]
    time_limit_minutes: int = 20


class TestAnswer(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=3)


class SubmitTestRequest(BaseModel):
    learner_id: UUID
    test_id: str
    answers: list[TestAnswer]


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


class CompleteReadingRequest(BaseModel):
    learner_id: UUID
    task_id: UUID
    time_spent_seconds: int = Field(ge=0)


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


async def _retrieve_chapter_chunks(db: AsyncSession, chapter_number: int, top_k: int = 5) -> list[str]:
    """Retrieve embedded chunks for a specific chapter from pgvector."""
    try:
        stmt = (
            select(EmbeddingChunk)
            .where(EmbeddingChunk.chapter_number == chapter_number)
            .limit(top_k * 3)
        )
        rows = (await db.execute(stmt)).scalars().all()
        if not rows:
            # Fallback: get any chunks
            stmt = select(EmbeddingChunk).where(
                EmbeddingChunk.chapter_number == chapter_number
            ).limit(top_k)
            rows = (await db.execute(stmt)).scalars().all()
        return [r.content for r in rows[:top_k]] if rows else []
    except Exception as exc:
        logger.warning("Chunk retrieval failed for chapter %s: %s", chapter_number, exc)
        return []


# ── In-memory test store (for simplicity; keyed by test_id) ─────────────────
_test_store: dict[str, dict] = {}


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

# 1. Get reading content for a chapter
@router.post("/content", response_model=ContentResponse)
async def get_reading_content(payload: ContentRequest, db: AsyncSession = Depends(get_db)):
    """Generate reading content for a chapter, adapted to student's ability."""
    profile = await _get_profile(db, payload.learner_id)
    ch_info = _chapter_info(payload.chapter_number)
    chapter_name = ch_info["title"]
    subtopics = [s["title"] for s in ch_info.get("subtopics", []) if "Summary" not in s["title"] and "Introduction" not in s["title"]]

    # Determine ability and tone
    ability = profile.cognitive_depth or 0.5
    mastery = (profile.concept_mastery or {}).get(chapter_display_name(payload.chapter_number), 0.5)
    combined_ability = (ability + mastery) / 2
    tone_config = _tone_for_ability(combined_ability)

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
    plan = await _get_plan(db, payload.learner_id)
    week_number = plan.current_week if plan else 1
    ch_info = _chapter_info(payload.chapter_number)
    chapter_name = ch_info["title"]
    chapter_key = chapter_display_name(payload.chapter_number)

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
                    for i, item in enumerate(parsed[:10]):
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
        except Exception as exc:
            logger.warning("LLM test generation failed: %s", exc)

    # Fallback: generate simple questions if LLM failed
    if len(questions) < 5:
        questions = []
        answer_key = {}
        subtopics = [s["title"] for s in ch_info.get("subtopics", [])
                     if "Summary" not in s["title"] and "Introduction" not in s["title"]]
        for i in range(10):
            qid = f"t_{test_id}_q{i+1}"
            topic = subtopics[i % len(subtopics)] if subtopics else chapter_name
            questions.append(TestQuestion(
                question_id=qid,
                prompt=f"Which of the following best describes a key concept in '{topic}'?",
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
        "answer_key": answer_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return GenerateTestResponse(
        learner_id=str(payload.learner_id),
        week_number=week_number,
        chapter=chapter_key,
        test_id=test_id,
        questions=questions,
        time_limit_minutes=20,
    )


# 3. Submit test answers
@router.post("/test/submit", response_model=SubmitTestResponse)
async def submit_chapter_test(payload: SubmitTestRequest, db: AsyncSession = Depends(get_db)):
    """Score a chapter test, apply threshold, update profile and progression."""
    test_data = _test_store.get(payload.test_id)
    if not test_data:
        raise HTTPException(status_code=404, detail="Test not found or expired.")

    answer_key = test_data["answer_key"]
    chapter = test_data["chapter"]

    # Score
    correct = 0
    total = len(answer_key)
    for ans in payload.answers:
        expected = answer_key.get(ans.question_id)
        if expected is not None and ans.selected_index == expected:
            correct += 1

    score = correct / max(total, 1)
    passed = score >= COMPLETION_THRESHOLD

    # Get or create chapter progression
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

    # Decision logic
    if passed:
        cp.status = "completed"
        decision = "chapter_completed"
        message = f"Congratulations! You scored {correct}/{total} ({score*100:.0f}%). Chapter completed! ✅"
    elif cp.attempt_count >= MAX_CHAPTER_ATTEMPTS:
        cp.status = "completed"
        cp.revision_queued = True
        decision = "move_on_revision"
        message = (
            f"You scored {correct}/{total} ({score*100:.0f}%). "
            f"After {cp.attempt_count} attempts, we're moving on. "
            f"This chapter has been added to your revision queue for later review."
        )
        # Add to revision queue
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
        decision = "retry"
        remaining = MAX_CHAPTER_ATTEMPTS - cp.attempt_count
        message = (
            f"You scored {correct}/{total} ({score*100:.0f}%). "
            f"You need {COMPLETION_THRESHOLD*100:.0f}% to pass. "
            f"You have {remaining} more attempt(s). Let's try again with more practice!"
        )

    # Save assessment result
    db.add(AssessmentResult(
        learner_id=payload.learner_id,
        concept=chapter,
        score=score,
        error_type="none" if passed else "below_threshold",
    ))

    # Update profile mastery
    profile = await _get_profile(db, payload.learner_id)
    mastery = dict(profile.concept_mastery or {})
    mastery[chapter] = max(mastery.get(chapter, 0.0), score)
    profile.concept_mastery = mastery

    # Mark test task as done
    test_task = (await db.execute(
        select(Task).where(
            Task.learner_id == payload.learner_id,
            Task.chapter == chapter,
            Task.task_type == "test",
            Task.status != "completed",
        ).order_by(desc(Task.created_at))
    )).scalars().first()
    if test_task:
        test_task.status = "completed"
        test_task.completed_at = datetime.now(timezone.utc)
        db.add(TaskAttempt(
            task_id=test_task.id,
            learner_id=payload.learner_id,
            proof_payload={"score": score, "correct": correct, "total": total, "test_id": payload.test_id},
            accepted=passed or cp.attempt_count >= MAX_CHAPTER_ATTEMPTS,
            reason=decision,
        ))

    await db.commit()

    try:
        await redis_client.delete(f"learning:dashboard:{payload.learner_id}")
    except Exception:
        pass
    _test_store.pop(payload.test_id, None)

    return SubmitTestResponse(
        learner_id=str(payload.learner_id),
        chapter=chapter,
        score=score,
        correct=correct,
        total=total,
        passed=passed,
        attempt_number=cp.attempt_count,
        max_attempts=MAX_CHAPTER_ATTEMPTS,
        decision=decision,
        message=message,
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
            # Reading task
            db.add(Task(
                learner_id=learner_id,
                week_number=new_week,
                chapter=next_ch_key,
                task_type="read",
                title=f"Read: {next_ch_info['title']}",
                sort_order=1,
                status="pending",
                is_locked=False,
                proof_policy={"type": "reading_time", "min_seconds": 180},
            ))
            # Test task
            db.add(Task(
                learner_id=learner_id,
                week_number=new_week,
                chapter=next_ch_key,
                task_type="test",
                title=f"Test: {next_ch_info['title']}",
                sort_order=2,
                status="pending",
                is_locked=False,
                proof_policy={"type": "test_score", "threshold": COMPLETION_THRESHOLD},
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
        current_tasks.append({
            "task_id": str(t.id),
            "chapter": t.chapter,
            "task_type": t.task_type,
            "title": t.title,
            "status": t.status,
            "is_locked": t.is_locked,
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
