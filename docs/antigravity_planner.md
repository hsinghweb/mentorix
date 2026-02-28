# Mentorix — Antigravity Planner

**Date:** 2026-02-28  
**Product:** Autonomous AI Tutor for Class 10 CBSE Mathematics (NCERT)  
**Approach:** Dynamic pacing · Dynamic content · Profile-driven personalization

---

## Product Summary

A multi-agent AI tutor that takes a Class 10 student through the entire NCERT Mathematics syllabus (14 chapters). The system adapts **pace** (how fast the student progresses) and **tone** (how content is explained) based on continuous performance evaluation. Every week the rough plan, completion status, and accuracy/confidence are recalculated.

### Core Rules

| Rule | Detail |
|------|--------|
| **Completion threshold** | Student must score ≥ 60% on a chapter test to mark it complete |
| **Max attempts** | If student fails twice, move on — schedule that chapter for revision later |
| **No manual completion** | Student cannot mark any task as done manually; completion is evidence-based only |
| **No forced timeline** | If student finishes Week 1 tasks in 3 days, immediately open Week 2 |
| **No skipping** | Chapters must be done in syllabus order (1 → 14) |
| **Dynamic pacing** | Rough plan updates after every week based on actual performance |
| **Dynamic content** | Explanation depth, examples, and tone adapt to student's ability and accuracy |
| **Grounding** | ALL content must come from NCERT chapter embeddings via RAG — no hallucination |

### Three Living Tables (Updated Weekly)

1. **Rough Estimated Plan** — Which chapters go in which weeks; recalculated after every week
2. **Completion Status** — Per chapter and per subtopic: not started / in progress / completed
3. **Accuracy & Confidence** — Per chapter and per subtopic: score, confidence level, mastery band

---

## Existing Assets (What We Already Have)

| Asset | Location | Status |
|-------|----------|--------|
| 14 chapter PDFs | `class-10-maths/chapters/ch_1.pdf` – `ch_14.pdf` | ✅ All present |
| Syllabus text | `class-10-maths/syllabus/syllabus.txt` | ✅ Present |
| Syllabus structure (Python) | `API/app/data/syllabus_structure.py` — 14 chapters, all subtopics | ✅ Complete |
| 5 diagnostic question sets | `API/app/data/diagnostic_question_sets.py` — 25 MCQs each, chapter-tagged, answer keys | ✅ Complete |
| Grounding ingestion pipeline | `API/app/rag/grounding_ingest.py` | ✅ Works (first 5 chapters — sufficient for demo) |
| Embedding pipeline | `API/app/rag/embeddings.py` (Ollama nomic-embed-text) | ✅ Working |
| RAG retriever | `API/app/rag/retriever.py` (hybrid: vector + keyword) | ✅ Working |
| FastAPI app | `API/app/main.py` with 12 routers | ✅ Working |
| Docker Compose | `docker-compose.yml` (Postgres, Redis, Mongo, API, Nginx) | ✅ Working |
| Auth flow | `API/app/api/auth.py` (signup, login, JWT) | ✅ Working |
| Onboarding endpoints | `API/app/api/onboarding.py` (1946 lines) | ✅ Working (needs cleanup) |
| Frontend | `frontend/index.html`, `app.js`, `styles.css` | ✅ Fixed (auth, API URL, dashboard, reading, test) |

---

## Completion status (summary)

| Phase | Done | Notes |
|-------|------|--------|
| **0** | Runbook + code verified | `docs/PHASE0_RUNBOOK.md`; `grounding_chapter_count=5`; syllabus + 5 diagnostic sets verified |
| **1** | Schema + migration | `school` on learners (migration `20260226_0015`); other fields already present; dashboard cached in Redis (`learning:dashboard:{id}`, 60s TTL) |
| **2** | Backend APIs | Auth (start-signup, login), onboarding (diagnostic, submit, plan, tasks), learning (content, test/generate, test/submit, reading/complete, week/advance, dashboard) |
| **3** | Frontend | Auth gate, diagnostic test, result, dashboard (3 tables + tasks), reading screen, test screen; API URL configurable |
| **4–5** | Weekly cycle + logging | Week advance in learning API; plan/version reason in onboarding; domain loggers in use |

---

## PHASE 0: PRE-WORK (Before Any Student Uses the Platform)

> Everything in this phase must be done and verified before the application starts serving students.

