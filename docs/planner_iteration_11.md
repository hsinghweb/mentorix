# Mentorix V2 - Planner Iteration 11 (UI-Driven Consolidation, MCP Adoption, Reliability)

**Date:** 2026-03-04  
**Purpose:** Consolidate the student journey around actively used UI paths, improve observability, and harden reliability before deeper feature expansion.

> [!IMPORTANT]
> Iteration 11 implementation and validation are complete. Status below reflects executed work.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Critical path correctness / architecture alignment |
| **P1** | Core product behavior and student journey quality |
| **P2** | Cleanup, docs, rollout safety, and optimization |

---

## 1. UI-Driven Backend Cleanup (Delete Unused Code) [P0]

**Goal:** Keep only backend code required for the current student product journey in UI.

- [x] Lock the in-scope UI journey as source of truth:
  - [x] Signup/Login
  - [x] Onboarding (diagnostic, plan init)
  - [x] Learning flow (read/test/practice/task completion)
  - [x] Dashboard (progress, confidence, roadmap, comparative analytics)
  - [x] Reminder-related UX and result-analysis views currently exposed to student/admin UI
- [x] Create endpoint inventory from all backend API modules and classify each route:
  - [x] `UI-USED` (called by frontend student/admin UI)
  - [x] `UI-INDIRECT` (needed by background jobs that power visible UI features, e.g. reminders)
  - [x] `NON-UI-LEGACY` (not used by UI product journey)
- [x] Create function/module-level call map for `NON-UI-LEGACY` candidates.
- [x] Add deletion decision rules:
  - [x] Delete only when confidently unused from UI journey and no indirect dependency.
  - [x] If any uncertainty exists, keep code and mark as `DEFERRED-SUSPECT`.
  - [x] Never delete code solely because it is old; delete only with evidence.
- [x] Produce explicit delete list (`SAFE-DELETE`) with file paths and rationale.
- [x] Remove `SAFE-DELETE` code and related dead imports/constants/tests.
- [x] Keep `DEFERRED-SUSPECT` list in docs for later review.
- [x] Run regression checks for full UI journey after cleanup.

### Acceptance
- [x] Backend contains only code required for current UI product journey plus explicitly documented deferred suspects.
- [x] Every deletion has evidence (UI call map + code reference).
- [x] No student/admin UI flow regresses after cleanup.

### Task 1 Progress Notes (2026-03-04)

- Aggressive cleanup wave completed for clear non-UI legacy code:
  - Removed legacy session and memory APIs (`api/sessions.py`, `api/memory.py`) and linked schema/agent modules.
  - Removed non-UI routes/modules (`api/events.py`, `api/notifications.py`, `api/runs.py`).
  - Removed legacy session-focused tests (`API/tests/test_session17_compliance.py`, `API/tests/test_session19_concepts.py`).
- Regression validation completed:
  - `scripts/test_fast.ps1` passed.
  - `scripts/test_full.ps1` passed.
  - `scripts/test_mvp.ps1` passed.

---

## 2. MCP Adoption for Student-Critical Flows [P0]

- [x] Audit current MCP usage vs non-MCP paths in student journey.
- [x] Expand MCP contract usage into selected high-value onboarding/learning flows.
- [x] Ensure consistent fallback behavior when MCP dispatch fails.
- [x] Extend MCP observability dashboards (counts, failures, fallback rate by operation).
- [x] Add operator-facing runbook for interpreting MCP metrics.

### Acceptance
- [x] Student-critical flows use MCP where planned.
- [x] MCP metrics clearly reflect active traffic and fallback behavior.

---

## 3. Student Dashboard Enhancements and Insights UX [P1]

- [x] Refine comparative analytics panel UX (clarity, labels, loading, empty state).
- [x] Add optional quick-link drilldowns for weak areas and recommendations.
- [x] Ensure comparative signals are understandable and non-misleading with small cohorts.
- [x] Add visual consistency pass across roadmap, confidence, and comparative cards.

### Acceptance
- [x] Comparative analytics is clear and actionable for students.
- [x] No broken/empty-state UI regressions.

---

## 4. Reminder and Email Reliability Hardening [P1]

- [x] Add reminder diagnostics endpoint/view for configuration readiness checks.
- [x] Improve reminder error transparency (delivery failure cause taxonomy).
- [x] Add retry policy tuning and dead-letter style logging for failed sends.
- [x] Validate anti-spam/rate-limit behavior under repeated dispatch attempts.
- [x] Document environment precedence clearly (`.env` vs `CONFIG/local.env` in Docker).

### Acceptance
- [x] Reminder delivery failures are diagnosable in one place.
- [x] Reminder system is stable under repeated dispatch and scheduler loops.

---

## 5. Content Rendering Robustness (Math/Markdown) [P1]

- [x] Expand frontend math-sanitization guardrails for malformed delimiters.
- [x] Add regression test cases for common broken render patterns.
- [x] Improve fallback rendering behavior for partially malformed content.

### Acceptance
- [x] Reading content avoids red/error rendering for known malformed patterns.

---

## 6. Test Suite Stabilization and Runtime Parity [P1]

- [x] Split fast/critical test profile vs full suite profile.
- [x] Ensure async test dependencies are present in canonical test environment.
- [x] Align local, Docker, and CI test commands.
- [x] Add smoke tests for new comparative/reminder/dashboard integrations.

### Acceptance
- [x] Fast profile is reliable for rapid iteration.
- [x] Full profile is reproducible across environments.

---

## 7. Documentation and Rollout Controls [P2]

- [x] Write iteration-11 migration and deprecation notes.
- [x] Update operator troubleshooting guide (scheduler, reminders, MCP metrics).
- [x] Add rollback checklist for MCP and route cleanup changes.
- [x] Finalize rollout sequence and validation checklist.

### Acceptance
- [x] Docs are sufficient for safe deployment and rollback.

## Completion Evidence

- Fast profile: `scripts/test_fast.ps1` passed.
- Full profile: `scripts/test_full.ps1` passed (`25 passed` + smoke).
- Additional frontend guardrail regression: `node frontend/tests/math_sanitize_cases.js` passed.

---

## Suggested Execution Order

1. P0.1 UI-driven route audit and cleanup candidate map  
2. P0.2 MCP adoption for student-critical flows  
3. P1.4 Reminder/email reliability hardening  
4. P1.6 Test-suite stabilization and environment parity  
5. P1.3 Dashboard/comparative UX refinement  
6. P1.5 Content rendering robustness  
7. P2.7 Docs, rollout controls, and deprecation plan
