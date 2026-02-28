# Phase 0 Runbook — Pre-work Verification

Use this before serving students. For **demo scope** we embed only the **first 5 chapters**; the syllabus still tracks all 14.

## 0.1 Grounding (First 5 Chapters)

### 0.1.1 Config
- **File:** `API/app/core/settings.py`
- **Check:** `grounding_chapter_count = 5` (do not change for demo).
- **Result:** ✅ Verified in code.

### 0.1.2 Run ingestion
With Docker stack and API running:
```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/grounding/status"
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/grounding/ingest"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/grounding/status"
```
Or set `grounding_prepare_on_start: true` in env so ingestion runs on API startup.

### 0.1.3 Verify embedding_chunks
In PostgreSQL:
```sql
SELECT chapter_number, COUNT(*) FROM embedding_chunks GROUP BY chapter_number ORDER BY 1;
```
Expect rows for chapters 1–5 (and optionally syllabus). For demo, chapters 1–5 are sufficient.

### 0.1.4 Verify curriculum_documents
```sql
SELECT id, doc_type, source_path FROM curriculum_documents;
```
Expect syllabus + first 5 chapter PDFs.

### 0.1.5 Verify syllabus_hierarchy
```sql
SELECT COUNT(*) FROM syllabus_hierarchy;
```
Expect entries for all 14 chapters (full syllabus structure).

### 0.1.6 Syllabus structure (backend)
- **File:** `API/app/data/syllabus_structure.py`
- **Check:** `SYLLABUS_CHAPTERS` has 14 chapters and subtopics matching `class-10-maths/syllabus/syllabus.txt`.
- **Result:** ✅ Matches syllabus.txt (all 14 chapters + subtopics).
- **Script:** From `API/` run: `uv run python scripts/verify_phase0.py` to verify syllabus + diagnostic sets in one go.

---

## 0.2 Diagnostic Question Sets

### 0.2.1–0.2.2 Sets and format
- **File:** `API/app/data/diagnostic_question_sets.py`
- **Check:** All 5 sets (`SET_1`–`SET_5`) have exactly 25 MCQs each; each question has `chapter_number` (1–14), `correct_index` (0–3), and 4 options.
- **Result:** ✅ Verified in code.

### 0.2.3 get_random_diagnostic_set()
- Returns `(questions, answer_key)`; used by `POST /onboarding/diagnostic-questions`.
- **Result:** ✅ Implemented and used.

### 0.2.4 KaTeX in frontend
- Diagnostic and test screens use `renderMathInElement` with `\\( \\)` and `\\[ \\]` delimiters.
- **Result:** ✅ KaTeX loaded and used in `frontend/index.html` and `app.js`.

---

## API URL (Frontend)

If the API is not at `http://localhost:8000` (e.g. different host/port in Docker), set **API URL** on the Login or Sign up form before submitting. The value is stored and used for all subsequent requests.
