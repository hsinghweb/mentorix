# Mentorix

Autonomous multi-agent personalized learning MVP (CBSE math focus) for capstone evaluation.

## Evaluator Quick Run (3-5 min)

Prerequisite: Docker Desktop/Engine is running.

```powershell
docker compose up --build -d
./scripts/check_ready.ps1
./scripts/test_mvp.ps1
```

Open:
- Frontend: `http://localhost:5500`
- API: `http://localhost:8000`

## What This Demo Proves

- **Autonomy:** session flow runs end-to-end (`start-session -> submit-answer -> dashboard`).
- **Adaptation:** `submit-answer` returns `adaptation_applied` using performance + response time.
- **Grounding:** lesson output stays concept/curriculum focused.
- **Traceability:** evaluator-visible fields (`score`, `error_type`, `weak_areas`).

## Grounding Pre-Work (Iteration 6 Slice)

Mentorix now includes a pre-work grounding ingestion flow for syllabus + first three chapters.

- Uses `class-10-maths/syllabus/syllabus.pdf` as canonical path.
- If `class-10-maths/syllabus/syllabus.txt` exists, ingestion prefers it (faster, no PDF extraction delay).
- Ingests chapter PDFs: `class-10-maths/chapters/ch_1.pdf`, `ch_2.pdf`, `ch_3.pdf`.
- Stores chunk embeddings + ingestion metadata in Postgres tables:
  - `curriculum_documents`
  - `embedding_chunks`
  - `ingestion_runs`

Grounding endpoints:
- `GET /grounding/status` -> readiness check (missing files / missing embeddings)
- `POST /grounding/ingest` -> run ingestion (`?force_rebuild=true` optional)

## Runtime Memory Backend (MongoDB default)

- Runtime learner/system memory now defaults to **MongoDB** via `MEMORY_STORE_BACKEND=mongo`.
- File-based JSON memory storage is kept only as an optional compatibility mode.
- Migration/backfill command:
  - `cd API`
  - `uv run python scripts/backfill_memory_to_mongo.py --mongodb-url mongodb://localhost:27017 --db-name mentorix`
- Optional export backup command (Mongo -> JSON files):
  - `cd API`
  - `uv run python scripts/export_memory_from_mongo.py --mongodb-url mongodb://localhost:27017 --db-name mentorix --out-dir data/system/export_from_mongo`
- Runtime verification endpoint:
  - `GET /memory/status`

### Memory PII/Security Mapping
- Learner runtime payloads are stored in Mongo collections (`memory_hubs`, `runtime_snapshots`, `episodic_memory`).
- Sensitive keys are redacted before persistence (for example: `password`, `secret`, `token`, `api_key`, `authorization`).
- Mongo connection errors returned by status checks are sanitized to avoid credential leakage.

## Session 19 Additions (Visible in Demo)

- **System 2 reasoning:** content generation runs a bounded Draft-Verify-Refine loop with trace artifacts.
- **Strict model governance:** role-based model routing (`planner`, `optimizer`, `verifier`, `content_generator`) from registry config.
- **Emergency remediation:** verifier fallback path if local verifier is unavailable.
- **Episodic skeleton memory:** run graphs are compressed into recipe-like memory skeletons.
- **Skills 2.0:** both Python skills and Markdown `SKILL.md` skills are supported.
- **JitRL optimizer:** user query optimization with offline rule generation hook.

Quick evaluator endpoints:
- `GET /runs`
- `POST /runs/start`
- `GET /events/stream` (SSE)
- `GET /metrics/fleet`
- `GET /metrics/resilience`
- `GET /memory/hubs`
- `GET /scheduler/jobs`

## Architecture Diagram + Module Map

### Current High-Level Diagram

![Mentorix High Level Design](mentorix_hld.png)

Reference docs:
- `Mentorix_High_Level_Design.pdf`
- `EAG_V2_Capstone_Idea_Mentorix.pdf`

### Repository Module Map (Current)

- **Runtime App:** `API/app/`
  - `api/` (HTTP endpoints)
  - `agents/` (profiling, planner, content, adaptation, assessment, reflection)
  - `orchestrator/` (state machine and transitions)
  - `rag/` (embedding + retriever pipeline)
  - `memory/` (PostgreSQL/Redis integrations)
  - `models/` (SQLAlchemy entities)
  - `core/` (settings, bootstrap, logging, error envelope)
- **Frontend Demo UI:** `frontend/` (static HTML/CSS/JS)
- **Operational Scripts:** `scripts/` (readiness, smoke, image export/import)
- **Configuration:** `CONFIG/` (`local.env`, templates)
- **Tests:** `tests/` (integration + failure-mode API tests)
- **Research/Design Partitions:** `PERCEPTION/`, `MEMORY/`, `DECISION/`, `ACTION/`, `ORCHESTRATOR/`, `AGENT/`, `MODELS/`, `RAG/`
- **Documentation:** `docs/` (`PLANNER.md`, `DEMO_RUNBOOK.md`)

