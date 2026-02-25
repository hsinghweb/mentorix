# Mentorix: Syllabus-Driven Plan & Student Onboarding

**Purpose:** Ground the platform on the Class 10 Maths syllabus, use it for planning and status, add login-first UI and a clear signup → test → plan flow. This doc is the single reference for (1) syllabus usage, (2) chapter embeddings setup, and (3) student onboarding — to be done before onboarding any student.

---

## 1. Canonical Files (Your Paths)

| Role | Path | Description |
|------|------|-------------|
| **Syllabus (source of truth)** | `class-10-maths/syllabus/syllabus.txt` | Full course: 14 chapters + appendices. Used for plan structure and student status. |
| **Chapter PDFs for embeddings (demo)** | `class-10-maths/chapters/ch_1.pdf` … `ch_5.pdf` | First five chapters for demo. Config: `GROUNDING_CHAPTER_COUNT=5`. |

- **Syllabus:** Defines chapters and sections (e.g. `1. Real Numbers`, `1.1 Introduction`, `1.2 The Fundamental Theorem of Arithmetic`). No code change needed for other courses — only this file and the PDFs.
- **Chapter PDFs:** Ingested into the vector store and used to generate course content for the student. For demo, the first **five** chapters (`ch_1.pdf` … `ch_5.pdf`) are used; no need to embed all 14 to avoid long load times on a local machine.

---

## 2. Using syllabus.txt

### 2.1 What syllabus.txt Represents

- **Chapters:** Lines like `1. Real Numbers`, `2. Polynomials`, … `14. Probability`, plus `Appendix A1`, `A2`.
- **Sections:** Lines like `1.1 Introduction`, `1.2 The Fundamental Theorem of Arithmetic`, `3.3.1 Substitution Method`, etc.

The existing ingestion in `API/app/rag/grounding_ingest.py` parses this format and builds a **syllabus hierarchy** (chapter → section → concept) in the DB. That hierarchy is used for:

1. **Planning** — What to do and in what order (chapter/section sequence).
2. **Student status** — Per chapter and per section: completed / not completed, and later confidence, accuracy, level.
3. **End view** — How much of the course is done, what’s left, weak areas, timeline vs goal.

### 2.2 Mapping Student Status to the Syllabus

- **Grain:** One status record per **section** (and optionally per chapter aggregate).
- **Fields to capture (per section, and rolled up per chapter):**
  - **Completion:** completed / not completed (evidence-based: read + test, no manual tick).
  - **Confidence:** e.g. 0–1 or band (weak / okay / strong).
  - **Accuracy / level:** from test/answer correctness and difficulty.
- **Storage:** Either extend existing `LearnerProfile` / profile snapshots with a structure keyed by `(chapter_number, section_id or section_title)` or add a small `syllabus_progress` table with `learner_id`, `chapter_number`, `section_ref`, `completed`, `confidence`, `accuracy`, `last_updated`.
- **Pre-work:** Before any student onboarding, the syllabus must be **ingested once** so that the hierarchy exists in the DB. Then all plans and status are expressed in terms of this hierarchy.

### 2.3 Flow

1. **One-time:** Ingest `syllabus.txt` (see Section 3 below). This populates `curriculum_documents` + `syllabus_hierarchy` (and optionally `embedding_chunks` for syllabus if you want syllabus in retrieval).
2. **Per student:** When creating a plan, the backend reads the syllabus hierarchy and builds a week-by-week plan (sections/chapters in order). As the student completes sections, update status for that section/chapter.
3. **APIs:** “Where I stand” and “Plan” responses should return data keyed by chapter/section as in syllabus.txt (e.g. chapter 1, sections 1.1–1.4).

---

## 3. Creating and Storing Embeddings for ch_1.pdf

### 3.1 File Layout

Ensure this structure exists under the repo root:

```
class-10-maths/
  syllabus/
    syllabus.txt
  chapters/
    ch_1.pdf
```

