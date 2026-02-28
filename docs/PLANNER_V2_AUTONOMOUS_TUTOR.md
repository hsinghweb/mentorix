# Mentorix V2 — Autonomous Multi-Agent AI Tutor Planner

**Status date:** 2026-02-28  
**Goal:** Transform Mentorix MVP into a fully autonomous, adaptive, multi-agent AI mentor for Class 10 CBSE Mathematics that behaves like a personal tutor — continuously evaluates progress, dynamically adjusts plan, and ensures syllabus mastery.

---

## Executive Summary

This planner documents the complete transformation of Mentorix from its current MVP state into the V2 vision. Each section maps the **V2 requirement** against **what already exists**, identifies the **gap**, and defines **what needs to be built or enhanced**.

> [!IMPORTANT]
> **Hard constraints:** Everything local except Gemini 2.5 Pro (free tier). Embeddings via Ollama (Nomic). PostgreSQL + pgvector + Redis. No LangChain/CrewAI. Extend existing MVP — do NOT rewrite.

---

## Gap Analysis — What Exists vs What's Needed

| Area | MVP Status | V2 Requirement | Gap |
|------|-----------|----------------|-----|
| Chapter PDFs | All 14 present (`ch_1.pdf` – `ch_14.pdf`) | All 14 ingested | Only 5 chapters embedded; need all 14 |
| Syllabus parsing | `syllabus.txt` parsed, `SyllabusHierarchy` table exists | Full chapter → section → concept hierarchy | Hierarchy exists but may need enrichment for section-level granularity |
| Onboarding | Sign up + 25 MCQ + profile + rough plan + week 1 | Same flow + school field | Minor: add `school` field to student info |
| Diagnostic MCQ | LLM-generated 25 MCQs from embeddings | Chapter-aware, difficulty-adaptive MCQs from NCERT | Partially exists; needs stricter NCERT grounding per chapter |
| Evaluation | Score calculation + chapter mastery + profile update | Score per chapter + concept-level mastery + confidence score | Partially exists; needs concept-level granularity |
| Student Profile | `LearnerProfile` with mastery, confidence, pacing | Dynamic profile with completion %, strength/weak areas, avg score, confidence metric, pace indicator, revision priority | Partially exists; needs expansion with revision priority, pace indicator |
| Planner Agent | Rough plan + weekly replan + threshold-based progression | 15-week roadmap, only Week 1 active, flexible draft for rest, adaptive pace | Core logic exists; needs refinement for strict draft vs committed model |
| Content Generator | RAG + Gemini with grounding guardrail | RAG from NCERT embeddings, depth-adjusted, examples, practice questions | Exists but needs profile-driven depth adjustment and practice Q generation |
| Scheduler | `SchedulerService` + Redis-based jobs + task model | Weekly tasks, daily breakdown, evidence-based completion | Task model exists with `is_locked` + `proof_policy`; needs daily breakdown |
| Progress & Revision | `RevisionQueueItem`, `RevisionPolicyState` tables exist | Weak chapter detection, revision weeks, reinforcement exercises | Tables exist; agent logic needs implementation |
| Dashboard | Course completion, confidence, schedule sections | Chapters completed, weak/strong areas, avg score, confidence trend, completion % bar | Partially exists; needs mastery band visualization and confidence trend |
| Mastery Tracking | Chapter mastery score stored in profile | 4-level: Beginner → Developing → Proficient → Mastered | Scores exist; need band classification and display |
| Memory System | MongoDB hubs, episodic, snapshots + Redis cache | Short-term (current week) + long-term (full history) | Exists; needs clearer week-context scoping |
| Strict Progression | `is_locked`, `proof_policy`, chapter advancement | No skipping, no unlock without threshold, no manual completion | Core rules exist; needs tighter enforcement across all paths |
| RAG Pipeline | Hybrid retrieval (vector + keyword), Redis cache | Chapter-aware query → top-k → Gemini → grounded output | Exists; needs chapter-scoped retrieval and all-14-chapter embeddings |
| Observability | Logging per agent, event bus, metrics | Plan adjustments, threshold decisions, revision triggers logged | Partially exists; needs decision-specific audit trail |

