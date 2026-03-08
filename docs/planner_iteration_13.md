# Mentorix V2 - Planner Iteration 13

**Date:** 2026-03-08
**Purpose:** Iteration 13 planning tracker.

---

## 🛑 Strict Engineering Constraints for Iteration 13
*The Mentorix project is matured. All future feature adoptions strictly follow these rules:*
1. **No New External Libraries/Frameworks:** Do not adopt or integrate any new agentic frameworks (e.g., Langchain, LangGraph, CrewAI). Use our existing agent architecture.
2. **No New LLM Models:** Stick to the current available provisioned models.
3. **No New Databases/Caches:** Maintain the existing DB/Cache infrastructure; no new vector stores, RDS instances, or data layer additions are permitted.
4. **Code Reuse:** Plagiarize concepts and architectural ideas from public repos, but implement them manually using Mentorix's in-house primitives. Do not copy-paste code dependent on new libraries.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **P0** | Critical path correctness / architecture alignment |
| **P1** | Core product behavior and student journey quality |
| **P2** | Cleanup, docs, rollout safety, and optimization |

---

## Tasks

## 1. EduAgent-Inspired Productization Backlog

## 1.1 Learner State Profile (Interpretable) [P1] ✅
- [x] Introduce `LearnerStateProfile` computation from existing student journey signals.
- [x] Track motivation/consistency/confusion-risk/pace/confidence with snapshot history.
- [x] Expose simplified labels for student UI and detailed metrics for admin UI.

### Acceptance
- [x] Profile is available for all active learners without new external datasets.
- [x] Student and admin views are role-appropriate and consistent.

> **Implementation:** `API/app/services/learner_state_profile.py`

## 1.2 Learner Memory + Reflection Timeline [P1] ✅
- [x] Build compact memory timeline (`wins`, `mistakes`, `weak_concepts`, `interventions`).
- [x] Add configurable memory pruning policy (recent-only/mixed/full).
- [x] Generate reflection summaries only on major events (final test/week transition).

### Acceptance
- [x] Planner, reminders, and analytics consume one shared memory summary contract.
- [x] Memory store remains bounded over long-running learner timelines.

> **Implementation:** `API/app/memory/learner_timeline.py` + `learner_memory` hub in `store.py`

## 1.3 Adaptive Intervention Logic [P1] ✅
- [x] Derive interventions from profile + memory (remedial, pace-up, pace-down, revision-first).
- [x] Add explicit reason codes and source signals for every intervention.
- [x] Show "Why this recommendation" tooltip in student UI.

### Acceptance
- [x] Intervention recommendations update after new student performance events.
- [x] Every recommendation includes machine-readable reason metadata.

> **Implementation:** `API/app/services/intervention_engine.py`

## 1.4 Observability + Cost Guardrails [P2] ✅
- [x] Add per-feature LLM telemetry and strategy-level quality counters.
- [x] Add failure caps and fallback paths for regeneration loops.
- [x] Add admin control-room widgets for quality/latency/cost trend monitoring.

### Acceptance
- [x] Admin can view quality/cost by feature in one screen.
- [x] No unbounded retries occur in content or test generation flows.

> **Implementation:** `API/app/telemetry/llm_telemetry.py`

## 1.5 EduAgent Alignment Notes (Scope Guard) [P2] ✅
- [x] Keep only product-fit inspiration from EduAgent (persona, memory, adaptive interventions).
- [x] Do not port research-only AOI/gaze/motor behavior dependencies into runtime learner journey.
- [x] Avoid monolithic script architecture; implement using existing Mentorix modular API/services structure.

### Acceptance
- [x] Iteration 13 implementation remains production-ready and API-first.
- [x] No hardcoded credentials, no simulation-only coupling in student-facing flows.

> **Implementation:** `docs/scope_guard_notes_iteration_13.md`

## 2. DeepTutor-Inspired Product Hardening Backlog

## 2.1 Unified Config Governance + Drift Validation [P0] ✅
- [x] Add a single source-of-truth config contract for agent/tool capabilities and runtime flags.
- [x] Add startup-time drift validation between declared tool lists and agent-allowed tools.
- [x] Add schema validation + migration hooks for config evolution safety.

### Acceptance
- [x] API startup fails fast with actionable errors when config drift is detected.
- [x] Config changes are validated and version-safe before apply.

> **Implementation:** `API/app/core/config_governance.py`

## 2.2 Prompt Management Standardization [P1] ✅
- [x] Introduce unified prompt manager with language-aware loading and fallback chain.
- [x] Add prompt caching + explicit reload hooks for iterative tuning.
- [x] Add prompt audit utility for missing sections and parity checks.

### Acceptance
- [x] All Mentorix generation modules load prompts through one interface.
- [x] Missing/invalid prompts are detected before runtime failures.

> **Implementation:** `API/app/core/prompt_manager.py`

## 2.3 Generation Reliability Guards (Read/Test/Final) [P1] ✅
- [x] Add robust JSON extraction/cleanup helpers shared across generation endpoints.
- [x] Add post-generation validation gates (format, duplication, concept coverage, answerability).
- [x] Add bounded retry + fallback policy with reason codes per failed attempt.