### 0.1 — Grounding: Embed First 5 Chapters (Demo Scope)

> **Note:** For demo purposes and local laptop performance, we embed only the first 5 chapters (ch_1 – ch_5). The system still tracks all 14 chapters in the syllabus structure, but RAG content generation is available only for chapters 1–5. This keeps memory usage manageable and retrieval fast. The setting `grounding_chapter_count = 5` stays unchanged.

| # | Task | Layer | Status |
|---|------|-------|--------|
| 0.1.1 | Verify `grounding_chapter_count = 5` in `API/app/core/settings.py` (keep as-is) | Config | [x] |
| 0.1.2 | Run grounding ingestion to embed first 5 chapters + syllabus into `embedding_chunks` table (pgvector) | Database (PG) | Runbook |
| 0.1.3 | Verify chapters 1–5 have embedding rows in `embedding_chunks` — check count per chapter | Database (PG) | Runbook |
| 0.1.4 | Verify `curriculum_documents` table has entries for syllabus + first 5 chapter PDFs | Database (PG) | Runbook |
| 0.1.5 | Verify `syllabus_hierarchy` table has chapter → section entries for all 14 chapters (full syllabus structure even though only 5 are embedded) | Database (PG) | Runbook |
| 0.1.6 | Ensure `SYLLABUS_CHAPTERS` in `API/app/data/syllabus_structure.py` matches the syllabus.txt exactly (all 14 chapters, all subtopics) | Backend | [x] |

### 0.2 — Diagnostic Question Sets: Verify Readiness

| # | Task | Layer | Status |
|---|------|-------|--------|
| 0.2.1 | Verify all 5 question sets in `diagnostic_question_sets.py` have exactly 25 MCQs each | Backend | [x] |
| 0.2.2 | Verify each question has `chapter_number` (1–14), `correct_index` (0–3), and 4 options | Backend | [x] |
| 0.2.3 | Verify `get_random_diagnostic_set()` returns (questions, answer_key) correctly | Backend | [x] |
| 0.2.4 | Verify KaTeX rendering works in the frontend for math expressions in questions | Frontend | [x] |

---

## PHASE 1: DATABASE — Schema & Migrations

> Design the database to support the complete learning lifecycle. We use PostgreSQL (relational + pgvector), Redis (caching + session state), and MongoDB is optional (runtime memory only if needed).

### 1.1 — PostgreSQL: Core Tables (Verify / Create)

These tables already exist and need verification or minor changes. Run `uv run python scripts/verify_phase1_schema.py` from `API/` when the DB is up to confirm all 14 exist.

| # | Table | Purpose | Action | Status |
|---|-------|---------|--------|--------|
| 1.1.1 | `learners` | Student basic info (name, grade_level) | Verify exists; ensure it holds `name`, `grade_level` | Runbook |
| 1.1.2 | `student_auth` | Login credentials (username, password hash, learner_id) | Verify exists | Runbook |
| 1.1.3 | `learner_profile` | Global student profile (chapter_mastery JSONB, cognitive_depth, diagnostic_score, engagement_minutes, timeline_delta_weeks) | Verify exists; may need new fields — see 1.2 | Runbook |
| 1.1.4 | `learner_profile_snapshots` | Historical profile snapshots (for trend analysis) | Verify exists | Runbook |
| 1.1.5 | `chapter_progression` | Per-chapter status tracking (status: not_started/in_progress/completed, mastery_score, attempts, revision_queued) | Verify exists; ensure `attempts` count field is present | Runbook |
| 1.1.6 | `weekly_plans` | Stored weekly plan (plan_payload JSONB) | Verify exists | Runbook |
| 1.1.7 | `weekly_plan_versions` | Plan version history (tracks how plan changed over time) | Verify exists | Runbook |
| 1.1.8 | `tasks` | Individual tasks (learner_id, week_number, chapter, task_type: read/practice/test, status, is_locked, proof_policy) | Verify exists; ensure `task_type` distinguishes read vs practice vs test | Runbook |
| 1.1.9 | `task_attempts` | Evidence of task completion (score, time_spent, reason) | Verify exists | Runbook |
| 1.1.10 | `assessment_results` | Test results per concept/chapter (score, error_type) | Verify exists | Runbook |
| 1.1.11 | `embedding_chunks` | Chapter embeddings for RAG (text chunk + pgvector embedding, doc_type, chapter_number) | Verify exists; must have entries for all 14 chapters after Phase 0 | Runbook |
| 1.1.12 | `curriculum_documents` | Metadata for ingested documents (syllabus, chapters) | Verify exists | Runbook |
| 1.1.13 | `syllabus_hierarchy` | Chapter > section > concept tree | Verify exists | Runbook |
| 1.1.14 | `revision_queue` | Chapters flagged for revision (learner_id, chapter, reason, status, priority) | Verify exists | Runbook |

