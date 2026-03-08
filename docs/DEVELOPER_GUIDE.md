# Mentorix Developer Onboarding Guide

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url> && cd mentorix
cp .env.example .env  # Fill in GEMINI_API_KEY at minimum
pip install -r requirements.txt

# 2. Start infrastructure
docker-compose up -d  # PostgreSQL, Redis, MongoDB

# 3. Run API
cd API && uvicorn app.main:app --reload --port 8000

# 4. Open frontend
# Open frontend/index.html in browser or:
cd frontend && python -m http.server 5500
```

## Project Structure

```
mentorix/
├── API/app/
│   ├── api/          # FastAPI route handlers (endpoints)
│   ├── agents/       # Agent stubs (assessment, onboarding, reflection)
│   ├── core/         # LLM provider, resilience, settings, auth, errors
│   ├── memory/       # Database, store, cache, content cache
│   ├── models/       # SQLAlchemy entities
│   ├── orchestrator/ # State engine (deprecated)
│   ├── prompts/      # Prompt template files
│   ├── rag/          # Grounding ingestion, retrieval
│   ├── runtime/      # Run manager, graph adapter
│   ├── services/     # Business logic (interventions, profiles, timeline)
│   ├── skills/       # SKILL.md-based skill system
│   └── telemetry/    # LLM telemetry, error rate tracker
├── frontend/         # Single-page app (HTML/JS/CSS)
├── CONFIG/           # Environment configs, model registry
├── scripts/          # Test and utility scripts
└── docs/             # Architecture docs, planner files
```

## Key Data Flows

1. **Student Login** → `POST /auth/login` → JWT token
2. **Diagnostic Test** → `POST /onboarding/diagnostic` → LLM generates MCQs → score → personalized plan
3. **Dashboard** → `GET /learning/dashboard/{id}` → queries 8+ tables → Redis cached (60s)
4. **Read Content** → `GET /learning/content/{ch}` → RAG retrieval + LLM generation
5. **Take Test** → `POST /learning/test/generate` → LLM generates MCQs → `POST /test/submit` → scores recorded

## Adding a New Feature

1. Add schema models to `API/app/models/entities.py` if needed
2. Create business logic in `API/app/services/your_feature.py`
3. Add route handler in `API/app/api/learning.py` (or new file)
4. Wire route into `API/app/main.py`
5. Add frontend UI in `frontend/app.js` and `frontend/index.html`

## Databases

| Database | Purpose | Access |
|----------|---------|--------|
| PostgreSQL (pgvector) | Structured data: learners, plans, assessments | `database.py` via SQLAlchemy |
| MongoDB | Content cache, memory store, snapshots | `store.py` via pymongo |
| Redis | Session cache, dashboard cache, rate limiting | `cache.py` via aioredis |
