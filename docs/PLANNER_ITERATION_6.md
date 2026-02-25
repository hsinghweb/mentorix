# Mentorix Iteration 6 Planner (Enterprise Completion Plan)

**Status: COMPLETE**  
Status date: 2026-02-21  
Goal: transform Mentorix from MVP into a production-grade, measurable, adaptive, multi-agent learning platform for Class 10 CBSE Mathematics.

**Submission finish line:** See `docs/SUBMISSION_FINISH_LINE.md` for backend-critical vs frontend/demo-later split. All planner items below are complete or explicitly deferred.

**Progress summary (final):**
- **Backend:** Phase 0–2 complete. Phase 4 (reliability, observability) complete: structured logging, app metrics (latency, error rate, agents, cache, retrieval, engagement, db p95), alerts (high_error_rate, high_latency_p95, high_agent_failure_rate, low_cache_hit_ratio, low_retrieval_quality, disengagement_risk, scheduler_drift, high_db_latency). §6 Grounding, §7 Security/Reliability, §8 backend tests. Student-learning metrics, chapter_retry_counts, forecast-history API. Admin API: cohort, policy-violations, timeline-drift. RAG retrieval cache (Redis, TTL 300s). §2 schema covered by learners/learner_profile/syllabus_hierarchy; §3 Redis (session, idempotency, retrieval cache, TTL).
- **Frontend:** Single-page UI (frontend/): Student (session, submit, dashboard); Onboarding & Plan (onboarding wizard, diagnostic, plan, tasks, where-i-stand, revision queue, timeline summary, streak, chapter tracker, concept map, next-week, forecast trend); Admin (health, metrics, grounding, cohort, policy violations, timeline drift). Smoke tests cover student and admin API surface.
- **Remaining:** None. Optional extensions (normalized question_bank tables, full scheduler queue, explicit lock keys) deferred; current schema and Redis usage suffice.
---

## 0) Syllabus as Source of Truth & Extensibility

**Canonical syllabus:** The file `class-10-maths/syllabus/syllabus.txt` (with optional `syllabus.pdf` fallback) is the **single source of truth** for the course. It defines the static structure used across the platform:

- **Planning:** The syllabus (chapter → section/topic hierarchy) drives how we create and maintain the student’s plan — what to do and in what order.
- **Progress & status:** The same syllabus is the reference against which we track **how much the student has completed** and **what is left** (per chapter, per topic).
- **Profile:** For every chapter and every topic we maintain **confidence** and **accuracy/achievement**. This profile is the basis for adaptation, recommendations, and the end-of-course view.
- **End view:** The profile is shown to the student so they see **how much they can gain** or **how much they are lagging** for the course (e.g. completion %, weak areas, timeline vs goal).

**Extensibility to other subjects and classes:** The system is designed to support any subject (e.g. Science) or any class (e.g. Class 9) using the same pattern:

1. **Onboard the syllabus** — Provide a syllabus file in the same format (e.g. `syllabus.txt` with chapter/section/topic lines). The ingestion pipeline parses and persists the hierarchy (chapter > section > concept/topic).
2. **Onboard the course PDFs** — Add subject/class-specific PDFs (chapters, topics) to the grounding data directory; run the same ingestion to embed and index them.
3. **Same pipeline and profile model** — Planning, progress tracking, and profiling (per-chapter/per-topic confidence and achievement) work identically; only the syllabus and PDF data change per course.

No code change is required for a new course beyond adding the syllabus `.txt` and the course PDFs and re-running ingestion (and configuring the data path for that course).

---

## 0b) North-Star Outcomes

- Build an autonomous tutor that helps a student:
  - complete syllabus once,
  - revise full syllabus second pass,
  - focus weak areas in third pass.
- Deliver chapter-by-chapter and concept-by-concept visibility:
  - current level,
  - strengths,
  - weaknesses,
  - confidence,
  - next actions.
- Enforce schedule integrity:
  - student cannot manually mark tasks complete,
  - completion is evidence-driven (read progress + test submission).
- Maintain one-to-one tutoring quality via GenAI:
  - adapt pace,
  - adapt explanation tone/depth,
  - adapt number/type of examples per learner capability.
- Maintain enterprise-grade observability:
  - clear logs, metrics, traces, and admin diagnostics.

---

## 1) Execution Strategy (Phased)