---

## 1. Ground Truth System — Grounding & Embeddings

### What exists
- [x] `class-10-maths/syllabus/syllabus.txt` + `syllabus.pdf`
- [x] All 14 chapter PDFs (`ch_1.pdf` – `ch_14.pdf`)
- [x] `SyllabusHierarchy` table (chapter > section > concept)
- [x] `CurriculumDocument` + `EmbeddingChunk` tables with vector columns
- [x] Grounding ingestion pipeline (`API/app/rag/grounding_ingest.py`)
- [x] Setting `grounding_chapter_count = 5` (only first 5 chapters embedded)

### What needs to change
- [ ] **Expand grounding to all 14 chapters** — change `grounding_chapter_count` from 5 → 14
- [ ] **Enrich hierarchy parsing** — ensure section-level and example-level nodes are captured in `SyllabusHierarchy`
- [ ] **Section-level embeddings** — split chapters into sections and embed each section separately (metadata: chapter, section, concept)
- [ ] **Example-level embeddings** — identify solved examples in PDFs and embed them with `doc_type = "example"`
- [ ] **Verify no content leakage** — ensure all RAG responses cite only NCERT content; add integration test

### Files to modify
- `API/app/core/settings.py` — `grounding_chapter_count: 5 → 14`
- `API/app/rag/grounding_ingest.py` — add section-level and example-level chunk splitting
- `API/app/models/entities.py` — potentially add `section_title` and `example_id` fields to `EmbeddingChunk`

---

## 2. Multi-Agent System — Agent Architecture

### 2.1 Onboarding Agent

**What exists:**
- `API/app/agents/onboarding.py` (simple wrapper)
- `API/app/api/onboarding.py` (1946 lines — extensive endpoints for signup, diagnostic, submit, etc.)
- `StudentAuth` model with username, password (hashed)
- Sign up collects: username, password, name, DOB, class 9 math %, weeks (14–28)

**What needs to change:**
- [ ] Add `school` field to student sign-up
- [ ] Refactor onboarding logic from API endpoint into proper agent class
- [ ] Agent should orchestrate the full "new student" flow: collect info → trigger diagnostic → create profile

**Files to modify:**
- `API/app/agents/onboarding.py` — promote to full agent with orchestration logic
- `API/app/api/onboarding.py` — delegate logic to agent
- `API/app/models/entities.py` — add `school` field to `Learner` or `StudentAuth`
- Alembic migration for new field

---

### 2.2 Diagnostic / Test Generator Agent

**What exists:**
- `API/app/agents/diagnostic_mcq.py` (6474 bytes) — LLM-generated MCQs
- Diagnostic questions endpoint: `POST /onboarding/diagnostic-questions`
- 25 MCQs generated via Gemini, with `correct_index` for answer key

**What needs to change:**
- [ ] Make MCQ generation **chapter-aware** — tag each question with source chapter
- [ ] Make difficulty **adaptive** — adjust based on student's class 9 math percentage
- [ ] Ensure all MCQs are **grounded in NCERT embeddings** (retrieve relevant chunks before generating)
- [ ] Add `question_bank` table for persisting generated questions (reusable across students)

**Files to modify:**
- `API/app/agents/diagnostic_mcq.py` — add chapter tagging, difficulty adaptation, RAG integration
- `API/app/models/entities.py` — add `QuestionBank` model
- Alembic migration

---

### 2.3 Evaluation Agent

**What exists:**
- `API/app/agents/assessment.py` (849 bytes — minimal)
- `API/app/agents/analytics_evaluation.py` (3383 bytes)
- `AssessmentResult` table with `score`, `error_type`, `concept`
- Score calculation in onboarding submit endpoint