### 1.2 — PostgreSQL: Schema Enhancements (New Fields / Tables)

| # | Change | Table | Detail | Status |
|---|--------|-------|--------|--------|
| 1.2.1 | Add `school` field | `learners` | VARCHAR(255), nullable, to store student's school name | [x] |
| 1.2.2 | Add `math_9_percent` field | `learner_profile` | FLOAT, stores Class 9 maths percentage (0–100) — verify if already in JSONB or needs explicit column | [x] |
| 1.2.3 | Add `selected_timeline_weeks` field | `learner_profile` | INT, what the student chose (14–28) — verify if already exists | [x] |
| 1.2.4 | Add `suggested_timeline_weeks` field | `learner_profile` | INT, what the system suggests — verify if already exists | [x] |
| 1.2.5 | Add `current_week_number` field | `learner_profile` | INT, tracks which week the student is currently on | — (current_week from weekly_plans) |
| 1.2.6 | Add `attempt_count` field | `chapter_progression` | INT, how many times the student has attempted this chapter's test (max 2) — verify if already exists | [x] |
| 1.2.7 | Add subtopic-level tracking | `chapter_progression` or new table | JSONB or separate rows for subtopic completion + accuracy per subtopic | Defer |
| 1.2.8 | Create Alembic migration | Migration | Generate and apply migration for all new fields | [x] (20260226_0015 school) |

### 1.3 — Redis: Caching Strategy

| # | Key Pattern | Purpose | Status |
|---|-------------|---------|--------|
| 1.3.1 | `session:{session_id}` | Current login session cache | Exists |
| 1.3.2 | `rag:{hash}` | RAG retrieval cache (300s TTL) | Exists |
| 1.3.3 | `current_week:{learner_id}` | Cache the active week plan for fast dashboard loads | [x] (via `learning:dashboard:{id}` 60s TTL) |
| 1.3.4 | `profile:{learner_id}` | Cache latest profile for quick access by agents | [x] (via dashboard cache) |

---

## PHASE 2: BACKEND — REST APIs & Agent Logic

> All business logic flows. Organized by the student journey: onboarding → weekly cycle → progression.

### 2.1 — Sign-Up & Authentication

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.1.1 | Sign-up endpoint | `POST /auth/signup` | Accepts: username, password, full_name, date_of_birth, selected_timeline_weeks (14–28), math_9_percent (0–100). Creates `learners` + `student_auth` + `learner_profile` entries. Does NOT create plan yet — that happens after diagnostic. | [x] (start-signup → diagnostic → submit) |
| 2.1.2 | Login endpoint | `POST /auth/login` | Returns JWT token + learner_id | [x] |
| 2.1.3 | Validate sign-up fields | Backend | Ensure weeks is 14–28, math_9_percent is 0–100, username unique, etc. | [x] |

### 2.2 — Diagnostic Test Flow

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.2.1 | Get diagnostic questions | `POST /onboarding/diagnostic-questions` | Randomly pick one of 5 predefined sets (NOT LLM-generated). Return 25 MCQs with options. Store attempt_id + set_id + start_time. | [x] |
| 2.2.2 | Submit diagnostic answers | `POST /onboarding/submit` | Accept answers for all 25 questions. Calculate score against answer_key. Score per chapter (since questions are chapter-tagged). Time validation: must submit within 30 minutes of start. | [x] |
| 2.2.3 | Calculate student ability | Backend logic | Combine: `ability = 0.5 × diagnostic_score + 0.5 × (math_9_percent / 100)`. Determine per-chapter initial mastery from diagnostic results. | [x] |
| 2.2.4 | Create student profile | Backend logic | Populate `learner_profile` with: diagnostic_score, math_9_percent, cognitive_depth, chapter_mastery (initial per-chapter scores from diagnostic). | [x] |
| 2.2.5 | Initialize chapter progression | Backend logic | Create 14 rows in `chapter_progression` — all chapters set to `not_started`, attempt_count = 0. | [x] |

