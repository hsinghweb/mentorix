# Mentorix MVP Planner

Status date: 2026-02-19  
Goal: ship a stable end-to-end MVP fast, then polish for capstone demo.

---

## 1) Scope Lock

### MVP Target Flow
- `start-session` -> concept selection -> grounded explanation -> question generation
- `submit-answer` -> scoring -> adaptation -> profile update
- `dashboard` -> mastery + weak areas + recent sessions

### Hard Constraints
- Gemini API for LLM generation
- Ollama `nomic-embed-text` for embeddings (local)
- PostgreSQL + pgvector (Docker)
- Redis (Docker)
- Web search provider: DuckDuckGo
- No LangChain/CrewAI orchestration

---

## 2) Database & Memory

### Completed
- [x] PostgreSQL + pgvector service configured in Docker
- [x] Redis service configured in Docker
- [x] SQLAlchemy models created:
  - [x] `learners`
  - [x] `learner_profile`
  - [x] `session_logs`
  - [x] `assessment_results`
  - [x] `concept_chunks` (vector column)
- [x] Startup bootstrap creates extension + tables
- [x] Seed curriculum chunks added
- [x] Vector-dimension mismatch fix implemented (768 dim for nomic)
- [x] Session cache model active in Redis (`session:{session_id}`)

### Left
- [ ] Add DB indexes for query hotspots (`learner_id`, `timestamp`, `concept`)
- [ ] Add migration workflow (Alembic baseline + first migration)
- [ ] Add retention/cleanup strategy for old session records

---

## 3) Backend APIs & Orchestration

### Completed
- [x] FastAPI app bootstrapped
- [x] Health endpoint: `GET /health`
- [x] Deterministic state enum + engine scaffold
- [x] Agent modules created:
  - [x] Profiling
  - [x] Planner
  - [x] Content
  - [x] Adaptation
  - [x] Assessment
  - [x] Reflection
- [x] RAG retriever + embedding pipeline integrated
- [x] Core APIs implemented:
  - [x] `POST /start-session`
  - [x] `POST /submit-answer`
  - [x] `GET /dashboard/{learner_id}`
- [x] Smoke tests passed in Swagger

### Left
- [x] Switch content generation path to Gemini (with deterministic fallback)
- [x] Add structured state-transition logging per request/session
- [x] Add robust error envelope and API-level exception mapping
- [ ] Add explicit validation for adaptation shift caps per concept/session

---

## 4) RAG & LLM Integration

### Completed
- [x] Embeddings from local Ollama API (`/api/embeddings`)
- [x] Embedding dimension normalized to configured size
- [x] Concept chunk retrieval wired into content generation

### Left
- [ ] Add true vector similarity retrieval ordering (not concept-only filtering)
- [ ] Add hybrid retrieval (vector + keyword signal)
- [x] Implement Gemini content prompt with strict grounding policy:
  - [x] "Only use provided curriculum context"
  - [x] "If missing, explicitly say limitation"
- [x] Add fallback chain:
  - [x] Gemini fail -> template explanation

---

## 5) Frontend

### Completed
- [x] Frontend folder scaffold exists

### Left
- [x] Build minimal learner UI page:
  - [x] Start session button/input
  - [x] Current explanation + question panel
  - [x] Submit answer form
  - [x] Show score + adaptation summary
- [x] Build dashboard page:
  - [x] Mastery map (simple table/cards)
  - [x] Weak areas
  - [x] Last 5 sessions
- [x] Handle API loading/error states cleanly

---

## 6) Docker, Runtime, Portability

### Completed
- [x] Docker Compose for API + Postgres + Redis
- [x] Health checks configured
- [x] Named volumes configured
- [x] API Dockerfile aligned with `uv + pyproject.toml + uv.lock`
- [x] Image export/import scripts added

### Left
- [ ] Add frontend service to compose (if FE containerized for demo)
- [x] Add one-command smoke test script
- [x] Add startup readiness check script

---

## 7) Testing & QA

### Completed
- [x] Manual smoke tests passed for key APIs

### Left
- [x] Add automated API smoke script (`scripts/test_mvp.ps1`)
- [ ] Add backend integration test for happy path
- [ ] Add failure-mode tests:
  - [ ] missing/expired session
  - [ ] embedding service unavailable
  - [ ] Gemini unavailable fallback

---

## 8) Documentation

### Completed
- [x] Docker run instructions in `README.md`
- [x] Image sharing instructions in `README.md`

### Left
- [ ] Update README with current architecture diagram + module map
- [ ] Add API request/response examples for all endpoints
- [ ] Add "known limitations" and "v2 plan" section
- [x] Add capstone demo script narrative (step-by-step for evaluator)

---

## 9) Priority Queue (Execution Order)

### P0 - Immediate
- [x] Gemini integration in content agent with grounded prompt + fallback
- [x] Minimal frontend flow (start -> answer -> dashboard)
- [x] Automated smoke script

### P1 - Stabilization
- [x] Structured logs + better error handling
- [ ] DB indexes + migration baseline
- [ ] Hybrid retrieval quality improvement

### P2 - Demo Polish
- [ ] UI polish and clearer adaptation visualization
- [x] Final README + architecture docs + demo walkthrough

---

## 10) Exit Criteria for MVP

- [ ] End-to-end flow works from frontend on fresh `docker compose up --build`
- [ ] `/start-session`, `/submit-answer`, `/dashboard` stable across reruns
- [ ] Gemini content path active with fallback
- [ ] RAG context visibly influences explanation output
- [ ] Evaluator can run locally with only Docker + Ollama + API key
