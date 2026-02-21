# Mentorix

Autonomous multi-agent personalized learning MVP (CBSE math focus) for capstone evaluation.

## Evaluator Quick Run (3-5 min)

Prerequisite: Docker Desktop/Engine is running.

```powershell
docker compose up --build -d
./scripts/check_ready.ps1
./scripts/test_mvp.ps1
```

Optional UI check:
```powershell
cd frontend
python -m http.server 5500
```
Open `http://localhost:5500` (API default: `http://localhost:8000`).

## What This Demo Proves

- **Autonomy:** session flow runs end-to-end (`start-session -> submit-answer -> dashboard`).
- **Adaptation:** `submit-answer` returns `adaptation_applied` using performance + response time.
- **Grounding:** lesson output stays concept/curriculum focused.
- **Traceability:** evaluator-visible fields (`score`, `error_type`, `weak_areas`).

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