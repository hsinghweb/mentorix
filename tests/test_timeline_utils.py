from __future__ import annotations

from datetime import date

from app.core.timeline import format_week_label, week_bounds_from_onboarding


def test_week_bounds_deterministic_from_onboarding_date():
    onboarding = date(2026, 3, 3)
    start1, end1 = week_bounds_from_onboarding(onboarding, 1)
    start2, end2 = week_bounds_from_onboarding(onboarding, 2)
    assert start1.isoformat() == "2026-03-03"
    assert end1.isoformat() == "2026-03-09"
    assert start2.isoformat() == "2026-03-10"
    assert end2.isoformat() == "2026-03-16"


def test_week_label_handles_year_boundary():
    onboarding = date(2026, 12, 30)
    start, end = week_bounds_from_onboarding(onboarding, 1)
    label = format_week_label(1, start, end)
    assert "Week 1" in label
    assert "2026" in label or "2027" in label