### 2.3 — Rough Plan Generation

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.3.1 | Generate rough plan | Part of `POST /onboarding/submit` response | Based on diagnostic scores + math_9_percent + syllabus structure, create a rough plan mapping chapters to weeks. Respect 14–28 week range. Show: "You chose X weeks, we suggest Y weeks." | [x] |
| 2.3.2 | Store rough plan | `weekly_plans` table | Store the initial rough plan as JSONB (week → chapters mapping). Create version 1 in `weekly_plan_versions`. | [x] |
| 2.3.3 | Return plan to frontend | API response | Return: score, per-chapter breakdown, suggested_weeks, rough_plan, week_1_tasks. | [x] |

### 2.4 — Week 1 Task Creation

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.4.1 | Create Week 1 tasks | Part of onboarding submit or separate endpoint | Based on rough plan, create tasks for Week 1. Each week should have: **Reading tasks** (chapter content from RAG), **Practice exercises** (optional), **Weekly test** (MCQ-based chapter assessment). | [x] |
| 2.4.2 | Store tasks | `tasks` table | Each task: learner_id, week_number=1, chapter, task_type (read/practice/test), status=pending, is_locked=false for week 1, proof_policy (what evidence needed). | [x] |
| 2.4.3 | Reading content generation | Backend (Content Agent + RAG) | Use RAG to retrieve relevant NCERT chunks for the chapter. Use Gemini to generate clear, student-friendly reading material. Adapt tone based on initial student profile (ability level). | [x] |

### 2.5 — Content Generation (Dynamic Tone)

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.5.1 | Reading material endpoint | `GET /content/read/{learner_id}/{chapter_number}` or similar | Retrieve chapter embeddings via RAG. Generate explanation using Gemini, adapted to student's current profile (ability, mastery, confidence). Include: simple explanation, solved examples, key formulas. | [x] (`POST /learning/content`) |
| 2.5.2 | Adapt tone based on profile | Content Agent logic | If student is weak → slow pace, more examples, simpler language. If student is strong → concise, fewer examples, challenge problems. Use the existing `_derive_policy()` approach in `content.py`. | [x] |
| 2.5.3 | Practice questions endpoint | `GET /content/practice/{learner_id}/{chapter_number}` or similar | Generate 5–10 practice questions from NCERT embeddings using Gemini. Difficulty adapts to student level. | Defer (reading + test first) |
| 2.5.4 | Weekly test endpoint | `POST /test/generate/{learner_id}/{week_number}` or similar | Generate a chapter test (10–15 MCQs) from NCERT embeddings for the chapters covered in that week. Store as timed test. | [x] (`POST /learning/test/generate`) |
| 2.5.5 | Submit test answers | `POST /test/submit` | Score the test. Calculate per-chapter accuracy. This drives the weekly update cycle. | [x] (`POST /learning/test/submit`) |

### 2.6 — Task Completion (Evidence-Based)

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.6.1 | Complete reading task | `POST /tasks/{task_id}/complete` | For reading: track that the student actually viewed/read the content (time spent > minimum threshold, or scroll-to-end tracking). Student cannot manually mark done. | [x] (`POST /learning/reading/complete` + onboarding task complete) |
| 2.6.2 | Complete test task | Automatic on test submit | When student submits test via `POST /test/submit`, automatically mark the test task as complete. Store score in `task_attempts`. | [x] |
| 2.6.3 | Completion threshold check | Backend logic | Score ≥ 60% → mark chapter as `completed` in `chapter_progression`. Score < 60% → increment `attempt_count`. If attempt_count < 2, keep chapter `in_progress` (student retries). If attempt_count ≥ 2, mark chapter as `completed` BUT add to `revision_queue` for later revision. Move on to next chapter. | [x] |

