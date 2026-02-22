# Mentorix Iteration 6 Planner (Enterprise Completion Plan)

Status date: 2026-02-21  
Goal: transform Mentorix from MVP into a production-grade, measurable, adaptive, multi-agent learning platform for Class 10 CBSE Mathematics.

---

## 0) North-Star Outcomes

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

## Phase 0: Runtime Memory Store Hardening (Pre-Iteration-6 Gate)
- [ ] Complete `docs/PLANNER_NOSQL_MEMORY_MIGRATION.md`
- [ ] Move learner/runtime JSON memory from filesystem to NoSQL backend (MongoDB)
- [ ] Keep runtime learner data out of repository workflows

## Phase 1: Data Grounding Pre-Work
- [x] Build offline ingestion job for syllabus + chapters PDFs
- [ ] Parse and persist syllabus hierarchy (chapter > section > concept)
- [x] Generate embeddings for:
  - [x] `class-10-maths/syllabus/syllabus.pdf` (full scope guardrail)
  - [x] `class-10-maths/chapters/ch_1.pdf`
  - [x] `class-10-maths/chapters/ch_2.pdf`
  - [x] `class-10-maths/chapters/ch_3.pdf`
- [x] Store extracted chunks + metadata + embeddings in Postgres vector tables
- [x] Add ingestion manifest tracking (what was embedded, when, hash/version)
- [x] Add pre-start validation so app can fail-fast if mandatory embeddings missing

## Phase 2: Enterprise Backend Core
- [ ] Introduce full student lifecycle APIs:
  - [x] onboarding
  - [x] diagnostics
  - [x] profile
  - [x] weekly plan
  - [ ] schedule execution
  - [ ] revision queue
- [ ] Add onboarding timeline contract (student-selected goal duration):
  - [ ] enforce min/max bounds (`14` to `28` weeks)
  - [ ] persist requested timeline weeks
  - [ ] generate system-recommended timeline from diagnostic score/profile
  - [ ] return both values (requested + recommended) in onboarding response
- [ ] Implement strict progression rules:
  - [x] chapter unlock threshold check (default 60%)
  - [ ] no skip without policy override
  - [ ] task completion by proof, not toggle
  - [x] timeout policy for stuck chapters (max attempts / max weeks before controlled progression)
  - [x] retry policy for low-score chapters (repeat with stronger support before timeout progression)
- [ ] Add adaptive pace engine:
  - [ ] behind pace -> extend week/load balance
  - [ ] ahead pace -> compress carefully
- [ ] Add revision policy engine:
  - [ ] pass 1 full completion
  - [ ] pass 2 full revision
  - [ ] pass 3 weak-zone focus
- [ ] Enforce planning mode:
  - [ ] rough long-range roadmap based on requested/recommended timeline (`14`-`28` weeks)
  - [ ] only current week schedule is active/committed

## Phase 3: Frontend Enterprise UX
- [ ] Build student portal:
  - [ ] onboarding flow
  - [ ] learning home with current week tasks
  - [ ] chapter/concept mastery map
  - [ ] confidence and score trends
  - [ ] revision queue and recommendations
- [ ] Build admin portal:
  - [ ] student cohort overview
  - [ ] system health/alerts
  - [ ] agent-run visibility
  - [ ] schedule compliance tracking
  - [ ] ingestion status + RAG quality signals
- [ ] Improve visual quality for education audience:
  - [ ] polished cards/charts
  - [ ] consistent design system
  - [ ] clear microcopy + status labels

## Phase 4: Reliability, Observability, Operations
- [ ] Add structured logging standards per domain:
  - [ ] onboarding
  - [ ] planning
  - [ ] adaptation
  - [ ] scheduling
  - [ ] compliance
  - [ ] RAG retrieval
- [ ] Add app metrics:
  - [ ] request latency and error rates
  - [ ] agent execution duration/failure counts
  - [ ] DB query performance
  - [ ] Redis cache hit/miss
  - [ ] retrieval quality metrics
- [ ] Add student-learning metrics:
  - [ ] mastery progression by chapter/concept
  - [ ] confidence trend
  - [ ] weak-area decay/improvement
  - [ ] completion and adherence rates
- [ ] Add alerts and anomaly flags:
  - [ ] repeated low scores
  - [ ] disengagement/inactivity
  - [ ] scheduler drift
  - [ ] embedding/retrieval failures

