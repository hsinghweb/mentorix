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

## 4) Frontend demo
```powershell
cd frontend
python -m http.server 5500
```
Open:
- `http://localhost:5500`

Default API URL in UI:
- `http://localhost:8000`

## 5) Suggested demo narrative (3-5 min)
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
