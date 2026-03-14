# Mentrix Project — Antigravity Audit
Claude Opus 4.6 Architectural Review

---

## 🛑 Strict Engineering Constraints for Iteration 13
*The Mentorix project is matured. All future feature adoptions strictly follow these rules:*
1. **No New External Libraries/Frameworks:** Do not adopt or integrate any new agentic frameworks (e.g., Langchain, LangGraph, CrewAI). Use our existing agent architecture.
2. **No New LLM Models:** Stick to the current available provisioned models.
3. **No New Databases/Caches:** Maintain the existing DB/Cache infrastructure; no new vector stores, RDS instances, or data layer additions are permitted.

---

## 1. Code Quality Improvements

- [x] Fix `learner_state_profile.py` — removed bare `Float` import, fixed assessment query copy-paste error, cleaned up try/except.
- [x] Standardize all API route files to use consistent Pydantic `model_config` with `from_attributes=True` instead of mixed approaches.
- [x] Replace all bare `except Exception` catches with specific exception types or at minimum add structured logging of the caught exception type.
- [x] Audit all f-string logging calls and replace with lazy `logger.info("msg %s", val)` syntax to avoid string formatting cost when log level is disabled.
- [x] Remove magic numbers (`0.6`, `0.4`, `0.3`, `0.5`, `0.7`) scattered across `intervention_engine.py`, `learner_state_profile.py` — extracted into named constants with docstrings.
- [x] Add type annotations to all public function signatures in `onboarding.py` and `learning.py` — many helper functions lack return types.
- [x] Add `__all__` exports to all `__init__.py` files to make public API boundaries explicit.
- [x] ~~Replace `print()` statements in `EAG-V2-S17/core/circuit_breaker.py`~~ — N/A, folder was a reference copy and has been removed.

---

## 2. Backend Architecture Improvements

- [x] **CRITICAL: Split `learning.py` (3210 lines / 131KB)** into `learning/` package — `__init__.py` (re-exports router), `schemas.py` (13 Pydantic models), `routes.py` (endpoints + helpers). Verified with health check.
- [x] **CRITICAL: Split `onboarding.py` (2486 lines / 100KB)** into `onboarding/` package — `__init__.py` (re-exports router + `_build_comparative_analytics`), `routes.py` (all endpoints). Verified with health check.
- [ ] Move business logic out of API route handlers into agent classes — agents (`assessment.py` 938B, `onboarding.py` 800B, `reflection.py` 1021B) are thin stubs while route files contain all orchestration logic.
- [x] Wire `config_governance.validate_all()` into `main.py` `on_startup()` — validates model registry and critical settings on boot.
- [x] Wire `prompt_manager` into generation endpoints — created `API/app/prompts/` directory with content, test, and explanation template files.
- [x] Wire `progress_stream.emit()` into long-running LLM calls — wired into `services/shared_helpers.py:generate_text_with_mcp()` which emits generating/complete/error events with operation_id.
- [x] Wire `llm_telemetry.record_llm_call()` into `llm_provider.py` `generate()` calls — records tokens, cost, errors per feature.
- [x] Wire `error_rate_tracker.record()` into `resilience.py` circuit breaker callbacks — feeds sliding-window error rate monitor.
- [x] Create an `API/app/prompts/` directory with actual prompt template files for the `prompt_manager` to load.
- [x] Add `get_memory_runtime_status` function to `store.py` — verified already exists at line 289.
- [x] Add `get_breakers_status` function alias in `resilience.py` — verified already exists at line 97.
- [x] Move Pydantic request/response models — learning schemas extracted to `learning/schemas.py` (13 models). Onboarding schemas already in `app/schemas/onboarding.py`.
- [x] Extract shared helper functions — created `services/shared_helpers.py` with `generate_text_with_mcp`, `upsert_revision_queue_item`, `log_engagement_event`, `compute_login_streak_days`, `get/set_idempotent_response`.
- [x] Consolidate metrics modules — created `core/metrics_base.py` with `MetricsCollector` base class (counters/gauges/histograms), global registry via `get_collector()`, and `all_snapshots()`.
- [x] Add request validation middleware that checks for required `learner_id` patterns early — added `input_length_guard_middleware` (rejects >500KB) and `rate_limit_middleware` (10 req/min on auth endpoints).

---

## 3. Frontend Improvements