---

## 2) Database Plan (Enterprise Schema)

## Core Student Domain
- [ ] `students`
- [ ] `student_profiles`
- [ ] `student_profile_history` (snapshot trail)
- [ ] timeline fields in profile domain (`requested_timeline_weeks`, `recommended_timeline_weeks`, `timeline_bounds_version`)

## Curriculum & Grounding
- [ ] `chapters`
- [ ] `sections`
- [ ] `concepts`
- [x] `curriculum_documents`
- [x] `embedding_chunks` (vector + source metadata)
- [x] `ingestion_runs` (status, version, hash, counts)

## Learning Journey
- [x] `weekly_plans`
- [ ] `weekly_plan_versions`
- [ ] `tasks`
- [ ] `task_attempts` (proof-based completion)
- [ ] `schedule_locks` / immutable task flags

## Assessment & Mastery
- [ ] `question_bank`
- [ ] `test_attempts`
- [ ] `test_attempt_items`
- [ ] `chapter_scores`
- [ ] `mastery_tracking`
- [ ] `concept_mastery_tracking`
- [ ] `revision_queue`

## Observability & Governance
- [ ] `agent_decision_logs`
- [ ] `system_events`
- [ ] `notifications`
- [ ] `policy_violations`

---

## 3) Redis / Cache & Runtime Plan

- [ ] Session cache model for active learner context
- [ ] Scheduler queue + delayed jobs
- [ ] Plan recalculation debounce cache
- [ ] Retrieval cache for repeated concept queries
- [ ] Rate-limit / idempotency keys for critical writes
- [ ] Lock keys for schedule/task completion workflows
- [ ] TTL and invalidation policy per keyspace

---

## 4) Backend Feature Breakdown (Agent + Service)

## Onboarding + Diagnostics
- [x] Collect student demographic + academic baseline
- [ ] Collect target completion timeline during onboarding (`14`-`28` weeks only)
- [x] Generate diagnostic objective test set from RAG:
  - [x] MCQ
  - [x] Fill-in-the-blank
  - [x] True/False
- [x] Score and initialize profile state
- [ ] Generate timeline recommendation after diagnostic:
  - [ ] keep student-selected timeline as explicit goal
  - [ ] compute recommended timeline and rationale (e.g., "you may need ~16 weeks")
  - [ ] use selected/recommended values to shape week-1 load and roadmap pacing

## Profiling Engine
- [ ] Maintain dynamic attributes:
  - [ ] chapter completion %
  - [ ] strengths/weaknesses
  - [ ] avg score
  - [ ] confidence
  - [ ] pace indicator
  - [ ] revision priority
  - [ ] chapter-level attempt count / retry count
  - [ ] chapter-level timeout flag
  - [ ] engagement minutes per day/week
  - [ ] login/logout events and streak count
- [ ] Update profile after every task/test outcome

## Planner Engine (Weekly Adaptive)
- [ ] Build rough long-range map from bounded timeline selection (`14`-`28` weeks)
- [x] Activate only current week details
- [x] Recalculate weekly plan after each evaluation window
- [x] Enforce threshold-based chapter unlocks
- [ ] Implement stuck-chapter rules:
  - [x] if below threshold -> reinforce and retry
  - [x] if repeatedly below threshold with timeout -> progress + push chapter to revision queue

## Content Agent
- [ ] RAG-only grounded explanation generation
- [ ] Difficulty and depth adaptation by profile
- [ ] Generate examples + practice set per concept
- [ ] Adapt tone and explanation style per learner profile:
  - [ ] weak learner -> simpler language + more examples
  - [ ] strong learner -> concise explanation + challenge questions

## Scheduler Engine
- [ ] Create daily task breakdown (read/practice/test)
- [ ] Lock completion without proof
- [ ] Track completion timestamps and evidence
- [ ] Track engagement evidence:
  - [ ] reading duration
  - [ ] test attempt proof
  - [ ] weekly adherence summary

## Evaluation + Analytics
- [ ] Evaluate objective answers
- [ ] Update chapter/concept mastery
- [ ] Detect misconception patterns
- [ ] Emit recommendations + risk level

## Progress + Revision
- [ ] Build/maintain revision queue
- [ ] Trigger full-pass and weak-area pass policies
- [ ] Measure retention over time

