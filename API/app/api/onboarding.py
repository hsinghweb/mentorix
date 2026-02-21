from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.cache import redis_client
from app.memory.database import get_db
from app.models.entities import ChapterProgression, EmbeddingChunk, Learner, LearnerProfile, WeeklyPlan
from app.schemas.onboarding import (
    ChapterPlan,
    DiagnosticQuestion,
    OnboardingStartRequest,
    OnboardingStartResponse,
    OnboardingSubmitRequest,
    OnboardingSubmitResponse,
    WeeklyPlanResponse,
    WeeklyReplanRequest,
    WeeklyReplanResponse,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _extract_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return (parts[0] if parts else "").strip() or "Review the core chapter concept."


def _extract_keywords(text: str, limit: int = 5) -> list[str]:
    words = re.findall(r"[A-Za-z0-9]+", (text or "").lower())
    seen: list[str] = []
    for word in words:
        if len(word) < 4:
            continue
        if word in seen:
            continue
        seen.append(word)
        if len(seen) >= limit:
            break
    return seen or ["concept", "chapter"]


def _build_questions(chunks: list[EmbeddingChunk]) -> tuple[list[DiagnosticQuestion], dict[str, str]]:
    questions: list[DiagnosticQuestion] = []
    answer_key: dict[str, str] = {}
    chapter_pool = sorted({c.chapter_number for c in chunks if c.chapter_number is not None}) or [1, 2, 3]

    for idx, chunk in enumerate(chunks[:9]):
        sentence = _extract_sentence(chunk.content)
        chapter_number = chunk.chapter_number or 1

        # Q1: True/False grounded directly in retrieved chunk sentence.
        tf_id = f"q_tf_{idx}"
        questions.append(
            DiagnosticQuestion(
                question_id=tf_id,
                question_type="true_false",
                chapter_number=chapter_number,
                prompt=f'True or False: "{sentence}"',
                options=["true", "false"],
            )
        )
        answer_key[tf_id] = "true"

        # Q2: Fill in the blank using a keyword from the chunk.
        keywords = _extract_keywords(sentence, limit=3)
        blank_word = keywords[-1]
        blank_prompt = re.sub(rf"\b{re.escape(blank_word)}\b", "_____", sentence, count=1, flags=re.IGNORECASE)
        fb_id = f"q_fb_{idx}"
        questions.append(
            DiagnosticQuestion(
                question_id=fb_id,
                question_type="fill_blank",
                chapter_number=chapter_number,
                prompt=f"Fill in the blank: {blank_prompt}",
                options=[],
            )
        )
        answer_key[fb_id] = blank_word.lower()

        # Q3: MCQ for chapter linkage.
        distractors = [str(ch) for ch in chapter_pool if ch != chapter_number][:3]
        options = [str(chapter_number), *distractors]
        options = options[:4]
        mcq_id = f"q_mcq_{idx}"
        questions.append(
            DiagnosticQuestion(
                question_id=mcq_id,
                question_type="mcq",
                chapter_number=chapter_number,
                prompt=f"This concept snippet is most aligned to which chapter number? '{sentence[:140]}'",
                options=options,
            )
        )
        answer_key[mcq_id] = str(chapter_number)

    return questions, answer_key


async def _get_diagnostic_chunks(db: AsyncSession) -> list[EmbeddingChunk]:
    rows = (
        await db.execute(
            select(EmbeddingChunk)
            .where(EmbeddingChunk.doc_type == "chapter")
            .order_by(EmbeddingChunk.chapter_number.asc(), EmbeddingChunk.chunk_index.asc())
            .limit(9)
        )
    ).scalars()
    return list(rows)


def _build_rough_plan(chapter_scores: dict[str, float], exam_in_months: int) -> tuple[list[ChapterPlan], ChapterPlan]:
    chapter_count = 14
    avg_score = (sum(chapter_scores.values()) / len(chapter_scores)) if chapter_scores else 0.5
    extra_weeks = max(0, min(6, int((0.65 - avg_score) * 10)))
    target_weeks = max(14, min(max(14, exam_in_months * 4), 20 + extra_weeks))

    weak_chapters = {k for k, v in chapter_scores.items() if v < 0.60}
    plan: list[ChapterPlan] = []
    chapter_index = 1
    for week in range(1, target_weeks + 1):
        if chapter_index <= chapter_count:
            chapter_name = f"Chapter {chapter_index}"
            focus = "learn + practice"
            if chapter_name in weak_chapters:
                focus = "reinforce fundamentals + extra examples"
            plan.append(ChapterPlan(week=week, chapter=chapter_name, focus=focus))
            chapter_index += 1
            continue
        plan.append(ChapterPlan(week=week, chapter="Revision", focus="mixed revision and weak-topic reinforcement"))

    first_week = plan[0]
    return plan, first_week


@router.post("/start", response_model=OnboardingStartResponse)
async def start_onboarding(payload: OnboardingStartRequest, db: AsyncSession = Depends(get_db)):
    learner = Learner(name=payload.name.strip(), grade_level=payload.grade_level)
    db.add(learner)
    await db.flush()

    profile = LearnerProfile(
        learner_id=learner.id,
        concept_mastery={},
        retention_decay=0.1,
        cognitive_depth=0.5,
        engagement_score=0.5,
    )
    db.add(profile)
    await db.commit()

    chunks = await _get_diagnostic_chunks(db)
    if not chunks:
        raise HTTPException(status_code=400, detail="Grounding chunks unavailable. Run /grounding/ingest first.")

    questions, answer_key = _build_questions(chunks)
    attempt_id = str(uuid4())
    redis_key = f"onboarding:attempt:{attempt_id}"
    await redis_client.set(redis_key, json.dumps({"answer_key": answer_key, "exam_in_months": payload.exam_in_months}), ex=7200)

    return OnboardingStartResponse(
        learner_id=learner.id,
        diagnostic_attempt_id=attempt_id,
        generated_at=datetime.now(timezone.utc),
        questions=questions,
    )


@router.post("/submit", response_model=OnboardingSubmitResponse)
async def submit_onboarding(payload: OnboardingSubmitRequest, db: AsyncSession = Depends(get_db)):
    redis_key = f"onboarding:attempt:{payload.diagnostic_attempt_id}"
    attempt_raw = await redis_client.get(redis_key)
    if not attempt_raw:
        raise HTTPException(status_code=404, detail="Diagnostic attempt not found or expired.")

    attempt = json.loads(attempt_raw)
    answer_key: dict[str, str] = attempt.get("answer_key", {})
    exam_in_months = int(attempt.get("exam_in_months", 10))

    if not answer_key:
        raise HTTPException(status_code=400, detail="Diagnostic answer key is unavailable.")

    total = len(answer_key)
    correct = 0
    chapter_total: dict[str, int] = {}
    chapter_correct: dict[str, int] = {}

    for item in payload.answers:
        expected = answer_key.get(item.question_id)
        if expected is None:
            continue
        answer = (item.answer or "").strip().lower()
        is_correct = answer == str(expected).strip().lower()
        if is_correct:
            correct += 1

        chapter_match = re.search(r"_(\d+)$", item.question_id)
        chapter_key = "Chapter 1"
        if chapter_match:
            # Diagnostics are chunk-indexed; map index to nearby chapter bucket.
            idx = int(chapter_match.group(1))
            chapter_key = f"Chapter {min(14, (idx // 3) + 1)}"

        chapter_total[chapter_key] = chapter_total.get(chapter_key, 0) + 1
        if is_correct:
            chapter_correct[chapter_key] = chapter_correct.get(chapter_key, 0) + 1

    score = float(correct / max(1, total))
    chapter_scores = {
        chapter: float(chapter_correct.get(chapter, 0) / max(1, q_count))
        for chapter, q_count in chapter_total.items()
    }

    learner = (await db.execute(select(Learner).where(Learner.id == payload.learner_id))).scalar_one_or_none()
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == payload.learner_id))
    ).scalar_one_or_none()
    if learner is None or profile is None:
        raise HTTPException(status_code=404, detail="Learner profile not found.")

    profile.concept_mastery = chapter_scores
    profile.cognitive_depth = max(0.1, min(1.0, 0.35 + (0.65 * score)))
    engagement_norm = min(1.0, payload.time_spent_minutes / 60.0)
    profile.engagement_score = max(0.1, min(1.0, engagement_norm))
    profile.last_updated = datetime.now(timezone.utc)
    await db.commit()

    rough_plan, week_1 = _build_rough_plan(chapter_scores, exam_in_months=exam_in_months)
    await redis_client.delete(redis_key)

    db.add(
        WeeklyPlan(
            learner_id=payload.learner_id,
            status="active",
            current_week=1,
            total_weeks=len(rough_plan),
            plan_payload={"rough_plan": [item.model_dump() for item in rough_plan]},
        )
    )
    await db.commit()

    return OnboardingSubmitResponse(
        learner_id=payload.learner_id,
        score=score,
        chapter_scores=chapter_scores,
        profile_snapshot={
            "cognitive_depth": profile.cognitive_depth,
            "engagement_score": profile.engagement_score,
            "chapter_mastery": chapter_scores,
        },
        rough_plan=rough_plan,
        current_week_schedule=week_1,
    )


