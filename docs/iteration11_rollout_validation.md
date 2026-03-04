# Iteration 11 Rollout and Validation Checklist

Date: 2026-03-04

## Rollout Order

1. Deploy API image with Iteration 11 changes.
2. Confirm API health and scheduler state.
3. Validate reminder diagnostics endpoint and policy values.
4. Validate MCP metrics payload shape.
5. Validate UI comparative panel rendering.
6. Run fast regression profile.
7. Run full regression profile.

## Validation Commands

- Build + run API:
  - `docker compose up -d --build api`
- Fast profile:
  - `powershell -ExecutionPolicy Bypass -File .\\scripts\\test_fast.ps1`
- Full profile:
  - `powershell -ExecutionPolicy Bypass -File .\\scripts\\test_full.ps1 -BaseUrl http://localhost:8000`
- Frontend math sanitization regression:
  - `node frontend/tests/math_sanitize_cases.js`

## Acceptance Gate

Release is approved only if:

- `scripts/test_fast.ps1` passes.
- `scripts/test_full.ps1` passes.
- `/onboarding/reminders/diagnostics` returns expected dispatch policy + email readiness payload.
- `/metrics/app` includes MCP operation breakdown (`mcp_by_operation`).
