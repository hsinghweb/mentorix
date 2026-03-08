# Mentorix V2 - Planner Iteration 12

**Date:** 2026-03-07
**Purpose:** Iteration 12 implementation tracker.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Critical path correctness / architecture alignment |
| **P1** | Core product behavior and student journey quality |
| **P2** | Cleanup, docs, rollout safety, and optimization |

---

## Tasks

## 1. Brand Message Under Logo/Title [P1]

- [x] Add a mission statement below the Mentor logo and application title.
- [x] Use exact text: `Agentic, Autonomous, and Adaptive Learning System`.
- [x] Ensure it is visible and well-positioned in the auth/landing header area.
- [x] Keep styling aligned with the existing product branding.

### Acceptance

- [x] The mission statement appears directly below the logo/title.
- [x] The text matches exactly: `Agentic, Autonomous, and Adaptive Learning System`.

---

## 2. Refer Actual NCERT Section Content from UI [P1]

- [x] Add a way for students to open/reference the real NCERT book content for the current chapter subsection.
- [x] Support this for subsection reading views, for example while reading `1.1`, `1.2`, etc.
- [x] Support this for subsection test views, so a student taking the section test can also refer back to the real book content.
- [x] Use the existing chapter/subsection-grounded content already loaded and mapped in the database.
- [x] Ensure the reference points to the correct chapter and subsection source content, not just the generated summary.
- [x] Design the UX so the student can jump to the book content without losing context of the current learning flow.
- [x] Keep this clearly distinguished from generated/adapted reading material.

### Acceptance

- [x] A student can access the real NCERT source content for a subsection directly from the section reading screen.
- [x] A student can access the real NCERT source content for a subsection directly from the section test screen.
- [x] The reference is section-specific, for example `1.1` opens/reveals the actual `1.1` source content.
- [x] The UI makes it clear which content is generated/adaptive and which content is the original NCERT source.

---

## 3. Simplify Student Comparative Analytics View [P1]

- [x] Reduce the amount of comparative analytics information shown to students on the main dashboard.
- [x] Keep only the most readable and student-relevant comparative insights.
- [x] Preserve useful student-facing actions such as weak-area drilldown and recommended next moves.
- [x] Remove or hide overly technical/statistical metrics that are better suited for admin/operator interpretation.
- [x] Rework labels and presentation so a Class 10 student can understand the analytics without needing interpretation help.
- [x] Add a clear tooltip/help message for every comparative metric that remains visible.
- [x] Ensure each tooltip explains both the meaning and purpose of that metric in simple language.
- [x] Make the comparative analytics section visually lighter and less crowded than the current version.

### Acceptance

- [x] The comparative analytics section shows fewer cards/metrics than the current implementation.
- [x] The remaining metrics are understandable to a Class 10 student.
- [x] Every visible comparative metric has a tooltip/help explanation.
- [x] Student-facing actions remain available without overwhelming the student with too many statistics.

---

## 4A. Admin Login and System Observability View [P0]

- [x] Add a separate admin login flow, distinct from the student page.
- [x] Support a simple initial admin credential setup for MVP, for example username `admin` and password `admin`.
- [x] Ensure only admin users can access the admin page/view.
- [x] After admin login, show a different admin-specific interface instead of the student learning page.
- [x] Add an admin system observability view focused on platform/runtime health.
- [x] Surface system-level information relevant to operations, such as API/system performance and request health.
- [x] Include infrastructure-oriented visibility where available, such as database, Redis cache, MongoDB, and PostgreSQL-related signals.
- [x] Show whether the system is handling load properly, including request success/failure and overall service condition.
- [x] Present observability data in a way that is useful for someone monitoring system performance.

### Acceptance

- [x] An admin can log in through a dedicated admin path/view.
- [x] Admin login opens a different interface from the student UI.
- [x] The admin can view system observability/performance information in one place.
- [x] The admin page provides useful operational visibility into service health, load, and request outcomes.

---

## 4B. Admin Student Monitoring and Control Room View [P0]

- [x] Add an admin-only student analytics/control-room page.
- [x] Show all students currently on the platform, or otherwise all active students available to the system.
- [x] Let the admin view each student's detailed learning analytics beyond what is shown on the student page.
- [x] Include richer student-level performance details that may be too complex for the student-facing UI.
- [x] Enable cohort/student comparison from the admin view so weaker and stronger students can be identified clearly.
- [x] Help the admin understand where each student is lacking and what kind of support/intervention may be needed.
- [x] Provide a visual overview so the admin can quickly judge how students are performing across the platform.
- [x] Design this as a practical monitoring/control-room experience rather than a student-style dashboard.
- [x] Keep future intervention hooks in mind, for example later support for sending email/message nudges to weaker students.

