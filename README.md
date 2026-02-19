# Mentorix

Mentorix: An Autonomous Agentic AI System for Personalized Learning.

## Run with Docker (recommended)

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