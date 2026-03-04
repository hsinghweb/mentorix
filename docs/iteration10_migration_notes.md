# Iteration 10 Migration Notes (MCP, Calendar, Analytics, Reminders)

## Scope
- MCP contract path introduced for inter-agent dispatch in `sessions` (`agent.dispatch`).
- Calendar-aware week mapping introduced for onboarding/learning plan and dashboard payloads.
- Comparative analytics endpoint added: `GET /onboarding/comparative-analytics/{learner_id}`.
- Student email + reminder profile and reminder delivery audit logs added.

## Database Additions
- `learner_profile` new columns:
  - `onboarding_date` (DATE)
  - `student_email` (VARCHAR)
  - `progress_status` (VARCHAR)
  - `progress_percentage` (FLOAT)
  - `last_reminder_sent_at` (TIMESTAMPTZ)
  - `reminder_enabled` (BOOLEAN)
- New table: `reminder_delivery_logs`
  - learner/email/mode/reason/status/details/created_at

## Backward Compatibility
- Existing fields are preserved.
- New payload keys are additive (week dates/labels, timeline visualization, completion estimate by active pace).
- MCP path has fallback to prior direct dispatch semantics.

## Rollback Strategy
1. Disable reminder scheduler with `REMINDER_DISPATCH_ENABLED=false`.
2. Revert to direct inter-agent dispatch by bypassing MCP client wrapper in `sessions._invoke_agent`.
3. Ignore additive API fields in clients (safe due additive shape).
4. Keep new DB columns/tables in place (non-destructive rollback).

