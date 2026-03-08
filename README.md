# Mentorix

**Your personal AI Math Tutor for Class 10 CBSE Mathematics.**  
Agentic, autonomous, and adaptive learning with NCERT-grounded content.

---

## Features

- **Diagnostic onboarding** — 25-question MCQ assessment; personalized timeline (14–28 weeks) and week-by-week plan
- **Adaptive dashboard** — Current week tasks, chapter completion, mastery overview, comparative analytics
- **Chapter reading** — Generated reading material from NCERT syllabus; section and chapter-level content with optional RAG grounding
- **Section & chapter tests** — MCQ generation, timed tests, pass/fail with retry and revision queue
- **Practice mode** — Extra questions with instant feedback and explanations
- **Admin dashboard** — Student list, agent overview, system metrics (when running as admin)
- **Auth** — Student signup (with diagnostic), login, JWT; optional admin login

---

## Tech Stack

| Layer      | Stack |
|-----------|--------|
| Frontend  | Vanilla JS (SPA), HTML/CSS, KaTeX, Marked, Chart.js |
| API       | FastAPI, Pydantic, SQLAlchemy (async), asyncpg |
| Databases | PostgreSQL (pgvector), Redis, MongoDB |
| LLM       | Gemini or Ollama (configurable) |
| Embeddings| Ollama (e.g. nomic-embed-text) or Gemini |

---

## Project Structure

```
mentorix/
├── API/                    # Backend (FastAPI)
│   ├── app/
│   │   ├── api/            # Route handlers (auth, learning, onboarding, admin, health, …)
│   │   ├── agents/         # Assessment, onboarding, reflection, diagnostic MCQ
│   │   ├── core/           # Settings, LLM provider, resilience, auth, config governance
│   │   ├── memory/         # DB session, Redis cache, MongoDB store, content cache
│   │   ├── models/         # SQLAlchemy entities
│   │   ├── rag/            # Grounding ingestion, retrieval, vector backends
│   │   ├── runtime/        # Run manager, persistence
│   │   ├── services/       # Timeline, reminders, learner profile, email
│   │   └── telemetry/      # LLM telemetry, error-rate tracking
│   ├── alembic/            # DB migrations
│   ├── tests/              # Pytest tests
│   ├── pyproject.toml      # Python deps (no top-level requirements.txt)
│   └── Dockerfile
├── frontend/               # Single-page app
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── renderer.js         # KaTeX / Markdown helpers
├── CONFIG/                 # Env and model registry (e.g. local.env)
├── data/                   # Runtime data (e.g. memory store when using file backend)
├── docs/                   # Architecture, developer guide, planner notes
├── scripts/                # MVP smoke test (PowerShell), test runners, utilities
├── docker-compose.yml      # Postgres, Redis, Mongo, API, frontend (nginx)
└── .env.example             # Copy to .env and set GEMINI_API_KEY etc.
```

---

## Prerequisites

- **Python 3.11+**
- **PostgreSQL** (with pgvector)
- **Redis**
- **MongoDB** (or use file memory store for light local runs)
- **LLM**: [Google Gemini](https://ai.google.dev/) API key, or local [Ollama](https://ollama.ai/)

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd mentorix
cp .env.example .env
# Edit .env: set GEMINI_API_KEY (or use LLM_PROVIDER=ollama and run Ollama locally)
```

### 2. Start infrastructure (Docker)

```bash
docker compose up -d
# Postgres :5432, Redis :6379, Mongo :27017
```

### 3. API (from repo root)

```bash
cd API
pip install -e ".[dev]"   # or: pip install -e .
# Set env so DB/Redis/Mongo match .env (or use CONFIG/local.env)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend

- **Option A:** Open `frontend/index.html` in a browser (API URL can be set in the login/signup form; default `http://localhost:8000`).
- **Option B:** Serve the folder and open the URL, e.g.  
  `python -m http.server 5500` from `frontend/` → `http://localhost:5500`

### 5. Use the app

1. Sign up (name, email, timeline weeks, Class 9 math %), then take the **diagnostic test**.
2. Submit the test → see results and **Go to Dashboard**.
3. From the dashboard, open **This Week’s Tasks** (read → section quiz → chapter test), comparative analytics, and learning roadmap.

---

## Configuration

Key environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL (async) | `postgresql+asyncpg://mentorix:mentorix@localhost:5432/mentorix` |
| `REDIS_URL` | Redis | `redis://localhost:6379/0` |
| `MONGODB_URL` | MongoDB | `mongodb://localhost:27017` |
| `MEMORY_STORE_BACKEND` | `mongo` or `file` | `mongo` |
| `LLM_PROVIDER` | `gemini` or `ollama` | `gemini` |
| `GEMINI_API_KEY` | Required for Gemini | — |
| `OLLAMA_BASE_URL` | For local LLM | `http://localhost:11434` |
| `JWT_SECRET` | Change in production | dev default in .env.example |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Admin dashboard | change in production |

For **tests**, the API uses `MEMORY_STORE_BACKEND=file` and `LLM_PROVIDER=none` (set in `API/tests/conftest.py` and root `tests/conftest.py`) so that PostgreSQL/Redis/Mongo/LLM are not required for the test suite.

---

## Running with Docker Compose

```bash
# From repo root; ensure CONFIG/local.env exists (or env_file in docker-compose)
docker compose up -d
# API: http://localhost:8000
# Frontend: http://localhost:5500 (nginx serving ./frontend)
```

API container expects Postgres, Redis, and Mongo to be healthy before starting. Frontend is served as static files.

---

## Tests

From repo root (API on path and env set) or from `API/`:

```bash
cd API
pip install -e ".[dev]"
pytest tests/ -v
# Exclude slow learning-flow tests if needed:
pytest tests/ -v --ignore=tests/test_learning_flow.py
```

Root-level `tests/` may require `PYTHONPATH=API` and `MEMORY_STORE_BACKEND=file` (see `tests/conftest.py`).

---

## Documentation

- **Architecture** — `docs/ARCHITECTURE.md` (overview, data flow, module deps)
- **Developer guide** — `docs/DEVELOPER_GUIDE.md` (quick start, structure, key flows)
- **API** — `API/API_README.md` (if present) or OpenAPI at `http://localhost:8000/docs` when the API is running

---

## License

See repository license file.
