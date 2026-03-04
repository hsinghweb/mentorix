# Iteration 11 Migration Notes

Date: 2026-03-04

## Removed Legacy API Surfaces

Deleted (non-UI legacy):

- `API/app/api/sessions.py`
- `API/app/api/memory.py`
- `API/app/api/events.py`
- `API/app/api/notifications.py`
- `API/app/api/runs.py`
- `API/app/schemas/session.py`
- `API/app/agents/memory_manager.py`

Router registrations removed from:

- `API/app/main.py`

## Test Path Changes

Deleted legacy tests:

- `API/tests/test_session17_compliance.py`
- `API/tests/test_session19_concepts.py`

Updated compatibility in `API/tests/test_learning_flow.py`:

- Added required `student_email` in signup payloads.

## Reminder Reliability Additions

- New endpoint: `GET /onboarding/reminders/diagnostics`
- Dispatch now includes:
  - retry attempts
  - failure taxonomy
  - dead-letter-style failure logs (`failed_dead_letter`)
  - dispatch cooldown + skip reason reporting

## MCP Additions

- New MCP providers:
  - `llm.generate_text`
  - `onboarding.recommend_timeline`
- Metrics extended with per-operation breakdown.

## Config Additions

New settings:

- `REMINDER_DISPATCH_MAX_ATTEMPTS`
- `REMINDER_DISPATCH_RETRY_BACKOFF_SECONDS`
- `REMINDER_DISPATCH_GLOBAL_COOLDOWN_SECONDS`

Updated templates:

- `env_template`
- `CONFIG/local_env_template.txt`