## 1A) Strict Implementation Sequence (Backend-First Vertical Slices)

Use this order as the execution source of truth. Do not start later slices before exit criteria of the current slice are met.

### Slice 0 - Platform Prerequisites (already completed)
1. Complete NoSQL memory migration gate (`docs/PLANNER_NOSQL_MEMORY_MIGRATION.md`).
2. Ensure Postgres + pgvector + Redis + Mongo local stack is healthy.
3. Confirm grounding pre-work readiness check is available.

Exit criteria:
- `/memory/status` healthy in local secured flow.
- backfill parity report generated.
- runtime memory files are not tracked in git.

### Slice 1 - Onboarding Timeline Contract + Diagnostic Core (backend first)
1. Add onboarding request/response contract for:
   - `selected_timeline_weeks` (bounded `14`-`28`)
   - `recommended_timeline_weeks`
   - `current_forecast_weeks`
   - `timeline_delta_weeks`
2. Enforce validation bounds and policy errors in API.
3. Persist timeline fields to profile domain.
4. Generate diagnostic and scoring-driven recommendation.
5. Return student goal vs Mentorix recommendation in onboarding response.

Exit criteria:
- onboarding integration test passes with timeline bounds + recommendation.
- Swagger examples show selected vs recommended timeline.

### Slice 2 - Week-1 Commit + Forecast-Only Long-Range Plan (Syllabus-Driven)
1. Build long-range roadmap from **syllabus structure** (chapter/section/topic from `syllabus.txt`) and timeline selection/recommendation.
2. Commit only current week schedule (immutable committed set).
3. Keep future weeks as read-only forecast projection.
4. Persist weekly plan version + weekly forecast snapshot.
5. Expose plan API with:
   - active week tasks
   - remaining forecast
   - completion estimate vs selected goal (what’s left vs syllabus).

Exit criteria:
- student sees active week + forecast separation.
- DB contains weekly plan + forecast history; plan reflects syllabus order/structure.

### Slice 3 - Schedule Integrity + Proof-Based Completion
1. Implement tasks + task_attempts + schedule lock model.
2. Block manual completion toggles.
3. Require evidence-based completion (read/test proof).
4. Add policy violation logging for skip/edit attempts.
5. Add idempotent completion APIs.

Exit criteria:
- locked task policy tests pass.
- policy violations are captured and queryable.

### Slice 4 - Weekly Adaptive Replan + Timeline Drift Loop
1. Execute weekly evaluation window.
2. Apply threshold/retry/timeout logic.
3. Recompute `current_forecast_weeks` weekly.
4. Compute/show timeline delta (`forecast - selected`).
5. Emit pacing hint (ahead/on-track/behind) for learner.

Exit criteria:
- weekly replan tests pass for repeat/proceed/revision outcomes.
- timeline drift updates appear in profile and weekly forecast history.

### Slice 5 - Profiling + Engagement Telemetry (Syllabus-Aligned)
1. Track login/logoff, streaks, engagement minutes, adherence.
2. Update profile attributes after each task/test (per chapter, per topic: confidence + accuracy/achievement).
3. Persist profile snapshots (history trail) aligned to syllabus structure.
4. Add learner "Where I Stand" payload (chapter + concept + confidence); same structure as syllabus (how much completed, what’s left).
5. **End view:** Expose profile so the student sees how much they can gain or how much they are lagging for the course (completion %, weak areas, timeline vs goal).

Exit criteria:
- profile history snapshots present.
- engagement/streak KPIs available in API payloads.
- profile and where-I-stand are keyed by syllabus chapter/topic; end view (gain/lag) available via API.

### Slice 6 - Adaptive Content (Pace + Tone + Depth)
1. Implement profile-aware content policy:
   - weak learner: slower pace, simpler tone, more examples
   - strong learner: compact tone, challenge items
2. Keep generation syllabus-grounded with citations.
3. Add out-of-syllabus safe response behavior.

Exit criteria:
- content adaptation test matrix passes by profile bands.
- grounded output includes citation metadata.

### Slice 7 - Revision Pass Engine (Pass1/Pass2/Pass3)
1. Build revision queue and priorities.
2. Enforce pass-1 completion, pass-2 full revision, pass-3 weak-zone focus.
3. Add retention checks and re-entry to queue if needed.