(Optional for later: `ch_2.pdf`, `ch_3.pdf` in `chapters/`.)

### 3.2 Configuration for syllabus.txt + ch_1.pdf

Use **syllabus.txt** and the **first five chapters** for the demo:

- In `CONFIG/local.env` (or the env you use when running the API), set:

```env
GROUNDING_DATA_DIR=class-10-maths
GROUNDING_SYLLABUS_RELATIVE_PATH=syllabus/syllabus.txt
GROUNDING_CHAPTERS_DIR=chapters
GROUNDING_CHAPTER_COUNT=5
```

- So:
  - Syllabus path = `class-10-maths/syllabus/syllabus.txt`
  - Chapters path = `class-10-maths/chapters/`
  - The first five chapter PDFs are ingested: `ch_1.pdf`, `ch_2.pdf`, `ch_3.pdf`, `ch_4.pdf`, `ch_5.pdf` (ingestion picks `ch_*.pdf` in order and takes the first `GROUNDING_CHAPTER_COUNT`).

### 3.3 Run Ingestion

1. Start the stack (Postgres + pgvector, API, etc.).
2. Trigger ingestion (e.g. from repo root):

   ```bash
   curl -X POST "http://localhost:8000/grounding/ingest?force_rebuild=false"
   ```

   Use `force_rebuild=true` only if you want to re-embed everything from scratch.

3. Verify:

   ```bash
   curl "http://localhost:8000/grounding/status"
   ```

   You should see no missing paths and no missing embeddings for:
   - `.../class-10-maths/syllabus/syllabus.txt`
   - `.../class-10-maths/chapters/ch_1.pdf` … `ch_5.pdf`

#### Generating embeddings for the first five chapters (without redoing syllabus and ch_1)

Ingestion is **incremental**: documents that are already in the DB with the same content hash are **skipped** (not re-embedded) when you run ingest again with `force_rebuild=false`.

1. **Ensure PDFs exist** in `class-10-maths/chapters/`: `ch_1.pdf`, `ch_2.pdf`, `ch_3.pdf`, `ch_4.pdf`, `ch_5.pdf`. (You may already have `ch_1.pdf` and `syllabus.txt` from earlier.)
2. **Config:** `GROUNDING_CHAPTER_COUNT=5` in `CONFIG/local.env` (already set for demo).
3. **Run ingest once** (before or after starting the system):
   ```bash
   curl -X POST "http://localhost:8000/grounding/ingest?force_rebuild=false"
   ```
   - Syllabus and ch_1 that were embedded earlier will be reported as `skipped_unchanged`.
   - ch_2, ch_3, ch_4, ch_5 will be embedded if the files exist; missing files are reported as `missing_file`.
4. **Optional – run before starting the system:** Start Postgres (and any dependencies), run the API, call the ingest endpoint above, then use the app. Or run ingest after the stack is up; no need to restart the API after ingestion.

Do **not** use `force_rebuild=true` unless you want to re-embed everything (syllabus + all five chapters) from scratch.

### 3.4 Where Embeddings Are Stored

- **Backend:** pgvector (see `API/app/core/settings.py`: `VECTOR_BACKEND=pgvector`).
- **Tables:** `curriculum_documents` (one row per document), `embedding_chunks` (one row per text chunk with `embedding` vector). Optionally `syllabus_hierarchy` is filled from the parsed syllabus/chapter content.
- **Usage:** RAG retrieval uses these embeddings to find relevant chunks for the student’s current topic; those chunks drive course content generation.

### 3.5 Adding More Chapters Later (e.g. up to 14)

- Add more PDFs under `class-10-maths/chapters/` (e.g. `ch_6.pdf` … `ch_14.pdf`).
- Set `GROUNDING_CHAPTER_COUNT=14` (or the desired number) and run the same ingest again with `force_rebuild=false`. New documents will be embedded; existing ones (syllabus + ch_1 … ch_5) are skipped unless their content changed or you use `force_rebuild=true`.

