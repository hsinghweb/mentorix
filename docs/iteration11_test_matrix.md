# Iteration 11 Test Matrix (Local / Docker / CI)

Date: 2026-03-04

## Profiles

- Fast/Critical: quick confidence for active dev.
- Full: complete API test suite + UI smoke.

## Commands

### Local (with Docker services running)

- Fast:
  - `powershell -ExecutionPolicy Bypass -File .\\scripts\\test_fast.ps1`
- Full:
  - `powershell -ExecutionPolicy Bypass -File .\\scripts\\test_full.ps1 -BaseUrl http://localhost:8000`
- Frontend sanitization:
  - `node frontend/tests/math_sanitize_cases.js`

### Docker

- Build + run:
  - `docker compose up -d --build`
- API-only rebuild:
  - `docker compose up -d --build api`

### CI (recommended)

1. `docker compose up -d --build api`
2. `powershell -ExecutionPolicy Bypass -File .\\scripts\\test_fast.ps1`
3. `powershell -ExecutionPolicy Bypass -File .\\scripts\\test_full.ps1 -BaseUrl http://localhost:8000`

## Notes

- API Docker image includes dev extra dependencies (`pytest`, `pytest-asyncio`) for test parity.
- `.dockerignore` allows `API/tests` to ensure in-container pytest paths resolve.
