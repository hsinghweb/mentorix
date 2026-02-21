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

## 6) API backup demo (if UI is unavailable)
Use Swagger:
- `http://localhost:8000/docs`

Run:
- `POST /start-session`
- `POST /submit-answer`
- `GET /dashboard/{learner_id}`

## 7) Stop
```powershell
docker compose down
```
