from types import SimpleNamespace
from datetime import date

from app.api.learning import _merge_replanned_future, _remaining_chapter_numbers
from app.api.onboarding import _build_timeline_visualization
from app.core.timeline import week_bounds_from_plan


def test_remaining_chapters_skips_completed_first_attempt():
    progressions = [
        SimpleNamespace(chapter="Chapter 1", status="completed_first_attempt"),
        SimpleNamespace(chapter="Chapter 2", status="in_progress"),
    ]
    remaining = _remaining_chapter_numbers(progressions)
    assert remaining[0] == 2
    assert 1 not in remaining


def test_week_bounds_shift_when_next_week_starts_early():
    onboarding_date = date(2026, 3, 7)
    overrides = {"2": "2026-03-07"}

    week1_start, week1_end = week_bounds_from_plan(onboarding_date, 1, overrides)
    week2_start, week2_end = week_bounds_from_plan(onboarding_date, 2, overrides)
    week3_start, week3_end = week_bounds_from_plan(onboarding_date, 3, overrides)

    assert week1_start == date(2026, 3, 7)
    assert week1_end == date(2026, 3, 13)
    assert week2_start == date(2026, 3, 7)
    assert week2_end == date(2026, 3, 13)
    assert week3_start == date(2026, 3, 14)
    assert week3_end == date(2026, 3, 20)


def test_replanned_weeks_replace_stale_chapter_assignment_after_week_advance():
    existing = [
        {"week": 1, "chapter": "Chapter 1", "focus": "learn + practice"},
        {"week": 2, "chapter": "Chapter 1", "focus": "stale"},
        {"week": 3, "chapter": "Chapter 2", "focus": "stale"},
    ]
    progressions = [
        SimpleNamespace(chapter="Chapter 1", status="completed_first_attempt"),
        SimpleNamespace(chapter="Chapter 2", status="not_started"),
    ]
    remaining = _remaining_chapter_numbers(progressions)
    replanned = _merge_replanned_future(
        existing,
        current_week=2,
        total_weeks=4,
        remaining_chapters=remaining,
    )

    week2 = next(item for item in replanned if item["week"] == 2)
    week3 = next(item for item in replanned if item["week"] == 3)
    assert week2["chapter"] == "Chapter 2"
    assert week3["chapter"] == "Chapter 3"


def test_api_timeline_visualization_uses_week_start_overrides():
    viz = _build_timeline_visualization(
        onboarding_date=date(2026, 3, 7),
        total_weeks=3,
        current_week=2,
        rough_plan_by_week={
            1: {"chapter": "Chapter 1", "focus": "learn + practice"},
            2: {"chapter": "Chapter 2", "focus": "learn + practice"},
            3: {"chapter": "Chapter 3", "focus": "learn + practice"},
        },
        week_start_overrides={"2": "2026-03-07"},
    )
    assert viz[1]["week_start_date"] == "2026-03-07"
    assert viz[1]["week_end_date"] == "2026-03-13"
    assert viz[2]["week_start_date"] == "2026-03-14"
