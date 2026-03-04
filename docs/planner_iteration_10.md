# Mentorix V2 - Planner Iteration 10 (Architecture Compliance, MCP, Skills, Calendar, Analytics)

**Date:** 2026-03-03  
**Purpose:** Enforce Session 17/19 architecture standards, adopt MCP + CLAUDE SKILLS, add calendar-aware planning, and implement comparative analytics.

> [!IMPORTANT]
> This iteration is architecture-heavy. Execute in small vertical slices and keep all public APIs backward-compatible unless explicitly versioned.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Architecture correctness / platform direction |
| **P1** | Core implementation and integration |
| **P2** | Documentation, rollout safety, and observability |

---

## 1. Session 17 Multi-Agent Architecture Compliance [P0]

- [x] Audit current backend/frontend orchestration against Session 17 blueprint.
- [x] Verify clear separation and ownership for agent roles:
  - [x] Planner
  - [x] Executor
  - [x] Memory
  - [x] Evaluator
  - [x] Other defined Session 17 roles (if present in spec)
- [x] Identify monolithic flows violating role boundaries.
- [x] Refactor violating flows into modular agent-based components.
- [x] Standardize inter-agent communication protocol and contracts.
- [x] Align orchestration control flow with Session 17 design principles.
- [x] Add explicit in-code responsibility docs per agent module.

### Acceptance
- [x] No critical flow contains mixed responsibilities across agent roles.
- [x] Inter-agent interfaces are documented and testable.
- [x] Architecture map matches Session 17 expectations.

---

## 2. Session 19 Concept Integration [P0]

- [x] Build Session 19 concept checklist from source materials.
- [x] Map each concept to current implementation (implemented / partial / missing).
- [x] Implement missing concepts with minimal disruption.
- [x] Refactor for structured reasoning patterns where required.
- [x] Integrate standardized tool invocation logic per Session 19.
- [x] Add/upgrade state tracking mechanisms for reasoning lifecycle.
- [x] Improve agent memory usage patterns (short-term + long-term where applicable).
- [x] Add validation tests for each Session 19 concept.

### Acceptance
- [x] 100% Session 19 checklist coverage marked implemented or intentionally deferred with rationale.
- [x] Tests prove operational usage of introduced concepts.

---

## 3. MCP Server-Client Adoption [P1]

- [x] Audit model/tool usage points for direct calls and hardcoded context handling.
- [x] Identify MCP-eligible components and migration scope.
- [x] Implement MCP server modules for context/tool exposure.
- [x] Implement MCP client request flow for structured model interactions.
- [x] Standardize request/response contract and error semantics.
- [x] Remove redundant non-MCP direct model-call paths where migrated.
- [x] Add observability for MCP calls (latency, failures, fallback usage).

### Acceptance
- [x] Migrated paths route through MCP contracts.
- [x] Equivalent or better behavior vs pre-migration paths.
- [x] Extensibility improved (new tools/context providers are pluggable).

---

## 4. CLAUDE Skills Modularity Integration [P1]

- [x] Identify reusable reasoning/tool patterns suitable as CLAUDE skills.
- [x] Convert patterns into modular CLAUDE skill units.
- [x] Define clear input/output contracts for each skill.
- [x] Ensure each skill is independently testable.
- [x] Refactor dependent code to consume skills instead of duplicated logic.
- [x] Reduce coupling and improve readability/changeability across modules.
- [x] Confirm compatibility with latest supported CLAUDE skill architecture.

### Acceptance
- [x] Reused logic is centralized into skills with tests.
- [x] Cross-agent reuse is demonstrable in production code paths.

---

## 5. Calendar-Based Week Tracking (Real Date Mapping) [P1]

- [x] Capture onboarding date as canonical learner timeline start.
- [x] Implement week-date computation (start/end) from onboarding date.
- [x] Make week mapping timezone-safe and deterministic.
- [x] Return date-mapped week labels in dashboard/plan APIs.
- [x] Support UI display format, e.g. `Week 1 (Mar 3 - Mar 9, 2026)`.
- [x] Add timeline visualization data payload (backend-ready for frontend rendering).
- [x] Add completion date estimation based on active pace.

