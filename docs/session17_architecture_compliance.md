# Session-17 Architecture Compliance (Mentorix)

Date: 2026-03-03
Scope: Task 1 from planner_iteration_10.md

## What was enforced

1. Explicit agent role ownership in code (`role`, `capabilities` on agent classes).
2. Capability-based agent contracts via `AgentCoordinator`.
3. Structured inter-agent envelopes (`run_id`, sender role, target role, capability, payload).
4. Protocol-level event publication for all agent requests/results.
5. Session flow refactor (`/sessions/start-session`, `/sessions/submit-answer`, `/sessions/dashboard`) to dispatch through coordinator instead of direct ad-hoc calls.

## Role mapping

- Planner:
  - `OnboardingAgent` (`summarize_onboarding`)
  - `CurriculumPlannerAgent` (`plan_curriculum`)
- Executor:
  - `ContentGenerationAgent` (`generate_content`)
  - `AdaptationAgent` (`adapt_strategy`)
- Evaluator:
  - `LearnerProfilingAgent` (`profile_learner`)
  - `AssessmentAgent` (`generate_assessment`, `evaluate_answer`)
  - `ReflectionAgent` (`reflect_progress`)
  - `AnalyticsEvaluationAgent` (`evaluate_analytics`)
- Memory:
  - `MemoryManagementAgent` (`update_memory`)
- Compliance:
  - `ComplianceAgent` (`check_compliance`)

## Inter-agent protocol

Coordinator dispatch contract:
- Input:
  - `run_id`
  - `sender_role`
  - `target_agent`
  - `capability`
  - `payload`
- Validation:
  - target agent exists
  - capability allowed for that target
  - target method exists
- Output:
  - agent result dict
- Events:
  - `agent_message`
  - `agent_result`

## Files changed

- `API/app/orchestrator/agent_compliance.py` (new)
- `API/app/api/sessions.py`
- `API/app/agents/base.py`
- Agent role/capability annotations:
  - `API/app/agents/planner.py`
  - `API/app/agents/content.py`
  - `API/app/agents/assessment.py`
  - `API/app/agents/adaptation.py`
  - `API/app/agents/memory_manager.py`
  - `API/app/agents/learner_profile.py`
  - `API/app/agents/progress_revision.py`
  - `API/app/agents/onboarding.py`
  - `API/app/agents/reflection.py`
  - `API/app/agents/analytics_evaluation.py`
  - `API/app/agents/compliance.py`

## Notes

- Existing public API contracts were preserved.
- Coordinator supports capability methods mapped to `run` or custom method (for example `AssessmentAgent.evaluate`).
