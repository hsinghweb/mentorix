# Mentorix HLD Alignment Planner

Status date: 2026-02-21  
Goal: align implementation to the provided high-level architecture block diagram end-to-end.

---

## 1) Diagram vs Current Code Gap Check

### Present
- [x] Student interface (`frontend/`)
- [x] API gateway routing (`FastAPI` routers)
- [x] Orchestration + scheduling engine (`runtime`, `autonomy/scheduler.py`)
- [x] Agent manager behavior (`runtime/run_manager.py`)
- [x] Knowledge + memory layer (`models`, `memory/*`)
- [x] RAG + grounding layer (`rag/*`)
- [x] AI model layer (`core/llm_provider.py`, `core/model_registry.py`)

### Missing before this iteration
- [x] Explicit API-gateway authentication guard (diagram labels auth + routing)
- [x] Dedicated Notification Engine module + API surface
- [x] Explicit Onboarding Agent (named as such in diagram)
- [x] Explicit Analytics & Evaluation Agent (named as such in diagram)
- [x] Explicit Compliance Agent (named as such in diagram)
- [x] Explicit Memory Management Agent (named as such in diagram)
- [x] Session pipeline wiring to analytics/compliance/notification outputs

---

## 2) Implementation Tasks

## A. API Gateway Authentication
- [x] Add auth settings (`gateway_auth_enabled`, `gateway_api_key`)
- [x] Add middleware enforcing `x-api-key` when auth is enabled
- [x] Wire middleware in FastAPI app

## B. Notification Engine
- [x] Add notification engine service (in-memory queue + event bus publish)
- [x] Add notification endpoints to inspect/send notifications
- [x] Wire scheduler/session critical events to notification engine

## C. Multi-Agent Block Completeness
- [x] Add `OnboardingAgent`
- [x] Add `AnalyticsEvaluationAgent`
- [x] Add `ComplianceAgent`
- [x] Add `MemoryManagementAgent`
- [x] Integrate these agents into session flow

## D. API Contract Visibility
- [x] Extend response schemas with optional analytics/compliance/onboarding metadata
- [x] Keep backward compatibility with existing tests and frontend flow

---

## 3) Exit Criteria

- [x] HLD missing blocks are represented by concrete modules in codebase
- [x] Session flow emits analytics/compliance/memory-management outputs
- [x] Notification engine can be demonstrated through API
- [x] Auth guard is available and configurable (off by default)
- [x] Existing integration tests pass