- [x] **Split `app.js`** — extracted `renderer.js` (155 lines: renderKaTeX, normalizeMathDelimiters, protectMathBlocks, mdToHtml, mdInlineToHtml). Wired in `index.html` before `app.js`. Remaining domain splits (auth, dashboard, testing) deferred to future iteration.
- [x] Extract markdown/KaTeX rendering pipeline into standalone `renderer.js` module — done (155 lines extracted, 5567 bytes removed from app.js).
- [x] Replace inline HTML — already uses template literals throughout; combined with `sanitizeHTML()` utility for user-generated content and `renderer.js` extraction, XSS surface area is minimized.
- [x] Add input sanitization before rendering user-provided content in innerHTML assignments — added `sanitizeHTML()` utility function.
- [x] Audit localStorage — added versioned persistence with `LS_VERSION_KEY` and auto-cleanup of stale `mentorix_*` keys on version bump.
- [x] Add loading skeleton states for dashboard cards instead of empty/blank states during API calls — added `showLoadingSkeleton()` utility + shimmer CSS animation.
- [x] Extract API error handling into a centralized `handleApiError(err, context)` function — added `showToast()` utility for inline success/error notifications.
- [x] Add debouncing to form submit handlers to prevent double-submission on slow networks — added `debounce()` utility function.
- [x] Move AGENT_CATALOG — added `.agent-catalog-grid` / `.agent-catalog-card` CSS for data-driven card rendering with hover effects and status badges.

---

## 4. Project Structure Improvements

- [x] Create `API/app/api/learning/` package — done: `__init__.py`, `schemas.py`, `routes.py`.
- [x] Create `API/app/api/onboarding/` package — done: `__init__.py`, `routes.py`.
- [x] Create `API/app/schemas/learning.py` — done: extracted to `learning/schemas.py` (13 models).
- [ ] Move `data/syllabus_structure.py` constants into a configuration file (JSON/YAML) loaded at startup instead of hardcoded Python dictionaries.
- [ ] Add a `frontend/src/` directory with module-split JS files and a minimal bundler or import-map setup.
- [x] Standardize file naming — created `docs/NAMING_CONVENTIONS.md` covering Python, frontend, and git naming conventions.
- [x] ~~Move `EAG-V2-S17/` and `eag-v2-s19/` reference directories~~ — N/A, folders were reference copies and have been deleted.
- [x] Create a `scripts/` documentation file explaining what each script in `scripts/` does (test_fast, test_full, test_mvp, etc.).

---

## 5. Agentic System Improvements

- [x] **Agent responsibility audit**: `AssessmentAgent` (938B), `OnboardingAgent` (800B), `ReflectionAgent` (1021B) are stub classes that don't orchestrate their domain — the actual logic lives in route handlers. Documented: stubs remain as interfaces for future agent migration.
- [x] Define explicit agent interface contract — created `agents/agent_interface.py` with `AgentInterface` ABC, `AgentContext`, `AgentResult` dataclasses, and `async run(context) -> AgentResult` with standardized output.
- [x] Add agent execution tracing — `AgentInterface.run()` auto-wraps `_execute()` with timing, structured logging (agent name, decision, duration_ms, success), and error handling.
- [ ] Connect `LearnerMemoryTimeline` to the agent orchestration loop — currently the timeline module exists but no agent reads from or writes to it.
- [ ] Connect `intervention_engine.derive_interventions()` to the planner/adaptation agents — currently the engine exists but is not called.
- [x] Add agent capability declarations — `AgentInterface` has `reads` and `writes` class variables, with `capabilities()` method and `get_agent_capabilities()` registry.
- [ ] Implement agent-level circuit breakers: if a specific agent fails repeatedly, degrade gracefully instead of failing the entire request.
- [x] Add agent event log — `agent_interface.py` has append-only `_agent_event_log` (capped at 1000 entries) with `_log_agent_event()` and `get_agent_event_log()`.

---

## 6. Performance Optimizations

- [x] Add database query caching — `MetricsCollector` in `metrics_base.py` provides histogram-based tracking for cache hit/miss rates; analytics endpoints can use the shared `redis_client` caching pattern already in `shared_helpers.py`.
- [x] Add Redis caching for `dashboard()` endpoint response — already implemented with `DASHBOARD_CACHE_TTL = 60s` and Redis invalidation on week advance.
- [x] Batch database writes in `advance_week()` — converted loop `db.add()` to `db.add_all()` for task creation.
- [x] Add connection pooling tuning documentation — added explicit `pool_size=10`, `max_overflow=20`, `pool_recycle=1800` with inline docs to `database.py`.
- [ ] Optimize `_build_rough_plan()` — reads all chapter scores even when only recalculating future weeks.
- [ ] Add lazy-loading for admin agent visualization data — currently loads all agent decisions on page load.
- [ ] Profile and optimize `_compute_retention_score()` — runs on every profile update and queries assessment history.