## HLD Block-to-Code Mapping

- **Student Interface (Web/Mobile):** `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`
- **API Gateway (FastAPI auth/routing):** `API/app/main.py`, `API/app/core/auth.py`, `API/app/core/errors.py`
- **Orchestration & Scheduling Engine:** `API/app/runtime/run_manager.py`, `API/app/runtime/graph_context.py`, `API/app/autonomy/scheduler.py`
- **Agent Manager:** `API/app/runtime/run_manager.py` (agent dispatch + lifecycle control)
- **Notification Engine:** `API/app/core/notification_engine.py`, `API/app/api/notifications.py`
- **Multi-Agent System:** `API/app/agents/` (`onboarding.py`, `planner.py`, `content.py`, `assessment.py`, `analytics_evaluation.py`, `compliance.py`, `memory_manager.py`, `reflection.py`)
- **Knowledge & Memory Layer:** `API/app/models/entities.py`, `API/app/memory/database.py`, `API/app/memory/hubs.py`, `API/app/memory/ingest.py`
- **RAG & Grounding Layer:** `API/app/rag/retriever.py`, `API/app/rag/embeddings.py`, `API/app/rag/vector_backends.py`
- **AI Model Layer:** `API/app/core/llm_provider.py`, `API/app/core/model_registry.py`, `CONFIG/models_registry.json`, `CONFIG/models_registry.yaml`

Evaluator-first API entry points:
- **Core learning flow:** `POST /start-session`, `POST /submit-answer`, `GET /dashboard/{learner_id}`
- **Onboarding + dynamic initial plan:** `POST /onboarding/start`, `POST /onboarding/submit`
- **Weekly adaptive progression policy:** `POST /onboarding/weekly-replan`
- **Persisted weekly plan lookup:** `GET /onboarding/plan/{learner_id}`
- **Runtime orchestration:** `POST /runs/start`, `GET /runs/{run_id}/graph`, `POST /runs/{run_id}/stop`
- **Notifications:** `GET /notifications`, `POST /notifications/send`
- **Scheduler:** `GET /scheduler/jobs`, `POST /scheduler/jobs`, `POST /scheduler/jobs/{job_id}/trigger`
- **Observability:** `GET /metrics/fleet`, `GET /metrics/resilience`, `GET /events/stream`

## API Contract (Core Endpoints)

### `POST /start-session`
Request:
```json
{ "learner_id": "11111111-1111-1111-1111-111111111111" }
```
Response fields:
- `session_id`, `concept`, `difficulty`, `explanation`, `question`, `state`

### `POST /submit-answer`
Request:
```json
{
  "session_id": "26e36f4a-964b-4925-a31a-a1c6fd60df95",
  "answer": "sample answer",
  "response_time": 9.5
}
```
Response fields:
- `score`, `error_type`, `adaptation_applied`, `next_explanation`

### `GET /dashboard/{learner_id}`
Response fields:
- `mastery_map`, `engagement_score`, `weak_areas`, `last_sessions`

### Runtime / Session-19 endpoints
- `POST /runs/start` -> start graph-first autonomous run
- `POST /runs/{run_id}/stop` -> controlled stop
- `GET /runs/{run_id}/graph` -> UI graph payload
- `GET /events/stream` -> live runtime events (SSE)
- `GET /metrics/fleet` -> fleet telemetry
- `GET /metrics/resilience` -> circuit breaker state
- `GET /memory/context/{learner_id}` -> structured memory injection context
- `GET|POST|PATCH|DELETE /scheduler/jobs` -> scheduler CRUD + trigger
- `GET /grounding/status` -> ingestion readiness state
- `POST /grounding/ingest` -> build grounding embeddings and manifest
- `POST /onboarding/start` -> generate objective diagnostic set from grounded chunks
- `POST /onboarding/submit` -> score diagnostic, update profile, return rough 14+ week plan + active week
- `POST /onboarding/weekly-replan` -> apply threshold + retry + timeout progression decision
- `GET /onboarding/plan/{learner_id}` -> fetch latest persisted rough weekly plan

## Key References for Review

- Demo flow: `docs/DEMO_RUNBOOK.md`
- Planner/checklist: `docs/PLANNER.md`
- API base: `http://localhost:8000`
- Health: `http://localhost:8000/health`

## Migration Command (if needed)

```powershell
cd API
uv run alembic -c alembic.ini upgrade head
```

## Known Limitations (MVP)

- Seeded curriculum corpus; not full production ingestion.
- Hybrid retrieval is concept-focused (not full cross-document semantic search).
- Heuristic assessment scoring (not exam-grade psychometrics).
- No auth/multi-tenant hardening in MVP.

## V2 (Planned)

- Full curriculum ingestion pipeline + richer chunk metadata.
- Stronger misconception analytics and evaluation engine.
- Auth, RBAC, and audit trail hardening.
- Richer learner analytics and timeline visualization.