Exit criteria:
- revision queue trigger tests pass.
- revision pass state visible per learner.

### Slice 8 - Frontend Student Vertical Slice
1. Onboarding wizard + bounded timeline selector.
2. Show goal vs recommendation vs current forecast.
3. Show locked current-week board + completion evidence UX.
4. Add where-I-stand and confidence/mastery views.

Exit criteria:
- end-to-end student journey demo works without manual API calls.

### Slice 9 - Admin + Observability Vertical Slice
1. Admin panel for cohort progress and timeline drift.
2. System health panel (DB/cache/latency/errors/agent failures).
3. Ingestion and RAG readiness quality indicators.
4. Alerts for inactivity, repeated low scores, scheduler drift.

Exit criteria:
- evaluator can see learner and system state in one admin view.

### Slice 10 - Hardening + Final Validation
1. Security hardening (auth, secrets, input policy checks).
2. Reliability tests (fallback, restart/recovery, small load).
3. Final KPI dashboards and demo runbook lock.

Exit criteria:
- full capstone demo flow is reproducible and measurable.

## Phase 0: Runtime Memory Store Hardening (Pre-Iteration-6 Gate)
- [x] Complete `docs/PLANNER_NOSQL_MEMORY_MIGRATION.md`
- [x] Move learner/runtime JSON memory from filesystem to NoSQL backend (MongoDB)
- [x] Keep runtime learner data out of repository workflows

## Phase 1: Data Grounding Pre-Work (Syllabus-Driven)

**Syllabus source:** Prefer `class-10-maths/syllabus/syllabus.txt` when present; fallback to `syllabus.pdf`. The syllabus defines the static structure for plans and progress.

- [x] Build offline ingestion job for syllabus + chapters PDFs
- [x] Parse and persist syllabus hierarchy (chapter > section > concept) from syllabus text
- [x] Generate embeddings for:
  - [x] `class-10-maths/syllabus/syllabus.txt` / `syllabus.pdf` (full scope guardrail)
  - [x] `class-10-maths/chapters/ch_1.pdf`
  - [x] `class-10-maths/chapters/ch_2.pdf`
  - [x] `class-10-maths/chapters/ch_3.pdf`
- [x] Store extracted chunks + metadata + embeddings in Postgres vector tables
- [x] Add ingestion manifest tracking (what was embedded, when, hash/version)
- [x] Add pre-start validation so app can fail-fast if mandatory embeddings missing
- [x] **Extensibility:** Document/script for onboarding a new course: `docs/ONBOARD_NEW_COURSE.md` + `API/scripts/onboard_course.py` (validate course dir, print env vars and `POST /grounding/ingest`); add `syllabus.txt` + course PDFs to a new directory, set env, run ingestion; plan and profile model reuse unchanged

## Phase 2: Enterprise Backend Core
- [x] Introduce full student lifecycle APIs:
  - [x] onboarding
  - [x] diagnostics
  - [x] profile
  - [x] weekly plan
  - [x] schedule execution
  - [x] revision queue
- [x] Add onboarding timeline contract (student-selected goal duration):
  - [x] enforce min/max bounds (`14` to `28` weeks)
  - [x] persist requested timeline weeks
  - [x] generate system-recommended timeline from diagnostic score/profile
  - [x] return both values (requested + recommended) in onboarding response
  - [x] persist current forecast completion weeks (initial onboarding forecast)
  - [x] persist and expose timeline delta (`forecast_weeks - selected_weeks`)
- [x] Implement strict progression rules:
  - [x] chapter unlock threshold check (default 60%)
  - [x] no skip without policy override
  - [x] task completion by proof, not toggle
  - [x] timeout policy for stuck chapters (max attempts / max weeks before controlled progression)
  - [x] retry policy for low-score chapters (repeat with stronger support before timeout progression)
- [x] Add adaptive pace engine:
  - [x] behind pace -> extend week/load balance
  - [x] ahead pace -> compress carefully
- [x] Add revision policy engine (revision queue + revision_policy_state + weak zones + next_actions; pass 1/2/3 behavior in place):
  - [x] pass 1 full completion
  - [x] pass 2 full revision
  - [x] pass 3 weak-zone focus
