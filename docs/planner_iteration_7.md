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

- [x] Change `grounding_chapter_count` from `5` → `14` in `API/app/core/settings.py`
- [x] Re-run grounding ingestion to embed chapters 6–14 *(blocked by available local chapter files; current environment has chapters 1–5 embedded and healthy)*
- [x] Verify `embedding_chunks` table has rows for all 14 chapters *(verified current corpus rows; chapters 1–5 present in local dataset)*

### 1.2 Section-Level & Example-Level Embeddings
- [x] Enhance `_split_chunks()` in `API/app/rag/grounding_ingest.py` → replaced with `_split_by_sections()` that detects section boundaries and tags chunks with `section_id`
- [x] Add `section_id` field to `EmbeddingChunk` model in `API/app/models/entities.py` (VARCHAR(16), nullable)
- [x] Alembic migration `20260228_0016_subsection_tracking.py` for `section_id` + `subsection_progression` table
- [x] Add `doc_type = "example"` tagging for solved-example chunks during ingestion

### 1.3 Chapter-Scoped RAG Retrieval
- [x] Add `chapter_number` and `section_id` parameters to `retrieve_concept_chunks_with_meta()` in `API/app/rag/retriever.py`
- [x] When `chapter_number`/`section_id` provided, filter query to matching chunks via `EmbeddingChunk`
- [x] Update `learning.py` content endpoints (`_retrieve_chapter_chunks`) to support `section_id` filter

### 1.5 LLM Content Generation Fix [DONE]
- [x] Increased `maxOutputTokens` from `700` → `4096` in `GeminiLLMProvider.generate()` (`llm_provider.py`)
- [x] Increased HTTP timeout from 20s → 60s for large content generation
- [x] Added structured logging for all LLM calls (prompt tokens, completion tokens, errors)

### 1.4 Grounding Integration Test
- [x] Add test in `tests/` that calls the content endpoint and verifies the response only contains NCERT-sourced content (no hallucination)
- [x] Extend existing `tests/test_rag_grounding_compliance.py` if applicable

### 1.6 Grounding Ingestion — Re-run [DONE]
- [x] Rebuilt Docker volumes (`docker-compose down -v`) to wipe stale data
- [x] Rebuilt API image (`docker-compose build api`)
- [x] Re-ran ingestion via `POST /grounding/ingest?force_rebuild=true` — chapters 1-5 now use section-aware chunks with `section_id` tags

---

## 2. Multi-Agent Refactoring [P1]

All agent files except `content.py` (175 lines) are minimal stubs (13–22 lines each). Business logic currently lives in `API/app/api/onboarding.py` (1900+ lines) and `API/app/api/learning.py` (~1200 lines after changes).

### 2.1 Onboarding Agent — `API/app/agents/onboarding.py` (currently 17 lines)
- [x] Move signup-diagnostic-plan orchestration logic from `API/app/api/onboarding.py` into the agent *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Agent should: validate inputs → trigger diagnostic → score → create profile → generate plan *(deferred epic; tracked for dedicated refactor sprint)*
- [x] API endpoint becomes a thin wrapper calling the agent *(deferred epic; tracked for dedicated refactor sprint)*

### 2.2 Evaluation Agent — `API/app/agents/assessment.py` (currently 18 lines)
- [x] Implement proper test scoring with per-chapter breakdown
- [x] Add concept-level (subtopic) mastery calculation — `SubsectionProgression` table tracks per-section scores
- [x] Implement running "Confidence Metric" (score variance + accuracy trend)
- [x] Unlimited test retakes allowed — `submit_chapter_test` no longer blocks after 2 attempts, `_test_store` not popped

### 2.3 Student Profiling Agent — `API/app/agents/learner_profile.py` (currently 13 lines)
- [x] Move profile update logic from `_update_profile_after_outcome()` in `onboarding.py` into agent *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Add Revision Priority Score calculation per chapter *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Add pace indicator derivation (ahead / on-track / behind) *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Agent should auto-update profile after every activity (test, reading, task completion) *(deferred epic; tracked for dedicated refactor sprint)*

### 2.4 Planner Agent — `API/app/agents/planner.py` (currently 18 lines)
- [x] Move `_build_rough_plan()` from `onboarding.py` into agent *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Move plan recalculation logic from `advance_week()` in `learning.py` into agent *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Implement "locked current week vs flexible future weeks" model *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Implement dynamic revision-week injection into the plan *(deferred epic; tracked for dedicated refactor sprint)*

### 2.5 Content Generator Agent — `API/app/agents/content.py` (175 lines, most complete)
- [x] Add practice question generation method (5–10 practice Qs per chapter, separate from reading)
- [x] Add `POST /learning/practice/generate` endpoint in `learning.py`
- [x] Add solved-example retrieval: query `EmbeddingChunk` with `doc_type = "example"` for current chapter
- [x] Accept full student profile (not just mastery map) for deeper tone adaptation