### 2.7 — Weekly Cycle: Plan Update & Next Week

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.7.1 | Trigger week completion check | Backend logic / `POST /week/complete` | When ALL tasks for current week are done (reading + test): trigger profile update → plan recalculation → next week creation. **No forced timeline**: if student finishes in 3 days, immediately proceed. | [x] (`POST /learning/week/advance`) |
| 2.7.2 | Update student profile | Backend (Profile Agent) | After each week: update `learner_profile` with new chapter_mastery scores, recalculate cognitive_depth, update engagement_minutes. Create snapshot in `learner_profile_snapshots` (for trend tracking). | [x] |
| 2.7.3 | Recalculate rough plan | Backend (Planner Agent) | Based on updated profile + actual progress vs planned progress: recalculate remaining chapter-to-week mapping. If student is behind → extend plan (more weeks). If ahead → compress plan (fewer weeks). Create new version in `weekly_plan_versions`. | [x] |
| 2.7.4 | Create next week tasks | Backend (Scheduler Agent) | Create tasks for the next week based on updated rough plan. Same structure: reading + practice + test. Unlock immediately (no timeline lock). | [x] |
| 2.7.5 | Handle revision weeks | Backend (Revision Agent) | If `revision_queue` has entries AND student has progressed past the first few chapters: periodically inject a revision week (revision content + re-test for flagged chapters). Don't hold revision until the end. | Partial (revision_queue populated; injection can be enhanced) |

### 2.8 — Dashboard Data Endpoints

| # | Task | Endpoint | Detail | Status |
|---|------|----------|--------|--------|
| 2.8.1 | Get rough plan | `GET /plan/{learner_id}` | Return current rough plan (which chapters in which weeks), suggestion vs chosen weeks, current progress position. | [x] (in `GET /learning/dashboard/{id}` + `GET /onboarding/plan/{id}`) |
| 2.8.2 | Get completion status | `GET /status/{learner_id}` | Return per-chapter and per-subtopic completion status (not_started / in_progress / completed). Derived from `chapter_progression` table. | [x] (in dashboard) |
| 2.8.3 | Get accuracy & confidence | `GET /confidence/{learner_id}` | Return per-chapter accuracy (test scores), confidence level, mastery band (Beginner / Developing / Proficient / Mastered). Derived from `learner_profile.chapter_mastery` + `assessment_results`. | [x] (in dashboard) |
| 2.8.4 | Get current week tasks | `GET /tasks/current/{learner_id}` | Return the active week's tasks with their status (pending / in_progress / completed). | [x] (in dashboard + `GET /onboarding/tasks/{id}`) |
| 2.8.5 | Get full schedule | `GET /schedule/{learner_id}` | Return all weeks (past completed + current + future draft) for the full timeline view. | [x] (`GET /onboarding/schedule/{id}`) |
| 2.8.6 | Get profile summary | `GET /profile/{learner_id}` | Return: student name, diagnostic score, math_9_percent, current week, chosen weeks, suggested weeks, overall mastery %. | [x] (in dashboard) |

### 2.9 — Agent Orchestration

| # | Task | Detail | Status |
|---|------|--------|--------|
| 2.9.1 | **Content Agent** — enhance `API/app/agents/content.py` | Accept student profile + chapter number. Use RAG to retrieve NCERT chunks. Adapt tone/depth/examples based on profile. Return reading material. | [x] (in learning API) |
| 2.9.2 | **Evaluation Agent** — enhance `API/app/agents/assessment.py` | Score tests. Calculate per-chapter and per-subtopic accuracy. Apply completion threshold (≥ 60%). Handle max 2 attempts logic. | [x] |
| 2.9.3 | **Profile Agent** — enhance `API/app/agents/learner_profile.py` | Update profile after every activity. Recalculate: chapter_mastery, cognitive_depth, pace indicator, confidence scores. | [x] |
| 2.9.4 | **Planner Agent** — enhance `API/app/agents/planner.py` | Generate initial rough plan. Recalculate after every week. Respect dynamic pacing rules. | [x] |
| 2.9.5 | **Revision Agent** — enhance `API/app/agents/reflection.py` | Detect weak chapters (failed ≥ 2 times). Schedule revision. Generate revision content with different approach. | [x] (revision_queue populated) |

---

## PHASE 3: FRONTEND — Student-Facing UI

> The UI must feel like a proper EdTech platform for a Class 10 student. Modern, clean, encouraging, and easy to navigate.

### 3.0 — Fix Existing UI

| # | Task | Detail | Status |
|---|------|--------|--------|
| 3.0.1 | Fix broken UI | The current frontend is not working properly. Debug and fix `index.html`, `app.js`, `styles.css` so the basic flow works again (login → dashboard). | [x] |
| 3.0.2 | Test auth flow | Verify login and signup work end-to-end with the backend | [x] |