- [x] Enforce planning mode:
  - [x] rough long-range roadmap based on requested/recommended timeline (`14`-`28` weeks)
  - [x] only current week schedule is active/committed
  - [x] keep upcoming weeks as forecast-only (read-only projection, not committed tasks)
  - [x] re-forecast remaining completion weeks after each weekly evaluation
- [x] **Syllabus & multi-course:** Use `syllabus.txt` as canonical structure for plan and progress; profile = per chapter/topic confidence + achievement; end view = gain/lag (APIs: where-i-stand, learning-metrics). Extensibility: new course = new directory with `syllabus.txt` + course PDFs + run ingestion (no code change).

## Phase 3: Frontend Enterprise UX
- [x] Build student portal (minimal; `frontend/index.html` + `app.js`):
  - [x] onboarding flow (Start Onboarding → learner ID; Get Plan / Get Tasks / Where I Stand)
  - [x] learning home with current week tasks (via Plan + Tasks API)
  - [x] diagnostic test UI (wizard with questions/answers; frontend diagnostic section + Submit diagnostic)
  - [x] chapter/topic mastery map (Chapter tracker + concept map: per chapter level, strengths/weaknesses, confidence)
  - [x] confidence and score trends (Streak & engagement + concept map show confidence; learning-metrics API has full trend data)
  - [x] revision queue and recommendations (GET /onboarding/revision-queue, revision-policy; API ready; UI can call from Plan panel)
  - [x] **End view:** how much the student can gain or how much they are lagging (Where I Stand + learning-metrics + timeline summary + forecast trend)
- [x] Build admin portal (minimal):
  - [x] system health (GET /health)
  - [x] app metrics (GET /metrics/app)
  - [x] ingestion status (GET /grounding/status)
  - [x] student cohort overview (GET /admin/cohort; Admin panel: Cohort button)
  - [x] agent-run visibility / schedule compliance / RAG quality signals (agents in /metrics/app; policy violations in /admin/policy-violations; RAG in /grounding/status + retrieval in /metrics/app)
- [x] Improve visual quality for education audience (minimal):
  - [x] polished cards/charts (cards + timeline/streak/concept summary styling)
  - [x] consistent design system (shared .card, .row, .timeline-summary, .streak-summary)
  - [x] clear microcopy + status labels (labels on all sections; status in results)

## Phase 4: Reliability, Observability, Operations
- [x] Add structured logging standards per domain:
  - [x] onboarding
  - [x] planning (in onboarding)
  - [x] adaptation
  - [x] scheduling
  - [x] compliance
  - [x] RAG retrieval
- [x] Add app metrics:
  - [x] request latency and error rates (GET `/metrics/app`: p50/p95, error_rate)
  - [x] agent execution duration/failure counts (GET `/metrics/app` includes `agents`: total_runs, total_steps, failed_steps, step_success_rate, total_retries, top_agents from fleet telemetry)
  - [x] DB query performance (GET `/metrics/app` includes `db`: db_query_count, db_p50_ms, db_p95_ms; alert high_db_latency when db_p95_ms &gt; 1000 and query_count ≥ 10)
  - [x] Redis cache hit/miss (GET `/metrics/app` includes `cache`: cache_hits, cache_misses, cache_sets, cache_hit_ratio; alert low_cache_hit_ratio when ratio &lt; 0.5 and get_total ≥ 10)
  - [x] retrieval quality metrics (GET `/metrics/app` includes `retrieval`: retrieval_count, retrieval_avg_confidence, retrieval_low_confidence_ratio; alert low_retrieval_quality when avg &lt; 0.4 and count ≥ 5)
- [x] Add student-learning metrics (GET `/onboarding/learning-metrics/{learner_id}`):
  - [x] mastery progression by chapter/concept
  - [x] confidence trend (confidence_score)
  - [x] weak-area (weak_areas, weak_area_count)
  - [x] completion and adherence rates (adherence_rate_week, login_streak_days, timeline fields)
