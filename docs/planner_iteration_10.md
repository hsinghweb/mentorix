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

- [ ] Build Session 19 concept checklist from source materials.
- [ ] Map each concept to current implementation (implemented / partial / missing).
- [ ] Implement missing concepts with minimal disruption.
- [ ] Refactor for structured reasoning patterns where required.
- [ ] Integrate standardized tool invocation logic per Session 19.
- [ ] Add/upgrade state tracking mechanisms for reasoning lifecycle.
- [ ] Improve agent memory usage patterns (short-term + long-term where applicable).
- [ ] Add validation tests for each Session 19 concept.

### Acceptance
- [ ] 100% Session 19 checklist coverage marked implemented or intentionally deferred with rationale.
- [ ] Tests prove operational usage of introduced concepts.

---

## 3. MCP Server-Client Adoption [P1]

- [ ] Audit model/tool usage points for direct calls and hardcoded context handling.
- [ ] Identify MCP-eligible components and migration scope.
- [ ] Implement MCP server modules for context/tool exposure.
- [ ] Implement MCP client request flow for structured model interactions.
- [ ] Standardize request/response contract and error semantics.
- [ ] Remove redundant non-MCP direct model-call paths where migrated.
- [ ] Add observability for MCP calls (latency, failures, fallback usage).

### Acceptance
- [ ] Migrated paths route through MCP contracts.
- [ ] Equivalent or better behavior vs pre-migration paths.
- [ ] Extensibility improved (new tools/context providers are pluggable).

---

## 4. CLAUDE Skills Modularity Integration [P1]

- [ ] Identify reusable reasoning/tool patterns suitable as CLAUDE skills.
- [ ] Convert patterns into modular CLAUDE skill units.
- [ ] Define clear input/output contracts for each skill.
- [ ] Ensure each skill is independently testable.
- [ ] Refactor dependent code to consume skills instead of duplicated logic.
- [ ] Reduce coupling and improve readability/changeability across modules.
- [ ] Confirm compatibility with latest supported CLAUDE skill architecture.

### Acceptance
- [ ] Reused logic is centralized into skills with tests.
- [ ] Cross-agent reuse is demonstrable in production code paths.

---

## 5. Calendar-Based Week Tracking (Real Date Mapping) [P1]

- [ ] Capture onboarding date as canonical learner timeline start.
- [ ] Implement week-date computation (start/end) from onboarding date.
- [ ] Make week mapping timezone-safe and deterministic.
- [ ] Return date-mapped week labels in dashboard/plan APIs.
- [ ] Support UI display format, e.g. `Week 1 (Mar 3 - Mar 9, 2026)`.
- [ ] Add timeline visualization data payload (backend-ready for frontend rendering).
- [ ] Add completion date estimation based on active pace.

### Acceptance
- [ ] Numeric week and calendar range are both available everywhere required.
- [ ] Plan/progress views align to real calendar dates correctly.

---

## 6. Comparative Student Performance Analytics (Backend) [P1]

- [ ] Define analytics schema and pipeline for individual + cohort metrics.
- [ ] Implement individual analytics:
  - [ ] Topic mastery score
  - [ ] Time spent per topic
  - [ ] Weak vs strong areas
  - [ ] Learning velocity
  - [ ] Completion rate
- [ ] Implement comparative analytics:
  - [ ] Percentile ranking
  - [ ] Average vs cohort
  - [ ] Similar learner cluster comparison
  - [ ] Improvement trend over time
- [ ] Implement anonymized aggregation and secure data handling controls.
- [ ] Expose dashboard-ready structured analytics outputs.
- [ ] Add scalability checks for analytics computation path.
- [ ] Add hooks for future adaptive difficulty + early warning signals.

### Acceptance
- [ ] API exposes stable analytics payloads for individual and comparative views.
- [ ] Cohort metrics are anonymized and privacy-safe.
- [ ] Computation remains performant at expected scale.

---

## 7. Student Email Capture and Automated Weekly Reminders [P1]

- [ ] Add required `student_email` field to onboarding flow.
- [ ] Validate email format and block duplicate email registrations.
- [ ] Persist email reminder profile fields:
  - [ ] `email`
  - [ ] `onboarding_date`
  - [ ] `current_week`
  - [ ] `progress_status` / `progress_percentage`
  - [ ] `last_reminder_sent_at`
  - [ ] `reminder_enabled`
- [ ] Implement reminder eligibility checks:
  - [ ] week incomplete
  - [ ] inactivity window exceeded
  - [ ] deadline proximity
- [ ] Implement static reminder mode:
  - [ ] every 3 days when week incomplete
  - [ ] 1 day before week deadline
- [ ] Implement dynamic reminder mode (recommended):
  - [ ] progress below threshold at mid-week
  - [ ] no login/activity in last 3 days
  - [ ] below cohort average
  - [ ] repeated weak performance signal
- [ ] Build email service module (`services/email_service.py`) with:
  - [ ] Gmail SMTP/Gmail API support
  - [ ] structured HTML templates
  - [ ] retry and failure logging
  - [ ] delivery audit logs
- [ ] Add scheduler/worker for daily reminder scans and dispatch.
- [ ] Add environment configuration support:
  - [ ] `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_FROM`
  - [ ] optional Gmail API credentials
- [ ] Add reminder safety controls:
  - [ ] unsubscribe/disable reminders
  - [ ] anti-spam rate limit
  - [ ] secure handling of email data and secrets

### Acceptance
- [ ] Onboarding captures and stores valid student email reliably.
- [ ] Eligible students receive reminders with correct week/progress context.
- [ ] Reminder sends are traceable, rate-limited, and resilient to transient failures.

---

## 8. Verification and Rollout [P2]

- [ ] Add architecture conformance tests (agent boundaries + orchestration).
- [ ] Add MCP contract tests and fallback behavior tests.
- [ ] Add CLAD skill unit tests and integration tests.
- [ ] Add calendar mapping edge-case tests (timezone/date boundary).
- [ ] Add analytics validation tests (correctness + anonymization).
- [ ] Prepare migration notes and rollback strategy for architecture changes.
- [ ] Update technical docs for new architecture/runtime contracts.

### Acceptance
- [ ] Test suite passes for all new architecture layers.
- [ ] Rollout plan includes migration and rollback safety.

---

## Suggested Execution Order

1. P0.1 Session 17 compliance baseline and refactor plan  
2. P0.2 Session 19 concept gap closure  
3. P1.3 MCP migration for highest-value paths  
4. P1.4 CLAD skill extraction and reuse  
5. P1.5 Calendar week-date mapping  
6. P1.6 Comparative analytics backend  
7. P1.7 Student email capture and reminder automation  
8. P2.8 Verification, docs, and rollout readiness
