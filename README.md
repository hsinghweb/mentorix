# Mentorix

Mentorix: An Autonomous Agentic AI System for Personalized Learning.

## Evaluator Quick Path (3-5 minutes)

Use this path if you are reviewing the capstone quickly.

1) Start stack:
```powershell
docker compose up --build -d
```
2) Run readiness + smoke:
```powershell
./scripts/check_ready.ps1
./scripts/test_mvp.ps1
```
3) (Optional) Open UI:
```powershell
cd frontend
python -m http.server 5500
```
Open `http://localhost:5500` (API default: `http://localhost:8000`).

Expected outcome:
- API health is green
- Session lifecycle works (`start-session -> submit-answer -> dashboard`)
- Adaptive response is visible in `adaptation_applied`

## Run with Docker (full)

### 1) Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine + Compose plugin (Linux)

### 2) Configure environment
- Default runtime config is already available at `CONFIG/local.env`.
- Optional: update `GEMINI_API_KEY` in `CONFIG/local.env`.

### 3) Start the full stack
```powershell
docker compose up --build -d
```

Dependency management uses `uv` with `API/pyproject.toml` (single source of truth).

Services:
- API: `http://localhost:8000`
- API health: `http://localhost:8000/health`
- PostgreSQL (pgvector): `localhost:5432`
- Redis: `localhost:6379`

### 4) Stop the stack
```powershell
docker compose down
```

To remove volumes too:
```powershell
docker compose down -v
```

## Share on another machine (prebuilt images)

### Export images
```powershell
./scripts/export_images.ps1
```
This creates:
- `artifacts/mentorix-api.tar`
- `artifacts/mentorix-postgres.tar`
- `artifacts/mentorix-redis.tar`

### Import images on peer/mentor machine
```powershell
./scripts/load_images.ps1
docker compose up -d
```

## Architecture Intent (MVP)
- Deterministic orchestration + specialized agents for learning flow.
- Curriculum-grounded generation (RAG-backed, with safe fallbacks).
- Closed-loop adaptation from learner response + timing signals.
- Explainability-oriented outputs via structured adaptation/evaluation fields.

## Notes
- `CONFIG/local.env` is intentionally included with safe defaults for quick startup.
- LLM provider is Gemini free API (`GEMINI_API_KEY`).
- Embeddings are configured to use local Ollama `nomic-embed-text` (no GPU required).
- PostgreSQL + Redis run locally via Docker images.
- Web search provider is constrained to DuckDuckGo.

## Quick Smoke Test
After services are running, execute:
```powershell
./scripts/test_mvp.ps1
```
Optional:
```powershell
./scripts/test_mvp.ps1 -BaseUrl "http://localhost:8000" -LearnerId "11111111-1111-1111-1111-111111111111"
```

## Startup Readiness Check
Run a full readiness gate (containers + API health + Ollama embeddings + smoke flow):
```powershell
./scripts/check_ready.ps1
```

## Minimal Frontend (No Build Tool)
Run a static server and open the page:
```powershell
cd frontend
python -m http.server 5500
```
Then open:
- `http://localhost:5500`

Default API URL in UI is:
- `http://localhost:8000`

## Demo Runbook
For evaluator-ready walkthrough steps, see:
- `docs/DEMO_RUNBOOK.md`

## Database Migrations (Alembic baseline)
From `API` directory:
```powershell
cd API
uv run alembic -c alembic.ini upgrade head
```
Check migration status:
```powershell
uv run alembic -c alembic.ini current
```

## API Contract Examples

### `POST /start-session`
Request:
```json
{
  "learner_id": "11111111-1111-1111-1111-111111111111"
}
```
Response (example):
```json
{
  "session_id": "26e36f4a-964b-4925-a31a-a1c6fd60df95",
  "concept": "quadratic_equations",
  "difficulty": 2,
  "explanation": "Generated grounded explanation...",
  "question": "Solve one practice question for 'quadratic_equations' at difficulty level 2.",
  "state": "DELIVER"
}
```

### `POST /submit-answer`
Request:
```json
{
  "session_id": "26e36f4a-964b-4925-a31a-a1c6fd60df95",
  "answer": "Quadratic equations can be solved by factorization...",
  "response_time": 9.5
}
```
Response (example):
```json
{
  "session_id": "26e36f4a-964b-4925-a31a-a1c6fd60df95",
  "score": 0.35,
  "error_type": "concept_mismatch",
  "adaptation_applied": {
    "adaptation_score": 0.463,
    "new_difficulty": 2,
    "explanation_granularity_level": "normal",
    "analogy_injection_flag": false,
    "cooldown_remaining": 1
  },
  "next_explanation": "Generated grounded next explanation..."
}
```

### `GET /dashboard/{learner_id}`
Response (example):
```json
{
  "learner_id": "11111111-1111-1111-1111-111111111111",
  "mastery_map": {
    "fractions": 0.45,
    "linear_equations": 0.35,
    "quadratic_equations": 0.315,
    "probability": 0.5
  },
  "engagement_score": 0.47,
  "weak_areas": ["quadratic_equations", "linear_equations", "fractions"],
  "last_sessions": [
    {
      "concept": "quadratic_equations",
      "difficulty_level": 2,
      "adaptation_score": 0.463,
      "timestamp": "2026-02-19T14:56:00.05+00:00"
    }
  ]
}
```

## What Evaluators Should Verify
- **Autonomy:** system continues through planned states without manual prompt engineering.
- **Adaptation:** `submit-answer` output changes instructional direction using score + response-time signals.
- **Grounding:** generated lesson text remains curriculum-aligned and concept-focused.
- **Traceability:** outputs include interpretable fields (`error_type`, `adaptation_applied`, `weak_areas`).

## Known Limitations (MVP)
- RAG currently uses a small seeded curriculum set; ingestion pipeline is minimal.
- Retrieval is concept-focused hybrid ranking, not full multi-document search.
- Assessment scoring is heuristic for MVP (not exam-grade evaluator).
- No auth/multi-tenant isolation in current MVP.
- Frontend is no-build static UI (fast for demo, not production UX).

## V2 Roadmap
- Full curriculum ingestion pipeline with richer chunk metadata.
- Stronger evaluation engine and misconception taxonomy.
- Better adaptation controls per learner segment and learning velocity.
- Auth + role-based access + audit trail hardening.
- Deeper analytics dashboard and richer learner timeline views.