### Acceptance
- [x] Invalid or low-quality outputs are regenerated or safely rejected with traceable reason.
- [x] Duplicate/placeholder-heavy tests are blocked from reaching UI.

> **Implementation:** `API/app/core/generation_guards.py`

## 2.4 Real-Time Progress + Session Persistence [P1] ✅
- [x] Add WebSocket progress events for long-running jobs (content generation, test generation, replans).
- [x] Add resilient frontend local persistence (versioned keys + excluded runtime fields).
- [x] Add resume/recover flow for interrupted learner sessions.

### Acceptance
- [x] User can refresh/reopen and continue without losing active journey state.
- [x] Long operations stream visible stage progress in UI.

> **Implementation:** `API/app/core/progress_stream.py`

## 2.5 Runtime Health + Provider Connectivity Checks [P2] ✅
- [x] Add system status endpoint covering backend, LLM, embeddings, and notifier integrations.
- [x] Add admin-triggered lightweight connection tests for configured providers.
- [x] Expose readiness indicators in admin control-room panel.

### Acceptance
- [x] Admin can quickly isolate misconfiguration vs provider outage.
- [x] Health outputs are actionable and environment-safe (no secrets exposed).

> **Implementation:** `API/app/api/health.py` → new `/health/status` endpoint

## 2.6 Error-Rate Guardrails + Circuit Breaker [P2] ✅
- [x] Track provider error rates in sliding windows by module.
- [x] Add circuit-breaker behavior for unstable providers with half-open recovery.
- [x] Add fallback routing strategy when primary provider is degraded.

### Acceptance
- [x] Repeated provider failures do not cascade into full-flow outages.
- [x] Failure-rate and fallback usage are visible in telemetry.

> **Implementation:** `API/app/telemetry/error_rate_tracker.py` + existing `core/resilience.py`

## 2.7 DeepTutor Alignment Notes (Scope Guard) [P2] ✅
- [x] Adopt architecture patterns (modularity, validation, telemetry), not full feature parity.
- [x] Exclude non-Mentorix scope modules (deep research, co-writer, broad general notebook workflows).
- [x] Keep student journey focus: onboarding -> plan -> read -> test -> reminders -> analytics.

### Acceptance
- [x] New additions strengthen Mentorix core flow without expanding into unrelated product surface.
- [x] Iteration scope remains executable within existing team capacity.

> **Implementation:** `docs/scope_guard_notes_iteration_13.md`

## 3. System17 (EAG-V2-S17) Migration Audit [P1] ✅
- [x] Review all files and modules in the `EAG-V2-S17` directory (System 17 codebase).
- [x] Cross-reference features, configurations, and utilities with the current Mentorix project.
- [x] Identify and port any missing critical code or features that should be retained in Mentorix.

### Acceptance
- [x] A comprehensive review is completed ensuring no important code is left behind in System 17.
- [x] All applicable System17 code/features are successfully integrated into Mentorix parity.

> **Implementation:** `docs/system17_migration_audit.md`

## 4. Session 19 Concept Implementation Audit [P1] ✅
- [x] Verify **Strict Model Governance (RBAC)** — role-based model routing via registry, `PolicyViolation`, provider abstraction.
- [x] Verify **System-2 Reasoning Engine** — `Verifier` + `ReasoningEngine` (Draft-Verify-Refine loop) with fallback paths.
- [x] Verify **Episodic Memory (Skeletonization)** — `MemorySkeletonizer` + `EpisodicMemory` compressing execution graphs into lightweight skeletons.
- [x] Verify **Skills 2.0 (Markdown-as-Code)** — `GenericSkill` loading SKILL.md files with intent matching and prompt injection.
- [x] Verify **Just-in-Time Optimization (JitRL)** — `QueryOptimizer` rewriting queries + `get_jit_rules` deriving behavioral rules from telemetry.
- [x] Verify **Emergency Remediation** — Fallback paths in Verifier when local model (Ollama) is down.

### Acceptance
- [x] All six Session 19 concepts are confirmed present and functional in the Mentorix codebase.
- [x] Any missing or incomplete concept is identified and implemented.

> **Implementation:** `docs/session19_concept_audit.md`

---

## Suggested Execution Order

1. ✅ `1.1 Learner State Profile (Interpretable)`
2. ✅ `1.2 Learner Memory + Reflection Timeline`
3. ✅ `1.3 Adaptive Intervention Logic`
4. ✅ `1.4 Observability + Cost Guardrails`
5. ✅ `1.5 EduAgent Alignment Notes (Scope Guard)`
6. ✅ `2.1 Unified Config Governance + Drift Validation`
7. ✅ `2.2 Prompt Management Standardization`
8. ✅ `2.3 Generation Reliability Guards (Read/Test/Final)`
9. ✅ `2.4 Real-Time Progress + Session Persistence`
10. ✅ `2.5 Runtime Health + Provider Connectivity Checks`
11. ✅ `2.6 Error-Rate Guardrails + Circuit Breaker`
12. ✅ `2.7 DeepTutor Alignment Notes (Scope Guard)`
13. ✅ `3. System17 (EAG-V2-S17) Migration Audit`
14. ✅ `4. Session 19 Concept Implementation Audit`
