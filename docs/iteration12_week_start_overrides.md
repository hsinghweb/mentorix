# Iteration 12: `week_start_overrides` Operator Note

## Purpose

`week_start_overrides` allows the planner to shift calendar week starts forward when a learner completes a week early.  
This makes schedule labels and completion dates reflect actual learner pace, not only nominal onboarding-date offsets.

## Payload Shape

- Location: `weekly_plans.plan_payload.week_start_overrides`
- Type: object (map)
- Key: week number as string (for example `"2"`, `"3"`)
- Value: ISO date string `YYYY-MM-DD`

Example:

```json
{
  "week_start_overrides": {
    "2": "2026-03-07",
    "3": "2026-03-14"
  }
}
```

## Semantics

- Week 1 starts at `onboarding_date` unless override `"1"` is set.
- For week `N`, if override `"N"` exists, that date is used as the week start.
- If override is missing, week `N` starts 7 days after the resolved start of week `N-1`.
- Week end is always `start + 6 days`.

## Rollback Expectations

- Safe rollback: remove `week_start_overrides` from `plan_payload`.
- Effect after rollback:
  - week labels/dates return to pure onboarding-date weekly offsets.
  - scheduled completion date returns to nominal week-grid projection.
  - no learner progress/task completion data is deleted.

## Operational Checks

1. Verify timeline fields from API:
   - `GET /learning/dashboard/{learner_id}`
   - `GET /onboarding/plan/{learner_id}`
   - `GET /onboarding/schedule/{learner_id}`
2. Confirm `current_week_label`, `week_start_date`, `week_end_date`, and `completion_estimate_date` align.
3. Check log line:
   - `event=week_advance_replan ... early_start_applied=true|false`
