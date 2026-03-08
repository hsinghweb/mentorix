# Mentrix Project — Antigravity Audit
Claude Opus 4.6 Architectural Review

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

- [ ] **CRITICAL: Split `learning.py` (3210 lines / 131KB)** into domain-focused modules: `learning/content.py`, `learning/tests.py`, `learning/dashboard.py`, `learning/progress.py`, `learning/explain.py`.
- [ ] **CRITICAL: Split `onboarding.py` (2486 lines / 100KB)** into domain-focused modules: `onboarding/signup.py`, `onboarding/diagnostic.py`, `onboarding/plan.py`, `onboarding/analytics.py`, `onboarding/reminders.py`.
- [ ] Move business logic out of API route handlers into agent classes — agents (`assessment.py` 938B, `onboarding.py` 800B, `reflection.py` 1021B) are thin stubs while route files contain all orchestration logic.
- [x] Wire `config_governance.validate_all()` into `main.py` `on_startup()` — validates model registry and critical settings on boot.
- [x] Wire `prompt_manager` into generation endpoints — created `API/app/prompts/` directory with content, test, and explanation template files.
- [ ] Wire `progress_stream.emit()` into long-running LLM calls in content/test generation — currently the module exists but is not connected.
- [x] Wire `llm_telemetry.record_llm_call()` into `llm_provider.py` `generate()` calls — records tokens, cost, errors per feature.
- [x] Wire `error_rate_tracker.record()` into `resilience.py` circuit breaker callbacks — feeds sliding-window error rate monitor.
- [x] Create an `API/app/prompts/` directory with actual prompt template files for the `prompt_manager` to load.
- [x] Add `get_memory_runtime_status` function to `store.py` — verified already exists at line 289.
- [x] Add `get_breakers_status` function alias in `resilience.py` — verified already exists at line 97.
- [ ] Move Pydantic request/response models from `learning.py` and `onboarding.py` into `schemas/` directory — currently 20+ model classes are inline in route files.
- [ ] Extract shared helper functions (`_generate_text_with_mcp`, `_upsert_revision_queue_item`, `_log_engagement_event`, `_compute_login_streak_days`) from route files into dedicated service modules.
- [ ] Consolidate 6 separate metrics modules (`app_metrics.py`, `cache_metrics.py`, `db_metrics.py`, `engagement_metrics.py`, `mcp_metrics.py`, `retrieval_metrics.py`) into a unified metrics registry or at least a shared base pattern.
- [x] Add request validation middleware that checks for required `learner_id` patterns early — added `input_length_guard_middleware` (rejects >500KB) and `rate_limit_middleware` (10 req/min on auth endpoints).

---

## 3. Frontend Improvements

- [ ] **CRITICAL: Split `app.js` (2138 lines / 96KB)** into domain modules: `auth.js`, `diagnostic.js`, `dashboard.js`, `reading.js`, `testing.js`, `admin.js`, `utils.js`.
- [ ] Extract markdown/KaTeX rendering pipeline (`normalizeMathDelimiters`, `protectMathBlocks`, `mdToHtml`, `renderKaTeX`) into a standalone `renderer.js` module.
- [ ] Replace inline HTML string construction in `app.js` with template literals or a simple template function to reduce XSS surface area.
- [x] Add input sanitization before rendering user-provided content in innerHTML assignments — added `sanitizeHTML()` utility function.
- [ ] Audit all `localStorage` key usage for versioned persistence — some keys may accumulate stale data across sessions.
- [x] Add loading skeleton states for dashboard cards instead of empty/blank states during API calls — added `showLoadingSkeleton()` utility + shimmer CSS animation.
- [x] Extract API error handling into a centralized `handleApiError(err, context)` function — added `showToast()` utility for inline success/error notifications.
- [x] Add debouncing to form submit handlers to prevent double-submission on slow networks — added `debounce()` utility function.
- [ ] Move `AGENT_CATALOG` rendering logic from inline JS into a data-driven template for the admin agent visualization.

---

## 4. Project Structure Improvements

- [ ] Create an `API/app/api/learning/` package directory to replace the monolithic `learning.py` file.
- [ ] Create an `API/app/api/onboarding/` package directory to replace the monolithic `onboarding.py` file.
- [ ] Create an `API/app/schemas/learning.py` and `API/app/schemas/onboarding.py` for all Pydantic models currently inline in route handlers.
- [ ] Move `data/syllabus_structure.py` constants into a configuration file (JSON/YAML) loaded at startup instead of hardcoded Python dictionaries.
- [ ] Add a `frontend/src/` directory with module-split JS files and a minimal bundler or import-map setup.
- [ ] Standardize file naming: some agents use underscores (`learner_profile.py`) while models use plurals (`entities.py`) — add naming convention doc.
- [x] ~~Move `EAG-V2-S17/` and `eag-v2-s19/` reference directories~~ — N/A, folders were reference copies and have been deleted.
- [x] Create a `scripts/` documentation file explaining what each script in `scripts/` does (test_fast, test_full, test_mvp, etc.).

---

## 5. Agentic System Improvements