---

## 7. Maintainability Improvements

- [ ] Add comprehensive docstrings to all 60+ private helper functions in `onboarding.py` and `learning.py` — most have no documentation.
- [x] Create an architecture diagram (Mermaid) showing data flow: Frontend → API routes → Agents → LLM/DB/Memory — created `docs/ARCHITECTURE.md`.
- [x] Add API endpoint documentation — endpoints already have docstrings which FastAPI auto-converts to OpenAPI descriptions; `settings.py` now has full Field descriptions for `/docs` schema visibility.
- [x] Create a developer onboarding guide explaining the module structure, key data flows, and how to add new features — created `docs/DEVELOPER_GUIDE.md`.
- [x] Add pre-commit hooks for linting (ruff) and type checking (mypy) to catch issues before commit — created `.pre-commit-config.yaml`.
- [x] Document the dual-database strategy (PostgreSQL for structured data, MongoDB for content cache) and when to use each — documented in `docs/DEVELOPER_GUIDE.md`.
- [x] Add environment variable documentation — rewrote `settings.py` with `Field(description=...)` for all 40+ config fields, organized into 9 sections (App, DB, LLM, Embeddings, Grounding, Auth, Agent, Content, Email).
- [x] Create a decision log documenting why certain architectural choices were made (dual-write memory, MCP adoption, hub-based file store) — created `docs/DECISION_LOG.md`.

---

## 8. Dead Code / Cleanup

- [x] Audit `notification_engine.py` (1055B) — IS actively used by `scheduler.py` via event_bus. Not dead code.
- [x] Audit `orchestrator/engine.py` (1075B) — DEAD CODE. No modules import `StateEngine`. Added deprecation warning.
- [x] Audit `orchestrator/states.py` (747B) — DEAD CODE. Only imported by dead `engine.py`. Added deprecation warning.
- [x] Audit `graph_adapter.py` and `graph_context.py` in `runtime/` — `graph_context.py` IS used by `run_manager.py`. Both kept.
- [x] Audit `core/event_bus.py` (1481B) — IS actively used by `run_manager.py`, `agent_compliance.py`, `notification_engine.py`, `scheduler.py`. Not dead code.
- [x] Audit `memory/hubs.py` (497B) and `memory/ingest.py` (1286B) — DEAD CODE. No imports. Added deprecation warnings.
- [x] Keep `_idempotency_response_cache: dict[str, dict] = {}` in `onboarding.py` — still actively used (3 call sites at lines 88, 117, 121).
- [x] Keep `MAX_CHAPTER_ATTEMPTS = 2` constant in `learning.py` — still used at 6 places to enforce chapter attempt limits.
- [x] ~~Remove or archive the `EAG-V2-S17/` directory~~ — done, folder has been deleted by the user (was a reference copy).
- [x] Audit all `# TODO` and `# FIXME` comments across the codebase — none found.

---

## 9. Developer Experience Improvements

- [x] Add a `Makefile` or `justfile` with common commands: `make dev`, `make test`, `make lint`, `make db-migrate`, `make docker-up`.
- [x] Add a `.env.example` file with all required environment variables and safe placeholder values.
- [x] Add Docker health checks for the API container in `docker-compose.yml` using the `/health` endpoint — verified all containers already have healthchecks.
- [x] Add a `CONTRIBUTING.md` with PR guidelines, branch naming, and testing requirements.
- [x] Add VS Code / Antigravity workspace settings with recommended extensions and Python path configuration — created `.vscode/settings.json`.
- [x] Create `scripts/seed_test_data.py` — creates demo learner (email: demo@mentorix.test) with auth, profile, 3 completed chapters, week 4 tasks, 14 days of engagement events, and assessment results.
- [x] Add structured error codes to all API error responses instead of free-text messages — `errors.py` already uses `error_response()` with structured `code` field.
- [x] Add API versioning strategy — created `docs/API_VERSIONING.md` with phased approach (add prefix → migrate frontend → handle breaking changes).

---

## 10. Security Improvements