**What needs to change:**
- [ ] Build a proper `EvaluationAgent` that:
  - Evaluates answers with per-chapter breakdown
  - Calculates concept-level mastery (not just chapter-level)
  - Maintains running confidence score
  - Updates student profile after every evaluation
- [ ] Add concept-level mastery tracking to `LearnerProfile` or new table

**Files to modify:**
- `API/app/agents/assessment.py` — expand into full evaluation agent
- `API/app/agents/analytics_evaluation.py` — enhance with concept-level analytics
- `API/app/models/entities.py` — potentially add `mastery_tracking` table

---

### 2.4 Student Profiling Agent

**What exists:**
- `API/app/agents/learner_profile.py` (415 bytes — minimal)
- `LearnerProfile` table with: `chapter_mastery` (JSONB), `cognitive_depth`, `onboarding_diagnostic_score`, `engagement_minutes`, `timeline_delta_weeks`
- `LearnerProfileSnapshot` for historical snapshots
- Profile update logic scattered in `API/app/api/onboarding.py` (`_update_profile_after_outcome`)

**What needs to change:**
- [ ] Build a proper `StudentProfilingAgent` with these profile dimensions:
  - Chapter completion % (per chapter)
  - Strength areas (chapters with mastery ≥ threshold)
  - Weak areas (chapters below threshold)
  - Average test score (running average)
  - Confidence metric (derived from test variance + accuracy)
  - Pace indicator (ahead / on-track / behind)
  - Revision priority score (per chapter)
- [ ] Profile must auto-update after EVERY activity (test, reading, task completion)
- [ ] Consolidate scattered profile logic into the agent

**Files to modify:**
- `API/app/agents/learner_profile.py` — expand to full profiling agent
- `API/app/models/entities.py` — add missing profile dimensions if not in JSONB
- `API/app/api/onboarding.py` — delegate profile updates to agent

---

### 2.5 Planner Agent (Adaptive Weekly Planner)

**What exists:**
- `API/app/agents/planner.py` (701 bytes — minimal)
- `WeeklyPlan`, `WeeklyPlanVersion`, `WeeklyForecast` tables
- `_build_rough_plan()` in onboarding endpoint
- `weekly_replan()` endpoint with threshold + retry + timeout progression
- `ChapterProgression` table with status tracking
- Adaptive pace: behind → extend (+1 week); ahead → compress (-1 week)

**What needs to change:**
- [ ] Promote planner to a proper agent that:
  - Creates a **rough 15-week roadmap** (flexible draft)
  - Only **activates Week 1** initially
  - Keeps remaining 14 weeks as **modifiable draft**
  - Does NOT lock the full plan upfront
  - Adjusts pace based on performance after each week
- [ ] If score < threshold → repeat chapter with more examples + practice
- [ ] If score ≥ threshold → unlock next chapter
- [ ] Consolidate planning logic from API endpoint into agent

**Files to modify:**
- `API/app/agents/planner.py` — expand to full planner agent
- `API/app/api/onboarding.py` — delegate planning logic to agent

---

### 2.6 Content Generator Agent

**What exists:**
- `API/app/agents/content.py` (7739 bytes — most complete agent)
- `ContentGenerationAgent` with:
  - Policy derivation (weak/developing/strong bands)
  - Grounded context extraction from RAG chunks
  - Template fallback if LLM fails
  - System 2 reasoning loop (draft → verify → refine)
  - Strict grounding guardrail: "only use curriculum context"

**What needs to change:**
- [ ] **Profile-driven depth adjustment** — use full student profile (not just mastery map) to set explanation depth
- [ ] **Practice question generation** — agent should also generate practice questions (not just explanations)
- [ ] **Solved example delivery** — retrieve and present relevant solved examples from NCERT embeddings
- [ ] Ensure content is **chapter-scoped** (only retrieve chunks from current chapter)

**Files to modify:**
- `API/app/agents/content.py` — add practice Q generation, example retrieval, profile integration
- `API/app/rag/retriever.py` — add chapter-scoped retrieval filter

---

### 2.7 Scheduler Agent

