# Onboarding a New Course (Extensibility)

You can add a **new subject or class** (e.g. Class 9 Maths, Class 10 Science) without changing application code. The same planning, progress, and profiling pipeline runs; only the syllabus and PDF data change.

---

## 1. Directory layout

Create a course directory at the **repository root** (same level as `class-10-maths`). Required structure:

```
<course-dir>/
├── syllabus/
│   ├── syllabus.txt    # Preferred: chapter/section/topic lines (see format below)
│   └── syllabus.pdf    # Optional fallback if .txt is missing
└── chapters/
    ├── ch_1.pdf
    ├── ch_2.pdf
    ├── ch_3.pdf
    └── ...             # ch_*.pdf; number extracted from filename (ch_1, ch_2, ch-3, etc.)
```

**Examples:** `class-9-maths`, `class-10-science`, `class-12-physics`.

---

## 2. Syllabus file format (`syllabus.txt`)

Use a plain-text file with one chapter/section/topic per line. The pipeline parses:

- **Chapters:** Lines like `1. Real Numbers`, `Chapter 2`, `2. Polynomials`, or `Ch. 3 Title`
- **Sections:** Lines like `1.1 Introduction`, `1.2 The Fundamental Theorem`, `2.1 Introduction`
- **Concepts (optional):** Lines starting with `Concept:` or `•` / `-`

Example (excerpt):

```
1. Real Numbers
1.1 Introduction
1.2 The Fundamental Theorem of Arithmetic
1.3 Revisiting Irrational Numbers
2. Polynomials
2.1 Introduction
...
```

If only `syllabus.pdf` exists (no `.txt`), the app will extract text from the PDF. Providing `syllabus.txt` is recommended for consistent hierarchy parsing.

---

## 3. Chapter PDFs

- Place PDFs in `chapters/` with names like `ch_1.pdf`, `ch_2.pdf`, `ch_3.pdf` (or `ch-1.pdf`).
- Chapter number is read from the filename and used for ordering and metadata.
- You can add as many chapters as you want; the app will ingest up to `GROUNDING_CHAPTER_COUNT` (see below).

---

## 4. Environment configuration

Set these before running the API (or ingestion). All paths are relative to the **repository root**.

| Variable | Description | Example |
|----------|-------------|---------|
| `GROUNDING_DATA_DIR` | Course directory name under repo root | `class-10-science` |
| `GROUNDING_SYLLABUS_RELATIVE_PATH` | Path to syllabus file inside course dir | `syllabus/syllabus.pdf` or `syllabus/syllabus.txt` |
| `GROUNDING_CHAPTERS_DIR` | Subfolder name for chapter PDFs | `chapters` |
| `GROUNDING_CHAPTER_COUNT` | Max number of chapter PDFs to ingest | `5` |

**Example (new course):**

```bash
export GROUNDING_DATA_DIR=class-10-science
export GROUNDING_SYLLABUS_RELATIVE_PATH=syllabus/syllabus.pdf
export GROUNDING_CHAPTERS_DIR=chapters
export GROUNDING_CHAPTER_COUNT=5
```

Reading prefers `.txt`: if `syllabus/syllabus.pdf` is set but `syllabus/syllabus.txt` exists, the pipeline uses the `.txt` content.

---

## 5. Run ingestion

With the API running and DB + embedding service available:

```bash
# From repo root (or set API URL)
curl -X POST "http://localhost:8000/grounding/ingest?force_rebuild=false"
```

- **First run for a new course:** Use `force_rebuild=false` (default). All documents will be ingested.
- **Re-run after changing syllabus/PDFs:** Use `force_rebuild=true` to replace existing chunks and hierarchy for changed files.

Alternatively, if `GROUNDING_PREPARE_ON_START=true`, ingestion runs once at API startup (using the same env vars).

---

## 6. Verify

- **Status:** `GET http://localhost:8000/grounding/status`  
  - Expect `ready: true` and no entries in `missing_paths` / `missing_embeddings` when ingestion succeeded.
- **Hierarchy:** Syllabus hierarchy (chapter > section > concept) is stored in `syllabus_hierarchy` during ingestion and used for planning and progress.

---

## 7. No code changes

Planning, progress tracking, and profiling (per-chapter/per-topic confidence and achievement) use the same logic for every course. Only the configured course directory and ingestion output change.
