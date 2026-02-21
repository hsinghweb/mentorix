import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.adaptation import AdaptationAgent
from app.agents.assessment import AssessmentAgent
from app.agents.content import ContentGenerationAgent
from app.agents.learner_profile import LearnerProfilingAgent
from app.agents.planner import CurriculumPlannerAgent
from app.agents.reflection import ReflectionAgent
from app.memory.cache import redis_client
from app.memory.database import get_db
from app.models.entities import AssessmentResult, Learner, LearnerProfile, SessionLog
from app.orchestrator.engine import StateEngine
from app.orchestrator.states import SessionState
from app.rag.retriever import retrieve_concept_chunks
from app.schemas.session import (
    DashboardResponse,
    StartSessionRequest,
    StartSessionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)

router = APIRouter(tags=["sessions"])
logger = logging.getLogger(__name__)

engine = StateEngine()
profiling_agent = LearnerProfilingAgent()
planner_agent = CurriculumPlannerAgent()
content_agent = ContentGenerationAgent()
adaptation_agent = AdaptationAgent()
assessment_agent = AssessmentAgent()
reflection_agent = ReflectionAgent()


DEFAULT_MASTERY = {
    "fractions": 0.45,
    "linear_equations": 0.35,
    "quadratic_equations": 0.3,
    "probability": 0.5,
}

MAX_DIFFICULTY_SHIFT_PER_TURN = 1
CONCEPT_DIFFICULTY_BOUNDS: dict[str, tuple[int, int]] = {
    "fractions": (1, 2),
    "linear_equations": (1, 3),
    "quadratic_equations": (1, 3),
    "probability": (1, 2),
}


def _apply_adaptation_shift_caps(*, concept: str, current_difficulty: int, adaptation: dict) -> dict:
    """
    Enforce explicit adaptation shift caps per session turn and per concept.
    """
    candidate = int(adaptation.get("new_difficulty", current_difficulty))
    bounded_delta = max(
        -MAX_DIFFICULTY_SHIFT_PER_TURN,
        min(MAX_DIFFICULTY_SHIFT_PER_TURN, candidate - current_difficulty),
    )
    capped = current_difficulty + bounded_delta

    concept_min, concept_max = CONCEPT_DIFFICULTY_BOUNDS.get(concept, (1, 3))
    capped = max(concept_min, min(concept_max, capped))

    if capped != candidate:
        logger.info(
            json.dumps(
                {
                    "type": "adaptation_cap_applied",
                    "concept": concept,
                    "from_difficulty": current_difficulty,
                    "candidate_difficulty": candidate,
                    "capped_difficulty": capped,
                    "max_shift": MAX_DIFFICULTY_SHIFT_PER_TURN,
                }
            )
        )

    adaptation["new_difficulty"] = capped
    adaptation["adaptation_score"] = max(0.0, min(1.0, float(adaptation.get("adaptation_score", 0.0))))
    return adaptation


def _log_state_transition(
    *,
    session_id: str,
    learner_id: str,
    step_index: int,
    from_state: SessionState,
    to_state: SessionState,
    event: str,
    payload: dict | None = None,
) -> None:
    log_obj = {
        "type": "state_transition",
        "session_id": session_id,
        "learner_id": learner_id,
        "step_index": step_index,
        "from_state": from_state.value,
        "to_state": to_state.value,
        "event": event,
        "payload": payload or {},
        "ts": datetime.utcnow().isoformat(),
    }
    logger.info(json.dumps(log_obj))


def _advance_state(
    *,
    session_id: str,
    learner_id: str,
    state: SessionState,
    step_index: int,
    event: str,
    payload: dict | None = None,
) -> tuple[SessionState, int]:
    transition = engine.next_transition(state, step_index)
    _log_state_transition(
        session_id=session_id,
        learner_id=learner_id,
        step_index=transition.step_index,
        from_state=transition.current_state,
        to_state=transition.next_state,
        event=event,
        payload=payload,
    )
    return transition.next_state, transition.step_index


