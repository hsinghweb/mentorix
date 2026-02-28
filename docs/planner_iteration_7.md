# Mentorix V2 — Planner Iteration 7 (All Incomplete Tasks)

**Date:** 2026-02-28 (updated: session 2)  
**Purpose:** Single source of truth for all remaining work. Consolidates every incomplete, partial, and deferred task from previous planners after codebase verification.

> [!IMPORTANT]
> **Hard constraints:** Everything local except Gemini 2.5 Flash (free tier). Embeddings via Ollama (Nomic). PostgreSQL + pgvector + Redis. No LangChain/CrewAI. Extend existing MVP — do NOT rewrite.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Foundation — blocks other work |
| **P1** | Core feature — needed for complete product |
| **P2** | Polish/enhancement — improves quality |

---

## 1. Ground Truth System — RAG & Embeddings [P0]

Currently only the first 5 of 14 chapters are embedded. The retriever has no chapter-scoped filtering.

### 1.1 Expand Grounding to All 14 Chapters

> [!NOTE]
> **Deferred** — keeping at 5 chapters for now (local laptop memory/compute constraints).

- [ ] Change `grounding_chapter_count` from `5` → `14` in `API/app/core/settings.py`
- [ ] Re-run grounding ingestion to embed chapters 6–14
- [ ] Verify `embedding_chunks` table has rows for all 14 chapters

### 1.2 Section-Level & Example-Level Embeddings
- [x] Enhance `_split_chunks()` in `API/app/rag/grounding_ingest.py` → replaced with `_split_by_sections()` that detects section boundaries and tags chunks with `section_id`
- [x] Add `section_id` field to `EmbeddingChunk` model in `API/app/models/entities.py` (VARCHAR(16), nullable)
- [x] Alembic migration `20260228_0016_subsection_tracking.py` for `section_id` + `subsection_progression` table
- [ ] Add `doc_type = "example"` tagging for solved-example chunks during ingestion

### 1.3 Chapter-Scoped RAG Retrieval
- [x] Add `chapter_number` and `section_id` parameters to `retrieve_concept_chunks_with_meta()` in `API/app/rag/retriever.py`
- [x] When `chapter_number`/`section_id` provided, filter query to matching chunks via `EmbeddingChunk`
- [x] Update `learning.py` content endpoints (`_retrieve_chapter_chunks`) to support `section_id` filter

### 1.5 LLM Content Generation Fix [DONE]
- [x] Increased `maxOutputTokens` from `700` → `4096` in `GeminiLLMProvider.generate()` (`llm_provider.py`)
- [x] Increased HTTP timeout from 20s → 60s for large content generation
- [x] Added structured logging for all LLM calls (prompt tokens, completion tokens, errors)

### 1.4 Grounding Integration Test
- [ ] Add test in `tests/` that calls the content endpoint and verifies the response only contains NCERT-sourced content (no hallucination)
- [ ] Extend existing `tests/test_rag_grounding_compliance.py` if applicable

### 1.6 Grounding Ingestion — Re-run [DONE]
- [x] Rebuilt Docker volumes (`docker-compose down -v`) to wipe stale data
- [x] Rebuilt API image (`docker-compose build api`)
- [x] Re-ran ingestion via `POST /grounding/ingest?force_rebuild=true` — chapters 1-5 now use section-aware chunks with `section_id` tags

---

## 2. Multi-Agent Refactoring [P1]

All agent files except `content.py` (175 lines) are minimal stubs (13–22 lines each). Business logic currently lives in `API/app/api/onboarding.py` (1900+ lines) and `API/app/api/learning.py` (~1200 lines after changes).

### 2.1 Onboarding Agent — `API/app/agents/onboarding.py` (currently 17 lines)
- [ ] Move signup-diagnostic-plan orchestration logic from `API/app/api/onboarding.py` into the agent
- [ ] Agent should: validate inputs → trigger diagnostic → score → create profile → generate plan
- [ ] API endpoint becomes a thin wrapper calling the agent

### 2.2 Evaluation Agent — `API/app/agents/assessment.py` (currently 18 lines)
- [ ] Implement proper test scoring with per-chapter breakdown
- [x] Add concept-level (subtopic) mastery calculation — `SubsectionProgression` table tracks per-section scores
- [ ] Implement running "Confidence Metric" (score variance + accuracy trend)
- [x] Unlimited test retakes allowed — `submit_chapter_test` no longer blocks after 2 attempts, `_test_store` not popped