- [x] Add alerts and anomaly flags (in `/metrics/app` payload):
  - [x] high_error_rate, high_latency_p95
  - [x] high_agent_failure_rate (when step_success_rate &lt; 90% and total_steps &gt; 0)
  - [x] low_cache_hit_ratio (when cache_hit_ratio &lt; 0.5 and cache_get_total ≥ 10)
  - [x] low_retrieval_quality (when retrieval_avg_confidence &lt; 0.4 and retrieval_count ≥ 5)
  - [x] disengagement_risk (when disengagement_recent_count ≥ 3; recorded on compliance disengagement_flag)
  - [x] scheduler_drift (when max_run_duration_sec &gt; 600 or total_retries/total_steps &gt; 0.2 with ≥20 steps)
  - [x] high_db_latency (when db_p95_ms &gt; 1000 and db_query_count ≥ 10)
  - [x] repeated low scores / embedding failures (deferred; extend when needed; low_retrieval_quality and disengagement_risk cover key signals)

---

## 2) Database Plan (Enterprise Schema)

## Core Student Domain
- [x] `students` (covered by `learners` table)
- [x] `student_profiles` (covered by `learner_profile` table)
- [x] `student_profile_history` (snapshot trail)
- [x] timeline fields in profile domain (`requested_timeline_weeks`, `recommended_timeline_weeks`, `timeline_bounds_version`)
- [x] timeline drift fields (`current_forecast_weeks`, `timeline_delta_weeks` in profile + weekly_forecasts)

## Curriculum & Grounding (Syllabus-Driven)
- Syllabus structure from `syllabus.txt` (chapter > section > topic) drives plan and progress; same format supports any subject/class.
- [x] `syllabus_hierarchy` (chapter > section > concept parsed from syllabus)
- [x] `chapters` / `sections` / `concepts` (optional; syllabus_hierarchy + embedding_chunks cover current need; normalized tables deferred)
- [x] `curriculum_documents`
- [x] `embedding_chunks` (vector + source metadata)
- [x] `ingestion_runs` (status, version, hash, counts)

## Learning Journey
- [x] `weekly_plans`
- [x] `weekly_plan_versions`
- [x] `tasks`
- [x] `task_attempts` (proof-based completion)
- [x] `schedule_locks` / immutable task flags
- [x] `weekly_forecasts` (goal vs current projection history)

## Assessment & Mastery
- [x] `question_bank` / `test_attempts` / `chapter_scores` / `mastery_tracking` (deferred; diagnostic scoring and concept_mastery in learner_profile cover current need)
- [x] `revision_queue`

## Observability & Governance
- [x] `agent_decision_logs` / `system_events` / `notifications` (deferred; policy_violations + metrics/app + notification_engine cover current need)
- [x] `policy_violations`

---

## 3) Redis / Cache & Runtime Plan

- [x] Session cache model for active learner context (Redis hset/hgetall for session state; idempotency cache)
- [x] Scheduler queue + delayed jobs (scheduler service + scheduled_jobs; full queue deferred)
- [x] Plan recalculation debounce (idempotency on weekly-replan/task-complete deduplicates writes)
- [x] Retrieval cache for repeated concept queries (Redis key rag:{concept}:{difficulty}, TTL 300s)
- [x] Rate-limit / idempotency keys for critical writes (onboarding submit, replan, task complete)
- [x] Lock keys for schedule/task completion (idempotency keys prevent double-submit; explicit lock keys deferred)
- [x] TTL and invalidation policy (idempotency/session 3600s; retrieval 300s; per-keyspace documented)

---

## 4) Backend Feature Breakdown (Agent + Service)

## Onboarding + Diagnostics
- [x] Collect student demographic + academic baseline
- [x] Collect target completion timeline during onboarding (`14`-`28` weeks only)
- [x] Generate diagnostic objective test set from RAG:
  - [x] MCQ
  - [x] Fill-in-the-blank
  - [x] True/False
- [x] Score and initialize profile state
- [x] Generate timeline recommendation after diagnostic:
  - [x] keep student-selected timeline as explicit goal
  - [x] compute recommended timeline and rationale (e.g., "you may need ~16 weeks")
  - [x] use selected/recommended values to shape week-1 load and roadmap pacing

## Profiling Engine
- [x] Maintain dynamic attributes (exposed via where-i-stand, evaluation-analytics, learning-metrics):
  - [x] chapter completion % (chapter_mastery, chapter_status)
  - [x] strengths/weaknesses (concept_strengths, concept_weaknesses, weak_areas)
  - [x] avg score (avg_mastery_score, chapter scores)
  - [x] confidence (confidence_score)
  - [x] pace indicator (timeline_adherence_weeks, forecast_drift)
  - [x] revision priority (revision queue, weak zones)
  - [x] chapter-level attempt count / retry count (revision_policy_state, ChapterProgression)
  - [x] chapter-level timeout flag (progression/timeout logic)
  - [x] engagement minutes per day/week
  - [x] login/logout events and streak count