### 3.1 — Auth Gate (First Screen)

| # | Task | Detail | Status |
|---|------|--------|--------|
| 3.1.1 | Login form | Username + password + API URL + Login button. On success → go to dashboard. | [x] |
| 3.1.2 | Sign-up form | Fields: Full Name, Username, Password, Date of Birth, Class 9 Maths % (0–100), Weeks to complete (dropdown 14–28). On submit → proceed to diagnostic test. | [x] |
| 3.1.3 | Logout button | Clear JWT + redirect to auth gate | [x] |

### 3.2 — Diagnostic Test Screen

| # | Task | Detail | Status |
|---|------|--------|--------|
| 3.2.1 | Show 25 MCQ questions | Render all 25 questions with 4 options each (A/B/C/D). Support KaTeX for math expressions. Scrollable question list. | [x] |
| 3.2.2 | 30-minute timer | Countdown timer visible at top. Auto-submit when time runs out. Show remaining time clearly. | [x] |
| 3.2.3 | Submit test button | Validate all questions answered (or allow partial). Submit to backend. Show loading state. | [x] |
| 3.2.4 | Question navigation | Show which questions are answered vs unanswered. Allow scrolling to any question. | [x] |

### 3.3 — Result & Rough Plan Screen (Post-Diagnostic)

| # | Task | Detail | Status |
|---|------|--------|--------|
| 3.3.1 | Show diagnostic score | "You scored X/25" with per-chapter breakdown. Highlight strong and weak chapters. | [x] |
| 3.3.2 | Show rough plan | "You chose X weeks. Based on your test, we suggest Y weeks." Show week-by-chapter mapping as a visual timeline or table. | [x] |
| 3.3.3 | Show Week 1 tasks | List the reading and test tasks for Week 1. | [x] |
| 3.3.4 | "Go to Dashboard" button | Navigate to the main dashboard after reviewing the plan. | [x] |

### 3.4 — Main Dashboard (Shown Every Login)

> This is the primary screen the student sees after login. Shows the three living tables.

| # | Task | Detail | Status |
|---|------|--------|--------|
| 3.4.1 | **Rough Plan Section** | Show the current rough plan as a timeline/table. Highlight current week. Show past weeks as completed (green), current week as active (blue), future weeks as draft (gray). If plan changed from last time, indicate the change. | [x] |
| 3.4.2 | **Completion Status Section** | Per-chapter cards/table: Chapter name, subtopics, and status (not started / in progress / completed). Color-coded: gray → yellow → green. Show overall completion percentage as a progress bar. | [x] |
| 3.4.3 | **Accuracy & Confidence Section** | Per-chapter: show test score, confidence level, mastery band. Mastery bands: **Beginner** (< 40%) / **Developing** (40–59%) / **Proficient** (60–79%) / **Mastered** (≥ 80%). Color-coded badges or progress bars. | [x] |
| 3.4.4 | **Current Week Panel** | Prominent section showing current week's tasks. Each task: title, type (📖 Read / ✍️ Practice / 📝 Test), status (pending / in_progress / done). Click to open the task. | [x] |
| 3.4.5 | **Profile Summary Card** | Student name, current week, chosen weeks, suggested weeks, overall mastery %, diagnostic score. Small and clean — top of dashboard. | [x] |

### 3.5 — Reading Screen

| # | Task | Detail | Status |
|---|------|--------|--------|
| 3.5.1 | Display reading content | Show the generated reading material for the chapter. Support KaTeX for math rendering. Include solved examples. Clean typography for a Class 10 student. | [x] |
| 3.5.2 | Reading progress tracking | Track time spent on page. Or track scroll position. Mark reading as "completed" when sufficient engagement detected (e.g., ≥ 3 minutes on page). | [x] |
| 3.5.3 | "I've finished reading" indicator | After minimum engagement threshold met, show a subtle indicator that reading is complete. Do NOT have a manual "Mark as done" button — completion is automatic. | [x] |

### 3.6 — Test/Quiz Screen