### 2.3 Student Profiling Agent — `API/app/agents/learner_profile.py` (currently 13 lines)
- [ ] Move profile update logic from `_update_profile_after_outcome()` in `onboarding.py` into agent
- [ ] Add Revision Priority Score calculation per chapter
- [ ] Add pace indicator derivation (ahead / on-track / behind)
- [ ] Agent should auto-update profile after every activity (test, reading, task completion)

### 2.4 Planner Agent — `API/app/agents/planner.py` (currently 18 lines)
- [ ] Move `_build_rough_plan()` from `onboarding.py` into agent
- [ ] Move plan recalculation logic from `advance_week()` in `learning.py` into agent
- [ ] Implement "locked current week vs flexible future weeks" model
- [ ] Implement dynamic revision-week injection into the plan

### 2.5 Content Generator Agent — `API/app/agents/content.py` (175 lines, most complete)
- [ ] Add practice question generation method (5–10 practice Qs per chapter, separate from reading)
- [ ] Add `POST /learning/practice/generate` endpoint in `learning.py`
- [ ] Add solved-example retrieval: query `EmbeddingChunk` with `doc_type = "example"` for current chapter
- [ ] Accept full student profile (not just mastery map) for deeper tone adaptation

### 2.6 Diagnostic MCQ Agent — `API/app/agents/diagnostic_mcq.py` (149 lines)
- [ ] Add difficulty adaptation: easier questions if `math_9_percent < 50`, harder if `> 75`
- [ ] Create `QuestionBank` table in `entities.py` to persist generated MCQs for reuse
- [ ] Add Alembic migration for `question_bank` table
- [ ] When generating: first check `QuestionBank` for existing questions before calling LLM