async def _get_or_create_learner_profile(db: AsyncSession, learner_id: uuid.UUID) -> LearnerProfile:
    learner = await db.get(Learner, learner_id)
    if learner is None:
        learner = Learner(id=learner_id, name=f"Learner-{str(learner_id)[:8]}", grade_level="10")
        db.add(learner)
        await db.flush()

    profile = await db.get(LearnerProfile, learner_id)
    if profile is None:
        profile = LearnerProfile(
            learner_id=learner_id,
            concept_mastery=DEFAULT_MASTERY,
            retention_decay=0.1,
            cognitive_depth=0.5,
            engagement_score=0.5,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.post("/start-session", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest, db: AsyncSession = Depends(get_db)):
    try:
        learner_id = uuid.UUID(payload.learner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid learner_id UUID") from exc

    session_id = str(uuid.uuid4())
    profile = await _get_or_create_learner_profile(db, learner_id)
    recent = (
        await db.execute(
            select(SessionLog.concept)
            .where(SessionLog.learner_id == learner_id)
            .order_by(desc(SessionLog.timestamp))
            .limit(5)
        )
    ).scalars().all()

    step_idx = 0
    state = SessionState.INITIALIZE_SESSION
    state, step_idx = _advance_state(
        session_id=session_id,
        learner_id=str(learner_id),
        state=state,
        step_index=step_idx,
        event="session_initialized",
    )

    p = await profiling_agent.run({"mastery_map": profile.concept_mastery, "learner_id": payload.learner_id})
    state, step_idx = _advance_state(
        session_id=session_id,
        learner_id=str(learner_id),
        state=state,
        step_index=step_idx,
        event="profile_loaded",
        payload={"weak_concepts": p.get("weak_concepts", [])},
    )

    plan = await planner_agent.run({"mastery_map": p["mastery_map"], "recent_concepts": recent})
    concept = plan["next_concept"]
    difficulty = int(plan["target_difficulty"])
    state, step_idx = _advance_state(
        session_id=session_id,
        learner_id=str(learner_id),
        state=state,
        step_index=step_idx,
        event="concept_selected",
        payload={"concept": concept, "difficulty": difficulty},
    )

    chunks = await retrieve_concept_chunks(db, concept=concept, top_k=5, difficulty=difficulty)
    content = await content_agent.run({"concept": concept, "difficulty": difficulty, "retrieved_chunks": chunks})
    state, step_idx = _advance_state(
        session_id=session_id,
        learner_id=str(learner_id),
        state=state,
        step_index=step_idx,
        event="content_generated",
        payload={"source": content.get("source", "template"), "chunk_count": len(chunks)},
    )

    adaptation = await adaptation_agent.run(
        {"rolling_error_rate": 0.0, "response_time_deviation": 0.0, "consecutive_failures": 0, "difficulty": difficulty}
    )
    adaptation = _apply_adaptation_shift_caps(
        concept=concept,
        current_difficulty=difficulty,
        adaptation=adaptation,
    )
    question_payload = await assessment_agent.run(
        {"concept": concept, "difficulty": adaptation["new_difficulty"]}
    )

    session_key = f"session:{session_id}"
    session_payload = {
        "learner_id": str(learner_id),
        "current_concept": concept,
        "difficulty": adaptation["new_difficulty"],
        "rolling_error_rate": 0.0,
        "consecutive_failures": 0,
        "adaptation_state": adaptation,
        "expected_answer": question_payload["expected_answer"],
        "question": question_payload["generated_question"],
        "step_index": step_idx,
        "updated_at": datetime.utcnow().isoformat(),
    }
    await redis_client.hset(session_key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in session_payload.items()})
    await redis_client.expire(session_key, 3600)

    db.add(
        SessionLog(
            learner_id=learner_id,
            concept=concept,
            difficulty_level=adaptation["new_difficulty"],
            adaptation_score=adaptation["adaptation_score"],
        )
    )
    await db.commit()
    _log_state_transition(
        session_id=session_id,
        learner_id=str(learner_id),
        step_index=step_idx,
        from_state=state,
        to_state=SessionState.DELIVER,
        event="session_ready_for_delivery",
        payload={"concept": concept, "difficulty": adaptation["new_difficulty"]},
    )

    return StartSessionResponse(
        session_id=session_id,
        concept=concept,
        difficulty=adaptation["new_difficulty"],
        explanation=content["explanation"],
        question=question_payload["generated_question"],
        state=SessionState.DELIVER.value,
    )


@router.post("/submit-answer", response_model=SubmitAnswerResponse)
async def submit_answer(payload: SubmitAnswerRequest, db: AsyncSession = Depends(get_db)):
    session_key = f"session:{payload.session_id}"
    raw = await redis_client.hgetall(session_key)
    if not raw:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    learner_id = uuid.UUID(raw["learner_id"])
    step_idx = int(raw.get("step_index", 0))
    concept = raw["current_concept"]
    difficulty = int(raw["difficulty"])
    expected = raw.get("expected_answer", concept).lower()
    rolling_error_rate = float(raw.get("rolling_error_rate", 0.0))
    failures = int(raw.get("consecutive_failures", 0))
    adaptation_state = json.loads(raw.get("adaptation_state", "{}"))

    eval_out = await assessment_agent.evaluate(payload.answer, expected)
    score = float(eval_out["score"])
    error_type = eval_out["error_type"]
    new_error = 1.0 - score
    rolling_error_rate = (rolling_error_rate * 0.7) + (new_error * 0.3)
    failures = failures + 1 if score < 0.6 else 0
    _log_state_transition(
        session_id=payload.session_id,
        learner_id=str(learner_id),
        step_index=step_idx + 1,
        from_state=SessionState.ASSESS,
        to_state=SessionState.UPDATE_MEMORY,
        event="answer_assessed",
        payload={"score": score, "error_type": error_type},
    )

    response_time_dev = min(1.0, max(0.0, payload.response_time / 30.0))
    adaptation = await adaptation_agent.run(
        {
            "rolling_error_rate": rolling_error_rate,
            "response_time_deviation": response_time_dev,
            "consecutive_failures": failures,
            "difficulty": difficulty,
            "cooldown_remaining": int(adaptation_state.get("cooldown_remaining", 0)),
        }
    )
    adaptation = _apply_adaptation_shift_caps(
        concept=concept,
        current_difficulty=difficulty,
        adaptation=adaptation,
    )
    _log_state_transition(
        session_id=payload.session_id,
        learner_id=str(learner_id),
        step_index=step_idx + 2,
        from_state=SessionState.UPDATE_MEMORY,
        to_state=SessionState.REFLECT,
        event="adaptation_computed",
        payload={
            "adaptation_score": adaptation["adaptation_score"],
            "new_difficulty": adaptation["new_difficulty"],
        },
    )

    profile = await _get_or_create_learner_profile(db, learner_id)
    reflection = await reflection_agent.run(
        {
            "concept": concept,
            "current_score": score,
            "mastery_map": profile.concept_mastery,
            "engagement_score": profile.engagement_score,
            "retention_decay": profile.retention_decay,
        }
    )
    _log_state_transition(
        session_id=payload.session_id,
        learner_id=str(learner_id),
        step_index=step_idx + 3,
        from_state=SessionState.REFLECT,
        to_state=SessionState.DELIVER,
        event="profile_reflected",
        payload={"new_mastery": reflection["new_mastery"], "concept": concept},
    )

    profile.concept_mastery = {**profile.concept_mastery, concept: reflection["new_mastery"]}
    profile.engagement_score = reflection["engagement_score"]
    profile.retention_decay = reflection["retention_decay"]
    profile.last_updated = datetime.utcnow()

    db.add(
        AssessmentResult(
            learner_id=learner_id,
            concept=concept,
            score=score,
            response_time=payload.response_time,
            error_type=error_type,
        )
    )
    db.add(
        SessionLog(
            learner_id=learner_id,
            concept=concept,
            difficulty_level=adaptation["new_difficulty"],
            adaptation_score=adaptation["adaptation_score"],
        )
    )
    await db.commit()

    chunks = await retrieve_concept_chunks(db, concept=concept, top_k=5, difficulty=adaptation["new_difficulty"])
    content = await content_agent.run(
        {
            "concept": concept,
            "difficulty": adaptation["new_difficulty"],
            "retrieved_chunks": chunks,
        }
    )

    await redis_client.hset(
        session_key,
        mapping={
            "difficulty": str(adaptation["new_difficulty"]),
            "rolling_error_rate": str(rolling_error_rate),
            "consecutive_failures": str(failures),
            "adaptation_state": json.dumps(adaptation),
            "updated_at": datetime.utcnow().isoformat(),
            "step_index": str(step_idx + 3),
        },
    )
    await redis_client.expire(session_key, 3600)

    return SubmitAnswerResponse(
        session_id=payload.session_id,
        score=score,
        error_type=error_type,
        adaptation_applied=adaptation,
        next_explanation=content["explanation"],
    )


@router.get("/dashboard/{learner_id}", response_model=DashboardResponse)
async def dashboard(learner_id: str, db: AsyncSession = Depends(get_db)):
    try:
        learner_uuid = uuid.UUID(learner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid learner_id UUID") from exc

    profile = await db.get(LearnerProfile, learner_uuid)
    if profile is None:
        raise HTTPException(status_code=404, detail="Learner profile not found")

    weak = sorted(profile.concept_mastery.items(), key=lambda x: x[1])[:3]
    recent_rows = (
        await db.execute(
            select(SessionLog)
            .where(SessionLog.learner_id == learner_uuid)
            .order_by(desc(SessionLog.timestamp))
            .limit(5)
        )
    ).scalars().all()

    return DashboardResponse(
        learner_id=learner_id,
        mastery_map=profile.concept_mastery,
        engagement_score=profile.engagement_score,
        weak_areas=[c for c, _ in weak],
        last_sessions=[
            {
                "concept": r.concept,
                "difficulty_level": r.difficulty_level,
                "adaptation_score": r.adaptation_score,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in recent_rows
        ],
    )
