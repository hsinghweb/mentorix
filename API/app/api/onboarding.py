from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt_auth import create_token
from app.core.logging import DOMAIN_ONBOARDING, get_domain_logger
from app.memory.cache import redis_client
from app.memory.database import get_db
from app.models.entities import (
    ChapterProgression,
    EmbeddingChunk,
    EngagementEvent,
    Learner,
    LearnerProfile,
    LearnerProfileSnapshot,
    PolicyViolation,
    RevisionPolicyState,
    RevisionQueueItem,
    AssessmentResult,
    StudentAuth,
    Task,
    TaskAttempt,
    WeeklyForecast,
    WeeklyPlan,
    WeeklyPlanVersion,
)
from app.agents.diagnostic_mcq import generate_diagnostic_mcq
from app.data.syllabus_structure import get_syllabus_for_api
from app.schemas.onboarding import (
    ChapterPlan,
    ChapterAdvanceRequest,
    ChapterAdvanceResponse,
    DiagnosticQuestion,
    DiagnosticQuestionsRequest,
    RevisionPolicyStateResponse,
    OnboardingStartRequest,
    OnboardingStartResponse,
    RevisionQueueItemResponse,
    TaskCompletionRequest,
    TaskCompletionResponse,
    TaskItem,
    OnboardingSubmitRequest,
    OnboardingSubmitResponse,
    WeeklyPlanResponse,
    WeeklyReplanRequest,
    WeeklyReplanResponse,
    EngagementEventRequest,
    EngagementEventResponse,
    EngagementSummaryResponse,
    LearnerStandResponse,
    EvaluationAnalyticsResponse,
    DailyPlanResponse,
    ForecastHistoryItem,
    ForecastHistoryResponse,
    StudentLearningMetricsResponse,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
logger = get_domain_logger(__name__, DOMAIN_ONBOARDING)
TIMELINE_MIN_WEEKS = 14
TIMELINE_MAX_WEEKS = 28
_idempotency_response_cache: dict[str, dict] = {}


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


async def _get_idempotent_response(cache_key: str) -> dict | None:
    try:
        raw = await redis_client.get(cache_key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis unavailable for idempotency read. Using degraded cache: %s", exc)
    return _idempotency_response_cache.get(cache_key)


async def _set_idempotent_response(cache_key: str, payload: dict) -> None:
    _idempotency_response_cache[cache_key] = payload
    try:
        await redis_client.set(cache_key, json.dumps(payload), ex=3600)
    except Exception as exc:
        logger.warning("Redis unavailable for idempotency write. Using degraded cache: %s", exc)


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


def _clamp_weeks(weeks: int) -> int:
    return max(TIMELINE_MIN_WEEKS, min(TIMELINE_MAX_WEEKS, int(weeks)))


def _recommend_timeline_weeks(selected_timeline_weeks: int, score: float) -> tuple[int, str]:
    selected = _clamp_weeks(selected_timeline_weeks)
    if score >= 0.85:
        recommended = _clamp_weeks(selected - 1)
        return recommended, "Strong diagnostic performance. You can target a slightly faster completion plan."
    if score >= 0.70:
        return selected, "Good baseline. Your selected timeline looks realistic."
    if score >= 0.55:
        recommended = _clamp_weeks(selected + 2)
        return recommended, "Moderate baseline. A slightly extended timeline should improve retention."
    if score >= 0.40:
        recommended = _clamp_weeks(selected + 4)
        return recommended, "Foundation needs reinforcement. A longer timeline is recommended for confidence."
    recommended = _clamp_weeks(selected + 6)
    return recommended, "Strongly recommended to extend timeline and focus on fundamentals first."


def _pacing_status(delta_weeks: int) -> str:
    if delta_weeks <= -1:
        return "ahead"
    if delta_weeks >= 2:
        return "behind"
    return "on_track"


def _weekly_forecast_adjustment(*, decision: str, score: float, threshold: float) -> int:
    if decision == "repeat_chapter":
        return 1
    if decision == "proceed_with_revision_queue" and score < threshold:
        return 1
    if decision == "proceed_next_chapter" and score >= min(1.0, threshold + 0.20):
        return -1
    return 0


def _adaptive_pace_extend_compress(
    selected_weeks: int, current_forecast_weeks: int
) -> int:
    """Adaptive pace: behind -> extend (+1 week); ahead -> compress (-1 week, not below min). Returns delta to add."""
    delta = current_forecast_weeks - selected_weeks
    if delta >= 2:
        return 1  # behind: extend
    if delta <= -1 and current_forecast_weeks > TIMELINE_MIN_WEEKS:
        return -1  # ahead: compress carefully (don't go below min)
    return 0


async def _upsert_revision_queue_item(
    *, db: AsyncSession, learner_id: UUID, chapter: str, reason: str, priority: int = 1
) -> None:
    existing = (
        await db.execute(
            select(RevisionQueueItem).where(
                RevisionQueueItem.learner_id == learner_id,
                RevisionQueueItem.chapter == chapter,
                RevisionQueueItem.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.priority = max(existing.priority, priority)
        existing.reason = reason
        existing.updated_at = datetime.now(timezone.utc)
        return
    db.add(
        RevisionQueueItem(
            learner_id=learner_id,
            chapter=chapter,
            status="pending",
            priority=priority,
            reason=reason,
        )
    )


def _log_policy_violation(
    *,
    db: AsyncSession,
    learner_id: UUID,
    policy_code: str,
    chapter: str | None,
    details: dict,
) -> None:
    db.add(
        PolicyViolation(
            learner_id=learner_id,
            policy_code=policy_code,
            chapter=chapter,
            details=details,
        )
    )


async def _compute_retention_score(db: AsyncSession, learner_id: UUID) -> float:
    recent = (
        await db.execute(
            select(AssessmentResult.score)
            .where(AssessmentResult.learner_id == learner_id)
            .order_by(desc(AssessmentResult.timestamp))
            .limit(20)
        )
    ).scalars().all()
    if not recent:
        return 0.5
    return max(0.0, min(1.0, float(sum(recent) / len(recent))))


def _profile_snapshot_payload(profile: LearnerProfile) -> dict:
    return {
        "concept_mastery": dict(profile.concept_mastery or {}),
        "retention_decay": float(profile.retention_decay or 0.0),
        "cognitive_depth": float(profile.cognitive_depth or 0.0),
        "engagement_score": float(profile.engagement_score or 0.0),
        "math_9_percent": profile.math_9_percent,
        "onboarding_diagnostic_score": profile.onboarding_diagnostic_score,
        "selected_timeline_weeks": profile.selected_timeline_weeks,
        "recommended_timeline_weeks": profile.recommended_timeline_weeks,
        "current_forecast_weeks": profile.current_forecast_weeks,
        "timeline_delta_weeks": profile.timeline_delta_weeks,
        "last_updated": profile.last_updated.isoformat() if profile.last_updated else None,
    }


def _persist_profile_snapshot(
    db: AsyncSession, learner_id: UUID, profile: LearnerProfile, reason: str, extra: dict | None = None
) -> None:
    payload = _profile_snapshot_payload(profile)
    if isinstance(extra, dict) and extra:
        payload["extra"] = extra
    db.add(
        LearnerProfileSnapshot(
            learner_id=learner_id,
            reason=reason,
            payload=payload,
        )
    )


def _log_engagement_event(
    db: AsyncSession, learner_id: UUID, event_type: str, duration_minutes: int = 0, details: dict | None = None
) -> None:
    db.add(
        EngagementEvent(
            learner_id=learner_id,
            event_type=event_type,
            duration_minutes=max(0, int(duration_minutes)),
            details=details or {},
        )
    )


async def _compute_adherence_rate_week(db: AsyncSession, learner_id: UUID) -> float:
    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    tasks = (
        await db.execute(
            select(Task).where(
                Task.learner_id == learner_id,
                Task.created_at >= week_start,
            )
        )
    ).scalars().all()
    if not tasks:
        return 0.0
    completed = len([t for t in tasks if t.status == "completed"])
    return round(float(completed / max(1, len(tasks))), 3)


async def _engagement_minutes_since(db: AsyncSession, learner_id: UUID, since: datetime) -> int:
    rows = (
        await db.execute(
            select(EngagementEvent.duration_minutes).where(
                EngagementEvent.learner_id == learner_id,
                EngagementEvent.created_at >= since,
            )
        )
    ).scalars().all()
    return int(sum(int(v or 0) for v in rows))


async def _update_profile_after_outcome(
    db: AsyncSession,
    learner_id: UUID,
    profile: LearnerProfile,
    *,
    reason: str,
    mastery_update: dict | None = None,
    engagement_minutes: int = 0,
    extra: dict | None = None,
) -> None:
    if isinstance(mastery_update, dict) and mastery_update:
        merged = dict(profile.concept_mastery or {})
        merged.update(mastery_update)
        profile.concept_mastery = merged
    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    minutes_week = await _engagement_minutes_since(db, learner_id, since=week_start)
    adherence = await _compute_adherence_rate_week(db, learner_id)
    normalized_minutes = min(1.0, float(max(0, minutes_week + max(0, int(engagement_minutes))) / 300.0))
    profile.engagement_score = round(max(0.1, min(1.0, (0.7 * normalized_minutes) + (0.3 * adherence))), 3)
    profile.last_updated = datetime.now(timezone.utc)
    _persist_profile_snapshot(
        db=db,
        learner_id=learner_id,
        profile=profile,
        reason=reason,
        extra={"adherence_rate_week": adherence, "engagement_minutes_week": minutes_week, **(extra or {})},
    )


async def _compute_login_streak_days(db: AsyncSession, learner_id: UUID) -> int:
    rows = (
        await db.execute(
            select(EngagementEvent.created_at)
            .where(
                EngagementEvent.learner_id == learner_id,
                EngagementEvent.event_type == "login",
            )
            .order_by(EngagementEvent.created_at.desc())
            .limit(60)
        )
    ).scalars().all()
    if not rows:
        return 0
    dates = sorted({dt.astimezone(timezone.utc).date() for dt in rows}, reverse=True)
    streak = 0
    cursor = datetime.now(timezone.utc).date()
    for login_day in dates:
        if login_day == cursor:
            streak += 1
            cursor = cursor - timedelta(days=1)
            continue
        if streak == 0 and login_day == cursor - timedelta(days=1):
            streak += 1
            cursor = login_day - timedelta(days=1)
            continue
        if login_day < cursor:
            break
    return streak


def _derive_recommendations(*, risk_level: str, misconception_patterns: list[dict], trend: str) -> list[str]:
    recommendations: list[str] = []
    if risk_level == "high":
        recommendations.append("Run a reinforced remediation cycle with worked examples before advancing pace.")
    elif risk_level == "medium":
        recommendations.append("Keep chapter progression controlled and add one focused revision block this week.")
    else:
        recommendations.append("Maintain current pace and include one challenge task to consolidate mastery.")
    if trend == "down":
        recommendations.append("Score trend is declining; schedule a short corrective quiz within 48 hours.")
    if misconception_patterns:
        top = misconception_patterns[0]["error_type"]
        recommendations.append(f"Prioritize fixing '{top}' mistakes in the next practice plan.")
    return recommendations


async def _build_evaluation_analytics(db: AsyncSession, learner_id: UUID) -> dict:
    results = (
        await db.execute(
            select(AssessmentResult)
            .where(AssessmentResult.learner_id == learner_id)
            .order_by(AssessmentResult.timestamp.desc())
            .limit(30)
        )
    ).scalars().all()
    scores = [float(r.score) for r in reversed(results)]
    response_times = [float(r.response_time) for r in reversed(results)]
    error_types = [str(r.error_type or "none").lower() for r in results]
    avg_score = float(sum(scores) / max(1, len(scores)))
    trend = "flat"
    if len(scores) > 1:
        trend = "up" if scores[-1] >= scores[0] else "down"
    misconceptions: dict[str, int] = {}
    for error in error_types:
        if error == "none":
            continue
        misconceptions[error] = misconceptions.get(error, 0) + 1
    misconception_patterns = [
        {"error_type": key, "count": value}
        for key, value in sorted(misconceptions.items(), key=lambda item: item[1], reverse=True)
    ]
    risk_level = "low"
    avg_response = float(sum(response_times) / max(1, len(response_times))) if response_times else 0.0
    if avg_score < 0.5 or (trend == "down" and avg_score < 0.65):
        risk_level = "high"
    elif avg_score < 0.75 or avg_response > 20.0:
        risk_level = "medium"
    chapter_rows = (
        await db.execute(
            select(ChapterProgression)
            .where(ChapterProgression.learner_id == learner_id)
            .order_by(ChapterProgression.updated_at.desc())
            .limit(20)
        )
    ).scalars().all()
    chapter_attempt_summary = [
        {
            "chapter": row.chapter,
            "attempt_count": int(row.attempt_count),
            "best_score": float(row.best_score),
            "last_score": float(row.last_score),
            "status": row.status,
            "revision_queued": bool(row.revision_queued),
        }
        for row in chapter_rows
    ]
    return {
        "objective_evaluation": {
            "attempted_questions": len(scores),
            "latest_score": round(scores[-1], 4) if scores else 0.0,
            "avg_score": round(avg_score, 4),
            "avg_response_time": round(avg_response, 4),
            "score_trend": trend,
        },
        "misconception_patterns": misconception_patterns,
        "risk_level": risk_level,
        "recommendations": _derive_recommendations(
            risk_level=risk_level, misconception_patterns=misconception_patterns, trend=trend
        ),
        "chapter_attempt_summary": chapter_attempt_summary,
    }


async def _upsert_revision_policy_state(db: AsyncSession, learner_id: UUID) -> RevisionPolicyState:
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Learner profile not found.")

    state = (
        await db.execute(select(RevisionPolicyState).where(RevisionPolicyState.learner_id == learner_id))
    ).scalar_one_or_none()
    if state is None:
        state = RevisionPolicyState(learner_id=learner_id)
        db.add(state)
        await db.flush()

    mastery = dict(profile.concept_mastery or {})
    covered_chapters = len([k for k, v in mastery.items() if str(k).startswith("Chapter") and float(v) > 0.0])
    weak_zones = [k for k, v in mastery.items() if str(k).startswith("Chapter") and float(v) < 0.60]
    pending_revision = (
        await db.execute(
            select(RevisionQueueItem).where(
                RevisionQueueItem.learner_id == learner_id,
                RevisionQueueItem.status == "pending",
            )
        )
    ).scalars().all()
    pending_chapters = sorted({item.chapter for item in pending_revision})
    retention_score = await _compute_retention_score(db, learner_id)

    now = datetime.now(timezone.utc)
    pass1_completed = covered_chapters >= 14
    if pass1_completed and state.pass1_completed_at is None:
        state.pass1_completed_at = now

    pass2_completed = bool(state.pass1_completed_at) and not pending_chapters and retention_score >= 0.70
    if pass2_completed and state.pass2_completed_at is None:
        state.pass2_completed_at = now

    if not pass1_completed:
        active_pass = 1
        next_actions = [
            "Complete remaining chapters to finish first full syllabus pass.",
            "Keep weekly chapter completion above threshold.",
        ]
    elif not pass2_completed:
        active_pass = 2
        next_actions = [
            "Clear pending revision queue chapters.",
            "Improve retention score to at least 0.70.",
        ]
    else:
        active_pass = 3
        next_actions = [
            "Focus only on weak-zone chapters and concepts.",
            "Run targeted revision cycles before final assessments.",
        ]

    weak_zone_list = sorted(set(weak_zones + pending_chapters))
    state.active_pass = active_pass
    state.retention_score = retention_score
    state.weak_zones = {"chapters": weak_zone_list}
    state.next_actions = {"items": next_actions}
    state.updated_at = now
    await db.commit()
    await db.refresh(state)
    return state


def _default_week_tasks(*, learner_id: UUID, chapter: str, week_number: int) -> list[Task]:
    return [
        Task(
            learner_id=learner_id,
            week_number=week_number,
            chapter=chapter,
            task_type="read",
            title=f"{chapter}: Read concept notes",
            sort_order=1,
            status="pending",
            is_locked=True,
            proof_policy={"min_reading_minutes": 8},
        ),
        Task(
            learner_id=learner_id,
            week_number=week_number,
            chapter=chapter,
            task_type="practice",
            title=f"{chapter}: Practice worksheet",
            sort_order=2,
            status="pending",
            is_locked=True,
            proof_policy={"min_reading_minutes": 12},
        ),
        Task(
            learner_id=learner_id,
            week_number=week_number,
            chapter=chapter,
            task_type="test",
            title=f"{chapter}: Weekly quiz attempt",
            sort_order=3,
            status="pending",
            is_locked=True,
            proof_policy={"require_test_attempt_id": True},
        ),
    ]


def _to_task_item(task: Task) -> TaskItem:
    return TaskItem(
        task_id=task.id,
        chapter=task.chapter,
        task_type=task.task_type,
        title=task.title,
        week_number=task.week_number,
        sort_order=task.sort_order,
        status=task.status,
        is_locked=bool(task.is_locked),
        proof_policy=task.proof_policy or {},
    )


def _daily_breakdown_from_tasks(tasks: list[Task], week_number: int) -> list[dict]:
    day_slots = ["Mon", "Wed", "Fri", "Sat", "Sun"]
    if not tasks:
        return []
    breakdown = []
    for idx, task in enumerate(tasks):
        proof = task.proof_policy or {}
        breakdown.append(
            {
                "day": day_slots[idx % len(day_slots)],
                "week_number": week_number,
                "task_id": str(task.id),
                "task_type": task.task_type,
                "title": task.title,
                "status": task.status,
                "proof_required": bool(proof),
            }
        )
    return breakdown


async def _create_plan_version(*, db: AsyncSession, plan: WeeklyPlan, reason: str) -> None:
    latest_version = (
        await db.execute(
            select(WeeklyPlanVersion.version_number)
            .where(WeeklyPlanVersion.weekly_plan_id == plan.id)
            .order_by(WeeklyPlanVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    version_number = int(latest_version or 0) + 1
    db.add(
        WeeklyPlanVersion(
            weekly_plan_id=plan.id,
            learner_id=plan.learner_id,
            version_number=version_number,
            current_week=plan.current_week,
            plan_payload=plan.plan_payload if isinstance(plan.plan_payload, dict) else {},
            reason=reason,
        )
    )


def _build_rough_plan(chapter_scores: dict[str, float], target_weeks: int) -> tuple[list[ChapterPlan], ChapterPlan]:
    chapter_count = 14
    target_weeks = _clamp_weeks(target_weeks)

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
        selected_timeline_weeks=_clamp_weeks(payload.selected_timeline_weeks),
        recommended_timeline_weeks=None,
        current_forecast_weeks=None,
        timeline_delta_weeks=None,
    )
    db.add(profile)
    _log_engagement_event(
        db=db,
        learner_id=learner.id,
        event_type="login",
        duration_minutes=0,
        details={"source": "onboarding_start"},
    )
    await db.commit()

    chunks = await _get_diagnostic_chunks(db)
    if not chunks:
        raise HTTPException(status_code=400, detail="Grounding chunks unavailable. Run /grounding/ingest first.")

    questions, answer_key = _build_questions(chunks)
    # For the generic onboarding diagnostic, cap the number of questions at 25 so the UI and scoring stay aligned.
    if len(questions) > 25:
        questions = questions[:25]
        answer_key = {q.question_id: answer_key.get(q.question_id, "") for q in questions}
    attempt_id = str(uuid4())
    redis_key = f"onboarding:attempt:{attempt_id}"
    await redis_client.set(
        redis_key,
        json.dumps(
            {
                "answer_key": answer_key,
                "exam_in_months": payload.exam_in_months,
                "selected_timeline_weeks": _clamp_weeks(payload.selected_timeline_weeks),
            }
        ),
        ex=7200,
    )

    return OnboardingStartResponse(
        learner_id=learner.id,
        diagnostic_attempt_id=attempt_id,
        generated_at=datetime.now(timezone.utc),
        questions=questions,
    )


@router.post("/diagnostic-questions", response_model=OnboardingStartResponse)
async def get_diagnostic_questions(payload: DiagnosticQuestionsRequest, db: AsyncSession = Depends(get_db)):
    """Return 25 MCQs: either for existing learner_id or for signup_draft_id (account created after test)."""
    use_draft = (payload.signup_draft_id or "").strip()
    use_learner = payload.learner_id
    if use_draft and use_learner:
        raise HTTPException(status_code=400, detail="Provide either learner_id or signup_draft_id, not both.")
    if not use_draft and not use_learner:
        raise HTTPException(status_code=400, detail="Provide learner_id or signup_draft_id.")

    selected_timeline_weeks = TIMELINE_MIN_WEEKS
    if use_learner:
        learner = (await db.execute(select(Learner).where(Learner.id == use_learner))).scalar_one_or_none()
        profile = (
            await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == use_learner))
        ).scalar_one_or_none()
        if not learner or not profile:
            raise HTTPException(status_code=404, detail="Learner not found.")
        existing_plan = (
            await db.execute(
                select(WeeklyPlan).where(WeeklyPlan.learner_id == use_learner).limit(1)
            )
        ).scalar_one_or_none()
        if existing_plan:
            raise HTTPException(status_code=400, detail="Onboarding already completed; plan exists.")
        selected_timeline_weeks = _clamp_weeks(profile.selected_timeline_weeks or TIMELINE_MIN_WEEKS)
    else:
        draft_raw = await redis_client.get(f"signup:draft:{use_draft}")
        if not draft_raw:
            raise HTTPException(status_code=404, detail="Signup session expired. Please start signup again.")
        draft = json.loads(draft_raw)
        selected_timeline_weeks = _clamp_weeks(int(draft.get("selected_timeline_weeks", TIMELINE_MIN_WEEKS)))

    from app.data.diagnostic_question_sets import get_random_diagnostic_set

    questions, answer_key = get_random_diagnostic_set()
    if len(questions) < 25:
        if use_learner:
            profile = (await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == use_learner))).scalar_one_or_none()
            math_9_percent = (profile.math_9_percent if profile else None) or 0
        else:
            math_9_percent = int(draft.get("math_9_percent", 0))
        questions, answer_key = await generate_diagnostic_mcq(math_9_percent=math_9_percent)
        if len(questions) < 10:
            chunks = await _get_diagnostic_chunks(db)
            if not chunks:
                raise HTTPException(status_code=503, detail="Could not generate diagnostic questions.")
            questions, answer_key = _build_questions(chunks)
    if len(questions) > 25:
        questions = questions[:25]
        answer_key = {q.question_id: answer_key.get(q.question_id, "") for q in questions}

    chapter_map = {q.question_id: f"Chapter {q.chapter_number or 1}" for q in questions}

    attempt_id = str(uuid4())
    redis_key = f"onboarding:attempt:{attempt_id}"
    attempt_payload = {
        "answer_key": answer_key,
        "selected_timeline_weeks": selected_timeline_weeks,
        "chapter_map": chapter_map,
    }
    if use_draft:
        attempt_payload["signup_draft_id"] = use_draft
    await redis_client.set(redis_key, json.dumps(attempt_payload), ex=7200)

    return OnboardingStartResponse(
        learner_id=use_learner,
        signup_draft_id=use_draft if use_draft else None,
        diagnostic_attempt_id=attempt_id,
        generated_at=datetime.now(timezone.utc),
        questions=questions,
    )


@router.post("/submit", response_model=OnboardingSubmitResponse)
async def submit_onboarding(payload: OnboardingSubmitRequest, db: AsyncSession = Depends(get_db)):
    use_draft = (payload.signup_draft_id or "").strip()
    use_learner_id = payload.learner_id
    if use_draft and use_learner_id:
        raise HTTPException(status_code=400, detail="Provide either learner_id or signup_draft_id, not both.")
    if not use_draft and not use_learner_id:
        raise HTTPException(status_code=400, detail="Provide learner_id or signup_draft_id.")

    idempotency_cache_key = None
    if (payload.idempotency_key or "").strip():
        idempotency_cache_key = (
            f"idempotency:onboarding-submit:{use_learner_id or use_draft}:{payload.diagnostic_attempt_id}:{payload.idempotency_key.strip()}"
        )
        cached = await _get_idempotent_response(idempotency_cache_key)
        if isinstance(cached, dict):
            return OnboardingSubmitResponse(**cached)

    redis_key = f"onboarding:attempt:{payload.diagnostic_attempt_id}"
    attempt_raw = await redis_client.get(redis_key)
    if not attempt_raw:
        raise HTTPException(status_code=404, detail="Diagnostic attempt not found or expired.")

    attempt = json.loads(attempt_raw)
    answer_key: dict[str, str] = attempt.get("answer_key", {})
    selected_timeline_weeks = _clamp_weeks(int(attempt.get("selected_timeline_weeks", TIMELINE_MIN_WEEKS)))
    chapter_map: dict[str, str] = attempt.get("chapter_map") or {}

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

        chapter_key = chapter_map.get(item.question_id)
        if not chapter_key:
            chapter_match = re.search(r"_(\d+)$", item.question_id)
            if chapter_match:
                idx = int(chapter_match.group(1))
                chapter_key = f"Chapter {min(14, (idx // 3) + 1)}"
            else:
                chapter_key = "Chapter 1"
        chapter_total[chapter_key] = chapter_total.get(chapter_key, 0) + 1
        if is_correct:
            chapter_correct[chapter_key] = chapter_correct.get(chapter_key, 0) + 1

    score = float(correct / max(1, total))
    chapter_scores = {
        ch: float(chapter_correct.get(ch, 0) / max(1, q_count))
        for ch, q_count in chapter_total.items()
    }
    correct_out_of_total = f"{correct} / {total}"

    if use_draft:
        draft_raw = await redis_client.get(f"signup:draft:{use_draft}")
        if not draft_raw:
            raise HTTPException(status_code=404, detail="Signup session expired. Please start signup again.")
        draft = json.loads(draft_raw)
        from datetime import date

        learner = Learner(name=draft["name"], grade_level="10")
        db.add(learner)
        await db.flush()
        profile = LearnerProfile(
            learner_id=learner.id,
            concept_mastery={},
            retention_decay=0.1,
            cognitive_depth=0.5,
            engagement_score=0.5,
            selected_timeline_weeks=selected_timeline_weeks,
            recommended_timeline_weeks=None,
            current_forecast_weeks=None,
            timeline_delta_weeks=None,
            math_9_percent=int(draft.get("math_9_percent", 0)),
        )
        db.add(profile)
        auth = StudentAuth(
            username=draft["username"],
            password_hash=draft["password_hash"],
            name=draft["name"],
            date_of_birth=date.fromisoformat(draft["date_of_birth"]),
            learner_id=learner.id,
        )
        db.add(auth)
        await db.flush()
        use_learner_id = learner.id
        _auth_for_token = auth
        try:
            await redis_client.delete(f"signup:draft:{use_draft}")
        except Exception:
            pass
    else:
        learner = (await db.execute(select(Learner).where(Learner.id == use_learner_id))).scalar_one_or_none()
        profile = (
            await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == use_learner_id))
        ).scalar_one_or_none()
        if learner is None or profile is None:
            raise HTTPException(status_code=404, detail="Learner profile not found.")
        _auth_for_token = None

    # Combine diagnostic score with Class 9 maths percentage to shape initial profile (global profile).
    math_9 = float(profile.math_9_percent or 0) / 100.0
    ability = 0.5 * score + 0.5 * math_9
    profile.cognitive_depth = max(0.1, min(1.0, 0.3 + (0.7 * ability)))
    profile.onboarding_diagnostic_score = round(score, 4)
    _log_engagement_event(
        db=db,
        learner_id=use_learner_id,
        event_type="test_submission",
        duration_minutes=payload.time_spent_minutes,
        details={"source": "onboarding_submit", "score": score},
    )

    math_9_percent = float(profile.math_9_percent or 0)
    recommended_timeline_weeks, recommendation_note = _recommend_timeline_weeks(selected_timeline_weeks, score)
    current_forecast_weeks = recommended_timeline_weeks
    timeline_delta_weeks = current_forecast_weeks - selected_timeline_weeks
    rough_plan, week_1 = _build_rough_plan(chapter_scores, target_weeks=current_forecast_weeks)
    await redis_client.delete(redis_key)

    # 1. Update Profile (including all 14 chapters in mastery)
    from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name
    
    mastery = {}
    for ch_data in SYLLABUS_CHAPTERS:
        ch_key = chapter_display_name(ch_data["number"])
        # All chapters start at 0.0 — diagnostic score is used only for
        # cognitive_depth and plan pacing, NOT for chapter mastery.
        mastery[ch_key] = 0.0
    
    profile.onboarding_diagnostic_score = score
    profile.math_9_percent = int(math_9_percent)
    profile.selected_timeline_weeks = selected_timeline_weeks
    profile.recommended_timeline_weeks = recommended_timeline_weeks
    profile.current_forecast_weeks = recommended_timeline_weeks
    profile.timeline_delta_weeks = recommended_timeline_weeks - selected_timeline_weeks
    profile.concept_mastery = mastery
    profile.cognitive_depth = round(float(0.5 * score + 0.5 * (math_9_percent / 100.0)), 3)
    profile.last_updated = datetime.now(timezone.utc)

    # 2. Initialize all 14 Chapters in Progression
    for ch_data in SYLLABUS_CHAPTERS:
        ch_key = chapter_display_name(ch_data["number"])
        ch_score = mastery[ch_key]
        
        # Create ChapterProgression for each
        existing_cp = (await db.execute(
            select(ChapterProgression).where(
                ChapterProgression.learner_id == use_learner_id,
                ChapterProgression.chapter == ch_key
            )
        )).scalar_one_or_none()
        
        if not existing_cp:
            db.add(ChapterProgression(
                learner_id=use_learner_id,
                chapter=ch_key,
                status="not_started" if ch_data["number"] > 1 else "in_progress",
                attempt_count=0,
                best_score=ch_score,
                last_score=ch_score
            ))

    # 3. Create Plan and Initial Tasks
    plan = WeeklyPlan(
        learner_id=use_learner_id,
        status="active",
        current_week=1,
        total_weeks=len(rough_plan),
        plan_payload={
            "rough_plan": [item.model_dump() for item in rough_plan],
            "timeline": {
                "selected_timeline_weeks": selected_timeline_weeks,
                "recommended_timeline_weeks": recommended_timeline_weeks,
                "current_forecast_weeks": current_forecast_weeks,
                "timeline_delta_weeks": timeline_delta_weeks,
            },
        },
    )
    db.add(plan)
    await db.flush()
    await _create_plan_version(db=db, plan=plan, reason="onboarding_initial_plan")
    
    week_tasks = _default_week_tasks(learner_id=use_learner_id, chapter=week_1.chapter, week_number=1)
    for task in week_tasks:
        db.add(task)
        
    db.add(
        WeeklyForecast(
            learner_id=use_learner_id,
            week_number=1,
            selected_timeline_weeks=selected_timeline_weeks,
            recommended_timeline_weeks=recommended_timeline_weeks,
            current_forecast_weeks=current_forecast_weeks,
            timeline_delta_weeks=timeline_delta_weeks,
            pacing_status=_pacing_status(timeline_delta_weeks),
            reason="initial_onboarding_forecast",
        )
    )
    
    await _update_profile_after_outcome(
        db=db,
        learner_id=use_learner_id,
        profile=profile,
        reason="onboarding_submit",
        mastery_update=mastery,
        engagement_minutes=payload.time_spent_minutes,
        extra={"diagnostic_score": score, "math_9_percent": profile.math_9_percent},
    )
    await db.commit()

    token = create_token(use_learner_id, _auth_for_token.username) if _auth_for_token else None

    response = OnboardingSubmitResponse(
        learner_id=use_learner_id,
        score=score,
        correct_out_of_total=correct_out_of_total,
        token=token,
        selected_timeline_weeks=selected_timeline_weeks,
        recommended_timeline_weeks=recommended_timeline_weeks,
        current_forecast_weeks=current_forecast_weeks,
        timeline_delta_weeks=timeline_delta_weeks,
        timeline_recommendation_note=recommendation_note,
        chapter_scores=chapter_scores,
        profile_snapshot={
            "global_profile": {
                "student_name": learner.name,
                "class_and_course": "Class 10 Mathematics",
                "math_9_percent": profile.math_9_percent,
                "onboarding_assessment_result": score,
            },
            "cognitive_depth": profile.cognitive_depth,
            "engagement_score": profile.engagement_score,
            "math_9_percent": profile.math_9_percent,
            "diagnostic_score": score,
            "onboarding_diagnostic_score": profile.onboarding_diagnostic_score,
            "chapter_mastery": chapter_scores,
            "selected_timeline_weeks": selected_timeline_weeks,
            "recommended_timeline_weeks": recommended_timeline_weeks,
            "current_forecast_weeks": current_forecast_weeks,
            "timeline_delta_weeks": timeline_delta_weeks,
        },
        rough_plan=rough_plan,
        current_week_schedule=week_1,
        current_week_tasks=[_to_task_item(task) for task in week_tasks],
    )
    if idempotency_cache_key:
        await _set_idempotent_response(idempotency_cache_key, response.model_dump(mode="json"))
    return response


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
    committed_week_schedule = next((item for item in parsed if item.week == row.current_week), None)
    forecast_plan = [item for item in parsed if item.week > row.current_week]
    timeline = row.plan_payload.get("timeline", {}) if isinstance(row.plan_payload, dict) else {}
    tasks = (
        await db.execute(
            select(Task)
            .where(Task.learner_id == learner_id, Task.week_number == row.current_week)
            .order_by(Task.sort_order.asc(), Task.created_at.asc())
        )
    ).scalars().all()
    estimate_weeks = timeline.get("current_forecast_weeks")
    selected_weeks = timeline.get("selected_timeline_weeks")
    return WeeklyPlanResponse(
        learner_id=row.learner_id,
        current_week=row.current_week,
        total_weeks=row.total_weeks,
        selected_timeline_weeks=timeline.get("selected_timeline_weeks"),
        recommended_timeline_weeks=timeline.get("recommended_timeline_weeks"),
        current_forecast_weeks=timeline.get("current_forecast_weeks"),
        timeline_delta_weeks=timeline.get("timeline_delta_weeks"),
        rough_plan=parsed,
        committed_week_schedule=committed_week_schedule,
        forecast_plan=forecast_plan,
        current_week_tasks=[_to_task_item(task) for task in tasks],
        current_week_daily_breakdown=_daily_breakdown_from_tasks(tasks, row.current_week),
        planning_mode={
            "committed_week_active_only": True,
            "committed_week_locked": True,
            "forecast_read_only": True,
            "system_replan_only": True,
        },
        completion_estimate_weeks=estimate_weeks,
        completion_estimate_vs_goal_weeks=(
            int(estimate_weeks) - int(selected_weeks)
            if estimate_weeks is not None and selected_weeks is not None
            else None
        ),
    )


@router.post("/weekly-replan", response_model=WeeklyReplanResponse)
async def weekly_replan(payload: WeeklyReplanRequest, db: AsyncSession = Depends(get_db)):
    idempotency_cache_key = None
    if (payload.idempotency_key or "").strip():
        idempotency_cache_key = (
            f"idempotency:weekly-replan:{payload.learner_id}:{payload.evaluation.chapter}:{payload.idempotency_key.strip()}"
        )
        cached = await _get_idempotent_response(idempotency_cache_key)
        if isinstance(cached, dict):
            return WeeklyReplanResponse(**cached)

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
        await _upsert_revision_queue_item(
            db=db,
            learner_id=payload.learner_id,
            chapter=chapter,
            reason=decision,
            priority=2,
        )

    _log_engagement_event(
        db=db,
        learner_id=payload.learner_id,
        event_type="test_submission",
        duration_minutes=0,
        details={"source": "weekly_replan", "chapter": chapter, "score": score},
    )
    await _update_profile_after_outcome(
        db=db,
        learner_id=payload.learner_id,
        profile=profile,
        reason="weekly_replan",
        mastery_update={chapter: score},
        engagement_minutes=0,
        extra={"decision": decision, "threshold": threshold, "attempt_count": attempt_count},
    )

    progress.attempt_count = attempt_count
    progress.best_score = best_score
    progress.last_score = score
    progress.status = decision
    progress.revision_queued = decision == "proceed_with_revision_queue"
    progress.updated_at = datetime.now(timezone.utc)

    selected_weeks = int(profile.selected_timeline_weeks or TIMELINE_MIN_WEEKS)
    recommended_weeks = int(profile.recommended_timeline_weeks or selected_weeks)
    baseline_forecast = int(profile.current_forecast_weeks or recommended_weeks)
    forecast_delta = _weekly_forecast_adjustment(decision=decision, score=score, threshold=threshold)
    current_forecast_weeks = _clamp_weeks(baseline_forecast + forecast_delta)
    # Adaptive pace: behind -> extend; ahead -> compress carefully
    adaptive_delta = _adaptive_pace_extend_compress(selected_weeks, current_forecast_weeks)
    current_forecast_weeks = _clamp_weeks(current_forecast_weeks + adaptive_delta)
    timeline_delta_weeks = current_forecast_weeks - selected_weeks
    pacing_status = _pacing_status(timeline_delta_weeks)

    profile.current_forecast_weeks = current_forecast_weeks
    profile.timeline_delta_weeks = timeline_delta_weeks
    profile.recommended_timeline_weeks = recommended_weeks

    latest_plan = (
        await db.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.learner_id == payload.learner_id)
            .order_by(WeeklyPlan.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_plan and isinstance(latest_plan.plan_payload, dict):
        plan_payload = dict(latest_plan.plan_payload)
        timeline = dict(plan_payload.get("timeline", {}))
        timeline.update(
            {
                "selected_timeline_weeks": selected_weeks,
                "recommended_timeline_weeks": recommended_weeks,
                "current_forecast_weeks": current_forecast_weeks,
                "timeline_delta_weeks": timeline_delta_weeks,
                "pacing_status": pacing_status,
            }
        )
        plan_payload["timeline"] = timeline
        latest_plan.plan_payload = plan_payload
        latest_plan.total_weeks = max(latest_plan.total_weeks, current_forecast_weeks)
        await _create_plan_version(db=db, plan=latest_plan, reason="weekly_replan_update")

    db.add(
        WeeklyForecast(
            learner_id=payload.learner_id,
            week_number=max(1, attempt_count),
            selected_timeline_weeks=selected_weeks,
            recommended_timeline_weeks=recommended_weeks,
            current_forecast_weeks=current_forecast_weeks,
            timeline_delta_weeks=timeline_delta_weeks,
            pacing_status=pacing_status,
            reason=decision,
        )
    )
    await db.commit()

    response = WeeklyReplanResponse(
        learner_id=payload.learner_id,
        chapter=chapter,
        score=score,
        threshold=threshold,
        attempt_count=attempt_count,
        selected_timeline_weeks=selected_weeks,
        recommended_timeline_weeks=recommended_weeks,
        current_forecast_weeks=current_forecast_weeks,
        timeline_delta_weeks=timeline_delta_weeks,
        pacing_status=pacing_status,
        decision=decision,
        reason=reason,
        revision_queue=revision_queue,
    )
    if idempotency_cache_key:
        await _set_idempotent_response(idempotency_cache_key, response.model_dump(mode="json"))
    return response


@router.get("/revision-queue/{learner_id}")
async def get_revision_queue(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(RevisionQueueItem)
            .where(RevisionQueueItem.learner_id == learner_id)
            .order_by(RevisionQueueItem.priority.desc(), RevisionQueueItem.created_at.asc())
        )
    ).scalars().all()
    return {
        "learner_id": learner_id,
        "items": [
            RevisionQueueItemResponse(
                chapter=row.chapter,
                status=row.status,
                priority=row.priority,
                reason=row.reason,
            )
            for row in rows
        ],
    }


@router.get("/revision-policy/{learner_id}", response_model=RevisionPolicyStateResponse)
async def get_revision_policy_state(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")
    state = await _upsert_revision_policy_state(db, learner_id)
    weak_zones = list((state.weak_zones or {}).get("chapters", []))
    next_actions = list((state.next_actions or {}).get("items", []))
    return RevisionPolicyStateResponse(
        learner_id=learner_id,
        active_pass=state.active_pass,
        retention_score=float(state.retention_score),
        pass1_completed=bool(state.pass1_completed_at),
        pass2_completed=bool(state.pass2_completed_at),
        weak_zones=weak_zones,
        next_actions=next_actions,
    )


@router.post("/chapters/advance", response_model=ChapterAdvanceResponse)
async def advance_chapter(payload: ChapterAdvanceRequest, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == payload.learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")

    chapter = payload.chapter.strip()
    if payload.score >= payload.threshold:
        return ChapterAdvanceResponse(
            learner_id=payload.learner_id,
            chapter=chapter,
            advanced=True,
            used_policy_override=False,
            reason="threshold_met",
        )

    if not payload.allow_policy_override:
        _log_policy_violation(
            db=db,
            learner_id=payload.learner_id,
            policy_code="NO_SKIP_BELOW_THRESHOLD",
            chapter=chapter,
            details={
                "score": payload.score,
                "threshold": payload.threshold,
                "action": "blocked",
            },
        )
        await db.commit()
        raise HTTPException(status_code=409, detail="Cannot skip chapter below threshold without policy override.")

    if not (payload.override_reason or "").strip():
        raise HTTPException(status_code=422, detail="override_reason is required when allow_policy_override=true")

    _log_policy_violation(
        db=db,
        learner_id=payload.learner_id,
        policy_code="NO_SKIP_OVERRIDE_APPROVED",
        chapter=chapter,
        details={
            "score": payload.score,
            "threshold": payload.threshold,
            "action": "override",
            "override_reason": payload.override_reason,
        },
    )
    await _upsert_revision_queue_item(
        db=db,
        learner_id=payload.learner_id,
        chapter=chapter,
        reason="policy_override_skip",
        priority=3,
    )
    await db.commit()
    return ChapterAdvanceResponse(
        learner_id=payload.learner_id,
        chapter=chapter,
        advanced=True,
        used_policy_override=True,
        reason="override_approved_and_revision_queued",
    )


@router.get("/tasks/{learner_id}")
async def list_current_week_tasks(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")

    plan = (
        await db.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.learner_id == learner_id)
            .order_by(WeeklyPlan.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if plan is None:
        plan = WeeklyPlan(
            learner_id=learner_id,
            status="active",
            current_week=1,
            total_weeks=14,
            plan_payload={"rough_plan": [{"week": 1, "chapter": "Chapter 1", "focus": "learn + practice"}]},
        )
        db.add(plan)
        await db.flush()
        await _create_plan_version(db=db, plan=plan, reason="system_bootstrap_current_week")
        for task in _default_week_tasks(learner_id=learner_id, chapter="Chapter 1", week_number=1):
            db.add(task)
        await db.commit()

    tasks = (
        await db.execute(
            select(Task)
            .where(Task.learner_id == learner_id, Task.week_number == plan.current_week)
            .order_by(Task.sort_order.asc(), Task.created_at.asc())
        )
    ).scalars().all()
    return {
        "learner_id": learner_id,
        "week_number": plan.current_week,
        "is_committed_week": True,
        "forecast_read_only": True,
        "tasks": [_to_task_item(task) for task in tasks],
        "daily_breakdown": _daily_breakdown_from_tasks(tasks, plan.current_week),
    }


@router.get("/syllabus")
async def get_syllabus():
    """Return Class 10 Maths syllabus: chapters and subtopics (from syllabus.txt)."""
    return {"chapters": get_syllabus_for_api()}


@router.get("/schedule/{learner_id}")
async def get_full_schedule(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return full schedule: all weeks with tasks and timeline (read-only for student)."""
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")

    plan = (
        await db.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.learner_id == learner_id)
            .order_by(WeeklyPlan.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if plan is None:
        plan = WeeklyPlan(
            learner_id=learner_id,
            status="active",
            current_week=1,
            total_weeks=14,
            plan_payload={"rough_plan": [{"week": 1, "chapter": "Chapter 1", "focus": "learn + practice"}]},
        )
        db.add(plan)
        await db.flush()
        await _create_plan_version(db=db, plan=plan, reason="system_bootstrap_current_week")
        for task in _default_week_tasks(learner_id=learner_id, chapter="Chapter 1", week_number=1):
            db.add(task)
        await db.commit()
        plan = (
            await db.execute(
                select(WeeklyPlan).where(WeeklyPlan.learner_id == learner_id).order_by(WeeklyPlan.generated_at.desc()).limit(1)
            )
        ).scalar_one()

    rough = (plan.plan_payload or {}).get("rough_plan", [])
    if not rough:
        rough = [{"week": 1, "chapter": "Chapter 1", "focus": "learn + practice"}]
    plan_by_week = {item["week"]: item for item in rough if isinstance(item, dict)}

    all_tasks = (
        await db.execute(
            select(Task)
            .where(Task.learner_id == learner_id)
            .order_by(Task.week_number.asc(), Task.sort_order.asc(), Task.created_at.asc())
        )
    ).scalars().all()
    tasks_by_week = {}
    for t in all_tasks:
        tasks_by_week.setdefault(t.week_number, []).append(_to_task_item(t))

    current = int(plan.current_week)
    total = int(plan.total_weeks or 14)
    weeks_list = []
    for w in range(1, total + 1):
        row = plan_by_week.get(w) or {}
        weeks_list.append({
            "week_number": w,
            "chapter": row.get("chapter") or f"Chapter {min(w, 14)}",
            "focus": row.get("focus") or "learn + practice",
            "is_current": w == current,
            "is_past": w < current,
            "tasks": tasks_by_week.get(w, []),
        })
    return {
        "learner_id": learner_id,
        "current_week": current,
        "total_weeks": total,
        "weeks": weeks_list,
    }


@router.post("/tasks/{task_id}/complete", response_model=TaskCompletionResponse)
async def complete_task(task_id: UUID, payload: TaskCompletionRequest, db: AsyncSession = Depends(get_db)):
    idempotency_cache_key = None
    if (payload.idempotency_key or "").strip():
        idempotency_cache_key = (
            f"idempotency:task-complete:{payload.learner_id}:{task_id}:{payload.idempotency_key.strip()}"
        )
        cached = await _get_idempotent_response(idempotency_cache_key)
        if isinstance(cached, dict):
            return TaskCompletionResponse(**cached)

    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.learner_id != payload.learner_id:
        raise HTTPException(status_code=403, detail="Task does not belong to learner.")
    latest_plan = (
        await db.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.learner_id == payload.learner_id)
            .order_by(WeeklyPlan.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_plan and task.week_number != latest_plan.current_week:
        _log_policy_violation(
            db=db,
            learner_id=payload.learner_id,
            policy_code="IMMUTABLE_WEEK_BOUNDARY",
            chapter=task.chapter,
            details={
                "task_week": task.week_number,
                "current_week": latest_plan.current_week,
                "task_id": str(task.id),
            },
        )
        await db.commit()
        raise HTTPException(status_code=409, detail="Task is outside current committed week boundary.")

    if task.status == "completed":
        response = TaskCompletionResponse(
            learner_id=payload.learner_id,
            task_id=task_id,
            accepted=True,
            reason="already_completed",
            status=task.status,
        )
        if idempotency_cache_key:
            await _set_idempotent_response(idempotency_cache_key, response.model_dump(mode="json"))
        return response

    policy = task.proof_policy or {}
    accepted = False
    reason = ""
    if task.task_type in ("read", "practice"):
        required_minutes = int(policy.get("min_reading_minutes", 0))
        accepted = int(payload.reading_minutes) >= required_minutes
        reason = "reading_proof_ok" if accepted else f"min_reading_minutes_{required_minutes}_required"
    elif task.task_type == "test":
        required = bool(policy.get("require_test_attempt_id", True))
        has_attempt = bool((payload.test_attempt_id or "").strip())
        accepted = (not required) or has_attempt
        reason = "test_proof_ok" if accepted else "test_attempt_id_required"
    else:
        accepted = bool((payload.notes or "").strip())
        reason = "notes_proof_ok" if accepted else "notes_required"

    db.add(
        TaskAttempt(
            task_id=task.id,
            learner_id=payload.learner_id,
            proof_payload={
                "reading_minutes": payload.reading_minutes,
                "test_attempt_id": payload.test_attempt_id,
                "notes": payload.notes,
            },
            accepted=accepted,
            reason=reason,
        )
    )
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == payload.learner_id))
    ).scalar_one_or_none()
    if accepted:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        event_minutes = int(payload.reading_minutes or 0)
        _log_engagement_event(
            db=db,
            learner_id=payload.learner_id,
            event_type="task_completion",
            duration_minutes=event_minutes,
            details={
                "task_id": str(task.id),
                "task_type": task.task_type,
                "week_number": task.week_number,
                "chapter": task.chapter,
                "proof_reason": reason,
            },
        )
        if profile is not None:
            await _update_profile_after_outcome(
                db=db,
                learner_id=payload.learner_id,
                profile=profile,
                reason="task_completion",
                engagement_minutes=event_minutes,
                extra={"task_id": str(task.id), "task_type": task.task_type},
            )
    await db.commit()
    await db.refresh(task)
    response = TaskCompletionResponse(
        learner_id=payload.learner_id,
        task_id=task.id,
        accepted=accepted,
        reason=reason,
        status=task.status,
    )
    if idempotency_cache_key:
        await _set_idempotent_response(idempotency_cache_key, response.model_dump(mode="json"))
    return response


@router.post("/engagement/events", response_model=EngagementEventResponse)
async def ingest_engagement_event(payload: EngagementEventRequest, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == payload.learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")
    _log_engagement_event(
        db=db,
        learner_id=payload.learner_id,
        event_type=payload.event_type,
        duration_minutes=payload.duration_minutes,
        details=payload.details,
    )
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == payload.learner_id))
    ).scalar_one_or_none()
    if profile is not None and payload.event_type in ("study", "task_completion", "test_submission"):
        await _update_profile_after_outcome(
            db=db,
            learner_id=payload.learner_id,
            profile=profile,
            reason="engagement_event",
            engagement_minutes=payload.duration_minutes,
            extra={"event_type": payload.event_type},
        )
    await db.commit()
    return EngagementEventResponse(
        learner_id=payload.learner_id,
        event_type=payload.event_type,
        duration_minutes=payload.duration_minutes,
        accepted=True,
    )


@router.get("/engagement/summary/{learner_id}", response_model=EngagementSummaryResponse)
async def get_engagement_summary(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")
    now = datetime.now(timezone.utc)
    day_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    minutes_today = await _engagement_minutes_since(db, learner_id, day_start)
    minutes_week = await _engagement_minutes_since(db, learner_id, week_start)
    adherence_rate = await _compute_adherence_rate_week(db, learner_id)
    login_streak_days = await _compute_login_streak_days(db, learner_id)
    last_login = (
        await db.execute(
            select(EngagementEvent.created_at)
            .where(EngagementEvent.learner_id == learner_id, EngagementEvent.event_type == "login")
            .order_by(EngagementEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_logout = (
        await db.execute(
            select(EngagementEvent.created_at)
            .where(EngagementEvent.learner_id == learner_id, EngagementEvent.event_type == "logout")
            .order_by(EngagementEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return EngagementSummaryResponse(
        learner_id=learner_id,
        engagement_minutes_today=minutes_today,
        engagement_minutes_week=minutes_week,
        login_streak_days=login_streak_days,
        adherence_rate_week=adherence_rate,
        last_login_at=last_login,
        last_logout_at=last_logout,
    )


@router.get("/profile-history/{learner_id}")
async def get_profile_history(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")
    rows = (
        await db.execute(
            select(LearnerProfileSnapshot)
            .where(LearnerProfileSnapshot.learner_id == learner_id)
            .order_by(LearnerProfileSnapshot.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        "learner_id": learner_id,
        "items": [
            {
                "reason": row.reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "payload": row.payload if isinstance(row.payload, dict) else {},
            }
            for row in rows
        ],
    }


@router.get("/where-i-stand/{learner_id}", response_model=LearnerStandResponse)
async def get_where_i_stand(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    ).scalar_one_or_none()
    if learner is None or profile is None:
        raise HTTPException(status_code=404, detail="Learner profile not found.")

    mastery_map = dict(profile.concept_mastery or {})
    chapter_status = []
    strengths = []
    weaknesses = []
    for chapter, value in sorted(mastery_map.items(), key=lambda item: item[0]):
        score = float(value)
        if score >= 0.85:
            band = "Mastered"
            strengths.append(chapter)
        elif score >= 0.70:
            band = "Proficient"
            strengths.append(chapter)
        elif score >= 0.45:
            band = "Developing"
        else:
            band = "Beginner"
            weaknesses.append(chapter)
        chapter_status.append({"chapter": chapter, "score": round(score, 3), "band": band})

    retention = await _compute_retention_score(db, learner_id)
    adherence = await _compute_adherence_rate_week(db, learner_id)
    confidence_score = round(
        max(
            0.0,
            min(
                1.0,
                (0.45 * float(profile.cognitive_depth or 0.0))
                + (0.25 * float(profile.engagement_score or 0.0))
                + (0.20 * retention)
                + (0.10 * adherence),
            ),
        ),
        3,
    )
    return LearnerStandResponse(
        learner_id=learner_id,
        chapter_status=chapter_status,
        concept_strengths=sorted(set(strengths))[:8],
        concept_weaknesses=sorted(set(weaknesses))[:8],
        confidence_score=confidence_score,
        retention_score=retention,
        adherence_rate_week=adherence,
    )


@router.get("/evaluation-analytics/{learner_id}", response_model=EvaluationAnalyticsResponse)
async def get_evaluation_analytics(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")
    payload = await _build_evaluation_analytics(db, learner_id)
    return EvaluationAnalyticsResponse(learner_id=learner_id, **payload)


@router.get("/learning-metrics/{learner_id}", response_model=StudentLearningMetricsResponse)
async def get_student_learning_metrics(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    """Aggregated student-learning metrics: mastery, confidence, weak areas, adherence, streak, timeline."""
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    ).scalar_one_or_none()
    if learner is None or profile is None:
        raise HTTPException(status_code=404, detail="Learner profile not found.")

    mastery_map = dict(profile.concept_mastery or {})
    weak_areas = [ch for ch, val in mastery_map.items() if float(val) < 0.45]
    avg_mastery = (
        sum(float(v) for v in mastery_map.values()) / len(mastery_map)
        if mastery_map
        else 0.0
    )
    retention = await _compute_retention_score(db, learner_id)
    adherence = await _compute_adherence_rate_week(db, learner_id)
    login_streak_days = await _compute_login_streak_days(db, learner_id)
    confidence_score = round(
        max(
            0.0,
            min(
                1.0,
                (0.45 * float(profile.cognitive_depth or 0.0))
                + (0.25 * float(profile.engagement_score or 0.0))
                + (0.20 * retention)
                + (0.10 * adherence),
            ),
        ),
        3,
    )
    selected_weeks = int(profile.selected_timeline_weeks or 0) or None
    forecast_weeks = int(profile.current_forecast_weeks or 0) or None
    delta = (forecast_weeks - selected_weeks) if (selected_weeks and forecast_weeks is not None) else None

    progress_rows = (
        await db.execute(
            select(ChapterProgression.chapter, ChapterProgression.attempt_count).where(
                ChapterProgression.learner_id == learner_id
            )
        )
    ).all()
    chapter_retry_counts = {row.chapter: int(row.attempt_count) for row in progress_rows}

    return StudentLearningMetricsResponse(
        learner_id=learner_id,
        mastery_progression=mastery_map,
        avg_mastery_score=round(avg_mastery, 3),
        confidence_score=confidence_score,
        weak_area_count=len(weak_areas),
        weak_areas=sorted(weak_areas)[:20],
        adherence_rate_week=adherence,
        login_streak_days=login_streak_days,
        timeline_adherence_weeks=delta,
        forecast_drift_weeks=delta,
        selected_timeline_weeks=selected_weeks,
        current_forecast_weeks=forecast_weeks,
        chapter_retry_counts=chapter_retry_counts,
    )


@router.get("/forecast-history/{learner_id}", response_model=ForecastHistoryResponse)
async def get_forecast_history(
    learner_id: UUID,
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
):
    """Return weekly forecast history (drift trend over time) for the learner."""
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")
    rows = (
        await db.execute(
            select(WeeklyForecast)
            .where(WeeklyForecast.learner_id == learner_id)
            .order_by(WeeklyForecast.generated_at.desc())
            .limit(min(limit, 50))
        )
    ).scalars().all()
    history = [
        ForecastHistoryItem(
            week_number=r.week_number,
            current_forecast_weeks=r.current_forecast_weeks,
            timeline_delta_weeks=r.timeline_delta_weeks,
            pacing_status=r.pacing_status or "on_track",
            generated_at=r.generated_at,
        )
        for r in rows
    ]
    return ForecastHistoryResponse(learner_id=learner_id, history=history)


@router.get("/daily-plan/{learner_id}", response_model=DailyPlanResponse)
async def get_daily_plan(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found.")
    plan = (
        await db.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.learner_id == learner_id)
            .order_by(WeeklyPlan.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="No weekly plan found for learner.")
    tasks = (
        await db.execute(
            select(Task)
            .where(Task.learner_id == learner_id, Task.week_number == plan.current_week)
            .order_by(Task.sort_order.asc(), Task.created_at.asc())
        )
    ).scalars().all()
    chapter = tasks[0].chapter if tasks else None
    return DailyPlanResponse(
        learner_id=learner_id,
        week_number=plan.current_week,
        chapter=chapter,
        is_committed_week=True,
        forecast_read_only=True,
        daily_breakdown=_daily_breakdown_from_tasks(tasks, plan.current_week),
    )


@router.get("/plan-versions/{learner_id}")
async def list_plan_versions(learner_id: UUID, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(WeeklyPlanVersion)
            .where(WeeklyPlanVersion.learner_id == learner_id)
            .order_by(WeeklyPlanVersion.version_number.asc(), WeeklyPlanVersion.created_at.asc())
        )
    ).scalars().all()
    return {
        "learner_id": learner_id,
        "versions": [
            {
                "version_number": row.version_number,
                "current_week": row.current_week,
                "reason": row.reason,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }
