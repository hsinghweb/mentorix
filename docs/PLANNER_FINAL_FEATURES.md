# Mentorix – Final Features Planner

**Purpose:** Single source of truth for the final product. All work proceeds from this file. We keep refining and completing within this document only.

---

## Status overview

| Area | Status | Notes |
|------|--------|--------|
| Grounding (syllabus + first 5 chapters embeddings) | **Done** | syllabus.txt + ch_1 … ch_5 embedded; stored in PostgreSQL (pgvector). |
| First screen: Login or Sign up | **Done** | Auth gate: login or sign up first; no dashboard until logged in. |
| Sign-up flow (name, DOB, weeks 14–28) | **Done** | Signup: username, password, name, date_of_birth, selected_timeline_weeks (14–28). |
| 25 MCQ test (LLM, Class 9→10 CBSE) | **Done** | POST /onboarding/diagnostic-questions (LLM-generated); submit → score. |
| Result calculation & rough plan | **Done** | On submit: score, recommended weeks, rough plan, “you asked X, we suggest Y”. |
| Initial student profile | **Done** | Profile + ChapterProgression for all 14 chapters on first submit. |
| First week schedule | **Done** | Week 1 tasks created (read/practice/test); locked, evidence-based completion. |
| Schedule visibility & lock-down | **Done** | Week 1 shown; tasks is_locked; no manual mark-done (proof_policy). |

---

## 1. Grounding (done)

- **Syllabus:** `class-10-maths/syllabus/syllabus.txt` — source of truth for course structure (14 chapters + appendices).
- **Embeddings:** Syllabus + first five chapters (`ch_1.pdf` … `ch_5.pdf`) embedded and stored in PostgreSQL (pgvector).
- **Usage:** RAG and planning use this grounded data. No change needed for current scope; we proceed only from this planner.

---

## 2. First screen: Login or Sign up

- When the user opens the web page, the **first thing** they see is:
  - **Login:** username and password (for returning users).
  - **Sign up:** for new users to create an account.
- No generic dashboard or anonymous flow first; the system must know who the user is (logged-in student) before showing anything else.
- Returning user: enters credentials → login → sees their dashboard/plan/schedule.
- New user: chooses Sign up → goes through sign-up flow (below) → then test → rough plan → first week schedule → then can use the app.

---

## 3. Sign-up: initial information

We collect only what we need for onboarding and planning:

- **Student’s name** (simple, required).
- **Date of birth** (required).
- **Weeks to complete the course:** student **must select** a value **between 14 and 28 weeks only**. We do not offer fewer than 14 or more than 28 (to avoid misuse and keep plans realistic).
- After submitting, we do **not** yet show a dashboard; we move to the **25 MCQ test**.

---

## 4. 25 MCQ mathematics test (LLM-generated)

- **When:** Right after sign-up (before any plan or schedule).
- **Count:** Exactly 25 multiple-choice questions.
- **Generation:** The assessment test is generated **based on the student’s Class 9 result in Mathematics** and the **percentage of marks obtained in Class 9** (entered at signup). The prompt includes:
  - We are onboarding a student to prepare for **Class 10 Mathematics** (CBSE, English medium).
  - The **percentage of marks obtained in Class 9 Mathematics** is &lt;value&gt;%. The LLM may adapt difficulty slightly based on this.
  - **Strict format:** Exactly 25 questions; each question is a **multiple-choice question with four options A, B, C, D**; **only one option is correct** per question. The LLM must provide the **correct answer** for each question (as `correct_index` 0–3) so we can build the **answer_key**, compare the student’s answers against it, and give the correct result.
- **Delivery:** Student answers all 25; we compare answers to the answer_key and **calculate the result**.

---

## 5. Result and rough plan

- **Result:** We compute the test score (e.g. correct answers out of 25).
- **Rough plan:** Based on the score, we generate a **rough plan** (e.g. suggested number of weeks, high-level pacing).
- **Message to student:** Show something like: “You asked for X weeks. Based on your test result, this is your rough plan and we suggest you will take Y weeks.” (Y can be between 14–28, possibly different from X based on performance.)
- At this point the student **only sees the rough plan**; we do not yet show a week-by-week schedule. Next step is building the **initial profile** and then the **first week schedule**.

---

## 6. Initial student profile and chapter status

