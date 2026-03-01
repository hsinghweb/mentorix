# Mentorix V2 - Planner Iteration 8 (Subsection-First Plan + Adaptive Content + Explainability)

**Date:** 2026-03-01  
**Purpose:** Move weekly planning to subsection-first learning flow, keep cache-first generation behavior, and add question-level explanation support.

> [!IMPORTANT]
> Keep existing CAS/cache-regenerate behavior intact. Do not reintroduce chapter-level always-generate paths.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Product behavior mismatch or blocking learner flow |
| **P1** | Core learning-quality improvements |
| **P2** | UX and observability polish |

---

## 1. Weekly Plan Restructure to Subsection-First [P0]

- [x] Replace chapter-level week tasks (`Read concept notes`, `Practice worksheet`, `Weekly quiz attempt`) with subsection-level tasks.
- [x] For each planned chapter in a week, emit subsection sequence:
  - [x] `1.1 Read`
  - [x] `1.1 Test`
  - [x] `1.2 Read`
  - [x] `1.2 Test`
  - [x] ... last subsection (including summary subsection if present)
- [x] Keep exactly one chapter-level final test task at the end of subsection flow for that chapter.
- [x] Define and enforce completion semantics:
  - [x] Subsection complete = read completed + subsection test attempted/submitted.
  - [x] Chapter complete = all subsection completions + chapter final test submitted.
- [x] Ensure top-level weekly tasks show subsection progression, not chapter-generic placeholders.

### Acceptance
- [x] Week 1 for Chapter 1 renders subsection tasks (including `1.4 Summary`) and one final chapter test.
- [x] No chapter-level `Practice worksheet` task appears unless explicitly backed by content pipeline.

---

## 2. Cache-First Content/Test Behavior at Week Plan Level [P0]

- [x] Remove any week-plan execution path that regenerates read/test content by default.
- [x] Route subsection read/test tasks through existing cached-content retrieval path.
- [x] Keep explicit regenerate action only (user-triggered) for read/test/final-test artifacts.
- [~] Add/verify final chapter test caching key strategy:
  - [ ] by `student_id + chapter_id + version + difficulty/profile_snapshot` *(current key is learner/chapter/section; versioned key refinement pending)*
  - [x] invalidation only on explicit regenerate or model/prompt version bump.

### Acceptance
- [x] Opening subsection read/test from weekly plan uses cached artifact when present.
- [x] Final chapter test submit path improved and chapter test artifacts are cached/reused.
- [x] Regenerate endpoint/path exists and returns fresh artifacts while preserving previous attempt history.

---

## 3. Final Test Submission + Regenerate Reliability [P0]

- [x] Trace and fix chapter final test `Error 400` submit path (payload schema, missing IDs, or state transition mismatch).
- [x] Add validation error details to API logs and structured response for easier debugging.
- [x] Ensure final-test attempt lifecycle mirrors subsection tests:
  - [x] generate/load
  - [x] submit
  - [x] score
  - [x] persist attempt metadata
- [~] Add integration test for end-to-end final test generate -> submit -> score. *(chapter-level pass-path test still pending; cache/explain integration tests added)*

### Acceptance
- [ ] Final test submit succeeds in local Docker flow. *(pending runtime validation in your local stack)*
- [x] Re-opening final test shows cached current artifact unless regenerate is requested.

---

## 4. Popup/UI Alignment for Subsection Cards [P1]

- [x] Remove `Read` and `Test` action buttons from subsection status popup/card where requested.
- [x] Keep popup focused on status metrics only: mastery level, score/accuracy, attempts, read state.
- [x] Ensure actionable read/test controls remain at weekly plan level (single source of action).

### Acceptance
- [x] Popup shows status-only information and no duplicate action controls.
- [x] Weekly plan remains the primary interaction surface for read/test actions.

---

## 5. Clarify Retrieval Strategy: Deterministic Section Fetch vs Similarity Search [P1]

- [x] Audit current codepaths and document where similarity search is actually used.
- [x] For subsection read generation, enforce deterministic fetch from canonical subsection store (Mongo) first.
- [x] Use embeddings/similarity retrieval only where semantic lookup is needed (for example, explanation support).
- [x] Add architecture note in docs describing:
  - [x] when to use direct subsection fetch
  - [x] when to use vector retrieval
  - [x] why both coexist.

### Acceptance
- [x] Documented map of retrieval paths exists and matches implementation.
- [x] Subsection content generation no longer depends on vector similarity for primary source fetch.

---

## 6. Adaptive Content Generation from Canonical Subsection Source [P1]

- [x] Store and fetch canonical subsection content from MongoDB by `chapter.section` identity.
- [x] Build prompt pipeline: `canonical subsection content + learner profile snapshot + pedagogy instructions`.
- [x] Generate adaptive read material (tone/simplification/examples) per student while preserving factual source.
- [ ] Cache adaptive outputs with profile/version-aware keys.

### Acceptance
- [x] Two students can receive differently adapted explanations for same subsection from same canonical source.
- [x] Regeneration produces a new variant while preserving grounded source constraints.

---

## 7. Question-Level Explain Feature After Tests [P1]

- [x] In test results, show per-question correctness and add `Explain` action for each question.
- [x] Implement explanation endpoint:
  - [x] input: question, chosen answer, correct answer, subsection/chapter context, learner profile
  - [x] retrieval: relevant canonical subsection chunk(s) and optional vector recall for supporting context
  - [x] output: concise why-correct/why-wrong + remediation tip.
- [x] Cache explanations per question-attempt to reduce repeated LLM calls.
- [x] Add guardrails to keep explanation grounded in syllabus context.

### Acceptance
- [x] Clicking `Explain` returns grounded explanation for wrong and correct responses.
- [x] Repeat clicks reuse cached explanation unless regenerate is requested.

---

## 8. Tests, Telemetry, and Rollout Safety [P2]

- [x] Add automated tests for subsection-first planner output structure.
- [x] Add automated tests for cache-hit vs regenerate behavior (read/test/final-test/explain).
- [~] Add event logging for:
  - [x] cache_hit/cache_miss
  - [x] regenerate_triggered
  - [x] final_test_submit_failed (with reason code)
  - [x] explain_requested
- [ ] Add brief rollout checklist for local Docker deployment and smoke tests.

### Acceptance
- [ ] Planner and learning flows pass regression tests. *(pending full suite run in your environment)*
- [x] Logs clearly indicate cache behavior and submit failures.

---

## Suggested Execution Order

1. P0.1 Weekly plan restructure  
2. P0.2 Cache-first behavior at week level  
3. P0.3 Final test submit/cache/regenerate reliability  
4. P1.4 Popup/UI status-only alignment  
5. P1.5 Retrieval strategy documentation + enforcement  
6. P1.6 Adaptive subsection generation pipeline  
7. P1.7 Question-level explain flow  
8. P2.8 Tests/telemetry/rollout