**What exists:**
- `API/app/autonomy/scheduler.py` — generic `SchedulerService` with JSON-based jobs, interval-based execution
- `Task` model with: `learner_id`, `week_number`, `chapter`, `task_type`, `status`, `is_locked`, `proof_policy`
- `TaskAttempt` model for evidence-based completion
- `_default_week_tasks()` creates read/practice/test tasks per week
- Redis used for session caching (not directly for task scheduling)

**What needs to change:**
- [ ] Build a proper `SchedulerAgent` that:
  - Creates weekly task sets (reading, practice, test)
  - Creates **daily breakdown** within each week
  - Uses Redis for task state tracking and scheduling
  - Tracks task completion status with evidence
- [ ] Student CANNOT manually mark tasks complete:
  - Reading → must track read progress (time spent / scroll completion)
  - Test → must attempt and submit
  - Only then auto-mark complete
- [ ] Add daily task scheduling to `Task` model (add `scheduled_day` field)

**Files to modify:**
- `API/app/autonomy/scheduler.py` — enhance or create `SchedulerAgent`
- `API/app/models/entities.py` — add `scheduled_day` to `Task` if not present
- `API/app/api/onboarding.py` — integrate scheduler with daily breakdown

---

### 2.8 Progress & Revision Agent

**What exists:**
- `API/app/agents/reflection.py` (953 bytes — minimal)
- `RevisionQueueItem` table with: `learner_id`, `chapter`, `reason`, `status`, `priority`
- `RevisionPolicyState` table with: `active_pass`, `pass_scores` (JSONB), `next_actions`
- `_upsert_revision_queue_item()` and `_upsert_revision_policy_state()` functions
- `_compute_retention_score()` function

**What needs to change:**
- [ ] Build a proper `ProgressRevisionAgent` that:
  - Detects weak chapters (mastery < threshold)
  - Schedules revision weeks (not at end — interspersed)
  - Suggests reinforcement exercises (more examples, different approach)
  - Prevents finishing entire syllabus without revision
- [ ] Add logic to insert revision weeks into the plan dynamically
- [ ] Connect revision trigger to planner agent for plan adjustment

**Files to modify:**
- `API/app/agents/reflection.py` — expand to progress & revision agent
- `API/app/agents/planner.py` — integrate revision week scheduling

---

## 3. Database Enhancements

### What exists
All of these tables already exist:
- `learners`, `student_auth`, `learner_profile`, `learner_profile_snapshots`
- `session_logs`, `assessment_results`
- `concept_chunks`, `embedding_chunks`, `curriculum_documents`
- `weekly_plans`, `weekly_plan_versions`, `weekly_forecasts`
- `tasks`, `task_attempts`
- `chapter_progression`
- `revision_queue`, `revision_policy_state`, `policy_violations`
- `engagement_events`
- `generated_artifacts`, `syllabus_hierarchy`, `ingestion_runs`

### What needs to be added
- [ ] `question_bank` — persisted MCQ bank (chapter, difficulty, question, options, correct_index, embedding)
- [ ] `mastery_tracking` — per-chapter mastery bands (beginner/developing/proficient/mastered) with timestamps
- [ ] Add `school` field to `learners` or `student_auth`
- [ ] Add `scheduled_day` field to `tasks` for daily breakdown
- [ ] Consider adding `concept_mastery` table for concept-level (not just chapter-level) tracking

### Migration
- [ ] Create Alembic migration for all new tables/columns

---

## 4. RAG Pipeline Enhancements

### What exists
- Hybrid retrieval: vector-semantic (pgvector) + keyword overlap re-scoring
- Redis cache (300s TTL) for repeated queries
- `retrieve_concept_chunks_with_meta()` returns chunks + confidence + metadata
- Generated artifacts also retrieved and blended

### What needs to change
- [ ] **Chapter-scoped retrieval** — add chapter filter to `retrieve_concept_chunks_with_meta()`
- [ ] **All 14 chapters embedded** — expand from 5 → 14
- [ ] **Section and example embeddings** — finer granularity for more precise retrieval
- [ ] **Query → identify chapter** — add chapter identification step before retrieval
- [ ] **Store generated content if reusable** — persist high-quality generated explanations as artifacts