---

## 5) Frontend Plan (Student + Admin)

## Student Experience
- [ ] Onboarding wizard
- [ ] Timeline selector in onboarding:
  - [ ] slider/input constrained to `14`-`28` weeks
  - [ ] helper text for minimum/maximum policy
  - [ ] show "your target" vs "Mentorix recommendation" after test
- [ ] Diagnostic test interface
- [ ] Current-week task board (locked completion logic)
- [ ] Daily/weekly streak and engagement tracker
- [ ] Chapter tracker with mastery levels:
  - [ ] Beginner
  - [ ] Developing
  - [ ] Proficient
  - [ ] Mastered
- [ ] Concept heatmap and confidence chart
- [ ] Next-week guidance + explanations
- [ ] "Where I stand" card:
  - [ ] chapter-by-chapter status
  - [ ] concept strengths/weaknesses
  - [ ] confidence + readiness summary

## Admin/Operator Experience
- [ ] Student progress monitor
- [ ] Agent/system health monitor
- [ ] Ingestion and vector DB readiness panel
- [ ] Policy violations + compliance panel
- [ ] Performance diagnostics (DB/cache/latency/errors)

---

## 6) Grounding + RAG Quality Controls

- [ ] Add strict syllabus boundary checker for generation prompts
- [ ] Store citation metadata for each generated output
- [ ] Add retrieval confidence score and fallback messaging
- [ ] Add "out of syllabus" safe response path
- [ ] Add retrieval evaluation script (manual gold checks on selected concepts)

---

## 7) Security, Reliability, and Guardrails

- [ ] API gateway auth enabled path (default off locally, on in secured mode)
- [ ] Secret handling hardening (never log keys)
- [ ] Input validation and policy checks on all write routes
- [ ] Failure fallback paths for:
  - [ ] Gemini outage
  - [ ] Ollama outage
  - [ ] DB/Redis outage
- [ ] Idempotent scheduling and test submission endpoints

---

## 8) Testing Plan

## Data/Embedding Tests
- [ ] PDF parse integrity tests
- [ ] embedding generation dimension consistency tests
- [ ] ingestion idempotency tests

## Backend Tests
- [ ] onboarding -> diagnostic -> profile integration test (including timeline bounds and recommendation payload)
- [x] weekly planning and threshold unlock tests
- [ ] locked-task completion policy tests
- [ ] revision queue trigger tests
- [ ] RAG grounding compliance tests
- [x] grounding readiness endpoint shape test

## Frontend Tests
- [ ] critical student journey smoke tests
- [ ] admin metrics panel rendering tests

## Reliability Tests
- [ ] fallback behavior tests
- [ ] scheduler restart/state recovery tests
- [ ] load test (small local profile)

---

## 9) Metrics & KPI Definition

## Student KPIs
- [ ] chapter completion rate
- [ ] concept mastery gain per week
- [ ] confidence growth trend
- [ ] weak-area reduction velocity
- [ ] weekly adherence rate
- [ ] streak length and engagement minutes
- [ ] chapter retry count and timeout progression rate
- [ ] timeline adherence: expected pace vs actual pace against selected timeline

## System KPIs
- [ ] p50/p95 API latency
- [ ] agent failure/retry rate
- [ ] DB query p95
- [ ] Redis cache hit ratio
- [ ] RAG retrieval relevance score proxy

---

## 10) Deliverables Checklist

- [ ] Enterprise architecture and modules implemented incrementally
- [x] Pre-work embedding pipeline complete for syllabus + first 3 chapters
- [ ] Full student lifecycle operational in UI
- [x] Dynamic onboarding-based initial plan generation operational
- [ ] Student-selectable bounded timeline + system recommendation operational
- [ ] Weekly re-planning with threshold + timeout rules operational
- [ ] Adaptive tone/content delivery operational and demonstrable
- [ ] Admin observability panel operational
- [ ] Logs + metrics + alerts operational
- [ ] Dockerized local reproducibility preserved
- [x] Documentation updated (runbook + architecture + API)

---

## 11) Operating Rules for Implementation

- [ ] Do not break existing MVP endpoints while extending
- [ ] Build in vertical slices (data + backend + UI + tests per feature)
- [ ] Every feature must include telemetry + tests before marked done
- [ ] Keep local-first constraints and no paid dependency policy intact
