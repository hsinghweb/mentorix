# Mentorix — V3 Improvement Plan

*Goal: Address all remaining gaps from the [V2 Audit Report](file:///d:/Himanshu/EAG-V2/Capstone/mentorix/docs/PROJECT_AUDIT_REPORT_V2.md) to push the weighted score from **7.4 → 8.0+**.*

---

## Current State Summary (Post-V2)

| Category | V2 Score | Target V3 |
|----------|:---:|:---:|
| Architecture | 8.0 | **8.5** |
| Agent Design | 7.5 | **8.5** |
| Code Quality | 7.5 | **8.0** |
| Scalability | 6.5 | **7.0** |
| Research Value | 7.0 | **7.5** |
| Production Readiness | 7.5 | **8.0** |
| **Weighted Overall** | **7.4** | **~8.0** |

---

## Discrepancies Found: V2 Audit vs. Actual Code

> [!IMPORTANT]
> The V2 audit contains inaccurate assessments that sell the project short. Several items listed as weaknesses have **already been fixed** in the codebase:

| V2 Audit Claim | Actual Codebase State |
|----------------|----------------------|
| "AssessmentAgent (21 lines) — **Stub**" | **134 lines** — Full LLM-backed evaluation with structured output parsing, error classification, deterministic fallback |
| "ReflectionAgent (25 lines) — **Thin**" | **150 lines** — Mastery recalculation, engagement scoring, retention decay adjustment, LLM-generated debrief |
| "OnboardingAgent (20 lines) — **Stub**" | **120 lines** — Risk classification, weak concept identification, pace recommendation, starting depth analysis |
| "No multi-stage Docker build" | **Already multi-stage** — `Dockerfile` has `builder` + `runtime` stages (48 lines) |
| "`agent_dispatch.py` calls agents" | **Method name mismatch** — dispatch calls `.evaluate()`, `.reflect()`, `.analyze()` but agents only have `.run()` and `._execute()` |

> [!CAUTION]
> The `agent_dispatch.py` dispatch calls (`agent.evaluate()`, `agent.reflect()`, `agent.analyze()`) reference methods that **do not exist** on the agent classes. This means dispatch calls are silently failing in the `except` handler. This must be fixed for agents to actually execute in the learning flow.

---

## Improvement Items

### 🔴 P0 — Critical (Highest Score Impact)

---

#### 1. Fix Agent Dispatch Method Mismatch

**Problem**: `agent_dispatch.py` calls methods that don't exist on agents, so dispatches silently fail.

| Dispatch Function | Calls | Agent Has |
|---|---|---|
| `dispatch_assessment()` | `agent.evaluate({...})` | `run()`, `_execute()`, `evaluate(answer, expected)` (2-arg) |
| `dispatch_reflection()` | `agent.reflect({...})` | `run()`, `_execute()` |
| `dispatch_onboarding_analysis()` | `agent.analyze({...})` | `run()`, `_execute()` |

**Fix**: Either add `.evaluate(dict)`, `.reflect(dict)`, `.analyze(dict)` convenience methods to each agent, or refactor `agent_dispatch.py` to call the existing `.run()` or `._execute()` methods with proper `AgentContext` objects.

**Score impact**: Agent Design +0.5, Architecture +0.5

---

#### 2. Extract Business Logic from Route Handlers into Service Layer

**Problem**: `learning/routes.py` (3,132 lines) and `onboarding/routes.py` (2,486 lines) contain orchestration logic.

**Fix**: Create service modules that extract groups of related functions:

| Service Module | Logic to Extract From |
|---|---|
| `services/test_orchestration.py` | Test submission scoring, progression update, mastery recalculation from `learning/routes.py` |
| `services/content_orchestration.py` | Content generation flow, reading material assembly from `learning/routes.py` |
| `services/plan_service.py` | Plan building, week advancement, plan history from `learning/routes.py` |
| `services/diagnostic_service.py` | Diagnostic flow, MCQ generation/validation from `onboarding/routes.py` |
| `services/onboarding_service.py` | Profile creation, timeline selection from `onboarding/routes.py` |

**Target**: Route handlers become thin request/response wrappers (<100 lines per endpoint). Service modules contain reusable business logic.

**Score impact**: Code Quality +0.5, Architecture +0.5

---

#### 3. Remove Dead Code Modules

**Problem**: 4 modules have deprecation warnings and are unused.

**Files to delete**:
- `orchestrator/engine.py` (42 lines) — `StateEngine` unused
- `orchestrator/states.py` (29 lines) — `SessionState` enum only imported by `engine.py`
- `memory/hubs.py` (26 lines) — `StructuredMemoryHubs` unused
- `memory/ingest.py` (50 lines) — `ingest_session_signal` unused

**Preserve**: `orchestrator/agent_compliance.py` — still actively used.

**Score impact**: Code Quality +0.25

---

### 🟡 P1 — Important (Moderate Score Impact)

---

#### 4. Unify Frontend: Migrate `app.js` to Use ES Modules

**Problem**: `app.js` (2,202 lines / 105KB) is the working monolith. 6 ES modules exist in `frontend/src/` but are not imported by `app.js` or `index.html`.

**Fix**:
1. Update `index.html` to use `<script type="module">` imports from `frontend/src/`
2. Split `app.js` into module imports: auth → `src/auth.js`, dashboard → `src/dashboard.js`, etc.
3. Keep `app.js` as a thin entry point that imports and initializes all modules

**Score impact**: Code Quality +0.25

---

#### 5. Add Hybrid Retrieval (BM25 + Semantic)

**Problem**: Vector retrieval is limited to pgvector cosine similarity. No keyword-based fallback.

**Fix**:
1. Add `pg_trgm` extension for trigram-based text search in PostgreSQL
2. Create a `hybrid_retriever.py` that combines:
   - pgvector cosine similarity (semantic)
   - `pg_trgm` trigram search or PostgreSQL `ts_vector` full-text search (keyword)
3. Score fusion: Reciprocal Rank Fusion (RRF) to merge results from both methods
4. Add Alembic migration for `ts_vector` column/index on `EmbeddingChunk`

**Score impact**: Architecture +0.25, Research Value +0.5

---

#### 6. Add Alerting Integration

**Problem**: `ErrorRateTracker` exists in telemetry but has no alerting output.

**Fix**:
1. Add a `WebhookAlertSink` that sends alerts via HTTP webhook (configurable URL)
2. Wire into `ErrorRateTracker` to fire when error rate exceeds threshold
3. Support Discord/Slack-compatible webhook payloads
4. Add configuration in settings: `alert_webhook_url`, `alert_error_rate_threshold`, `alert_cooldown_seconds`

**Score impact**: Production Readiness +0.25

---

#### 7. Naming Consistency Cleanup

**Problem**: Session logs, chapter progression, and subsection progression use different field names for the same concept.

**Fix**: Audit all models and create a naming map. Standardize via Alembic migration + code updates. Examples:
- Unify `score` / `test_score` / `assessment_score`
- Unify `chapter_name` / `chapter` / `concept`
- Unify `time_spent` / `time_spent_minutes` / `duration_minutes`

**Score impact**: Code Quality +0.25

---

### 🟢 P2 — Nice-to-Have (Small Score Impact)

---

#### 8. Extract Magic Numbers into Named Constants

**Problem**: Thresholds like `0.60`, `0.3 + 0.7 * ability`, `0.5 * score + 0.5 * math_9` scattered in route handlers.

**Fix**: Create `core/constants.py` with all learning-domain thresholds:
```python
# Mastery bands
MASTERY_WEAK_THRESHOLD = 0.40
MASTERY_DEVELOPING_THRESHOLD = 0.65
MASTERY_STRONG_THRESHOLD = 0.80

# Scoring weights
ABILITY_BASE_WEIGHT = 0.3
ABILITY_SCALE_WEIGHT = 0.7
```

**Score impact**: Code Quality +0.1

---

#### 9. Add OpenTelemetry Tracing

**Problem**: Correlation ID tracing added in V2 but no distributed tracing standard.

**Fix**:
1. Add `opentelemetry-api` + `opentelemetry-sdk` dependencies
2. Instrument FastAPI with OTEL middleware
3. Add spans for: LLM calls, DB queries, agent dispatch
4. Export to OTLP endpoint (configurable, off by default)

**Score impact**: Production Readiness +0.25

---

#### 10. Student Outcome Analytics

**Problem**: No pre/post assessment comparison for research evaluation.

**Fix**:
1. Add `analytics/outcome_report.py` — generates per-learner trajectory report
2. Compute: mastery growth rate, chapter completion velocity, diagnostic-to-final score delta
3. Expose via `/api/admin/analytics/outcomes` endpoint
4. Add visualization in admin dashboard

**Score impact**: Research Value +0.5

---

## Priority Execution Order

| Phase | Items | Expected Score Impact |
|-------|-------|:---:|
| **Phase 1** | #1 (Fix dispatch mismatch), #3 (Remove dead code) | +0.75 |
| **Phase 2** | #2 (Extract route handler logic into services) | +1.0 |
| **Phase 3** | #4 (Unify frontend), #7 (Naming cleanup), #8 (Magic numbers) | +0.5 |
| **Phase 4** | #5 (Hybrid retrieval), #6 (Alerting), #10 (Outcome analytics) | +1.0 |
| **Phase 5** | #9 (OpenTelemetry) | +0.25 |

---

## Projected V3 Scorecard

| Category | V2 Score | V3 Target | Key Drivers |
|----------|:---:|:---:|-----------|
| Architecture | 8.0 | **8.5** | Route handler extraction, hybrid retrieval, dispatch fix |
| Agent Design | 7.5 | **8.5** | Fix dispatch so agents actually execute, agents already enriched |
| Code Quality | 7.5 | **8.0** | Dead code removal, frontend unification, naming cleanup, constants |
| Scalability | 6.5 | **7.0** | Hybrid retrieval, already has multi-stage Docker |
| Research Value | 7.0 | **7.5** | Hybrid retrieval, outcome analytics |
| Production Readiness | 7.5 | **8.0** | Alerting, OpenTelemetry, multi-stage Docker already done |
| **Weighted Overall** | **7.4** | **~8.0** | |

---

## Verification Strategy

- **Agent dispatch fix**: Write integration test that calls each `dispatch_*` function and asserts non-None return
- **Route extraction**: Run existing test suite + verify no import errors
- **Dead code removal**: `grep -r` to confirm no remaining imports of deleted modules
- **Frontend unification**: Manual browser test of all pages (login, onboarding, dashboard, testing, admin)
- **Hybrid retrieval**: Unit test comparing retrieval recall on known test queries vs. pure pgvector