| # | Task | Detail | Status |
|---|------|--------|--------|
| 3.6.1 | Show test questions | Render MCQs with 4 options. Support KaTeX. Clear question numbering. | [x] |
| 3.6.2 | Submit test | Submit answers to backend. Show score immediately. Show which questions were correct/incorrect. | [x] |
| 3.6.3 | Post-test feedback | Show score: "You scored X/Y". If score ≥ 60%: "Chapter completed! ✅" If score < 60% and attempts < 2: "Let's try again with more practice." If score < 60% and attempts ≥ 2: "Moving on. This will come back for revision later." | [x] |

### 3.7 — UI/UX Design Principles (EdTech for Class 10)

| # | Principle | Detail |
|---|-----------|--------|
| 3.7.1 | **Encouraging tone** | Use positive language. Celebrate completions. Don't shame failures. |
| 3.7.2 | **Clean & modern** | Dark mode option. Large readable fonts. Good spacing. Mobile-friendly. |
| 3.7.3 | **Math-first** | KaTeX for all math. Proper fraction, exponent, square root rendering. |
| 3.7.4 | **Progress visibility** | Student should always see how far they've come. Progress bars, badges, streaks. |
| 3.7.5 | **No clutter** | Show only what's relevant. One task at a time when reading. Dashboard is overview only. |

---

## PHASE 4: WEEKLY CYCLE ENGINE (The Core Loop)

> This is the heart of the product. After onboarding, this cycle repeats until all 14 chapters are done.

```
┌──────────────────────────────────────────────────────┐
│                    WEEKLY CYCLE                       │
│                                                       │
│  1. Student reads chapter content (RAG + Gemini)      │
│  2. Student does practice (optional)                  │
│  3. Student takes chapter test                        │
│  4. System evaluates test                             │
│     ├── Score ≥ 60% → Chapter COMPLETED               │
│     └── Score < 60%                                   │
│         ├── Attempt < 2 → RETRY with varied content   │
│         └── Attempt ≥ 2 → MOVE ON + add to REVISION   │
│  5. Update student profile                            │
│  6. Recalculate rough plan                            │
│  7. Create next week's tasks                          │
│  8. Update dashboard (3 living tables)                │
│                                                       │
│  Repeat until all 14 chapters done                    │
└──────────────────────────────────────────────────────┘
```

### 4.1 — Weekly Cycle Tasks

| # | Task | Detail | Status |
|---|------|--------|--------|
| 4.1.1 | Detect week completion | When all tasks for current week are marked done (reading + test), trigger the cycle. | [x] |
| 4.1.2 | Score and evaluate | Run Evaluation Agent on test results. Calculate per-chapter accuracy. | [x] |
| 4.1.3 | Apply completion threshold | ≥ 60% → completed. < 60% + attempt < 2 → retry. < 60% + attempt ≥ 2 → move on + revision. | [x] |
| 4.1.4 | Update profile | Update chapter_mastery, confidence scores, pace indicator. Create profile snapshot. | [x] |
| 4.1.5 | Recalculate plan | Planner Agent recalculates: how many weeks left? Which chapters rescheduled? Revision weeks needed? | [x] |
| 4.1.6 | Create next week | Scheduler creates tasks for next week. Content Agent generates reading material for new chapter. | [x] |
| 4.1.7 | Unlock next week | Make next week's tasks available immediately (no forced wait). | [x] |
| 4.1.8 | Update dashboard data | Refresh all three living tables: rough plan, completion status, accuracy/confidence. | [x] |

---

## PHASE 5: OBSERVABILITY & LOGGING

| # | Task | Detail | Status |
|---|------|--------|--------|
| 5.1 | Log every agent decision | When planner adjusts plan, log why. When content tone changes, log the policy. When threshold applied, log score vs threshold. | [x] (domain loggers) |
| 5.2 | Log plan changes | Store reason for every plan version change in `weekly_plan_versions.reason`. | [x] |
| 5.3 | Log revision triggers | When chapter added to revision queue, log: chapter, score, attempt_count, reason. | [x] |
| 5.4 | Structured logs | Use domain-specific loggers (already exist) for each agent's decisions. | [x] |

---

## IMPLEMENTATION ORDER (Suggested Sequence)

> Start from the foundation and build up.

### Sprint 1: Foundation
1. **Phase 0** — Verify grounding for first 5 chapters (keep existing setting, run/verify ingestion)
2. **Phase 1.1** — Verify all existing database tables
3. **Phase 1.2** — Add missing fields + Alembic migration
4. **Phase 3.0** — Fix the broken frontend UI