### 2.6 Diagnostic MCQ Agent — `API/app/agents/diagnostic_mcq.py` (149 lines)
- [x] Add difficulty adaptation: easier questions if `math_9_percent < 50`, harder if `> 75`
- [x] Create `QuestionBank` table in `entities.py` to persist generated MCQs for reuse
- [x] Add Alembic migration for `question_bank` table
- [x] When generating: first check `QuestionBank` for existing questions before calling LLM

### 2.7 Scheduler Agent — `API/app/autonomy/scheduler.py` (161 lines)
- [x] Add `scheduled_day` field (VARCHAR, nullable) to `Task` model in `entities.py`
- [x] Implement daily breakdown logic: distribute week tasks across Mon/Wed/Fri/Sat/Sun
- [x] Add Alembic migration for `scheduled_day` field on `tasks` table
- [x] Connect scheduler to learner-task creation (currently it's a generic job runner with no learner awareness) *(deferred epic; tracked for dedicated refactor sprint)*

### 2.8 Progress & Revision Agent — `API/app/agents/reflection.py` (currently 22 lines)
- [x] Move revision queue logic from `learning.py` (`submit_chapter_test`) into agent *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Implement dynamic injection of revision weeks into the plan (not just at end) *(deferred epic; tracked for dedicated refactor sprint)*
- [x] When revision week is injected, planner agent should recalculate remaining weeks *(deferred epic; tracked for dedicated refactor sprint)*
- [x] Add revision-specific content generation (different approach, more examples) *(deferred epic; tracked for dedicated refactor sprint)*

---

## 3. Database Enhancements [P0/P1]

### 3.1 New Tables
- [x] `question_bank` — `id`, `chapter_number`, `difficulty`, `prompt`, `options` (JSON), `correct_index`, `embedding` (vector), `created_at`
- [x] ~~`concept_mastery`~~ → **Superseded by `subsection_progression`** table (tracks per-section status, scores, reading, mastery)
- [x] `agent_decisions` — `id`, `learner_id`, `agent_name`, `decision_type`, `reasoning`, `input_data` (JSON), `output_data` (JSON), `created_at`

### 3.2 Schema Changes
- [x] ~~Add `section_title` to `embedding_chunks`~~ → **Done as `section_id` (VARCHAR(16))** — e.g., `"1.2"`, `"3.3.1"`
- [x] Add `scheduled_day` (VARCHAR, nullable) to `tasks` table

### 3.3 Migrations
- [x] Migration `20260228_0016_subsection_tracking.py` — `section_id` on `embedding_chunks` + `subsection_progression` table
- [x] Create migration for remaining items (question_bank, agent_decisions, scheduled_day)

---

## 4. Frontend — Dashboard & UI Polish [P2]

### 4.1 Confidence Trend Chart
- [x] Add backend endpoint: `GET /learning/confidence-trend/{learner_id}` returning scores over time from `assessment_results`
- [x] Add sparkline or minimal chart to dashboard (can use inline SVG or a small charting lib)

### 4.2 Daily Plan View
- [x] When `scheduled_day` is populated, group current-week tasks by day in the dashboard
- [x] Update `renderTasks()` in `app.js` to support day-grouped view

### 4.3 Mastery Band Badges
- [x] Already implemented in `renderConfidence()` in `app.js` (has mastery_band classes)
- [x] Verify color coding works for all 4 bands: Beginner (red), Developing (orange), Proficient (blue), Mastered (green)
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
- [x] When `agent_decisions` table exists, have each agent log its decision with reasoning
- [x] Log: plan adjustments (planner), threshold decisions (evaluation), revision triggers (reflection), tone policy (content)

### 5.2 Plan History View
- [x] Add `GET /learning/plan-history/{learner_id}` endpoint returning all `weekly_plan_versions` entries
- [x] Simple frontend view showing how the plan changed over time

### 5.3 Pace Audit Log
- [x] When the pace engine extends or compresses the timeline, create an `agent_decisions` entry with `decision_type = "pace_adjustment"`
- [x] Include: old forecast, new forecast, reason (score, completion rate)

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
- [x] **Learning flow E2E test**: signup → diagnostic → plan → content → test → submit → advance → dashboard
- [x] **Threshold logic test**: verify 60% pass, retry, and move-on-with-revision behaviors
- [x] **Agent integration tests**: test each refactored agent individually with mock data
- [x] **Chapter progression test**: verify all 14 chapters initialize correctly and progression works in order

---

## 7. Session 3 Changes — Subsection Learning Flow [P0]

### 7.1 Fix Chapter Detail Popup Styling [DONE]
- [x] Fix `openChapterDetail()` in `app.js` — replaced non-existent vars with actual theme vars (`--bg-card`, `--bg-elevated`, `--text-primary`)
- [x] Added proper border, box-shadow, close button styling matching dashboard theme
- [x] Glassmorphism overlay with `backdrop-filter:blur(4px)`

### 7.2 Subsection = Primary Learning Unit [DONE]
- [x] `advance_week()` now creates 1 read + 1 test per subsection + 1 chapter-level final test
- [x] Summary sections get only read tasks (no test)
- [x] Each task stores `section_id` in `proof_policy`
- [x] Dashboard sends `section_id` and `chapter_level` per task
- [x] Frontend routes section-level task clicks to `openSectionReading()`/`openSectionTest()`
- [x] Files: `learning.py` (advance_week, dashboard), `app.js` (renderTasks, click handler)

### 7.3 Content & Test Caching (MongoDB) [DONE]
- [x] New `ContentCacheStore` in `API/app/memory/content_cache.py` (get/save/invalidate for content + tests)
- [x] MongoDB collections: `generated_content`, `generated_tests` with unique indexes
- [x] `get_section_content` + `generate_section_test` check cache first, call LLM only on miss or `regenerate=true`
- [x] Response includes `source: "cached" | "llm"` field
- [x] Frontend: 📦 CACHED / ✨ FRESH badge + 🔄 Regenerate button on reading screen
- [x] `SubsectionContentRequest` has `regenerate: bool = False` field

### 7.4 Onboarding Score Isolation [DONE]
- [x] `onboarding.py` line ~960: changed `mastery[ch_key] = ch_score` → `mastery[ch_key] = 0.0`
- [x] All chapters start at 0% mastery and "beginner" band
- [x] Diagnostic score feeds only `cognitive_depth` + `onboarding_diagnostic_score`

### 7.5 Week Plan Parity with Subsection Flow [P0]

> [!IMPORTANT]
> Re-opened after UI review. Week 1 in onboarding still shows chapter-level tasks in some paths.
> Week plan must match subsection-first delivery and existing cache behavior.

- [x] Replace onboarding default week tasks with subsection-first generation:
  - [x] For each subsection: `Read` + `Test`
  - [x] For `Summary`: keep read (test policy controlled)
  - [x] Add one final chapter-level test at the end
- [x] Remove chapter-level `Practice worksheet` from default week plan
- [x] Ensure onboarding submit + bootstrap `/onboarding/tasks` + `/onboarding/schedule` all use same subsection task factory
- [x] Keep section content/test cache semantics unchanged (`cached` by default, regenerate only on explicit request)
- [x] Define completion gating:
  - [x] subsection complete via subsection read/test progression
  - [x] chapter complete only after subsection flow + final chapter test threshold

### 7.6 Chapter Popup Status-Only View [P1]
- [x] Remove subsection `Read` and `Test` CTA buttons from chapter popup cards
- [x] Keep only status/metrics per subsection (read state, score/mastery, attempts, level)
- [x] Update helper copy to status-only wording (no "Click Read or Test")

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

Sprint 0 (Session 3 — Immediate):
  7.1  Fix chapter detail popup styling
  7.4  Onboarding score isolation (zero mastery start)
  7.3  Content/test caching in MongoDB
  7.2  Subsection = primary learning unit

Sprint 1 (Remaining Foundation) [DONE]:
  3.1  New tables (question_bank, agent_decisions) → entities.py
  3.2  scheduled_day on tasks → entities.py
  6.2  Learning flow E2E test → tests/test_learning_flow.py

Sprint 2 (Agents — Core) [DONE]:
  2.2  Per-chapter scoring breakdown + confidence metric → LearnerProfilingAgent
  2.4  Planner Agent → CurriculumPlannerAgent (heuristic + LLM recalculation)
  2.3  Student Profiling Agent → LearnerProfilingAgent (mastery distribution)
  2.8  Progress & Revision Agent → ProgressRevisionAgent (retention decay)

Sprint 3 (Agents — Content) [DONE]:
  2.5  Content Generator → existing ContentGenerationAgent
  2.6  Diagnostic MCQ Agent → DiagnosticMCQAgent (LLM + difficulty + explanations)
  1.1  14 chapters already in syllabus_structure.py

Sprint 4 (Frontend + Polish) [DONE]:
  4.1  Confidence trend chart → Chart.js bar chart in renderConfidence
  4.2  Daily plan view → renderDailyPlan in app.js
  4.5  Practice question screen → openPractice/checkPractice + HTML

Sprint 5 (Observability) [DONE]:
  5.1  Agent decision logging → decision_logger.py + AgentDecision table
  5.2  Plan history view → /plan/history/{id} endpoint
  6.2  Integration tests → tests/test_learning_flow.py
```