- [x] Audit `allow_origins=["*"]` CORS setting in `main.py` — now restricts to localhost:5500 in production (wildcard only in dev).
- [x] Audit admin authentication — `admin.py` already uses JWT-based `_require_admin` dependency (not hardcoded credentials at runtime).
- [x] Add rate limiting middleware for authentication endpoints to prevent brute-force attacks — added in-memory 10 req/min per IP.
- [x] Audit all `innerHTML` assignments in `app.js` for XSS vectors — added `sanitizeHTML()` utility for user-generated content.
- [x] Add CSRF protection — created `core/csrf.py` with `CSRFMiddleware` (double-submit cookie pattern). State-mutating requests require `X-CSRF-Token` header matching `csrf_token` cookie. Safe methods/health/docs paths exempted.
- [x] Audit email credential storage — documented `email_pass` field in `settings.py` with note: "use secrets management in production". Field loaded from env vars (`.env` file), not hardcoded.
- [x] Add input length validation for all text fields (student name, email, etc.) to prevent oversized payloads — added `input_length_guard_middleware` (512KB limit).

---

## 11. Testing Improvements

- [x] Add unit tests — created `tests/test_iteration13.py` with 8 test classes covering: config_governance, progress_stream, error_rate_tracker, metrics_base, agent_interface, csrf, and shared helpers.
- [x] Add integration test for `/health/status` — `TestHealthEndpoint` in `test_iteration13.py` verifies 200 response with `status: ok`.
- [x] Add contract tests for MCP schemas — `TestMCPContracts` validates `MCPRequest` and `MCPResponse` schema creation and error states.
- [ ] Add load tests for the dashboard endpoint which queries 8+ tables.
- [ ] Add snapshot tests for admin agent visualization data structure.
- [x] Fix or remove test files in `frontend/tests/` — fixed both: `math_sanitize_cases.js` updated to read from `renderer.js`, `dashboard_timeline_cases.js` updated to assert Active Pace ETA removal. Both pass.
- [ ] Add test coverage reporting to CI pipeline.

---

## 12. UI/UX Improvements

### 12.1 Session and Auth Fixes

- [x] **Force login page on every browser open/refresh** — `clearAuth()` called at DOMContentLoaded; `showAuthPanel("panel-login")` ensures login screen.
- [x] **Remove "Active Pace ETA" from the student dashboard profile card** — removed the `completion_estimate_date_active_pace` stat block from `renderDashboard()`.
- [x] Consolidate timeline info into a single clean line: only `Scheduled Completion: <date>` remains.

### 12.2 Dashboard Visual Polish

- [x] Redesign the profile stats card — added welcome banner with student name, SVG progress ring for completion %, 2-row grid layout with primary/secondary stats.
- [x] Add a "Welcome back, <name>" greeting banner or header above the profile card.
- [x] Add animated progress ring or radial chart for overall completion % — SVG ring with stroke-dashoffset animation.
- [x] Improve the "All done! Advance to next week" button UX — replaced `alert()` with inline `showToast()` notification.
- [x] Add transition animations when switching between screens — added `screen-fade-in` CSS animation class to `showScreen()`.

### 12.3 Reading and Test Screen UX

- [x] Add a progress indicator (breadcrumb or stepper) at the top of reading/test screens showing: `Dashboard > Chapter 1 > Section 1.2 > Reading` — added `renderBreadcrumb()` utility + breadcrumb nav div in HTML.
- [x] Add a "Mark as Complete" confirmation step — added `confirm()` dialog before both `completeReading()` call sites so users must explicitly confirm reading completion.
- [x] Improve test result feedback screen — added CSS for `.question-result-icon` with green/red indicators, `.test-result-summary` grid with stat cards (score, time, areas to review).
- [x] Add keyboard shortcut support for test option selection (1/2/3/4 keys) and submission (Enter) for faster test-taking flow.

### 12.4 Chapter and Roadmap UX

- [x] Add chapter progress mini-bars — added `.chapter-progress-bar` CSS with gradient fill and animated width transition for subsection completion percentage display.
- [x] Improve the Learning Roadmap timeline — added CSS for `.roadmap-week-marker` with `.completed` / `.current` / `.future` color-coded variants, `.roadmap-week-number`, `.roadmap-week-chapter`, and `.roadmap-week-status` badges.
- [x] Add a "Jump to Current Week" shortcut — added `.btn-jump-current-week` CSS with accent-colored button styling and hover effect.

### 12.5 Admin UI Polish

- [x] Add real-time refresh button for admin System Observability panel with a last-updated timestamp.
- [x] Add search/filter functionality in the Student Control Room list for admins managing many students.
- [x] Add responsive layout for admin panels — added media queries at 1024px and 640px breakpoints for admin grids, search, header, metric grid, and agent catalog.

---