**Files to modify:**
- `API/app/rag/retriever.py` — add `chapter_number` filter parameter
- `API/app/rag/grounding_ingest.py` — section/example chunking
- `API/app/core/settings.py` — `grounding_chapter_count: 5 → 14`

---

## 5. Dashboard & Frontend Enhancements

### What exists
- Auth gate (login / signup) → diagnostic → result → dashboard
- Dashboard shows: course completion, profile confidence/accuracy, current schedule
- Static HTML/CSS/JS frontend (`frontend/index.html`, `app.js`, `styles.css`)

### What needs to change
- [ ] **Chapters completed** — visual progress bar with completion %
- [ ] **Weak areas** — highlighted chapter cards
- [ ] **Strong areas** — highlighted chapter cards
- [ ] **Average score** — displayed prominently
- [ ] **Confidence trend** — chart/sparkline showing trend over time
- [ ] **Mastery bands** — per-chapter: Beginner → Developing → Proficient → Mastered (color-coded)
- [ ] **Daily breakdown view** — show today's tasks within current week

**Files to modify:**
- `frontend/index.html` — new dashboard sections
- `frontend/app.js` — API calls for mastery, confidence trend, daily plan
- `frontend/styles.css` — styling for new components

---

## 6. Enterprise Features

### 6.1 Adaptive Pace Engine

**What exists:**
- `_adaptive_pace_extend_compress()` — extend if behind, compress if ahead
- `WeeklyForecast` table tracks forecast drift

**What needs to change:**
- [ ] Make pace engine more granular — per-chapter pace, not just overall
- [ ] Add explicit "extend plan by N weeks" and "compress plan by N weeks" audit log
- [ ] Connect pace engine output to planner agent for dynamic roadmap updates

---

### 6.2 Memory System

**What exists:**
- MongoDB: hubs (learner preferences, operating context, soft identity), snapshots, episodic memory
- Redis: session cache, RAG cache
- `LearnerProfileSnapshot` in Postgres

**What needs to change:**
- [ ] **Short-term memory:** Clear definition of current-week context (tasks, progress, attempts)
- [ ] **Long-term memory:** Full performance history, concept-level tracking
- [ ] Ensure memory is available to all agents for decision-making

---

### 6.3 Strict Progression Rules

**What exists:**
- `is_locked` flag on tasks
- `proof_policy` field on tasks (read/practice/test)
- `TaskAttempt` for evidence
- `advance_chapter()` endpoint with threshold check

**What needs to change:**
- [ ] Enforce at API level: no chapter skip regardless of endpoint
- [ ] No unlock without passing threshold (hard block, not just warning)
- [ ] No task completion without evidence (reading time tracked, test submitted)
- [ ] Add explicit progression audit trail

---

## 7. Observability & Logging

### What exists
- Domain-specific loggers (`DOMAIN_COMPLIANCE`, `DOMAIN_ADAPTATION`, `DOMAIN_SCHEDULING`, etc.)
- Event bus for system events
- Notification engine
- Metrics: fleet telemetry, resilience, retrieval confidence, cache metrics

### What needs to change
- [ ] **Agent decision log** — each agent logs its reasoning and decision
- [ ] **Plan adjustment log** — when planner adjusts, log why (score, pace, threshold)
- [ ] **Threshold decision log** — when student passes/fails threshold, log decision
- [ ] **Revision trigger log** — when revision is scheduled, log trigger reason
- [ ] Consider adding an `agent_decisions` table for full audit trail

---

## 8. Learning Flow — End-to-End