### Acceptance
- [x] Numeric week and calendar range are both available everywhere required.
- [x] Plan/progress views align to real calendar dates correctly.

---

## 6. Comparative Student Performance Analytics (Backend) [P1]

- [x] Define analytics schema and pipeline for individual + cohort metrics.
- [x] Implement individual analytics:
  - [x] Topic mastery score
  - [x] Time spent per topic
  - [x] Weak vs strong areas
  - [x] Learning velocity
  - [x] Completion rate
- [x] Implement comparative analytics:
  - [x] Percentile ranking
  - [x] Average vs cohort
  - [x] Similar learner cluster comparison
  - [x] Improvement trend over time
- [x] Implement anonymized aggregation and secure data handling controls.
- [x] Expose dashboard-ready structured analytics outputs.
- [x] Add scalability checks for analytics computation path.
- [x] Add hooks for future adaptive difficulty + early warning signals.

### Acceptance
- [x] API exposes stable analytics payloads for individual and comparative views.
- [x] Cohort metrics are anonymized and privacy-safe.
- [x] Computation remains performant at expected scale.

---

## 7. Student Email Capture and Automated Weekly Reminders [P1]

- [x] Add required `student_email` field to onboarding flow.
- [x] Validate email format and block duplicate email registrations.
- [x] Persist email reminder profile fields:
  - [x] `email`
  - [x] `onboarding_date`
  - [x] `current_week`
  - [x] `progress_status` / `progress_percentage`
  - [x] `last_reminder_sent_at`
  - [x] `reminder_enabled`
- [x] Implement reminder eligibility checks:
  - [x] week incomplete
  - [x] inactivity window exceeded
  - [x] deadline proximity
- [x] Implement static reminder mode:
  - [x] every 3 days when week incomplete
  - [x] 1 day before week deadline
- [x] Implement dynamic reminder mode (recommended):
  - [x] progress below threshold at mid-week
  - [x] no login/activity in last 3 days
  - [x] below cohort average
  - [x] repeated weak performance signal
- [x] Build email service module (`services/email_service.py`) with:
  - [x] Gmail SMTP/Gmail API support
  - [x] structured HTML templates
  - [x] retry and failure logging
  - [x] delivery audit logs
- [x] Add scheduler/worker for daily reminder scans and dispatch.
- [x] Add environment configuration support:
  - [x] `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_FROM`
  - [x] optional Gmail API credentials
- [x] Add reminder safety controls:
  - [x] unsubscribe/disable reminders
  - [x] anti-spam rate limit
  - [x] secure handling of email data and secrets

### Acceptance
- [x] Onboarding captures and stores valid student email reliably.
- [x] Eligible students receive reminders with correct week/progress context.
- [x] Reminder sends are traceable, rate-limited, and resilient to transient failures.

---

## 8. Verification and Rollout [P2]

- [x] Add architecture conformance tests (agent boundaries + orchestration).
- [x] Add MCP contract tests and fallback behavior tests.
- [x] Add CLAD skill unit tests and integration tests.
- [x] Add calendar mapping edge-case tests (timezone/date boundary).
- [x] Add analytics validation tests (correctness + anonymization).
- [x] Prepare migration notes and rollback strategy for architecture changes.
- [x] Update technical docs for new architecture/runtime contracts.

### Acceptance
- [x] Test suite passes for all new architecture layers.
- [x] Rollout plan includes migration and rollback safety.

---

## Suggested Execution Order

1. P0.1 Session 17 compliance baseline and refactor plan  
2. P0.2 Session 19 concept gap closure  
3. P1.3 MCP migration for highest-value paths  
4. P1.4 CLAUDE skill extraction and reuse  
5. P1.5 Calendar week-date mapping  
6. P1.6 Comparative analytics backend  
7. P1.7 Student email capture and reminder automation  
8. P2.8 Verification, docs, and rollout readiness