### Acceptance

- [x] An admin can view a list/overview of students from the admin interface.
- [x] An admin can inspect detailed analytics for individual students.
- [x] An admin can compare students and identify weaker learners clearly.
- [x] The admin page provides actionable visibility that can later support outreach/intervention workflows.

---

## 4C. Admin Multi-Agent Orchestration Visualization [P0]

- [x] Add an admin-only visualization showing how the multi-agent system is connected and coordinated.
- [x] Represent the orchestrator and the different agents involved in the platform.
- [x] Show each agent with its name and clear purpose/responsibility.
- [x] Reflect how agents are triggered during key flows such as onboarding, study, test generation, content generation, regeneration, and test submission.
- [x] Show runtime status for each agent, for example `idle`, `working`, `completed`, or similar states.
- [x] Display a short human-readable hint of what an active agent is currently doing, for example planning, generating content, evaluating, etc.
- [x] Show completion state/output summary in a simple way when an agent finishes a task.
- [x] Use strong visual cues such as color/status coding so the admin can quickly understand current agent activity.
- [x] Make the visualization understandable enough that the admin can see how agents interact and hand off work through the orchestrator.

### Acceptance

- [x] The admin can see a visual representation of the orchestrator and relevant agents.
- [x] Each agent shows name, purpose, and current status.
- [x] Active work is visible in a human-readable way.
- [x] The admin can understand how agents are triggered and interact during major platform workflows.

---

## Validation

- [x] `python -m py_compile API/app/api/auth.py API/app/api/admin.py API/app/api/learning.py API/app/api/onboarding.py API/app/core/jwt_auth.py API/app/core/settings.py`
- [x] `node --check frontend/app.js`
- [x] `PYTHONPATH=API python -c "import app.api.admin, app.api.auth, app.api.learning, app.api.onboarding"`

---

## 5. Adaptive Week Progression and Timeline Compression [P0]

- [x] Fix week advancement so a chapter completed in `completed_first_attempt` state is treated as fully completed for next-week planning.
- [x] Ensure Week 2 does not repeat Chapter 1 when Chapter 1 is already completed in Week 1.
- [x] Rebuild future rough-plan weeks from actual chapter progression state instead of appending stale onboarding plan rows.
- [x] Generate next-week tasks from the first truly incomplete chapter in syllabus order.
- [x] Preserve past committed weeks while re-planning future weeks.
- [x] Add actual week-start override support so when a week is completed early, the next week can begin immediately.
- [x] Use actual week-start overrides for dashboard/plan/schedule week labels and calendar ranges.
- [x] Update scheduled completion date calculation so early completion visibly pulls the end date forward.
- [x] Keep active-pace completion estimation alongside scheduled timeline date.
- [x] Add targeted regression tests for chapter rollover and early-start week-date compression.

### Acceptance

- [x] If Chapter 1 is completed in Week 1, Week 2 starts with Chapter 2 tasks, not Chapter 1 again.
- [x] A `completed_first_attempt` chapter is treated as completed everywhere relevant to progression.
- [x] Finishing a week early can start the next week immediately in the displayed timeline.
- [x] Plan/progress/schedule views show recalculated week date ranges after early completion.
- [x] Completion date becomes earlier when the learner finishes weeks ahead of nominal calendar pace.

---

## 6. Post-Audit Improvements (GPT-5.3 Recheck) [P2]

- [x] Remove duplicated comparative analytics renderer blocks in `frontend/app.js` and keep a single source of truth.
- [x] Add one backend integration test that advances week from a `completed_first_attempt` chapter and asserts Week 2 chapter assignment is correct.
- [x] Add one API regression test to verify `week_start_overrides` shifts week labels/dates after early completion.
- [x] Add one UI regression check to confirm the displayed scheduled completion date changes after early week completion.
- [x] Add structured planner logs for week advancement: previous forecast, new forecast, and whether early-start override was applied.
- [x] Add a short operator note in docs for `week_start_overrides` payload semantics and rollback expectations.

### Acceptance

- [x] No duplicated comparative analytics render functions remain in frontend.
- [x] Week advancement regressions are covered by both unit and integration-level tests.
- [x] Timeline date compression is validated at API and UI levels.
- [x] Week advancement behavior is easier to diagnose from logs and docs.
