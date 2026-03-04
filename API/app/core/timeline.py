from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


TIMELINE_TZ = timezone.utc


def canonical_today() -> date:
    return datetime.now(TIMELINE_TZ).date()


def week_bounds_from_onboarding(onboarding_date: date, week_number: int) -> tuple[date, date]:
    safe_week = max(1, int(week_number))
    start = onboarding_date + timedelta(days=(safe_week - 1) * 7)
    end = start + timedelta(days=6)
    return start, end


def format_week_label(week_number: int, start: date, end: date) -> str:
    start_fmt = f"{start:%b} {start.day}"
    end_fmt = f"{end:%b} {end.day}"
    if start.year == end.year:
        return f"Week {week_number} ({start_fmt} - {end_fmt}, {end.year})"
    return f"Week {week_number} ({start_fmt}, {start.year} - {end_fmt}, {end.year})"


def build_week_timeline_item(*, onboarding_date: date, week_number: int, is_current: bool, is_past: bool) -> dict:
    start, end = week_bounds_from_onboarding(onboarding_date, week_number)
    return {
        "week_number": week_number,
        "week_start_date": start.isoformat(),
        "week_end_date": end.isoformat(),
        "week_label": format_week_label(week_number, start, end),
        "is_current": bool(is_current),
        "is_past": bool(is_past),
    }


def estimate_completion_date(
    *,
    onboarding_date: date,
    current_week: int,
    total_weeks_forecast: int | None,
    as_of: date | None = None,
) -> dict:
    today = as_of or canonical_today()
    elapsed_days = max(1, (today - onboarding_date).days + 1)
    elapsed_weeks = max(1.0, elapsed_days / 7.0)
    completed_weeks = max(0, int(current_week) - 1)
    pace = max(0.01, completed_weeks / elapsed_weeks)

    forecast = int(total_weeks_forecast or current_week or 1)
    remaining_weeks = max(0.0, float(forecast - completed_weeks))
    eta_weeks_active_pace = int(round(remaining_weeks / pace)) if remaining_weeks > 0 else 0
    eta_days = int(round(eta_weeks_active_pace * 7))
    completion_date = today + timedelta(days=eta_days)
    return {
        "active_pace_weeks_per_week": round(pace, 3),
        "estimated_completion_date": completion_date.isoformat(),
        "completion_estimate_weeks_active_pace": max(0, eta_weeks_active_pace),
    }
