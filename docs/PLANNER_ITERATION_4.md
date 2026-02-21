# Mentorix Iteration 4 Planner (Session 19 Concept Parity)

Status date: 2026-02-21  
Goal: close Session 19 concept gaps on top of Iteration 3 (Reasoning AI, strict model control, markdown skills, JitRL depth).

---

## 1) Gap Check (from Session 19)

### Missing before Iteration 4
- [x] Model registry lacked Session-19 style metadata depth (`id`, `cost_per_1k`, `context_window`) and YAML-ready behavior.
- [x] Verifier flow did not include explicit emergency fallback model path when local verifier fails.
- [x] Skill system only handled Python plugins; no Markdown `SKILL.md` "skills as docs" path.
- [x] Query optimizer parsing was weak and lacked offline JitRL-style rules (`get_jit_rules`).
- [x] Episodic skeleton memory did not explicitly preserve `logic_prompt` and tool/code action traces from iterations.

---

## 2) Iteration 4 Tasks

## A. Strict Model Governance (Session-19 style)
- [x] Extend model registry schema to include model metadata (`id`, `provider`, `cost_per_1k`, `context_window`)
- [x] Add policy-specific exception (`PolicyViolation`) for verifier-local enforcement
- [x] Add YAML-compatible loading path (with JSON fallback) for registry portability
- [x] Add per-role estimated cost emission in LLM usage payloads

## B. System-2 Reliability Remediation
- [x] Add explicit verifier fallback path when primary verifier generation fails
- [x] Preserve tuple-safe verifier return contract (`score`, `critique`) across all failure paths

## C. Skills 2.0 (Markdown-as-Code)
- [x] Add `GenericSkill` implementation for `SKILL.md` based skills
- [x] Add frontmatter parsing (`name`, `version`, `description`, `intent_triggers`)
- [x] Extend skill registry scanner to support both Python and Markdown skills
- [x] Add one production-style markdown skill example

## D. JitRL Query Optimization Depth
- [x] Add robust LLM JSON parsing utility for optimizer output
- [x] Upgrade optimizer to parse strict JSON and handle malformed output safely
- [x] Implement `get_jit_rules()` using fleet telemetry as offline rule source

## E. Episodic Memory Compression Quality
- [x] Add `logic_prompt` capture in skeletonized node output
- [x] Add tool/code action extraction from iteration traces with truncation

---

## 3) Exit Criteria

- [x] Session 19 strict model governance concepts are represented in runtime code
- [x] Verifier resilience includes emergency fallback behavior
- [x] Markdown-only skills are loadable and injectable at run start
- [x] Optimizer has online rewrite + offline rule generation path
- [x] Episodic skeletons preserve reasoning/logic/action traces as recipes
- [x] Existing integration tests still pass

---

## 4) Validation

- [x] `uv run pytest ..\tests -q -p no:pytest_asyncio` passed after Iteration 4 changes