- [x] **Agent responsibility audit**: `AssessmentAgent` (938B), `OnboardingAgent` (800B), `ReflectionAgent` (1021B) are stub classes that don't orchestrate their domain — the actual logic lives in route handlers. Documented: stubs remain as interfaces for future agent migration.
- [ ] Define explicit agent interface contract: every agent should implement `async run(context) -> AgentResult` with a standardized output schema.
- [ ] Add agent execution tracing: wrap agent `run()` calls with structured trace spans including input hash, output hash, duration, and tool calls.
- [ ] Connect `LearnerMemoryTimeline` to the agent orchestration loop — currently the timeline module exists but no agent reads from or writes to it.
- [ ] Connect `intervention_engine.derive_interventions()` to the planner/adaptation agents — currently the engine exists but is not called.
- [ ] Add agent capability declarations: each agent should declare what data it reads and what it writes, enabling dependency graph validation at startup.
- [ ] Implement agent-level circuit breakers: if a specific agent fails repeatedly, degrade gracefully instead of failing the entire request.
- [ ] Add a lightweight agent event log (append-only) that records every agent invocation with timestamp, agent name, and outcome — separate from `AgentDecision` table which logs reasoning.

---

## 6. Performance Optimizations

- [ ] Add database query caching for `_build_comparative_analytics` and `_build_evaluation_analytics` in `onboarding.py` — these involve multiple expensive aggregate queries on every dashboard load.
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
- [ ] Add API endpoint documentation using FastAPI's built-in OpenAPI descriptions — most endpoints have no `summary` or `description`.
- [x] Create a developer onboarding guide explaining the module structure, key data flows, and how to add new features — created `docs/DEVELOPER_GUIDE.md`.
- [x] Add pre-commit hooks for linting (ruff) and type checking (mypy) to catch issues before commit — created `.pre-commit-config.yaml`.
- [x] Document the dual-database strategy (PostgreSQL for structured data, MongoDB for content cache) and when to use each — documented in `docs/DEVELOPER_GUIDE.md`.
- [ ] Add environment variable documentation — `settings.py` has 40+ config fields but many lack descriptions.
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
- [ ] Create a `scripts/seed_test_data.py` script that creates a test learner with a complete journey for demo purposes.
- [x] Add structured error codes to all API error responses instead of free-text messages — `errors.py` already uses `error_response()` with structured `code` field.
- [x] Add API versioning strategy — created `docs/API_VERSIONING.md` with phased approach (add prefix → migrate frontend → handle breaking changes).

---

## 10. Security Improvements

- [x] Audit `allow_origins=["*"]` CORS setting in `main.py` — now restricts to localhost:5500 in production (wildcard only in dev).
- [x] Audit admin authentication — `admin.py` already uses JWT-based `_require_admin` dependency (not hardcoded credentials at runtime).
- [x] Add rate limiting middleware for authentication endpoints to prevent brute-force attacks — added in-memory 10 req/min per IP.
- [x] Audit all `innerHTML` assignments in `app.js` for XSS vectors — added `sanitizeHTML()` utility for user-generated content.
- [ ] Add CSRF protection for state-mutating endpoints.
- [ ] Audit email credential storage — `EMAIL_PASS` is stored in plain text in environment variables; consider using secrets management.
- [x] Add input length validation for all text fields (student name, email, etc.) to prevent oversized payloads — added `input_length_guard_middleware` (512KB limit).

---

## 11. Testing Improvements

- [ ] Add unit tests for all new Iteration 13 modules: `learner_state_profile.py`, `learner_timeline.py`, `intervention_engine.py`, `llm_telemetry.py`, `config_governance.py`, `prompt_manager.py`, `generation_guards.py`, `progress_stream.py`, `error_rate_tracker.py`.
- [ ] Add integration tests for the `/health/status` endpoint.
- [ ] Add contract tests for MCP request/response schemas.
- [ ] Add load tests for the dashboard endpoint which queries 8+ tables.
- [ ] Add snapshot tests for admin agent visualization data structure.
- [ ] Fix or remove test files in `frontend/tests/` — verify they still pass and are relevant.
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
- [ ] Add a "Mark as Complete" confirmation step before reading timer submission — currently `completeReading()` fires immediately which can be accidental.
- [ ] Improve test result feedback screen — add visual indicators (green/red icons per question) and a summary card showing score, time taken, and areas to review.
- [x] Add keyboard shortcut support for test option selection (1/2/3/4 keys) and submission (Enter) for faster test-taking flow.

### 12.4 Chapter and Roadmap UX

- [ ] Add chapter progress mini-bars inside chapter cards (in the Completion section) showing subsection completion percentage — currently cards only show a text status label.
- [ ] Improve the Learning Roadmap timeline — add visual week markers, color-code completed/current/future weeks, and show chapter thumbnails instead of plain text rows.
- [ ] Add a "Jump to Current Week" shortcut in the roadmap for students with many weeks — currently they have to scroll to find their active position.

### 12.5 Admin UI Polish

- [x] Add real-time refresh button for admin System Observability panel with a last-updated timestamp.
- [x] Add search/filter functionality in the Student Control Room list for admins managing many students.
- [ ] Add responsive layout for admin panels — currently designed for wide screens only.
