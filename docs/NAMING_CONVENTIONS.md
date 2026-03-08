# Mentorix Naming Conventions

## Python / Backend

| Entity | Convention | Example |
|--------|-----------|---------|
| **Modules** | `snake_case.py` | `learner_state_profile.py` |
| **Classes** | `PascalCase` | `LearnerProfile`, `AgentInterface` |
| **Functions** | `snake_case` | `compute_login_streak_days` |
| **Private helpers** | `_snake_case` | `_build_rough_plan` |
| **Constants** | `UPPER_SNAKE_CASE` | `COMPLETION_THRESHOLD`, `MAX_CHAPTER_ATTEMPTS` |
| **Pydantic models** | `PascalCase` + suffix | `ContentRequest`, `DashboardResponse` |
| **Database models** | `PascalCase` (singular) | `Task`, `LearnerProfile`, `AssessmentResult` |

## Package Directories

| Type | Convention | Example |
|------|-----------|---------|
| **API routes** | `api/<domain>/` package | `api/learning/`, `api/onboarding/` |
| **Schemas** | `schemas/<domain>.py` | `schemas/onboarding.py` |
| **Services** | `services/<domain>.py` | `services/shared_helpers.py` |
| **Agents** | `agents/<name>.py` | `agents/assessment.py` |
| **Core infra** | `core/<feature>.py` | `core/csrf.py`, `core/metrics_base.py` |

## Frontend / JavaScript

| Entity | Convention | Example |
|--------|-----------|---------|
| **Files** | `camelCase.js` or `snake_case.js` | `renderer.js`, `app.js` |
| **Functions** | `camelCase` | `renderKaTeX`, `loadDashboard` |
| **Constants** | `UPPER_SNAKE_CASE` | `TOKEN_KEY`, `API_BASE_KEY` |
| **CSS classes** | `kebab-case` | `chapter-progress-bar`, `reading-status` |
| **HTML IDs** | `kebab-case` | `test-chapter-title`, `btn-submit-chapter-test` |

## Git / Files

| Type | Convention | Example |
|------|-----------|---------|
| **Branches** | `feature/<slug>`, `fix/<slug>` | `feature/csrf-protection` |
| **Docs** | `UPPER_CASE.md` | `DEVELOPER_GUIDE.md`, `DECISION_LOG.md` |
| **Config** | `lower_case` | `.env.example`, `docker-compose.yml` |
| **Scripts** | `snake_case.py` or `snake_case.sh` | `seed_test_data.py`, `test_fast.sh` |