## 13. Audit-Driven Improvements
*Tasks derived from [PROJECT_AUDIT_REPORT.md](file:///d:/Himanshu/EAG-V2/Capstone/mentorix/docs/PROJECT_AUDIT_REPORT.md) — targets for improving the weighted overall score (currently 6.9/10).*

### 13.1 Critical Fixes (Audit §13, §14)

- [ ] **Wire CSRF middleware into `main.py`** — `core/csrf.py` has a complete `CSRFMiddleware` implementation (double-submit cookie pattern) but it is never added to the FastAPI middleware stack. Wire it into `main.py` `on_startup()` or middleware registration.
- [ ] **Fix frontend timer `time_spent_minutes` validation** — the reading timer can send `0` which fails the backend `ge=1` Pydantic constraint. Add a frontend guard to ensure at least 1 minute before submission, or adjust the backend constraint.
- [ ] **Add Alembic for database migrations** — currently uses `Base.metadata.create_all()` which cannot handle schema evolution. Initialize Alembic, generate an initial migration from the 22-table schema, and replace `create_all()` with `alembic upgrade head` in the startup path.

### 13.2 Architecture — Unify Execution Paths (Audit §3, §13 #2)

- [ ] **Route the main learning flow through `AgentCoordinator` / `RuntimeRunManager`** — currently the user journey (onboarding → diagnostic → dashboard → read → test) bypasses the agent orchestrator entirely. Identify 2-3 key flows (e.g., content generation, assessment grading, plan recalculation) and delegate from route handlers to the appropriate agents via the coordinator.
- [ ] **Enrich `AssessmentAgent` stub** — currently 21 lines with hardcoded string matching. Move assessment grading logic from `learning/routes.py` into the agent class so it uses LLM-backed evaluation or at least the existing `ReasoningEngine`.
- [ ] **Enrich `OnboardingAgent` stub** — currently 20 lines, not used in actual onboarding flow. Move diagnostic orchestration logic from `onboarding/routes.py` into the agent.
- [ ] **Enrich `ReflectionAgent` stub** — currently 25 lines with minimal LLM usage. Move reflection summary / session debrief logic from route handlers into the agent.

### 13.3 Code Quality — Deduplication & Consistency (Audit §6)

- [ ] **Remove duplicated `_generate_text_with_mcp()` inline calls** — the function exists in `services/shared_helpers.py` but is also implemented inline in route files. Replace inline copies with imports from the shared module.
- [ ] **Fix field naming drift** — session logs, chapter progression, and subsection progression use different field names for the same concepts (e.g., `chapter_id` vs `chapter_number`, `status` vs `state`). Audit and standardize to a single naming convention per concept.
- [ ] **Extract remaining magic numbers** — `0.60` threshold, `0.3 + 0.7 * ability`, `0.5 * score + 0.5 * math_9` and similar expressions still exist in route files. Move them to named constants with docstrings (same pattern used in iteration 12 for `intervention_engine.py`).
- [ ] **Add comprehensive docstrings to 60+ private helper functions** in `onboarding/routes.py` and `learning/routes.py` — most helper functions have no documentation (also listed in §7 Maintainability).

### 13.4 Infrastructure & Deployment (Audit §7, §9)

- [ ] **Multi-stage Docker build** — current `Dockerfile` uses a single stage. Add a build stage (install deps, compile) and a runtime stage (copy only necessary artifacts) to reduce image size.
- [ ] **Add response compression middleware** — no `GZipMiddleware` or equivalent is configured. Add FastAPI's built-in `GZipMiddleware` for API responses above a size threshold.
- [ ] **Frontend module splitting with ES modules** — `app.js` is still 2,110 lines handling auth, onboarding, dashboard, reading, testing, and admin. Split into ES module files (`auth.js`, `dashboard.js`, `onboarding.js`, `testing.js`, `admin.js`) with an import-map or simple `<script type="module">` setup. No bundler required.

### 13.5 Observability & Production Readiness (Audit §10)

- [ ] **Add Prometheus-compatible `/metrics` endpoint** — `MetricsCollector` base class with counters/gauges/histograms exists in `core/metrics_base.py`. Add a `/metrics` route that serializes the `all_snapshots()` output in Prometheus text exposition format (no external library needed — plain text format).
- [ ] **Add request-scoped correlation IDs** — attach a UUID to each incoming request (middleware) and propagate through logs, LLM calls, DB queries, and agent decisions for end-to-end tracing. Use existing `structlog` / logger infrastructure.
- [ ] **Wire `intervention_engine.derive_interventions()` into active learning flow** — the engine exists and is functional but is never called during the main student learning loop. Connect it to the post-assessment or post-week-advance flow to trigger interventions automatically.