### 2.7 Scheduler Agent — `API/app/autonomy/scheduler.py` (161 lines)
- [ ] Add `scheduled_day` field (VARCHAR, nullable) to `Task` model in `entities.py`
- [ ] Implement daily breakdown logic: distribute week tasks across Mon/Wed/Fri/Sat/Sun
- [ ] Add Alembic migration for `scheduled_day` field on `tasks` table
- [ ] Connect scheduler to learner-task creation (currently it's a generic job runner with no learner awareness)

### 2.8 Progress & Revision Agent — `API/app/agents/reflection.py` (currently 22 lines)
- [ ] Move revision queue logic from `learning.py` (`submit_chapter_test`) into agent
- [ ] Implement dynamic injection of revision weeks into the plan (not just at end)
- [ ] When revision week is injected, planner agent should recalculate remaining weeks
- [ ] Add revision-specific content generation (different approach, more examples)

---

## 3. Database Enhancements [P0/P1]

### 3.1 New Tables
- [ ] `question_bank` — `id`, `chapter_number`, `difficulty`, `prompt`, `options` (JSON), `correct_index`, `embedding` (vector), `created_at`
- [x] ~~`concept_mastery`~~ → **Superseded by `subsection_progression`** table (tracks per-section status, scores, reading, mastery)
- [ ] `agent_decisions` — `id`, `learner_id`, `agent_name`, `decision_type`, `reasoning`, `input_data` (JSON), `output_data` (JSON), `created_at`

### 3.2 Schema Changes
- [x] ~~Add `section_title` to `embedding_chunks`~~ → **Done as `section_id` (VARCHAR(16))** — e.g., `"1.2"`, `"3.3.1"`
- [ ] Add `scheduled_day` (VARCHAR, nullable) to `tasks` table

### 3.3 Migrations
- [x] Migration `20260228_0016_subsection_tracking.py` — `section_id` on `embedding_chunks` + `subsection_progression` table
- [ ] Create migration for remaining items (question_bank, agent_decisions, scheduled_day)

---

## 4. Frontend — Dashboard & UI Polish [P2]

### 4.1 Confidence Trend Chart
- [ ] Add backend endpoint: `GET /learning/confidence-trend/{learner_id}` returning scores over time from `assessment_results`
- [ ] Add sparkline or minimal chart to dashboard (can use inline SVG or a small charting lib)

### 4.2 Daily Plan View
- [ ] When `scheduled_day` is populated, group current-week tasks by day in the dashboard
- [ ] Update `renderTasks()` in `app.js` to support day-grouped view

### 4.3 Mastery Band Badges
- [x] Already implemented in `renderConfidence()` in `app.js` (has mastery_band classes)
- [ ] Verify color coding works for all 4 bands: Beginner (red), Developing (orange), Proficient (blue), Mastered (green)
- [x] Band badges added to chapter drill-down modal (per-subsection mastery badges)

### 4.4 Subtopic Tracking [DONE]
- [x] `SubsectionProgression` table created with per-section status, scores, mastery tracking
- [x] `GET /learning/chapter/{n}/sections/{learner_id}` — returns per-subsection progress
- [x] `POST /learning/content/section` — section-scoped reading with grounded NCERT content
- [x] `POST /learning/test/section/generate` — 5-MCQ section test
- [x] Frontend: chapter card click → modal drill-down showing all subsections with Read/Test buttons
- [x] Frontend: `openSectionReading()` and `openSectionTest()` functions

### 4.6 Test Retake UI [DONE]
- [x] Removed `completed` click-block on task cards — all tasks always accessible
- [x] Test feedback now shows "🔄 Retake Test" + "← Dashboard" buttons
- [x] `checkWeekComplete()` updated to recognize `completed_first_attempt` status

---

## 5. Observability & Audit Trail [P2]

### 5.1 Agent Decision Logging
- [ ] When `agent_decisions` table exists, have each agent log its decision with reasoning
- [ ] Log: plan adjustments (planner), threshold decisions (evaluation), revision triggers (reflection), tone policy (content)

### 5.2 Plan History View
- [ ] Add `GET /learning/plan-history/{learner_id}` endpoint returning all `weekly_plan_versions` entries
- [ ] Simple frontend view showing how the plan changed over time

### 5.3 Pace Audit Log
- [ ] When the pace engine extends or compresses the timeline, create an `agent_decisions` entry with `decision_type = "pace_adjustment"`
- [ ] Include: old forecast, new forecast, reason (score, completion rate)

---

## 6. Integration Testing [P1]

### 6.1 Existing Tests (in `tests/` directory)
- `test_api_integration.py` — API integration tests
- `test_content_policy.py` — Content generation policy tests
- `test_grounding_ingestion.py` — Grounding pipeline tests
- `test_rag_grounding_compliance.py` — RAG compliance tests
- `test_reliability_scheduler.py` — Scheduler reliability tests
- `test_security_guardrails.py` — Security tests

### 6.2 New Tests Needed
- [ ] **Learning flow E2E test**: signup → diagnostic → plan → content → test → submit → advance → dashboard
- [ ] **Threshold logic test**: verify 60% pass, retry, and move-on-with-revision behaviors
- [ ] **Agent integration tests**: test each refactored agent individually with mock data
- [ ] **Chapter progression test**: verify all 14 chapters initialize correctly and progression works in order

---

## Implementation Order (Updated)

```
DONE (Session 2 — 2026-02-28):
  1.2  Section-level embeddings (_split_by_sections, section_id)
  1.3  Chapter-scoped RAG retrieval (chapter_number + section_id filters)
  1.5  LLM fix (maxOutputTokens 700→4096, timeout 20→60s, logging)
  1.6  Ingestion re-run with section-aware chunks
  2.2  Unlimited test retakes + subsection mastery tracking
  3.2  section_id on embedding_chunks
  3.3  Migration 20260228_0016
  4.4  Subtopic tracking endpoints + frontend drill-down
  4.6  Test retake UI

Sprint 1 (Remaining Foundation):
  3.1  New tables (question_bank, agent_decisions)
  3.2  scheduled_day on tasks
  6.2  Learning flow E2E test

Sprint 2 (Agents — Core):
  2.2  Remaining: per-chapter scoring breakdown, confidence metric
  2.4  Planner Agent (plan generation + recalculation)
  2.3  Student Profiling Agent (profile updates)
  2.8  Progress & Revision Agent

Sprint 3 (Agents — Content):
  2.5  Content Generator (practice Qs + examples)
  2.6  Diagnostic MCQ Agent (question bank)
  1.1  Expand to 14 chapters (when hardware allows)

Sprint 4 (Frontend + Polish):
  4.1  Confidence trend chart
  4.2  Daily plan view
  4.5  Practice question screen

Sprint 5 (Observability):
  5.1  Agent decision logging
  5.2  Plan history view
  6.2  Integration tests
```
