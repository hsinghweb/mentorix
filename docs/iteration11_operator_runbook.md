# Iteration 11 Operator Runbook

Date: 2026-03-04

## 1) Health and Scheduler

- Check API health:
  - `GET /health`
- Expected fields:
  - `scheduler_enabled`
  - `scheduled_jobs`

If scheduler should be active, ensure:

- `SCHEDULER_ENABLED=true`
- API restarted after env changes.

## 2) Reminder Operations

### Diagnostic readiness

- `GET /onboarding/reminders/diagnostics`

Read:

- `runtime_ready`
- `dispatch_policy`
- `email.smtp.ready`
- `email.gmail_api.ready`
- `configuration_precedence` (`.env`, `CONFIG/local.env`)

### Dispatch

- `POST /onboarding/reminders/dispatch-due`

Response includes:

- `scanned`, `sent`, `failed`, `skipped`
- `skip_reasons`
- `dispatch_policy`
- per-learner `items[]`

### Failure taxonomy

`items[].error_code`/delivery log details can include:

- `smtp_config_incomplete`
- `smtp_auth_failed`
- `smtp_recipients_refused`
- `smtp_connect_failed`
- `smtp_timeout`
- `gmail_api_credentials_missing`
- `gmail_api_flow_not_configured`
- `unknown_delivery_error`

## 3) MCP Metrics Interpretation

Endpoint:

- `GET /metrics/app`

Use `mcp.mcp_by_operation`:

- High `failure_rate` + low fallback success: provider instability.
- High `fallback_rate` with low `failure_rate`: MCP provider path may be degraded while fallback preserves UX.
- High `latency_ms_avg`: inspect provider-specific bottleneck.

## 4) Common Troubleshooting

- Reminder 404 route issue after deploy:
  - rebuild/restart API container (`docker compose up -d --build api`).
- `scheduler_enabled=false` unexpectedly:
  - check active env source and restart API.
- Zero MCP traffic:
  - run student journey endpoints that use LLM/onboarding submit, then check `/metrics/app`.
