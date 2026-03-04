# Iteration 11 MCP Adoption Audit

Date: 2026-03-04

## Student Journey MCP Coverage

### UI-critical flow map

- Signup/Login:
  - `POST /auth/start-signup`, `POST /auth/login`
  - MCP usage: `none` (not required)
- Onboarding:
  - `POST /onboarding/diagnostic-questions`
  - `POST /onboarding/submit`
  - MCP usage:
    - `onboarding.recommend_timeline` used by onboarding submit to compute recommended timeline with fallback.
- Learning:
  - `POST /learning/content`
  - `POST /learning/test/generate`
  - `POST /learning/test/question/explain`
  - `POST /learning/content/section`
  - `POST /learning/test/section/generate`
  - MCP usage:
    - `llm.generate_text` used for LLM text generation in the above endpoints, with deterministic fallback path.

## Fallback Behavior

- MCP execution uses `execute_mcp(...)` fallback handler.
- If MCP provider fails/unavailable, fallback executes direct local logic and request still succeeds when fallback succeeds.
- Failure payload preserves error + `fallback_used` for observability.

## Observability

`GET /metrics/app` now returns:

- `mcp.mcp_calls_total`
- `mcp.mcp_calls_failed`
- `mcp.mcp_fallback_used`
- `mcp.mcp_failure_rate`
- `mcp.mcp_fallback_rate`
- `mcp.mcp_latency_ms_avg`
- `mcp.mcp_by_operation[]` with per-operation totals, failures, fallback rate, and avg latency.

## Current MCP Operations Registered

- `llm.generate_text`
- `onboarding.recommend_timeline`