---

## 4. Student Onboarding (Sign Up & Login-First UI)

### 4.1 First Screen: Login or Sign Up

- **First page** when a user opens the app: only **username** and **password** (and a way to switch to “Sign up”).
- **Returning user:** Enters username + password → login → sees their dashboard/plan/status.
- **New user:** Clicks “Sign up” → goes through signup flow → then test → then plan → then proceeds into the app.

No fixed “generic” dashboard first — the system must know who the user is (logged in) before showing anything else.

### 4.2 Sign-Up Inputs

Collect:

- **Name** (or display name)
- **Password** (with confirmation; store hashed)
- **Date of birth**
- **Timeline to complete the course:** a single choice in the range **14–28 weeks** (no free-form or “no timeline” option, to avoid misuse).

### 4.3 Post–Sign-Up: Diagnostic Test

- After sign-up (and before showing the main plan), the student takes a **diagnostic test**.
- **Format:** e.g. **25 multiple-choice questions**.
- **Content:** Basic maths and logic suitable for **Class 10 CBSE, English medium**, assuming the student has just completed Class 9. Aligned with the scope of `syllabus.txt` (no out-of-syllabus or higher-grade content).
- **Generation:** Use the LLM to generate MCQs, with strict constraints so that questions stay within Class 10 level and syllabus.

### 4.4 After the Test: Marks and Suggested Plan

- **Evaluate:** Compute marks (e.g. correct answers / 25).
- **Recommend timeline:** From the student’s **score**, derive a **recommended number of weeks** (e.g. “We suggest you take 20 weeks”).
  - Better performance → can suggest fewer weeks (e.g. down to 14).
  - Weaker performance → suggest more weeks (e.g. up to 28).
- **Rough plan:** Build a first **rough plan** from the syllabus (chapter/section order) and the **recommended** timeline (and optionally the student’s **selected** timeline). Show the student: “You chose X weeks; based on your test we suggest Y weeks. Your plan is built for Y weeks.”
- **Later:** In subsequent weeks, if the student performs better, the system can suggest reducing the timeline (e.g. “You can aim to finish in fewer weeks”).

### 4.5 What Must Exist Before Onboarding

- **Syllabus:** Ingested from `class-10-maths/syllabus/syllabus.txt` (hierarchy in DB).
- **At least one chapter embedded:** `class-10-maths/chapters/ch_1.pdf` ingested and embeddings stored.
- **Auth:** User/student table with username (unique), hashed password, name, date of birth; and a way to login (username + password) and to create a new account (sign up).
- **Diagnostic:** Endpoint or flow that generates 25 MCQs (LLM, constrained), records answers, returns marks and recommended timeline, then creates the rough plan from the syllabus.

---

## 5. Implementation Order (Summary)

1. **Syllabus and embeddings (pre-work)**  
   - Set env to use `syllabus/syllabus.txt` and `chapters/ch_1.pdf`.  
   - Run grounding ingest.  
   - Confirm `grounding/status` is green for both files.

2. **Auth and first screen**  
   - Implement login (username + password) and sign-up (name, password, DOB, timeline 14–28 weeks).  
   - First page = login; from there, sign up or proceed when logged in.

3. **Status model from syllabus**  
   - Add or align schema so that progress is stored per chapter/section as in syllabus.txt.  
   - Plan and “where I stand” APIs use this structure.

4. **Diagnostic test**  
   - 25 MCQs, LLM-generated, Class 10 CBSE scope.  
   - Score → recommended weeks → rough plan from syllabus.  
   - After test, show suggested timeline and plan, then let student proceed.

5. **Rough plan API**  
   - Input: recommended (or selected) weeks + syllabus hierarchy.  
   - Output: week-by-week rough plan (chapters/sections).  
   - Optionally persist as the student’s initial plan.

Once this is in place, you can add more chapter PDFs (ch_2, ch_3) and expand the plan/status logic without changing the onboarding or syllabus structure.
