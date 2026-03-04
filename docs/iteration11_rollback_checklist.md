# Iteration 11 Rollback Checklist

Date: 2026-03-04

## Pre-Rollback Snapshot

- Capture current image tag/hash for `mentorix-api`.
- Export current env used by API container.
- Capture:
  - `GET /health`
  - `GET /metrics/app`
  - `GET /onboarding/reminders/diagnostics`

## Rollback Steps

1. Deploy previous stable API image/tag.
2. Restart API container:
   - `docker compose up -d --force-recreate api`
3. Verify health:
   - `GET /health`
4. Verify student UI critical APIs:
   - login/signup + onboarding + learning dashboard endpoints.
5. Verify reminder baseline:
   - `GET /onboarding/reminders/status/{learner_id}` (sample learner)
6. Verify metrics:
   - `GET /metrics/app`

## If Reminder Issues Continue

1. Set `REMINDER_DISPATCH_ENABLED=false` (safe mode).
2. Keep scheduler up for non-reminder jobs if required.
3. Re-run diagnostics endpoint and confirm email config.

## If MCP Path Is Unstable

1. Keep deployment; fallbacks are active by design.
2. Monitor `mcp.mcp_by_operation` failure/fallback rates.
3. If needed, temporarily disable MCP provider registration in startup and redeploy previous tag.

## Post-Rollback Validation

- Run:
  - `scripts/test_mvp.ps1`
- Confirm no student journey regression in UI.
