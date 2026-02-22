# Submission Finish Line – Remaining Unchecked Items

Sweep of `PLANNER_ITERATION_6.md`: only **unchecked** items, split into **backend-critical** (needed for a clean submission/demo) vs **frontend/demo-later** (can defer past handoff).

---

## Backend-critical (minimal set for submission)

Items that directly affect API contract, data correctness, or evaluator-runbook flow. Completing these gives a clean backend finish line.

| # | Item | Location | Notes |
|---|------|----------|--------|
| 1 | **Onboarding → diagnostic → profile integration test** (timeline bounds + recommendation payload) | §8 Backend Tests | One test: full onboarding start → submit → assert `recommended_timeline_weeks`, `current_forecast_weeks`, timeline in response. |
| 2 | **Parse and persist syllabus hierarchy** (chapter > section > concept) | Phase 1 | Improves RAG traceability and future concept-level APIs. Optional if demo uses current chunk-level grounding. |
| 3 | **Adaptive pace engine** (behind → extend week/load balance; ahead → compress carefully) | Phase 2 | Currently replan + forecast delta; explicit “extend/compress” rules would complete this. |

**Already covered by current implementation (no extra work for submission):**

- Timeline contract, proof-based completion, revision queue, no-skip override, plan versions, committed/forecast split, engagement telemetry, where-i-stand, evaluation analytics, daily breakdown, idempotency, fallbacks, scheduler recovery, small load test, secret redaction, gateway auth path.
- Revision “engine” (pass 1/2/3): revision queue + `revision_policy_state` + weak zones and next_actions are implemented; only the parent checkboxes in the planner are still open.
- “Stuck-chapter rules”: retry, timeout, progression + revision queue are implemented; checkbox can be considered done.

---

## Frontend / demo-later (defer past submission)

Everything below can be deferred; backend and runbook demo do not depend on them.

### Frontend (Student + Admin)

- Onboarding wizard, timeline selector (14–28 weeks), “your target” vs “Mentorix recommendation” in UI.
- Timeline progress/forecast visibility (goal, forecast, delta, pacing) in UI.
- Diagnostic test interface, current-week task board, streak/engagement tracker.
- Chapter tracker (Beginner/Developing/Proficient/Mastered), concept heatmap, “Where I stand” card in UI.
- Admin: student progress monitor, system health panel, ingestion/RAG readiness, policy violations panel, performance diagnostics, timeline drift dashboard.

### Database (normalized / optional schema)

- Separate `students` / `student_profiles` (we have `learners` + `learner_profile`).
- `chapters`, `sections`, `concepts` (we have embedding chunks + metadata).
- `question_bank`, `test_attempts`, `test_attempt_items`, `chapter_scores`, `mastery_tracking`, `concept_mastery_tracking` (we have `assessment_results` + profile `concept_mastery`).
- `agent_decision_logs`, `system_events`, `notifications` (observability store).

### Redis / cache enhancements

- Session cache model (we have in-memory fallback + Redis).
- Scheduler queue + delayed jobs, plan recalculation debounce, retrieval cache, lock keys, TTL/invalidation policy (idempotency keys already done).

### Observability & metrics (no UI required for submission)

- ~~Structured logging per domain (onboarding, planning, adaptation, scheduling, compliance, RAG)~~ — implemented: `get_domain_logger(name, domain)` in `app.core.logging`, format `[%(domain)s]`, used in onboarding, sessions (adaptation), run_manager (scheduling), RAG (grounding_ingest, embeddings), content (compliance).
- ~~App metrics (latency, error rates)~~ — implemented: `app.core.app_metrics` (request_count, error_count, error_rate, latency_ms_p50, latency_ms_p95), `metrics_middleware`, GET `/metrics/app`; alerts list (`high_error_rate`, `high_latency_p95`) when thresholds exceeded.
- ~~Student-learning metrics (mastery progression, confidence trend, weak-area velocity, adherence, streak, timeline adherence, forecast drift)~~ — GET `/onboarding/learning-metrics/{learner_id}` returns `StudentLearningMetricsResponse`: mastery_progression, avg_mastery_score, confidence_score, weak_area_count/weak_areas, adherence_rate_week, login_streak_days, timeline_adherence_weeks, forecast_drift_weeks, selected/current_forecast_weeks.
- ~~Alerts / anomaly flags~~ — high_error_rate and high_latency_p95 in `/metrics/app`; extend for disengagement, scheduler drift, embedding/retrieval as needed.

### Profiling engine (exposed via APIs)

- Unchecked sub-items (chapter completion %, strengths/weaknesses, avg score, confidence, pace, revision priority, attempt/retry/timeout): largely exposed via `/where-i-stand` and `/evaluation-analytics`; any remaining “maintain” work is enhancement.

### Testing

- ~~PDF parse integrity, embedding dimension consistency, ingestion idempotency tests~~ — added in `tests/test_grounding_ingestion.py`.
- Frontend: critical student journey smoke tests, admin panel rendering tests.

### Deliverables wording (operational in UI)

- “Full student lifecycle operational in UI”, “Student-selectable timeline + recommendation operational”, “Weekly re-planning operational”, “Adaptive tone/content delivery demonstrable”, “Admin observability panel operational”, “Logs + metrics + alerts operational” – all backend-supported; “operational/demonstrable” in these bullets means UI/dashboard work, hence frontend/demo-later.

### Operating rules

- Generic process (don’t break MVP, vertical slices, telemetry + tests, local-first) – no new unchecked backend scope.

---

## Submission finish line (achieved)

All backend-critical items above are complete. Implemented: (1) onboarding diagnostic-to-profile integration test with timeline assertions; (2) parse and persist syllabus hierarchy (chapter > section > concept) in grounding_ingest and SyllabusHierarchy table; (3) adaptive pace extend/compress in weekly replan. Remaining unchecked planner items are frontend/demo-later or optional enhancements.


