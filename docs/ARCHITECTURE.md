# Mentorix Architecture

## System Overview

```mermaid
flowchart TD
    subgraph Frontend
        UI["app.js (SPA)"]
        CSS["styles.css"]
    end

    subgraph API Layer
        MAIN["main.py (FastAPI)"]
        AUTH["auth.py"]
        HEALTH["health.py"]
        ONBOARD["onboarding.py"]
        LEARN["learning.py"]
        ADMIN["admin.py"]
        METRICS["metrics.py"]
        SCHED["scheduler.py"]
    end

    subgraph Core
        LLM["llm_provider.py"]
        RESIL["resilience.py (Circuit Breakers)"]
        CONFIG["config_governance.py"]
        SETTINGS["settings.py"]
        MODEL_REG["model_registry.py"]
        JWT["jwt_auth.py"]
    end

    subgraph Agents
        ORCH["Orchestrator"]
        OB_AGENT["OnboardingAgent"]
        ASSESS_AGENT["AssessmentAgent"]
        REFLECT_AGENT["ReflectionAgent"]
    end

    subgraph Memory
        DB["PostgreSQL (Structured)"]
        MONGO["MongoDB (Content Cache)"]
        REDIS["Redis (Session/Cache)"]
        STORE["store.py"]
    end

    subgraph Telemetry
        LLM_TEL["llm_telemetry.py"]
        ERR_TRACK["error_rate_tracker.py"]
        APP_MET["app_metrics.py"]
    end

    subgraph RAG
        GROUNDING["grounding_ingest.py"]
        RETRIEVAL["retrieval.py"]
        MCP["MCP Providers"]
    end

    UI -->|fetch API| MAIN
    MAIN --> AUTH & HEALTH & ONBOARD & LEARN & ADMIN & METRICS & SCHED
    ONBOARD --> LLM & DB & MONGO
    LEARN --> LLM & DB & MONGO & RETRIEVAL
    LLM --> RESIL --> ERR_TRACK
    LLM --> LLM_TEL
    LLM --> MODEL_REG
    RETRIEVAL --> GROUNDING --> MCP
    STORE --> MONGO & DB
    MAIN -->|startup| CONFIG
```

## Data Flow: Student Journey

```mermaid
sequenceDiagram
    participant S as Student (Browser)
    participant F as Frontend (app.js)
    participant A as API (FastAPI)
    participant L as LLM (Gemini/Ollama)
    participant D as Database (PostgreSQL)

    S->>F: Login
    F->>A: POST /auth/login
    A->>D: Verify credentials
    A-->>F: JWT token

    S->>F: Take Diagnostic
    F->>A: POST /onboarding/diagnostic
    A->>L: Generate MCQ questions
    L-->>A: Questions
    A-->>F: Test data

    S->>F: Submit Diagnostic
    F->>A: POST /onboarding/submit
    A->>D: Score + create plan
    A-->>F: Results + redirected to dashboard

    S->>F: Load Dashboard
    F->>A: GET /learning/dashboard/{id}
    A->>D: Query 8+ tables
    A-->>F: Dashboard data (profile, tasks, progress)

    S->>F: Read Content
    F->>A: GET /learning/content/{chapter}
    A->>L: Generate content (grounded)
    L-->>A: Content
    A-->>F: Rendered material

    S->>F: Take Test
    F->>A: POST /learning/test
    A->>L: Generate test
    A-->>F: Questions
    S->>F: Submit Test
    F->>A: POST /learning/submit-test
    A->>D: Record scores, update mastery
    A-->>F: Results + feedback
```

## Module Dependencies

| Module | Depends On | Used By |
|--------|-----------|---------|
| `llm_provider.py` | resilience, model_registry, settings, llm_telemetry, error_rate_tracker | learning.py, onboarding.py |
| `resilience.py` | (standalone) | llm_provider.py, health.py |
| `config_governance.py` | model_registry, settings | main.py (startup) |
| `llm_telemetry.py` | (standalone) | llm_provider.py |
| `error_rate_tracker.py` | (standalone) | llm_provider.py |
| `store.py` | settings, pymongo | health.py, persistence.py |
| `database.py` | settings | all route handlers |
