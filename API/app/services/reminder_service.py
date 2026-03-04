from __future__ import annotations

import asyncio
import smtplib
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeline import format_week_label, week_bounds_from_onboarding
from app.models.entities import EngagementEvent, Learner, LearnerProfile, ReminderDeliveryLog, Task, WeeklyPlan
from app.services.email_service import email_service


def _classify_delivery_error(exc: Exception) -> str:
    msg = str(exc or "").lower()
    if "smtp configuration is incomplete" in msg:
        return "smtp_config_incomplete"
    if "gmail api credentials not configured" in msg:
        return "gmail_api_credentials_missing"
    if "gmail api send flow is not configured" in msg:
        return "gmail_api_flow_not_configured"
    if isinstance(exc, smtplib.SMTPAuthenticationError) or "authentication" in msg:
        return "smtp_auth_failed"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "smtp_recipients_refused"
    if isinstance(exc, smtplib.SMTPConnectError):
        return "smtp_connect_failed"
    if isinstance(exc, TimeoutError) or "timed out" in msg or "timeout" in msg:
        return "smtp_timeout"
    return "unknown_delivery_error"


async def _is_dispatch_cooldown_active(
    *,
    db: AsyncSession,
    learner_id: UUID,
    cooldown_seconds: int,
) -> bool:
    if cooldown_seconds <= 0:
        return False
    latest_log = (
        await db.execute(
            select(ReminderDeliveryLog)
            .where(ReminderDeliveryLog.learner_id == learner_id)
            .order_by(ReminderDeliveryLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_log is None or latest_log.created_at is None:
        return False
    return (datetime.now(timezone.utc) - latest_log.created_at) < timedelta(seconds=int(cooldown_seconds))


def _rate_limit_ok(profile: LearnerProfile, hours: int) -> bool:
    if profile.last_reminder_sent_at is None:
        return True
    return datetime.now(timezone.utc) - profile.last_reminder_sent_at >= timedelta(hours=max(1, int(hours)))


async def evaluate_reminder_eligibility(
    *,
    db: AsyncSession,
    learner_id: UUID,
    inactivity_days: int = 3,
    reminder_rate_limit_hours: int = 24,
) -> dict:
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    ).scalar_one_or_none()
    plan = (
        await db.execute(
            select(WeeklyPlan).where(WeeklyPlan.learner_id == learner_id).order_by(WeeklyPlan.generated_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if not learner or not profile or not plan:
        return {"eligible": False, "reason": "missing_profile_or_plan"}
    if not profile.reminder_enabled or not profile.student_email:
        return {"eligible": False, "reason": "reminder_disabled_or_missing_email"}
    if not _rate_limit_ok(profile, reminder_rate_limit_hours):
        return {"eligible": False, "reason": "rate_limited"}

    current_week = int(plan.current_week or 1)
    onboarding_date = profile.onboarding_date or datetime.now(timezone.utc).date()
    week_start, week_end = week_bounds_from_onboarding(onboarding_date, current_week)
    week_label = format_week_label(current_week, week_start, week_end)

    tasks = (
        await db.execute(select(Task).where(Task.learner_id == learner_id, Task.week_number == current_week))
    ).scalars().all()
    week_complete = bool(tasks) and all(t.status == "completed" for t in tasks)
    if week_complete:
        return {"eligible": False, "reason": "week_complete"}

    last_activity = (
        await db.execute(
            select(EngagementEvent.created_at)
            .where(EngagementEvent.learner_id == learner_id)
            .order_by(EngagementEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    inactivity_cutoff = datetime.now(timezone.utc) - timedelta(days=inactivity_days)
    inactive = last_activity is None or last_activity < inactivity_cutoff
    near_deadline = (week_end - datetime.now(timezone.utc).date()).days <= 1
    progress = float(profile.progress_percentage or 0.0)
    low_progress_midweek = progress < 45.0 and (datetime.now(timezone.utc).date() - week_start).days >= 3
    below_cohort_average = progress < 50.0
    repeated_weak = progress < 35.0

    reasons: list[str] = []
    if inactive:
        reasons.append("inactivity_window_exceeded")
    if near_deadline:
        reasons.append("deadline_proximity")
    if low_progress_midweek:
        reasons.append("progress_below_midweek_threshold")
    if below_cohort_average:
        reasons.append("below_cohort_average")
    if repeated_weak:
        reasons.append("repeated_weak_performance_signal")
    if not reasons:
        reasons.append("week_incomplete")

    return {
        "eligible": True,
        "learner_name": learner.name,
        "email": profile.student_email,
        "week_label": week_label,
        "progress_percentage": progress,
        "reason": reasons[0],
        "all_reasons": reasons,
        "reminder_mode": "dynamic" if any(
            r in reasons for r in ("progress_below_midweek_threshold", "below_cohort_average", "repeated_weak_performance_signal")
        ) else "static",
    }


async def dispatch_due_reminders(
    *,
    db: AsyncSession,
    reminder_rate_limit_hours: int = 24,
    max_batch: int = 200,
    max_attempts: int = 2,
    retry_backoff_seconds: int = 2,
    global_cooldown_seconds: int = 60,
) -> dict:
    profiles = (
        await db.execute(
            select(LearnerProfile)
            .where(LearnerProfile.reminder_enabled.is_(True), LearnerProfile.student_email.isnot(None))
            .limit(max_batch)
        )
    ).scalars().all()
    sent = 0
    failed = 0
    skipped = 0
    items: list[dict] = []
    skip_reasons: dict[str, int] = {}
    attempts_limit = max(1, int(max_attempts))
    backoff_seconds = max(0, int(retry_backoff_seconds))
    for profile in profiles:
        if await _is_dispatch_cooldown_active(
            db=db,
            learner_id=profile.learner_id,
            cooldown_seconds=global_cooldown_seconds,
        ):
            skipped += 1
            reason = "dispatch_cooldown_active"
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            items.append({"learner_id": str(profile.learner_id), "status": "skipped", "reason": reason})
            continue
        verdict = await evaluate_reminder_eligibility(
            db=db,
            learner_id=profile.learner_id,
            reminder_rate_limit_hours=reminder_rate_limit_hours,
        )
        if not verdict.get("eligible"):
            skipped += 1
            reason = str(verdict.get("reason", "ineligible"))
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            continue
        reason = str(verdict.get("reason", "week_incomplete"))
        email = str(verdict.get("email"))
        delivery_attempts: list[dict] = []
        delivered = False
        last_exc: Exception | None = None
        for attempt in range(1, attempts_limit + 1):
            try:
                send_meta = email_service.send_reminder(
                    recipient=email,
                    learner_name=str(verdict.get("learner_name", "Student")),
                    week_label=str(verdict.get("week_label", "Current Week")),
                    progress_percentage=float(verdict.get("progress_percentage", 0.0)),
                    reason=reason,
                    mode="smtp",
                )
                delivery_attempts.append(
                    {"attempt": attempt, "status": "sent", "delivery": send_meta}
                )
                profile.last_reminder_sent_at = datetime.now(timezone.utc)
                db.add(
                    ReminderDeliveryLog(
                        learner_id=profile.learner_id,
                        email=email,
                        mode=str(verdict.get("reminder_mode", "static")),
                        reason=reason,
                        status="sent",
                        details={
                            "reasons": verdict.get("all_reasons", []),
                            "attempts": delivery_attempts,
                            "delivery": send_meta,
                        },
                    )
                )
                sent += 1
                items.append(
                    {
                        "learner_id": str(profile.learner_id),
                        "status": "sent",
                        "reason": reason,
                        "attempts": attempt,
                    }
                )
                delivered = True
                break
            except Exception as exc:
                last_exc = exc
                classified = _classify_delivery_error(exc)
                delivery_attempts.append(
                    {
                        "attempt": attempt,
                        "status": "failed",
                        "error_code": classified,
                        "error": str(exc),
                    }
                )
                if attempt < attempts_limit and backoff_seconds > 0:
                    await asyncio.sleep(backoff_seconds)
        if delivered:
            continue
        failed += 1
        error_code = _classify_delivery_error(last_exc or RuntimeError("unknown"))
        db.add(
            ReminderDeliveryLog(
                learner_id=profile.learner_id,
                email=email,
                mode=str(verdict.get("reminder_mode", "static")),
                reason=reason,
                status="failed_dead_letter",
                details={
                    "error_code": error_code,
                    "error": str(last_exc) if last_exc else "unknown",
                    "attempts": delivery_attempts,
                },
            )
        )
        items.append(
            {
                "learner_id": str(profile.learner_id),
                "status": "failed",
                "reason": reason,
                "error_code": error_code,
                "attempts": attempts_limit,
            }
        )
    await db.commit()
    return {
        "scanned": len(profiles),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "skip_reasons": skip_reasons,
        "dispatch_policy": {
            "reminder_rate_limit_hours": max(1, int(reminder_rate_limit_hours)),
            "max_attempts": attempts_limit,
            "retry_backoff_seconds": backoff_seconds,
            "global_cooldown_seconds": max(0, int(global_cooldown_seconds)),
        },
        "items": items,
    }

