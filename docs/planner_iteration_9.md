# Mentorix V2 - Planner Iteration 9 (Rendering, Test Quality, Final-Test Gating, UX Clarity)

**Date:** 2026-03-01  
**Purpose:** Fix math rendering quality, enforce test-question uniqueness, block final-test generation before prerequisites, and improve dashboard explanation clarity.

> [!IMPORTANT]
> Do not change core CAS cache/regenerate semantics. Improvements are additive and backward-compatible with current learning APIs.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Blocking UX/logic defect |
| **P1** | Core quality improvement |
| **P2** | Clarity/polish |

---

## 1. Final Test Pre-Generation Gating [P0]

- [x] Add prerequisite validation at final chapter test generation entry (`/learning/test/generate`) before any LLM/token usage.
- [x] If chapter-level final test requested and prerequisites are incomplete, return structured blocked response with:
  - [x] `blocked: true`
  - [x] `reason_code` (for example `pending_subsection_tasks`)
  - [x] `pending_tasks` (titles or section IDs)
- [x] Keep submit-time validation (`/learning/test/submit`) as a safety net.
- [x] Prevent `_test_store` write and cache write when blocked.
- [x] Add explicit compliance log for blocked generation attempts.

### Acceptance
- [x] Clicking final test before subsection completion does not generate questions.
- [x] User sees clear actionable message listing what remains.
- [x] No unnecessary LLM calls happen in blocked scenario.

---

## 2. Math Rendering Consistency (Reading + Review + Explain) [P0]

- [x] Replace fragile markdown string transforms in frontend with robust markdown rendering flow.
- [x] Normalize math delimiters before render (`\\(` `\\)` and `\(` `\)` variants).
- [x] Ensure KaTeX rendering runs consistently on:
  - [x] subsection/chapter reading content
  - [x] test question cards
  - [x] post-submit question review (right/wrong)
  - [x] explain output text
- [x] Validate rendering with known examples:
  - [x] `17 = 5 × 3 + 2`
  - [x] `p` divides `a^2`
  - [x] fractions like `p/q`

### Acceptance
- [x] No raw slash-escaped math artifacts shown to users.
- [x] Fractions, powers, and inline equations display correctly in all above surfaces.

---

## 3. Test Question Uniqueness Enforcement [P1]

- [x] Improve LLM prompts (section + chapter tests) with explicit uniqueness rules.
- [x] Add backend dedupe pass on generated questions:
  - [x] exact duplicate check
  - [x] normalized-text duplicate check
  - [x] near-duplicate threshold check
- [x] Auto-regenerate/refill only missing slots until required unique count met.
- [x] Fail safely with fallback question generation if uniqueness cannot be satisfied.
- [x] Add generation diagnostics log: requested, unique_count, duplicates_removed.

### Acceptance
- [x] Final chapter test generation pipeline enforces uniqueness before response.
- [x] Section test returns unique set (asserted in integration test).
- [x] No obvious repeated stems in blocked/partial-progress scenarios.

---

## 4. Blocked-State UX Messaging [P1]

- [x] Frontend: handle blocked final-test generation response gracefully (no generic error alert).
- [x] Show structured modal/toast explaining unmet prerequisites and next actions.
- [x] Link/route user back to pending subsection tasks directly from message.
- [x] Preserve current successful path behavior unchanged.

### Acceptance
- [x] User gets immediate understandable message at click time (not only on submit).
- [x] Message matches backend pending list and removes confusion.

---

## 5. Diagnostic and Timeline Explanation Copy [P2]

- [x] Add concise tooltip/help text for **Diagnostic %** in dashboard:
  - [x] Baseline onboarding assessment definition
  - [x] Not a weekly score
- [x] Add concise tooltip/help text for **Selected weeks / Suggested weeks**:
  - [x] selected = learner preference
  - [x] suggested = adaptive system recommendation
  - [x] can move up or down based on performance/consistency
- [x] Ensure copy is visible on desktop and mobile layouts.

### Acceptance
- [x] Users can understand these metrics without external explanation.
- [x] No ambiguity about whether suggested weeks can change dynamically.

---

## 6. Tests and Verification [P1]

- [x] Add/extend integration tests for:
  - [x] final-test generation blocked before subsection completion
  - [x] uniqueness checks for generated tests
  - [x] explain/render API payload compatibility
- [x] Add frontend smoke checklist for math rendering across screens.
- [x] Validate no regressions in existing `tests/test_learning_flow.py`.

### Acceptance
- [x] Updated tests pass locally (`18 passed`).
- [x] Regression suite remains green for existing iteration 8 behavior.

### Frontend Smoke Checklist (Math Rendering)

- [x] Read content renders inline/block math without raw slash escapes.
- [x] Test question cards render math symbols and expressions correctly.
- [x] Post-submit right/wrong review renders math in question + options.
- [x] Explain panel renders math and markdown consistently.

---

## Suggested Execution Order

1. P0.1 Final test pre-generation gating  
2. P0.2 Math rendering consistency  
3. P1.3 Test uniqueness enforcement  
4. P1.4 Blocked-state UX messaging  
5. P2.5 Diagnostic/timeline explanation copy  
6. P1.6 Tests and verification