- **Global profile:** Create the student’s **global profile** during onboarding from the assessment result. The global profile includes: **student’s name**, **Class 9 marks** (math_9_percent), **class and course** (e.g. Class 10 Mathematics), and **onboarding assessment result** (diagnostic score). Ability is combined as: `ability = 0.5 * diagnostic_score + 0.5 * (math_9_percent/100)`; this drives `cognitive_depth` and the initial plan. We store `onboarding_diagnostic_score` on the profile and in snapshots. The same profile is **updated over time** (e.g. after study sessions, weekly replan, task completion) so we keep refining the student’s profile for future use.
- **Chapter status:** Start a **status structure for all 14 chapters** (as in syllabus.txt). We do not mark any chapter complete yet; we only initialize the tracking (e.g. not started / in progress / completed) so we can update it as the student progresses.
- This profile and status are used for:
  - Deciding the rough plan (and later, weekly schedules).
  - Creating the **first week schedule**.
  - Future evidence-based completion (read content + pass test → then mark done).

---

## 7. First week schedule

- **What:** We create and assign the **very first week’s schedule** for the student.
- **Content:** We follow **chapter order** (chapter 1 first, then next as per syllabus). We assign content to **read** (and later, tests) based on:
  - Syllabus structure (syllabus.txt).
  - Our understanding of the **student profile** (ability, logical/mathematical from the test).
- **Visibility:** The schedule for **week 1** is **reflected on the page** so the student clearly sees what is scheduled for week one.
- **Rules:**
  - Student **cannot** change the schedule.
  - Student **cannot** skip tasks or mark something complete from his side.
  - Completion is **evidence-based only:** the student must **actually read** the given content and **complete** the given test; only then will that task be marked done (no manual tick/checkbox to mark done without evidence).

---

## 8. Agents (planning)

We will need multiple agents to implement the above flow. Current plan:

| # | Agent / responsibility | Purpose |
|---|------------------------|--------|
| 1 | **Onboarding** | Collect sign-up info (name, DOB, weeks 14–28); orchestrate “new student” flow. |
| 2 | **Test creation** | Generate 25 MCQ mathematics questions using LLM (Class 9 passed, Class 10 CBSE, syllabus-aware). |
| 3 | **Result / scoring** | Check answers and compute test result (score). |
| 4 | **Profile** | Create initial student profile (ability, logical, mathematical); initialize status for all 14 chapters. |
| 5 | **Rough plan** | Generate rough plan and suggested weeks from profile and score; show “you asked X, we suggest Y” and rough plan. |
| 6 | **First week schedule** | Create and assign the very first week schedule (content to read, chapter order, profile-aware); persist and show on the page. |

Refinements (e.g. merging or splitting agents) will be updated in this section as we proceed.

---

## 9. Flow summary (end-to-end)

1. User opens app → **Login** or **Sign up**.
2. **Sign up:** Name, DOB, weeks (14–28) → submit.
3. **25 MCQ test** (LLM-generated, Class 9→10 CBSE, syllabus.txt) → student submits answers.
4. **Result** calculated → **initial profile** created (ability, logical, mathematical; 14-chapter status initialized).
5. **Rough plan** generated and shown (“you asked X weeks; we suggest Y weeks” + rough plan).
6. **First week schedule** created and shown (content to read, chapter order; evidence-based completion only; student cannot change/skip/mark done without evidence).
7. Student sees week 1 on the page and can start reading and completing tasks; only when they complete content + test will tasks be marked done.

---

## 10. Refinements and next steps

- **Refinements:** Any change to scope, flow, or agents will be noted here.
- **Next steps:** We will proceed only from this planner and keep updating this file as we implement and refine.

### Implementation summary (completed)

- **Backend:** `StudentAuth` model + migration; `POST /auth/signup`, `POST /auth/login` (JWT); `POST /onboarding/diagnostic-questions` (25 LLM MCQs); submit creates profile, 14-chapter status, rough plan, week 1 schedule. Tasks are locked; completion is evidence-based.
- **Frontend:** First screen = auth gate (Login | Sign up). Sign up → 25 MCQ test → result + rough plan + Week 1 → “Go to my dashboard”. Logout clears session. Learner ID and API base stored in localStorage and applied in app.
- **How to run and test:** Start stack (`docker compose up -d`). Open frontend (e.g. http://localhost:5500). If DB was already at schema 20260222_0011, run `alembic stamp 20260222_0011` then `alembic upgrade head` once to add `student_auth`. New deployments run `alembic upgrade head` from scratch. Ensure LLM (e.g. Gemini) is configured for diagnostic question generation.

### Run when ready (after stack is up)

| Step | Command / reference |
|------|----------------------|
| 1. Migration | From `API/`: `uv run alembic upgrade head` |
| 2. Phase 0 (no DB) | From `API/`: `uv run python scripts/verify_phase0.py` |
| 3. Phase 1.1 schema | From `API/`: `uv run python scripts/verify_phase1_schema.py` |
| 4. Grounding | `docs/PHASE0_RUNBOOK.md` — ingest + verify embedding_chunks |
| 5. Full tests | From repo root: `$env:PYTHONPATH="API"; uv run pytest tests/` |
