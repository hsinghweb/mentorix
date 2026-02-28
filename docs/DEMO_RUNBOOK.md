# Mentorix Demo Runbook

This runbook is for evaluators/mentors to reproduce the MVP in minutes.

## 1) Prerequisites
- Docker Desktop running
- Ollama running on host
- Ollama model pulled:
  - `ollama pull nomic-embed-text`
- `CONFIG/local.env` contains a valid `GEMINI_API_KEY`

## 2) Start stack
```powershell
docker compose up --build -d
```

## 3) Readiness gate (recommended)
```powershell
./scripts/check_ready.ps1
```
This verifies:
- Docker containers are running
- API health endpoint
- Env file minimum keys
- Ollama embeddings endpoint
- End-to-end API smoke flow

## 3.0) Schema migration (once per DB)
After the stack is up, apply the latest Alembic migration (e.g. adds `school` to `learners`):

```powershell
cd API
uv run alembic upgrade head
```

Optional: verify Phase 1.1 tables exist: `uv run python scripts/verify_phase1_schema.py`

## 3.1) Grounding pre-work (recommended before demo)
See **Phase 0** in `docs/PHASE0_RUNBOOK.md` for full verification steps.

```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/grounding/status"
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/grounding/ingest"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/grounding/status"
```
Notes:
- `syllabus.txt` is auto-preferred if present beside `syllabus.pdf`.
- For demo, only the first 5 chapters are embedded (`grounding_chapter_count = 5`).
- This ensures embeddings are precomputed before learner session flow.

## 3.2) Memory migration + backup ops (NoSQL)
Use this once (or when needed) to keep runtime memory fully in MongoDB.

```powershell
cd API
uv run python scripts/backfill_memory_to_mongo.py --mongodb-url mongodb://localhost:27017 --db-name mentorix
uv run python scripts/export_memory_from_mongo.py --mongodb-url mongodb://localhost:27017 --db-name mentorix --out-dir data/system/export_from_mongo
```

Outputs:
- Backfill parity report: `API/data/system/reports/memory_backfill_report.json`
- Optional backup export: `API/data/system/export_from_mongo/`

Quick runtime check:
```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/memory/status"
```

## 4) Frontend demo
```powershell
cd frontend
python -m http.server 5500
```
Open:
- `http://localhost:5500`

API URL in UI:
- Default `http://localhost:8000`. If your API runs elsewhere (e.g. different port/host), set **API URL** on the Login or Sign up form; it is stored for the session.

## 5) Suggested demo narrative (3-5 min)
0. (Optional) Run onboarding-first adaptive plan:
   - `POST /onboarding/start`
   - `POST /onboarding/submit`
   - show score + initial profile + rough plan + active week.
1. Generate learner ID in UI.
2. Click **Start Session**.
3. Show concept/question/explanation.
4. Submit an answer.
5. Show score + adaptation output.
6. Refresh dashboard and show:
   - mastery map
   - weak areas
   - recent sessions

## 6) Session 19 demo extension (2-3 min, API-first)
Use this after core MVP flow to show Reasoning/System-2 additions.

### 6.1 Start an autonomous graph run
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/runs/start" -ContentType "application/json" -Body '{"query":"Create a stronger adaptive plan for weak algebra concepts"}'
```
Save returned `run_id`.

### 6.2 Inspect live progress and graph runtime state
```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/runs"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/runs/<run_id>/graph"
```

### 6.3 Show observability + resilience + memory
```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/metrics/fleet"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/metrics/resilience"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/memory/hubs"
```

### 6.4 Show scheduler + skill path
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/scheduler/jobs" -ContentType "application/json" -Body '{"name":"Iteration4Demo","query":"restart agent and improve plan","interval_seconds":120}'
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/scheduler/jobs"
```
This demonstrates autonomous scheduling and intent-to-skill matching (Python + Markdown skills).

## 7) API backup demo (if UI is unavailable)
Use Swagger:
- `http://localhost:8000/docs`

Run:
- `POST /start-session`
- `POST /submit-answer`
- `GET /dashboard/{learner_id}`
- `POST /runs/start`
- `GET /metrics/fleet`

## 8) Stop
```powershell
docker compose down
```
