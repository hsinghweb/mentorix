# Mentorix Iteration 3 Planner (S17 Architectural Alignment)

Status date: 2026-02-21  
Goal: align Mentorix implementation style with `eag-v2-s17` architecture and coding patterns before final capstone freeze.

---

## 1) Comparison Baseline (Completed)

### Source compared
- [x] `eag-v2-s17/core/*` (loop, model manager, scheduler, event bus, circuit breaker, persistence, graph adapter, metrics)
- [x] `eag-v2-s17/memory/context.py` (NetworkX graph-first runtime context)
- [x] `eag-v2-s17/core/skills/*` (skill plugin manager pattern)
- [x] `eag-v2-s17/remme/*` (structured memory hubs + extraction pipeline)
- [x] Current Mentorix runtime in `API/app/*` and existing planners/docs

### Current Mentorix strengths already present
- [x] Deterministic state machine (`orchestrator/states.py`, `orchestrator/engine.py`)
- [x] Multi-agent modular split (`agents/*`)
- [x] LLM provider abstraction (`core/llm_provider.py`)
- [x] RAG retrieval + vector backend abstraction (`rag/retriever.py`, `rag/vector_backends.py`)
- [x] Structured state-transition logging in session APIs

---

## 2) Missing S17 Concepts (Implemented)

## A. Runtime Architecture Parity (Graph-First + Control Plane)
- [x] Introduce graph-first execution context manager (node status, reads/writes, dependencies, globals map)
- [x] Add graph-runner loop with explicit step lifecycle (`pending -> running -> completed/failed/waiting_input`)
- [x] Add adaptive re-planning hook when dead-end or clarification blocks occur
- [x] Add run control endpoints (`start run`, `stop run`, `resume/check run state`)
- [x] Add persisted run snapshots for interrupted sessions and restart-time recovery signal

## B. Reliability/Resilience Patterns
- [x] Add reusable async exponential backoff utility for transient provider/tool failures
- [x] Add circuit breaker module with `CLOSED/OPEN/HALF_OPEN` states for external dependencies
- [x] Integrate circuit breaker + backoff into LLM/embedding/retrieval call paths
- [x] Add explicit per-step retry counters and retry telemetry fields

## C. Eventing + Observability Parity
- [x] Add in-process async event bus (publish/subscribe, bounded replay history)
- [x] Emit step-level events (`step_start`, `step_success`, `step_failed`, `run_status_changed`)
- [x] Add streaming endpoint (SSE/WebSocket) for live run/event feed
- [x] Add graph adapter/serializer for frontend execution visualization payloads
- [x] Add fleet-level metrics aggregator (runs, outcomes, retries, cost, token efficiency, top failures)

## D. Scheduler + Autonomy Patterns
- [x] Add scheduler service (APScheduler or equivalent) with persisted job definitions
- [x] Add scheduler CRUD + manual trigger API endpoints
- [x] Add scheduled run lifecycle hooks (on_start/on_success/on_failure)
- [x] Add scheduler notification channel (in-app first; email optional)
- [x] Add startup restoration of scheduled jobs from disk/db

## E. Skill/Capability Plugin Pattern
- [x] Add skill registry format + auto-discovery manager (plugin loading)
- [x] Add intent-to-skill matcher for scheduled/autonomous tasks
- [x] Add skill lifecycle hooks (`on_run_start`, `on_run_success`, `on_run_failure`)
- [x] Add one reference skill to validate end-to-end plugin path

## F. Memory Architecture Parity (Beyond Learner Profile)
- [x] Add episodic memory skeletonizer for run graph compression (store logic/actions, drop heavy payloads)
- [x] Add structured long-term memory hubs (preferences/context/identity-style buckets adapted to Mentorix domain)
- [x] Add ingestion pipeline for memory signals from sessions/artifacts/assessments
- [x] Add retrieval API that injects structured memory context into planner/content agents

## G. Model Governance Parity
- [x] Move from provider-only selection to role-based model governance (`planner`, `verifier`, `optimizer`, etc.)
- [x] Add central model registry config and policy checks (including local-enforcement flags where needed)
- [x] Add per-role cost/latency accounting for evaluator-facing analysis

## H. System-2 Reasoning + Query Optimization (S17/S19-style cognition parity)
- [x] Add draft-verify-refine reasoning loop module with bounded refinements
- [x] Add verifier model path with safe fallback behavior
- [x] Add query optimizer pre-processor (JIT rewrite for ambiguous/underspecified input)
- [x] Log reasoning trace artifacts for explainability and post-run audits

---

## 3) Iteration 3 Execution Order

### P0 (Must-Have for architectural parity)
- [x] A: Graph-first execution context + run control API
- [x] B: Backoff + circuit breaker integration
- [x] C: Event bus + live stream + step events
- [x] G: Role-based model governance config + manager

### P1 (High-value autonomy and extensibility)
- [x] D: Scheduler service + persisted jobs + manual trigger
- [x] E: Skill plugin manager + one production-grade skill
- [x] H: System-2 reasoning loop + query optimizer

### P2 (Research-grade memory/analytics depth)
- [x] F: Episodic skeleton memory + structured hubs
- [x] C: Fleet telemetry aggregator and dashboard endpoints

---

## 4) Exit Criteria for Iteration 3

- [x] Mentorix run engine is graph-first and supports controlled stop/recovery
- [x] External dependency failures are handled via retry + circuit breaker (no hard crash path)
- [x] Live run/event stream works for demo visibility
- [x] Scheduled autonomous tasks execute and persist across restarts
- [x] Skill plugin path works end-to-end with lifecycle hooks
- [x] Role-based model governance is active via central config
- [x] Reasoning loop and query optimization are integrated (bounded, traceable)
- [x] Episodic memory compression and retrieval-enhanced planning are functional

---

## 5) Notes

- This planner captures **missing architectural concepts/patterns** from `eag-v2-s17`, not only feature-level gaps.
- Existing Mentorix components from Iteration 1/2 remain valid and are treated as foundation, not rework targets.

- Iteration 3 implementation validated with uv run pytest ..\tests -q -p no:pytest_asyncio (4 passed).