```
Step 1: Student Onboards
  └─ Sign up (name, DOB, school, class 9%, weeks 14–28)
  └─ Takes 25 MCQ diagnostic test (NCERT-grounded)
  └─ Profile created (ability, strengths, weaknesses)

Step 2: Planner Creates
  └─ Rough 15-week roadmap generated
  └─ Only Week 1 activated (locked schedule)
  └─ Weeks 2–15 remain flexible draft

Step 3: Week Execution
  └─ Student reads content (RAG-generated from NCERT)
  └─ Student does practice exercises
  └─ Student gives chapter test
  └─ Evaluation agent scores and updates profile

Step 4: Progression Decision
  └─ Score ≥ threshold → unlock next chapter
  └─ Score < threshold → repeat chapter with:
      └─ Different examples
      └─ More practice
      └─ Deeper explanations

Step 5: Continuous Adaptation
  └─ Profile updates dynamically after every activity
  └─ Planner recalculates pace
  └─ Revision agent schedules revision weeks as needed
  └─ Repeat until course complete
```

---

## 9. Implementation Priority Order

### P0 — Foundation (Must do first)
- [ ] Expand grounding to all 14 chapters (change setting + re-ingest)
- [ ] Section-level and example-level embeddings
- [ ] Chapter-scoped RAG retrieval
- [ ] Database migrations for new tables/fields

### P1 — Agent Architecture
- [ ] Refactor agents from thin wrappers to proper classes:
  - [ ] Onboarding Agent
  - [ ] Evaluation Agent
  - [ ] Student Profiling Agent
  - [ ] Planner Agent
  - [ ] Scheduler Agent
  - [ ] Progress & Revision Agent
- [ ] Content Generator Agent enhancements (practice Qs, examples)
- [ ] Diagnostic MCQ Agent (chapter-aware, difficulty-adaptive, NCERT-grounded)

### P2 — Dashboard & Frontend
- [ ] Mastery band visualization
- [ ] Confidence trend chart
- [ ] Daily breakdown view
- [ ] Completion progress bar
- [ ] Weak/strong area highlighting

### P3 — Enterprise Features
- [ ] Adaptive pace engine granularity
- [ ] Memory system scoping (short-term / long-term)
- [ ] Full observability with agent decision audit trail
- [ ] Strict progression enforcement hardening

---

## 10. Files Impact Summary

| File | Change Type | Scope |
|------|-----------|-------|
| `API/app/core/settings.py` | MODIFY | `grounding_chapter_count: 5 → 14` |
| `API/app/rag/grounding_ingest.py` | MODIFY | Section/example chunking |
| `API/app/rag/retriever.py` | MODIFY | Chapter-scoped retrieval |
| `API/app/models/entities.py` | MODIFY | New tables + fields |
| `API/app/agents/onboarding.py` | MODIFY | Full agent refactor |
| `API/app/agents/assessment.py` | MODIFY | Expand to evaluation agent |
| `API/app/agents/learner_profile.py` | MODIFY | Full profiling agent |
| `API/app/agents/planner.py` | MODIFY | Full planner agent |
| `API/app/agents/content.py` | MODIFY | Practice Qs + examples |
| `API/app/agents/diagnostic_mcq.py` | MODIFY | Chapter-aware + grounded |
| `API/app/agents/reflection.py` | MODIFY | Progress & revision agent |
| `API/app/autonomy/scheduler.py` | MODIFY | Daily breakdown + evidence |
| `API/app/api/onboarding.py` | MODIFY | Delegate to agents |
| `frontend/index.html` | MODIFY | Dashboard sections |
| `frontend/app.js` | MODIFY | New API calls + rendering |
| `frontend/styles.css` | MODIFY | New component styles |
| `API/alembic/versions/` | NEW | Migration for new tables/columns |

---

## 11. Core Principles Checklist

- [ ] Full syllabus control (all 14 chapters structured)
- [ ] Strict grounding to NCERT (no hallucinated math theory)
- [ ] Adaptive mentoring (profile-driven personalization)
- [ ] Profile-driven personalization (every agent uses student profile)
- [ ] Local-first architecture (only Gemini API external)
- [ ] No paid tools, no cloud dependencies
- [ ] Extend existing MVP (not rewrite)