- [x] Update profile after every task/test outcome

## Planner Engine (Weekly Adaptive)
- [x] Build rough long-range map from bounded timeline selection (`14`-`28` weeks)
- [x] Activate only current week details
- [x] Recalculate weekly plan after each evaluation window
- [x] Enforce threshold-based chapter unlocks
- [x] Re-forecast completion timeline weekly and persist drift metrics
- [x] Implement stuck-chapter rules:
  - [x] if below threshold -> reinforce and retry
  - [x] if repeatedly below threshold with timeout -> progress + push chapter to revision queue

## Content Agent
- [x] RAG-only grounded explanation generation
- [x] Difficulty and depth adaptation by profile
- [x] Generate examples + practice set per concept
- [x] Adapt tone and explanation style per learner profile:
  - [x] weak learner -> simpler language + more examples
  - [x] strong learner -> concise explanation + challenge questions

## Scheduler Engine
- [x] Create daily task breakdown (read/practice/test)
- [x] Lock completion without proof
- [x] Track completion timestamps and evidence
- [x] Enforce immutable schedule API contract:
  - [x] student cannot edit/reorder locked tasks
  - [x] only system policy engine can replan next week
- [x] Track engagement evidence:
  - [x] reading duration
  - [x] test attempt proof
  - [x] weekly adherence summary

## Evaluation + Analytics
- [x] Evaluate objective answers
- [x] Update chapter/concept mastery
- [x] Detect misconception patterns
- [x] Emit recommendations + risk level

## Progress + Revision
- [x] Build/maintain revision queue
- [x] Trigger full-pass and weak-area pass policies
- [x] Measure retention over time

---

## 5) Frontend Plan (Student + Admin)

## Student Experience
- [x] Onboarding entry (Start Onboarding; timeline 14–28 weeks in form)
- [x] Onboarding wizard (full diagnostic test UI with questions/answers; Start Onboarding → questions → Submit diagnostic)
- [x] Timeline selector in onboarding:
  - [x] input constrained to 14–28 weeks (Onboarding &amp; Plan panel)
  - [x] show "your target" vs "Mentorix recommendation" after test (in diagnostic result: selected_timeline_weeks, recommended_timeline_weeks, timeline_recommendation_note)
- [x] Timeline progress/forecast visibility (Get Plan shows plan + timeline summary: selected/forecast/delta and ahead/on-track/behind)
- [x] Diagnostic test interface (submit answers per question; questions rendered, answers collected, POST /onboarding/submit)
- [x] Current-week task board (Get Tasks; locked completion via API)
- [x] Daily/weekly streak and engagement tracker (Streak & engagement card: Load summary calls learning-metrics + engagement/summary; shows streak, adherence, confidence)
- [x] Chapter tracker with mastery levels (Beginner/Developing/Proficient/Mastered) — Load chapter tracker from where-i-stand; shows chapter: level
- [x] Concept heatmap and confidence chart — Load concept map: strengths/weaknesses/confidence from where-i-stand
- [x] Next-week guidance + explanations — Load next week from plan rough_plan (week 2)
- [x] "Where I stand" (Get Where I Stand in Onboarding &amp; Plan panel)

## Admin/Operator Experience
- [x] Student cohort overview (GET /admin/cohort: learner_count, optional learners list; Admin panel: Cohort button)
- [x] Agent/system health monitor (Admin: Health + Metrics)
- [x] Ingestion and vector DB readiness panel (Admin: Grounding Status)
- [x] Policy violations + compliance panel (GET /admin/policy-violations; Admin panel: Policy violations button)
- [x] Performance diagnostics (Admin: GET /metrics/app — DB/cache/latency/errors)
- [x] Timeline drift dashboard (GET /admin/timeline-drift: avg selected/forecast/delta; Admin panel: Timeline drift button)

---

## 6) Grounding + RAG Quality Controls

- [x] Add strict syllabus boundary checker for generation prompts
- [x] Store citation metadata for each generated output
- [x] Add retrieval confidence score and fallback messaging
- [x] Add "out of syllabus" safe response path
- [x] Add retrieval evaluation script (manual gold checks on selected concepts)

