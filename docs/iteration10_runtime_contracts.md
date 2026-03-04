# Iteration 10 Runtime Contracts

## MCP Contract
- Request shape: `operation`, `payload`, `context`.
- Response shape: `ok`, `result`, `error`, `fallback_used`, `latency_ms`, `ts`.
- Registered operation: `agent.dispatch`.
- Observability: `/metrics/app -> mcp`.

## Calendar Mapping Contract
- Timeline fields now exposed in plan/dashboard payloads:
  - `onboarding_date`
  - `timeline_timezone`
  - `current_week_label`
  - `timeline_visualization[]` (`week_start_date`, `week_end_date`, `week_label`)
  - `completion_estimate_date_active_pace`

## Comparative Analytics Contract
- Endpoint: `GET /onboarding/comparative-analytics/{learner_id}`
- Top-level keys:
  - `individual` (topic mastery/time/velocity/completion/weak-strong/trend)
  - `comparative` (percentile, cohort avg, similar cluster, trend)
  - `hooks` (adaptive difficulty hints + early warning signals)
  - `performance` (computation/scalability metadata)
- Privacy: comparative values suppressed when cohort is too small (`anonymized=false`).

## Reminder Contract
- Onboarding/auth capture `student_email`.
- Reminder endpoints:
  - `GET /onboarding/reminders/status/{learner_id}`
  - `POST /onboarding/reminders/dispatch-due`
  - `POST /onboarding/reminders/unsubscribe/{learner_id}`
  - `GET /onboarding/reminders/logs/{learner_id}`

