"""Admin API: auth-protected observability, control-room, and agent views."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.onboarding import _build_comparative_analytics
from app.api.metrics import app_metrics as build_app_metrics
from app.autonomy.scheduler import scheduler_service
from app.core.jwt_auth import decode_token, token_role
from app.core.settings import settings
from app.memory.cache import _real_client
from app.memory.database import get_db
from app.models.entities import (
    AgentDecision,
    AssessmentResult,
    EngagementEvent,
    Learner,
    LearnerProfile,
    PolicyViolation,
    ReminderDeliveryLog,
    StudentAuth,
    WeeklyPlan,
)
from app.runtime.run_manager import run_manager
from app.services.email_service import email_service

router = APIRouter(prefix="/admin", tags=["admin"])
bearer = HTTPBearer(auto_error=False)

AGENT_CATALOG = [
    {
        "agent_name": "orchestrator",
        "title": "Orchestrator",
        "purpose": "Coordinates flow hand-offs across onboarding, planning, content, assessment, and analytics.",
        "decision_types": ["orchestrate_flow", "run_started", "run_finished"],
    },
    {
        "agent_name": "onboarding",
        "title": "Onboarding Agent",
        "purpose": "Scores diagnostic performance and shapes the first learner plan.",
        "decision_types": ["diagnostic_scored", "timeline_recommended", "onboarding_plan_created"],
    },
    {
        "agent_name": "planner",
        "title": "Planner Agent",
        "purpose": "Builds and adjusts timeline, weekly plan, and pace decisions.",
        "decision_types": ["plan_generated", "pace_adjusted", "weekly_replan_decision"],
    },
    {
        "agent_name": "content",
        "title": "Content Agent",
        "purpose": "Generates grounded adaptive reading material from NCERT context.",
        "decision_types": ["chapter_content_served", "section_content_served", "source_section_requested"],
    },
    {
        "agent_name": "assessment",
        "title": "Assessment Agent",
        "purpose": "Generates tests, evaluates attempts, and returns explanations.",
        "decision_types": ["chapter_test_generated", "section_test_generated", "question_explained"],
    },
    {
        "agent_name": "analytics",
        "title": "Analytics Agent",
        "purpose": "Tracks learner progress, cohort position, and weak-area signals.",
        "decision_types": ["evaluation_recorded", "comparative_analytics_computed"],
    },
]


def _serialize_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def _require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Admin authentication required.")
    payload = decode_token(credentials.credentials)
    if not payload or token_role(payload) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return payload


async def _redis_status() -> dict:
    try:
        pong = await _real_client.ping()
        return {"connected": bool(pong), "url": settings.redis_url}
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "url": settings.redis_url, "error": str(exc)}


@router.get("/system-overview")
async def system_overview(
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    app = await build_app_metrics()
    try:
        from app.memory.store import get_memory_runtime_status

        memory = get_memory_runtime_status()
    except Exception as exc:  # noqa: BLE001
        memory = {"active_mode": "unavailable", "mongo": {"connected": False, "error": str(exc)}}
    redis = await _redis_status()
    learner_count = (await db.execute(select(func.count(Learner.id)))).scalar() or 0
    plan_count = (await db.execute(select(func.count(WeeklyPlan.id)))).scalar() or 0
    policy_violations_today = (
        await db.execute(
            select(func.count(PolicyViolation.id)).where(
                PolicyViolation.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
            )
        )
    ).scalar() or 0
    return {
        "service": {
            "name": "mentorix-api",
            "environment": settings.app_env,
            "scheduler_enabled": settings.scheduler_enabled,
            "scheduled_jobs": len(scheduler_service.list_jobs()),
            "active_runs": len(run_manager.list_runs()),
        },
        "traffic": {
            "request_metrics": app,
            "learners_total": learner_count,
            "plans_total": plan_count,
            "policy_violations_last_24h": policy_violations_today,
        },
        "infrastructure": {
            "database_url": settings.database_url,
            "redis": redis,
            "memory_runtime": memory,
            "email": email_service.diagnostics(),
            "mongodb_url": settings.mongodb_url,
        },
    }


@router.get("/students")
async def student_control_room(
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = (
        select(Learner, LearnerProfile, StudentAuth)
        .join(LearnerProfile, LearnerProfile.learner_id == Learner.id)
        .join(StudentAuth, StudentAuth.learner_id == Learner.id, isouter=True)
        .order_by(Learner.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    students = []
    for learner, profile, auth in rows:
        mastery_map = {
            k: float(v) for k, v in dict(profile.concept_mastery or {}).items() if str(k).startswith("Chapter")
        }
        mastery_avg = sum(mastery_map.values()) / max(1, len(mastery_map)) if mastery_map else 0.0
        weak_count = len([v for v in mastery_map.values() if v < 0.45])
        risk_flags = []
        if mastery_avg < 0.4:
            risk_flags.append("low_mastery")
        if (profile.timeline_delta_weeks or 0) >= 2:
            risk_flags.append("timeline_drift")
        if weak_count >= 4:
            risk_flags.append("broad_weak_areas")
        students.append(
            {
                "learner_id": str(learner.id),
                "name": auth.name if auth else learner.name,
                "username": auth.username if auth else None,
                "grade_level": learner.grade_level,
                "progress_percentage": round(float(profile.progress_percentage or 0.0), 1),
                "mastery_average": round(mastery_avg, 3),
                "weak_area_count": weak_count,
                "selected_timeline_weeks": profile.selected_timeline_weeks,
                "current_forecast_weeks": profile.current_forecast_weeks,
                "timeline_delta_weeks": profile.timeline_delta_weeks,
                "onboarding_date": profile.onboarding_date.isoformat() if profile.onboarding_date else None,
                "reminder_enabled": bool(profile.reminder_enabled),
                "last_updated": _serialize_dt(profile.last_updated),
                "risk_flags": risk_flags,
            }
        )
    return {"total": len(students), "students": students}


@router.get("/students/{learner_id}")
async def student_detail(
    learner_id: UUID,
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    profile = (await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))).scalar_one_or_none()
    auth = (await db.execute(select(StudentAuth).where(StudentAuth.learner_id == learner_id))).scalar_one_or_none()
    if learner is None or profile is None:
        raise HTTPException(status_code=404, detail="Learner not found.")

    latest_plan = (
        await db.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.learner_id == learner_id)
            .order_by(desc(WeeklyPlan.generated_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    recent_events = (
        await db.execute(
            select(EngagementEvent)
            .where(EngagementEvent.learner_id == learner_id)
            .order_by(desc(EngagementEvent.created_at))
            .limit(8)
        )
    ).scalars().all()
    recent_assessments = (
        await db.execute(
            select(AssessmentResult)
            .where(AssessmentResult.learner_id == learner_id)
            .order_by(desc(AssessmentResult.timestamp))
            .limit(8)
        )
    ).scalars().all()
    recent_reminders = (
        await db.execute(
            select(ReminderDeliveryLog)
            .where(ReminderDeliveryLog.learner_id == learner_id)
            .order_by(desc(ReminderDeliveryLog.created_at))
            .limit(8)
        )
    ).scalars().all()
    comparative = await _build_comparative_analytics(db, learner_id)
    return {
        "learner": {
            "learner_id": str(learner.id),
            "name": auth.name if auth else learner.name,
            "username": auth.username if auth else None,
            "grade_level": learner.grade_level,
            "created_at": _serialize_dt(learner.created_at),
        },
        "profile": {
            "progress_percentage": round(float(profile.progress_percentage or 0.0), 1),
            "progress_status": profile.progress_status,
            "selected_timeline_weeks": profile.selected_timeline_weeks,
            "recommended_timeline_weeks": profile.recommended_timeline_weeks,
            "current_forecast_weeks": profile.current_forecast_weeks,
            "timeline_delta_weeks": profile.timeline_delta_weeks,
            "cognitive_depth": profile.cognitive_depth,
            "engagement_score": profile.engagement_score,
            "onboarding_date": profile.onboarding_date.isoformat() if profile.onboarding_date else None,
            "concept_mastery": dict(profile.concept_mastery or {}),
            "last_updated": _serialize_dt(profile.last_updated),
        },
        "plan": {
            "current_week": latest_plan.current_week if latest_plan else None,
            "total_weeks": latest_plan.total_weeks if latest_plan else None,
            "status": latest_plan.status if latest_plan else None,
        },
        "comparative": comparative,
        "recent_events": [
            {
                "event_type": e.event_type,
                "duration_minutes": e.duration_minutes,
                "details": e.details,
                "created_at": _serialize_dt(e.created_at),
            }
            for e in recent_events
        ],
        "recent_assessments": [
            {
                "concept": a.concept,
                "score": round(float(a.score or 0.0), 3),
                "response_time": round(float(a.response_time or 0.0), 2),
                "error_type": a.error_type,
                "timestamp": _serialize_dt(a.timestamp),
            }
            for a in recent_assessments
        ],
        "recent_reminders": [
            {
                "status": r.status,
                "reason": r.reason,
                "mode": r.mode,
                "details": r.details,
                "created_at": _serialize_dt(r.created_at),
            }
            for r in recent_reminders
        ],
    }


@router.get("/agents/overview")
async def agents_overview(
    _: dict = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    recent = (
        await db.execute(
            select(AgentDecision)
            .order_by(desc(AgentDecision.created_at))
            .limit(60)
        )
    ).scalars().all()
    recent_by_agent: dict[str, list[AgentDecision]] = {}
    for item in recent:
        recent_by_agent.setdefault(item.agent_name, []).append(item)

    active_runs = run_manager.list_runs()
    active_hint = (
        f"{len(active_runs)} runtime run(s) active"
        if active_runs
        else "No runtime runs active"
    )
    now = datetime.now(timezone.utc)
    agents = []
    for spec in AGENT_CATALOG:
        history = recent_by_agent.get(spec["agent_name"], [])
        latest = history[0] if history else None
        if spec["agent_name"] == "orchestrator" and active_runs:
            status = "working"
            hint = active_hint
        elif latest and latest.created_at and (now - latest.created_at) <= timedelta(minutes=10):
            status = "completed"
            hint = latest.decision_type.replace("_", " ")
        else:
            status = "idle"
            hint = "Awaiting next trigger"

        latest_output = latest.output_payload if latest and isinstance(latest.output_payload, dict) else {}
        latest_input = latest.input_snapshot if latest and isinstance(latest.input_snapshot, dict) else {}
        agents.append(
            {
                "agent_name": spec["agent_name"],
                "title": spec["title"],
                "purpose": spec["purpose"],
                "status": status,
                "status_hint": hint,
                "latest_activity_at": _serialize_dt(latest.created_at if latest else None),
                "latest_decision_type": latest.decision_type if latest else None,
                "latest_input": latest_input,
                "latest_output": latest_output,
                "recent_decisions": [
                    {
                        "decision_type": row.decision_type,
                        "chapter": row.chapter,
                        "section_id": row.section_id,
                        "created_at": _serialize_dt(row.created_at),
                    }
                    for row in history[:4]
                ],
            }
        )
    return {
        "active_runs": active_runs,
        "agents": agents,
    }


@router.get("/cohort")
async def cohort_overview(
    db: AsyncSession = Depends(get_db),
    include_list: bool = Query(False, description="Include learner list"),
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(_require_admin),
):
    count_result = await db.execute(select(func.count(Learner.id)))
    learner_count = count_result.scalar() or 0
    out = {"learner_count": learner_count}
    if include_list and learner_count > 0:
        result = await db.execute(select(Learner.id, Learner.name, Learner.grade_level).limit(limit))
        rows = result.all()
        out["learners"] = [{"id": str(r.id), "name": r.name, "grade_level": r.grade_level} for r in rows]
    return out


@router.get("/policy-violations")
async def list_policy_violations(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    learner_id: UUID | None = Query(None, description="Filter by learner"),
    _: dict = Depends(_require_admin),
):
    stmt = select(PolicyViolation).order_by(desc(PolicyViolation.created_at)).limit(limit)
    if learner_id is not None:
        stmt = stmt.where(PolicyViolation.learner_id == learner_id)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "total": len(rows),
        "violations": [
            {
                "id": str(v.id),
                "learner_id": str(v.learner_id),
                "policy_code": v.policy_code,
                "chapter": v.chapter,
                "details": v.details,
                "created_at": _serialize_dt(v.created_at),
            }
            for v in rows
        ],
    }


@router.get("/timeline-drift")
async def timeline_drift_summary(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(_require_admin),
):
    stmt = select(
        func.count(LearnerProfile.learner_id).label("count"),
        func.avg(LearnerProfile.selected_timeline_weeks).label("avg_selected"),
        func.avg(LearnerProfile.current_forecast_weeks).label("avg_forecast"),
        func.avg(LearnerProfile.timeline_delta_weeks).label("avg_delta"),
    ).where(
        LearnerProfile.selected_timeline_weeks.isnot(None),
        LearnerProfile.current_forecast_weeks.isnot(None),
    )
    row = (await db.execute(stmt)).one()
    return {
        "learners_with_timeline": row.count or 0,
        "avg_selected_weeks": round(float(row.avg_selected or 0), 1),
        "avg_forecast_weeks": round(float(row.avg_forecast or 0), 1),
        "avg_delta_weeks": round(float(row.avg_delta or 0), 1),
    }