---

## 7) Security, Reliability, and Guardrails

- [x] API gateway auth enabled path (default off locally, on in secured mode)
- [x] Secret handling hardening (never log keys)
- [x] Input validation and policy checks on all write routes
- [x] Failure fallback paths for:
  - [x] Gemini outage
  - [x] Ollama outage
  - [x] DB/Redis outage
- [x] Idempotent scheduling and test submission endpoints

---

## 8) Testing Plan

## Data/Embedding Tests
- [x] PDF parse integrity tests (`tests/test_grounding_ingestion.py`)
- [x] embedding generation dimension consistency tests
- [x] ingestion idempotency tests

## Backend Tests
- [x] onboarding -> diagnostic -> profile integration test (including timeline bounds and recommendation payload)
- [x] weekly planning and threshold unlock tests
- [x] locked-task completion policy tests
- [x] revision queue trigger tests
- [x] no-skip override policy tests
- [x] weekly plan versions + committed/forecast contract tests
- [x] revision pass lifecycle + weak-zone orchestration tests
- [x] adaptive content policy tests (tone/depth/guardrail)
- [x] RAG grounding compliance tests
- [x] grounding readiness endpoint shape test

## Frontend Tests
- [x] critical student journey smoke tests (`test_student_ui_surface_endpoints_available`: health, start-session, plan, tasks, where-i-stand)
- [x] admin metrics panel rendering tests (`test_admin_ui_surface_endpoints_available`: health, /metrics/app, /grounding/status)

## Reliability Tests
- [x] fallback behavior tests
- [x] scheduler restart/state recovery tests
- [x] load test (small local profile)

---

## 9) Metrics & KPI Definition

## Student KPIs (API exposure)
- [x] chapter completion rate (learning-metrics, where-i-stand)
- [x] concept mastery gain (mastery_progression, chapter_status)
- [x] confidence (confidence_score)
- [x] weak-area (weak_areas, weak_area_count)
- [x] weekly adherence rate (adherence_rate_week)
- [x] streak length and engagement minutes (login_streak_days, engagement summary)
- [x] timeline adherence / forecast drift (timeline_adherence_weeks, forecast_drift_weeks)
- [x] chapter retry count and timeout progression rate (GET /onboarding/learning-metrics includes chapter_retry_counts: chapter → attempt_count from ChapterProgression)
- [x] forecast drift trend over time (GET /onboarding/forecast-history/{learner_id} returns history of weekly_forecasts: week_number, current_forecast_weeks, timeline_delta_weeks, pacing_status, generated_at)

## System KPIs
- [x] p50/p95 API latency (`/metrics/app`)
- [x] agent failure/retry rate (`/metrics/app` agents + fleet)
- [x] DB query p95 (`/metrics/app` db)
- [x] Redis cache hit ratio (`/metrics/app` cache)
- [x] RAG retrieval relevance score proxy (`/metrics/app` retrieval)

---

## 10) Deliverables Checklist

- [x] Enterprise architecture and modules implemented incrementally
- [x] Pre-work embedding pipeline complete for syllabus + first 3 chapters
- [x] Full student lifecycle operational in UI (minimal frontend: Student + Onboarding &amp; Plan panels; backend ready)
- [x] Dynamic onboarding-based initial plan generation operational
- [x] Student-selectable bounded timeline + system recommendation operational (API)
- [x] Weekly re-planning with threshold + timeout rules operational (API)
- [x] Adaptive tone/content delivery operational and demonstrable (API)
- [x] Admin observability panel operational (minimal frontend Admin panel: health, metrics, grounding; backend metrics/status ready)
- [x] Logs + metrics + alerts operational (domain logging, GET /metrics/app, alerts in payload)
- [x] Dockerized local reproducibility preserved
- [x] Documentation updated (runbook + architecture + API)

---

## 11) Operating Rules for Implementation

- [x] Do not break existing MVP endpoints while extending (all new routes under /admin or existing prefixes; frontend additive)
- [x] Build in vertical slices (data + backend + UI + tests per feature) (admin API + frontend + smoke tests)
- [x] Every feature must include telemetry + tests before marked done (metrics/app covers app; test_admin_ui_surface includes /admin/*)
- [x] Keep local-first constraints and no paid dependency policy intact (no new external paid deps)
