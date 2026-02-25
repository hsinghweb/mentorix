# Mentorix – Testing & Demo Guide

This guide ensures **database** (PostgreSQL relational + pgvector, MongoDB NoSQL), **Redis cache**, **REST API backend**, and **frontend** are verified before demoing to an instructor or business audience.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Backend testing](#2-backend-testing)
3. [Frontend testing](#3-frontend-testing)
4. [Instructor / business pitch demo](#4-instructor--business-pitch-demo)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Prerequisites

### 1.1 Environment

- **Docker Desktop** (or Docker Engine) running.
- **Ollama** on host (for local embeddings): `ollama pull nomic-embed-text`.
- **API key:** `CONFIG/local.env` with at least `GEMINI_API_KEY` (for content generation in demo).
- **Repo root:** All commands below assume you are at the repository root unless stated otherwise.

### 1.2 Start the full stack

```powershell
docker compose up --build -d
```

**The frontend is part of this stack.** You do not need to build or start it separately. One command brings up all five services; the frontend container (`mentorix-frontend`) uses the pre-built `nginx:alpine` image and mounts the `frontend/` folder. It starts after the API is healthy and is available at **http://localhost:5500**.

Services:

| Service   | Port  | Role                                      |
|----------|-------|-------------------------------------------|
| Postgres | 5432  | Relational DB + pgvector (embeddings)    |
| Redis    | 6379  | Session cache, idempotency keys           |
| Mongo    | 27017 | NoSQL runtime memory (hubs, snapshots)    |
| API      | 8000  | FastAPI backend                           |
| Frontend | 5500  | Nginx serving static UI (included in compose) |

### 1.3 Readiness check (recommended)

```powershell
./scripts/check_ready.ps1
```

This verifies containers, API health, env keys, and a minimal API smoke flow.

---

## 2. Backend testing

### 2.1 Database & cache health (manual)

Confirm each data layer is reachable and the API reports healthy.

| Check              | How to verify |
|--------------------|---------------|
| **PostgreSQL**     | API uses it for learners, plans, chunks; health depends on Postgres. `GET http://localhost:8000/health` → `"status":"ok"`. |
| **pgvector**       | Used for embedding chunks. After ingestion, `GET /grounding/status` shows `ready: true` and no `missing_embeddings`. |
| **Redis**          | Session cache + idempotency. `POST /start-session` then `POST /submit-answer`; if Redis is down, tests use in-memory fallback (see `test_redis_outage_falls_back_to_degraded_session_cache`). |
| **MongoDB**        | Runtime memory. `GET http://localhost:8000/memory/status` → `configured_backend`, `mongo.connected`, etc. |

**Quick curl checks:**

```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/grounding/status | jq .
curl -s http://localhost:8000/memory/status | jq .
```

### 2.2 Automated backend test suite

From **repository root**:

```powershell
cd API
uv run pytest ..\tests -v
```

Or with pytest from repo root (if `API` is on `PYTHONPATH`):

```powershell
uv run pytest tests -v
```

**What the suite covers:**

| Test file / area | What it verifies |
|-------------------|------------------|
| **test_api_integration.py** | Session flow (start → submit → dashboard), failure modes (missing session, embedding/Gemini fallbacks, Redis fallback), grounding status, onboarding (start, timeline bounds, diagnostic→profile), weekly replan, plan/tasks/where-i-stand, revision queue, idempotency, learning-metrics, forecast-history, app metrics, student UI surface, admin UI surface. |
| **test_grounding_ingestion.py** | PDF/text parse integrity, chunking determinism, embedding dimension consistency, ingestion idempotency. |
| **test_memory_migration.py**   | File vs Mongo store parity, Mongo index idempotency, backfill script, memory status when Mongo unavailable. (Some tests skip if Mongo is not running.) |
| **test_rag_grounding_compliance.py** | RAG/grounding compliance and policy. |
| **test_content_policy.py**    | Content policy and guardrails. |
| **test_security_guardrails.py** | Security and auth behavior. |
| **test_reliability_scheduler.py** | Scheduler and reliability paths. |

**Run a subset (examples):**

```powershell
# Only API integration (student + admin surface)
uv run pytest tests/test_api_integration.py -v

# Only grounding
uv run pytest tests/test_grounding_ingestion.py -v

# Only memory (requires Mongo on localhost:27017)
uv run pytest tests/test_memory_migration.py -v
```

**Expected:** All tests pass (or memory tests are skipped if Mongo is not running). No code changes are required for “things to work”; the suite is the gate.

### 2.3 REST API surface (smoke)

Endpoints used by the frontend and by evaluators:

**Health & infra**

- `GET /health` – API and DB health.
- `GET /grounding/status` – Grounding readiness (chunks, missing paths/embeddings).
- `GET /memory/status` – Memory backend (Mongo/file) and connectivity.
- `GET /metrics/app` – Request count, error rate, latency p50/p95, cache, alerts.

**Student / session**

- `POST /start-session` – Body: `{"learner_id": "<uuid>"}`.
- `POST /submit-answer` – Body: `session_id`, `answer`, `response_time` (optional idempotency key).
- `GET /dashboard/{learner_id}` – Mastery map, weak areas, last sessions.

**Onboarding & plan**

- `POST /onboarding/start` – Start onboarding (name, grade, timeline 14–28 weeks).
- `POST /onboarding/submit` – Submit diagnostic; returns recommendation and profile.
- `GET /onboarding/plan/{learner_id}` – Current plan (active week + forecast).
- `GET /onboarding/tasks/{learner_id}` – Current week tasks.
- `GET /onboarding/where-i-stand/{learner_id}` – Chapter status, confidence, stand summary.
- `GET /onboarding/revision-queue/{learner_id}` – Revision queue.
- `GET /onboarding/learning-metrics/{learner_id}` – Aggregated learning metrics.
- `GET /onboarding/forecast-history/{learner_id}` – Forecast history.
- `POST /onboarding/weekly-replan` – Weekly evaluation and replan (adaptive pace).

**Admin**

- `GET /admin/cohort` – Learner cohort summary.
- `GET /admin/policy-violations` – Policy violations.
- `GET /admin/timeline-drift` – Timeline drift across learners.

**Grounding**

- `POST /grounding/ingest?force_rebuild=false|true` – Run ingestion (syllabus + chapter PDFs → chunks + syllabus_hierarchy).

Scripted smoke (from repo root):

```powershell
./scripts/test_mvp.ps1
```

This runs a minimal end-to-end API flow (health, start-session, submit-answer, dashboard).

### 2.4 Grounding pre-work (before demo)

So that sessions use real curriculum chunks and the UI shows meaningful content:

```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/grounding/status"
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/grounding/ingest?force_rebuild=false"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/grounding/status"
```

Expect final status: `ready: true`, empty `missing_paths` and `missing_embeddings` (when syllabus + chapter PDFs are present under `class-10-maths/`).

---

## 3. Frontend testing

### 3.1 Serving the frontend

**Option A – Docker (default):**  
If you ran `docker compose up --build -d`, the frontend is already running. Open **http://localhost:5500** (nginx service in the same compose; no separate build or start needed).

**Option B – Local static server:**  
Only if you are not using Docker at all (e.g. API running locally, no compose):

```powershell
cd frontend
python -m http.server 5500
```

Then open **http://localhost:5500**.

Ensure the API base URL in the UI is **http://localhost:8000** (or your API URL). The UI has an “API Base URL” field in each panel.

### 3.2 Student panel

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open **Student** tab. | Session, Lesson, Submit, Evaluation, Dashboard, Status sections visible. |
| 2 | (Optional) Click **Generate Learner ID**. | Learner ID field populated with a UUID. |
| 3 | Enter or generate Learner ID; click **Start Session**. | Status shows success; Session ID, Concept, Question, Explanation populated. |
| 4 | Enter an answer, set response time; click **Submit Answer**. | Score, Error Type, Adaptation shown in Evaluation. |
| 5 | Click **Refresh Dashboard**. | Engagement, Weak Areas, Mastery Map, Last Sessions updated. |

**Pass criteria:** No console errors; API calls return 200; data appears in the panels.

### 3.3 Onboarding & Plan panel

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open **Onboarding & Plan** tab. | Onboarding, Diagnostic, Plan & Tasks, Streak, Chapter tracker, Next-week, Forecast trend sections visible. |
| 2 | Set Name, Grade, Timeline (14–28); click **Start Onboarding**. | Learner ID shown; diagnostic section can load. |
| 3 | (If diagnostic loaded) Submit diagnostic. | Result and recommendation shown. |
| 4 | Click **Get Plan**, **Get Tasks**, **Where I Stand**, **Revision queue**. | Plan/Tasks/Where I Stand/Revision queue JSON or summary in result area. |
| 5 | Click **Load summary** (Streak), **Load chapter tracker**, **Load concept map**, **Load next week**, **Load forecast trend**. | Corresponding data loads without errors. |

**Pass criteria:** Buttons trigger the correct APIs; response appears in the result area or summary placeholders; no 4xx/5xx in network tab.

### 3.4 Admin panel

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open **Admin** tab. | Health, Metrics, Grounding, Cohort, Policy violations, Timeline drift buttons visible. |
| 2 | Click **Health**. | JSON with `status: ok` (or equivalent). |
| 3 | Click **Metrics (app)**. | request_count, error_rate, latency, cache, alerts. |
| 4 | Click **Grounding Status**. | ready, missing_paths, missing_embeddings. |
| 5 | Click **Cohort**, **Policy violations**, **Timeline drift**. | Each returns JSON (learner_count, violations, learners_with_timeline, etc.). |

**Pass criteria:** All admin endpoints return 200 and display in the response area.

### 3.5 Automated frontend surface test (backend proxy)

The backend test suite includes smoke tests that hit the **same API surface** the frontend uses:

- **Student + Onboarding surface:** `test_student_ui_surface_endpoints_available` (health, start-session, plan, tasks, where-i-stand).
- **Admin surface:** `test_admin_ui_surface_endpoints_available` (health, metrics/app, grounding/status, cohort, policy-violations, timeline-drift).

So: if `pytest tests/test_api_integration.py` passes, the backend is ready for the frontend; the remaining frontend check is manual UI flow above.

---

## 4. Instructor / business pitch demo

### 4.1 Pre-demo checklist

- [ ] Docker stack running (`docker compose up -d`).
- [ ] Readiness script passed (`./scripts/check_ready.ps1`).
- [ ] Grounding ingested (`POST /grounding/ingest`; `GET /grounding/status` → ready).
- [ ] Backend tests passed (`uv run pytest tests -v`).
- [ ] Frontend opens at http://localhost:5500; API base URL = http://localhost:8000.
- [ ] Optional: Memory backfill to Mongo done if you want to show `/memory/status` with Mongo.

### 4.2 Demo narrative (5–8 minutes)

**1. One-line pitch (30 s)**  
“Mentorix is an autonomous, multi-agent learning platform for CBSE math: it adapts to each student’s pace, grounds teaching in the syllabus, and gives instructors visibility into progress and risk.”

**2. Architecture (1 min)**  
“Backend: Postgres for learners and curriculum, pgvector for semantic search over chapters, MongoDB for runtime memory, Redis for session cache. One API serves the student UI and admin tools.”

**3. Student flow (2–3 min)**  
- Open **Student** tab; generate Learner ID; **Start Session**.  
- Show concept, question, and explanation (mention: “content is grounded in our class-10-maths curriculum”).  
- Submit an answer; show score and adaptation (difficulty/explanation adapt to performance).  
- **Refresh Dashboard**: mastery map, weak areas, last sessions.  
- Optional: switch to **Onboarding & Plan**; show timeline (14–28 weeks), **Where I Stand**, **Revision queue**, **Learning metrics** (streak, forecast, adherence).

**4. Planning & adaptation (1–2 min)**  
- **Onboarding & Plan**: Start onboarding with a timeline; submit diagnostic; show “your target vs Mentorix recommendation.”  
- Get Plan / Tasks; show “Where I Stand” (chapter-level status, confidence).  
- Mention: “Weekly replan uses adaptive pace: behind → extend a week; ahead → compress carefully.”

**5. Admin & observability (1 min)**  
- **Admin** tab: **Health**, **Metrics (app)** (latency, error rate, alerts), **Grounding Status**, **Cohort**, **Policy violations**, **Timeline drift**.  
- “Instructors see system health, learner cohort, policy violations, and timeline drift in one place.”

**6. Closing (30 s)**  
“Everything we showed—sessions, onboarding, plans, metrics—is backed by the same REST API. The stack is Docker-first so evaluators can run it with one command.”

### 4.3 Backup talking points

- **Extensibility:** New course = new directory (syllabus + PDFs), set env, run ingestion; see `docs/ONBOARD_NEW_COURSE.md`.
- **No code change for new course:** Same planning and profiling logic; only data changes.
- **Evidence-based completion:** Tasks are completed from progress and submissions, not manual checkboxes.
- **Enterprise readiness:** Structured logging, app metrics, alerts, gateway auth path, Mongo for memory, Redis for cache.

---

## 5. Troubleshooting

| Issue | What to check |
|-------|----------------|
| **Docker API image build fails** | Build from scratch: `docker compose build --no-cache api` then `docker compose up -d`. See [5.1 Build API image from scratch](#51-build-api-image-from-scratch). |
| API 502 / not responding | Containers up (`docker compose ps`); API health `GET /health`. Postgres/Redis/Mongo healthy in compose. |
| Grounding not ready | Run `POST /grounding/ingest`. Ensure `class-10-maths/syllabus/` and `class-10-maths/chapters/` exist and env `GROUNDING_DATA_DIR` (or default) points to `class-10-maths`. |
| Frontend “network error” | API base URL in UI must match API (e.g. http://localhost:8000). CORS is enabled for all origins. |
| Tests fail: Mongo | Memory tests need Mongo on localhost:27017 or they skip. Start stack with `docker compose up -d`. |
| Tests fail: LLM/embedding | Tests use `LLM_PROVIDER=none` and local embedding fallback; no Gemini/Ollama required for test run. |
| Demo: empty or generic content | Run grounding ingest; ensure syllabus/chapter PDFs exist. If using Gemini, ensure `GEMINI_API_KEY` in `CONFIG/local.env`. |

### 5.1 Build API image from scratch

If the API image fails to build (e.g. cached layers, lockfile, or network issues), do a **full rebuild without cache**.

From **repository root**:

```powershell
# Rebuild the API image from scratch (no cache). Takes longer but avoids stale layers.
docker compose build --no-cache api

# Then start the stack
docker compose up -d
```

Or rebuild and start in one go:

```powershell
docker compose build --no-cache api && docker compose up -d
```

To rebuild **all** services from scratch:

```powershell
docker compose build --no-cache
docker compose up -d
```

---

## Summary

| Layer | How to verify |
|-------|----------------|
| **PostgreSQL + pgvector** | API health; grounding ingest and `/grounding/status`; integration tests. |
| **MongoDB** | `GET /memory/status`; `test_memory_migration.py` (with Mongo running). |
| **Redis** | Session flow and idempotency tests; optional Redis-down test (fallback). |
| **REST API** | `./scripts/test_mvp.ps1`; `uv run pytest tests/test_api_integration.py`. |
| **Frontend** | Manual Student / Onboarding & Plan / Admin flows; API surface covered by backend smoke tests. |
| **Demo** | Pre-demo checklist + narrative above; no code changes required for a working demo. |