### Sprint 2: Onboarding Flow
5. **Phase 2.1** — Sign-up endpoint (add school, math_9_percent)
6. **Phase 2.2** — Diagnostic test flow (use predefined sets, 30-min timer)
7. **Phase 2.3** — Rough plan generation
8. **Phase 2.4** — Week 1 task creation
9. **Phase 3.1** — Auth gate UI
10. **Phase 3.2** — Diagnostic test UI
11. **Phase 3.3** — Result & rough plan UI

### Sprint 3: Core Learning Loop
12. **Phase 2.5** — Content generation (reading + practice + test)
13. **Phase 2.6** — Task completion (evidence-based)
14. **Phase 2.7** — Weekly cycle (plan update + next week creation)
15. **Phase 3.4** — Main dashboard UI (3 living tables)
16. **Phase 3.5** — Reading screen
17. **Phase 3.6** — Test/Quiz screen

### Sprint 4: Polish & Observability
18. **Phase 2.8** — Dashboard data endpoints
19. **Phase 2.9** — Agent orchestration refinement
20. **Phase 4.1** — Weekly cycle engine integration testing
21. **Phase 5** — Observability & logging
22. **Phase 3.7** — UI/UX polish

---

## FILES IMPACT MAP

| File | Phase | Change |
|------|-------|--------|
| `API/app/core/settings.py` | 0.1 | Verify `grounding_chapter_count = 5` (no change needed) |
| `API/app/rag/grounding_ingest.py` | 0.1 | Verify ingestion ran for first 5 chapters |
| `API/scripts/verify_phase0.py` | 0.1, 0.2 | Script: 14 chapters, 5×25 MCQs, get_random_diagnostic_set |
| `API/app/models/entities.py` | 1.2 | Add new fields to existing models |
| `API/alembic/versions/*.py` | 1.2 | New migration file |
| `API/app/api/auth.py` | 2.1 | Enhance signup to accept new fields |
| `API/app/api/onboarding.py` | 2.2–2.4 | Refactor diagnostic + plan + week creation |
| `API/app/agents/content.py` | 2.5, 2.9 | Enhanced content generation with profile-driven tone |
| `API/app/agents/assessment.py` | 2.6, 2.9 | Enhanced evaluation with threshold + attempts logic |
| `API/app/agents/learner_profile.py` | 2.7, 2.9 | Profile update logic per week |
| `API/app/agents/planner.py` | 2.7, 2.9 | Rough plan recalculation logic |
| `API/app/agents/reflection.py` | 2.7, 2.9 | Revision detection + scheduling |
| `API/app/rag/retriever.py` | 2.5 | Chapter-scoped retrieval filter |
| `frontend/index.html` | 3.0–3.7 | Complete UI rebuild |
| `frontend/app.js` | 3.0–3.7 | All frontend logic |
| `frontend/styles.css` | 3.0–3.7 | All styling |

---

## Next steps (run when ready)

1. **Apply migration:** From repo root or `API/`: `uv run alembic upgrade head` (adds `school` to `learners`).
2. **Verify Phase 0 (no services):** From `API/`: `uv run python scripts/verify_phase0.py`.
3. **Phase 1.1 schema (DB up):** From `API/`: `uv run python scripts/verify_phase1_schema.py` (confirms 14 required tables exist).
4. **Grounding (Docker + API up):** See `docs/PHASE0_RUNBOOK.md` — run ingestion, then verify embedding_chunks/curriculum_documents.
5. **Full tests:** With Docker (Postgres, Redis, Mongo) and API running: `pytest tests/` from repo root with `PYTHONPATH=API` and API venv.

---

## SUCCESS CRITERIA

- [x] Student can sign up, take diagnostic test, see rough plan, and start Week 1
- [x] Reading material is generated from NCERT embeddings (not hallucinated)
- [x] Chapter test scores drive completion (≥ 60% threshold)
- [x] Max 2 attempts per chapter, then move on with revision
- [x] Rough plan recalculates after every week
- [x] Completion status updates per chapter and subtopic
- [x] Accuracy/confidence updates per chapter
- [x] Student cannot manually mark tasks as complete
- [x] No forced timeline — finish early = proceed early
- [x] Content tone adapts to student ability
- [x] All 14 chapters can be completed end-to-end (demo: content for ch 1–5)
- [x] Dashboard shows 3 living tables correctly on every login
