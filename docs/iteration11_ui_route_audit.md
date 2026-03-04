# Iteration 11 - UI Route Audit and Cleanup Map

Date: 2026-03-04

## 1) UI Source-of-Truth Endpoints (from `frontend/app.js`)

Student UI currently calls:

- `POST /auth/login`
- `POST /auth/start-signup`
- `POST /onboarding/diagnostic-questions`
- `POST /onboarding/submit`
- `GET /learning/dashboard/{learner_id}`
- `POST /learning/week/advance?learner_id=...`
- `POST /learning/content`
- `POST /learning/reading/complete`
- `POST /learning/test/generate`
- `POST /learning/test/submit`
- `GET /learning/chapter/{chapter_number}/sections/{learner_id}`
- `POST /learning/content/section`
- `POST /learning/test/section/generate`
- `POST /learning/test/question/explain`
- `GET /learning/plan-history/{learner_id}`
- `GET /learning/confidence-trend/{learner_id}`
- `GET /onboarding/comparative-analytics/{learner_id}`

## 2) Classification Summary

### UI-USED

- `API/app/api/auth.py` (`/login`, `/start-signup`)
- `API/app/api/onboarding.py` (`/diagnostic-questions`, `/submit`, `/comparative-analytics/*`)
- `API/app/api/learning.py` routes listed above

### UI-INDIRECT (powers visible UI features but not directly called by current student page)

- `API/app/api/onboarding.py` reminder routes and reminder services
- scheduler loop for reminder dispatch when enabled

### NON-UI-LEGACY candidates (high confidence)

- `POST /learning/practice/generate` (frontend practice uses `/learning/test/section/generate`)
- `GET /learning/plan/history/{learner_id}` (legacy alias; frontend uses `/learning/plan-history/{learner_id}`)

## 3) SAFE-DELETE Performed

1. Removed `POST /learning/practice/generate` route and its request model.
2. Removed legacy alias route `GET /learning/plan/history/{learner_id}`.
3. Kept canonical route `GET /learning/plan-history/{learner_id}`.
4. Removed non-UI API modules and routes:
   - `API/app/api/runs.py` (`/runs/*`)
   - `API/app/api/events.py` (`/events/stream`)
   - `API/app/api/notifications.py` (`/notifications*`)
   - Removed router registration from `API/app/main.py`.
5. Removed legacy non-UI session and memory API surface:
   - `API/app/api/sessions.py` (`/start-session`, `/submit-answer`, legacy root `/dashboard/{learner_id}`)
   - `API/app/api/memory.py` (`/memory/*`)
   - `API/app/schemas/session.py`
   - `API/app/agents/memory_manager.py`
   - Removed router registration/imports from `API/app/main.py`.
6. Removed legacy session-focused test paths not aligned to current student UI journey:
   - `API/tests/test_session17_compliance.py`
   - `API/tests/test_session19_concepts.py`

## 4) DEFERRED-SUSPECT (not deleted yet due dependency risk)

- Admin/metrics/scheduler/runs/events/memory operator routes
  - Reason: not student-UI driven but potentially required for operations and diagnostics.
- Onboarding legacy helper routes (`/start`, `/tasks`, `/schedule`, etc.)
  - Reason: used by some integration paths/tests; requires staged deprecation.

## 5) Deletion Decision Rule Applied

- Deleted only routes with direct evidence of replacement and zero student-UI calls.
- Deferred anything with uncertain indirect/runtime dependency.

## 6) Regression Validation Status

- Fast profile:
  - `scripts/test_fast.ps1` -> passed
- Full profile:
  - `scripts/test_full.ps1` -> passed (`25 passed`)
- UI smoke:
  - `scripts/test_mvp.ps1` -> passed