@router.get("/plan/{learner_id}", response_model=WeeklyPlanResponse)
async def get_latest_plan(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.learner_id == learner_id)
            .order_by(WeeklyPlan.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No weekly plan found for learner.")

    rough = row.plan_payload.get("rough_plan", []) if isinstance(row.plan_payload, dict) else []
    parsed = [ChapterPlan(**item) for item in rough]
    return WeeklyPlanResponse(
        learner_id=row.learner_id,
        current_week=row.current_week,
        total_weeks=row.total_weeks,
        rough_plan=parsed,
    )


@router.post("/weekly-replan", response_model=WeeklyReplanResponse)
async def weekly_replan(payload: WeeklyReplanRequest, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == payload.learner_id))).scalar_one_or_none()
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == payload.learner_id))
    ).scalar_one_or_none()
    if learner is None or profile is None:
        raise HTTPException(status_code=404, detail="Learner profile not found.")

    chapter = payload.evaluation.chapter.strip()
    score = payload.evaluation.score
    threshold = payload.threshold
    max_attempts = payload.max_attempts

    progress = (
        await db.execute(
            select(ChapterProgression).where(
                ChapterProgression.learner_id == payload.learner_id,
                ChapterProgression.chapter == chapter,
            )
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = ChapterProgression(
            learner_id=payload.learner_id,
            chapter=chapter,
            attempt_count=0,
            best_score=0.0,
            last_score=0.0,
            status="in_progress",
            revision_queued=False,
        )
        db.add(progress)
        await db.flush()

    prev_score = float(progress.last_score or 0.0)
    attempt_count = int(progress.attempt_count) + 1
    best_score = max(float(progress.best_score or 0.0), score)
    improved = score > (prev_score + 0.05)

    decision = "repeat_chapter"
    reason = "Below threshold. Repeat with reinforced explanation and additional examples."

    if score >= threshold:
        decision = "proceed_next_chapter"
        reason = "Threshold met. Proceed to next chapter."
    elif attempt_count >= max_attempts:
        decision = "proceed_with_revision_queue"
        reason = "Timeout reached. Proceed to next chapter and queue this chapter for revision."
    elif attempt_count >= 2 and improved:
        decision = "proceed_with_revision_queue"
        reason = "Below threshold but improving trajectory detected. Proceed while scheduling revision."

    revision_queue = []
    if decision in ("proceed_with_revision_queue",) and chapter not in revision_queue:
        revision_queue.append(chapter)

    # Update dynamic mastery profile at chapter level.
    mastery = dict(profile.concept_mastery or {})
    mastery[chapter] = score
    profile.concept_mastery = mastery
    profile.last_updated = datetime.now(timezone.utc)

    progress.attempt_count = attempt_count
    progress.best_score = best_score
    progress.last_score = score
    progress.status = decision
    progress.revision_queued = decision == "proceed_with_revision_queue"
    progress.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return WeeklyReplanResponse(
        learner_id=payload.learner_id,
        chapter=chapter,
        score=score,
        threshold=threshold,
        attempt_count=attempt_count,
        decision=decision,
        reason=reason,
        revision_queue=revision_queue,
    )
