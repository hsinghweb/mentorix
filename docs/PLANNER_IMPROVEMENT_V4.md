# Mentorix V4 Improvement Plan

*Based on [PROJECT_AUDIT_REPORT_V3.md](file:///d:/Himanshu/EAG-V2/Capstone/mentorix/docs/PROJECT_AUDIT_REPORT_V3.md) — targeting weighted score **7.9 → ~8.5+***

---

## Current Scores (V3)

| Category | Score | Key Gap |
|----------|:-----:|---------|
| Architecture | 8.5 | Route files still 3,160 + 2,437 lines |
| Agent Design | 8.5 | `AdaptationAgent` only 40 lines |
| Code Quality | 8.0 | Frontend `app.js` monolith (2,266 lines) |
| Scalability | 7.0 | No async batching, no read replicas |
| Research Value | 7.5 | No empirical data, no A/B framework |
| Production Readiness | 8.0 | No secret management, no log aggregation |

---

## Phase 1 — Route Handler Decomposition (Architecture 8.5 → 9.0)

> **Impact**: Largest remaining code quality gap. Directly addresses audit §6 weakness: "Route handlers still large."

### Task 1: Split `learning/routes.py` into sub-routers

**File**: `API/app/api/learning/routes.py` (3,160 lines)

Break into 5 focused sub-router modules:

| New Module | Endpoints | Est. Lines |
|-----------|-----------|:----------:|
| `content_routes.py` | `/content`, `/subsection-content`, `/explain-question` | ~500 |
| `test_routes.py` | `/generate-test`, `/submit-test`, `/section-test/*`, `/practice/*` | ~800 |
| `dashboard_routes.py` | `/dashboard`, `/decisions/*`, `/source/*` | ~600 |
| `week_routes.py` | `/complete-week`, `/complete-reading`, `/tasks/*` | ~500 |
| `plan_routes.py` | `/plan-versions/*`, `/replan`, `/forecast` | ~400 |

Keep `routes.py` as a thin aggregator that imports and mounts the sub-routers.

### Task 2: Split `onboarding/routes.py` into sub-routers

**File**: `API/app/api/onboarding/routes.py` (2,437 lines)

Break into 3 focused sub-router modules:

| New Module | Endpoints | Est. Lines |
|-----------|-----------|:----------:|
| `diagnostic_routes.py` | `/diagnostic-test`, `/submit-diagnostic` | ~600 |
| `plan_routes.py` | `/generate-plan`, `/plan-history`, `/replan` | ~500 |
| `profile_routes.py` | `/profile`, `/update-profile`, `/signup` | ~400 |

---

## Phase 2 — Frontend Modularization (Code Quality 8.0 → 8.5)

> **Impact**: Addresses audit §6 weakness: "Frontend `app.js` still primary (2,266 lines)."

### Task 3: Migrate `app.js` into ES module consumers

Split `app.js` into domain-specific modules that import from existing `src/` modules:

| Module | Responsibility |
|--------|---------------|
| `src/auth.js` | Already exists — auth flows |
| `src/dashboard.js` | Already exists — dashboard rendering |
| `src/onboarding.js` | Already exists — diagnostic + plan generation |
| `src/testing.js` | Already exists — test UI + submission |
| `src/admin.js` | Already exists — admin panel |
| `src/helpers.js` | Already exists — shared utilities |

**Action**: Move the corresponding functionality from `app.js` into these modules. Update `main.js` to be the primary entry point and remove the `app.js` script tag from `index.html`.

### Task 4: Add type-safe API client

Create `src/api-client.js` with typed request/response wrappers for each backend endpoint. This eliminates scattered `fetch()` calls throughout `app.js`.

---

## Phase 3 — Agent Enrichment (Agent Design 8.5 → 9.0)

> **Impact**: `AdaptationAgent` is only 40 lines. Enriching it brings all agents to "Rich" classification.

### Task 5: Enrich `AdaptationAgent`

**File**: `API/app/agents/adaptation.py` (40 lines)

Current: Simple LLM call with minimal context.
Target: Enriched adaptation with:
- Multi-signal input (mastery map, engagement trend, retention decay, completion velocity)
- LLM-based policy recommendation with structured output parsing
- Deterministic fallback when LLM unavailable
- Logging and tracing integration

### Task 6: Wire `AdaptationAgent` into dispatch

**File**: `API/app/services/agent_dispatch.py`

Add `dispatch_adaptation()` function that calls `AdaptationAgent.run(AgentContext)` after plan adjustments, similar to the existing assessment/reflection/onboarding dispatches.

---

## Phase 4 — Scalability (Scalability 7.0 → 8.0)

> **Impact**: Addresses audit §9 "Still Missing" items.

### Task 7: Add async LLM request batching

**File**: `API/app/core/llm_provider.py`

Add a `BatchLLMProvider` wrapper that:
- Collects concurrent `generate()` calls within a configurable window (e.g., 50ms)
- Sends them as a batch to the LLM API (if supported) or runs them concurrently via `asyncio.gather()`
- Returns individual results to callers
- Tracks batch statistics in Prometheus

### Task 8: Add background task queue for content generation

Create `API/app/core/task_queue.py`:
- Use `asyncio.Queue` for in-process task queuing
- Configurable concurrency limit (default: 3 parallel LLM calls)
- Priority queue: test generation > content generation > practice generation
- Expose queue depth via Prometheus gauge

### Task 9: Add GIN index for full-text search performance

Create Alembic migration to add GIN indexes on `embedding_chunks.content` using `to_tsvector('english', content)`. This makes the hybrid retriever's keyword search path significantly faster.

---

## Phase 5 — Production Hardening (Prod Readiness 8.0 → 8.5)

> **Impact**: Addresses audit §7 gaps: "No secret management", "No log aggregation."

### Task 10: Add environment-aware secret management

Create `API/app/core/secrets.py`:
- Support 3 backends: environment variables (default), AWS Secrets Manager, HashiCorp Vault
- Auto-detect backend from `SECRET_BACKEND` env variable
- Cache secrets with configurable TTL
- Rotate API keys without restart

### Task 11: Add structured JSON logging with log aggregation support

Modify `API/app/core/logging.py`:
- Add optional JSON formatter (`LOG_FORMAT=json`)
- Include correlation ID, learner ID, agent name in all structured log entries
- Add Loki/Fluentd-compatible output format
- Add log sampling for high-volume endpoints (content generation, dashboard)

### Task 12: Add rate limiting per learner

Create `API/app/core/rate_limiter.py`:
- Redis-backed sliding window rate limiter
- Per-learner limits for LLM-intensive endpoints (content generation: 10/min, test generation: 5/min)
- Global burst limit for the API (100 req/s)
- Return `429 Too Many Requests` with `Retry-After` header

---

## Phase 6 — Research & Analytics (Research Value 7.5 → 8.5)

> **Impact**: Addresses audit §11: "Still needs actual student data" and "No A/B testing framework."

### Task 13: Add A/B testing framework for content strategies

Create `API/app/services/ab_testing.py`:
- Random learner assignment to experiment groups (control/treatment)
- Track which content strategy, tone, or difficulty level each learner received
- Store experiment metadata in PostgreSQL
- Expose experiment results via outcome analytics

### Task 14: Add analytics export API

Create `API/app/api/analytics/routes.py`:
- `GET /analytics/outcomes` → cohort summary (uses existing `outcome_analytics.py`)
- `GET /analytics/outcomes/{learner_id}` → individual learner outcome
- `GET /analytics/export` → CSV download of all learner outcomes
- `GET /analytics/experiments` → A/B test results

### Task 15: Add data-driven evaluation README

Create `docs/RESEARCH_EVALUATION.md`:
- Document how to run outcome analytics against student data
- Define the evaluation metrics (mastery growth, completion velocity, retention)
- Provide sample analysis queries
- Include template for workshop/conference paper results section

---

## Summary

| Phase | Tasks | Target Score Delta |
|-------|:-----:|:------------------:|
| 1. Route Decomposition | 1–2 | Architecture +0.5 |
| 2. Frontend Modularization | 3–4 | Code Quality +0.5 |
| 3. Agent Enrichment | 5–6 | Agent Design +0.5 |
| 4. Scalability | 7–9 | Scalability +1.0 |
| 5. Production Hardening | 10–12 | Prod Readiness +0.5 |
| 6. Research & Analytics | 13–15 | Research Value +1.0 |

**Projected V4 score: ~8.5+ / 10** (up from 7.9)

---

## Priority Order

1. **Phase 1** (Tasks 1–2): Highest impact per effort — directly addresses the single largest code quality gap
2. **Phase 3** (Tasks 5–6): Quick win — `AdaptationAgent` enrichment is a small, focused change
3. **Phase 6** (Tasks 13–15): Research value — the A/B testing + analytics export make the system publishable
4. **Phase 2** (Tasks 3–4): Frontend cleanup — important but lower risk
5. **Phase 4** (Tasks 7–9): Scalability — highest effort, most operational benefit
6. **Phase 5** (Tasks 10–12): Production hardening — vault + rate limiting are deployment prerequisites
