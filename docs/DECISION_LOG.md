# Mentorix Decision Log

Architecture and design decisions with rationale.

---

## 1. Dual Database Strategy (PostgreSQL + MongoDB)

**Decision:** Use PostgreSQL for structured/relational data and MongoDB for document-oriented content caching.

**Rationale:**
- **PostgreSQL (pgvector):** Student profiles, plans, assessments, tasks, and progressions are relational with foreign keys, joins, and ACID guarantees needed. pgvector extension enables semantic search without a separate vector DB.
- **MongoDB:** Content cache, memory snapshots, and learner timelines are document-shaped with varying schemas. MongoDB's flexible schema allows rapid evolution of cached content structures without migrations.

**Alternatives considered:** Single PostgreSQL with JSONB columns — rejected because memory store access patterns are append-heavy with flexible schemas that benefit from document-native querying.

---

## 2. MCP (Model Context Protocol) for RAG

**Decision:** Use MCP provider abstraction for retrieval-augmented generation instead of direct embedding calls.

**Rationale:**
- MCP standardizes the tool/resource interface for retrieval
- Enables swapping between local PDF ingestion, external search APIs, or custom knowledge bases without changing generation code
- Aligns with agentic architecture principles from Session 17/19

---

## 3. Hub-Based Memory Store

**Decision:** Organize learner memory into named "hubs" (`learner_preferences`, `operating_context`, `soft_identity`) with typed access patterns.

**Rationale:**
- Prevents single monolithic memory blob that becomes hard to version and prune
- Each hub can have an independent retention/pruning policy
- Agents can request specific hub data without loading full memory

**Note:** `memory/hubs.py` was initially created but is now deprecated (no importers). The hub concept is instead implemented directly in `store.py`.

---

## 4. In-Memory Circuit Breakers (Not Redis-Based)

**Decision:** Implement circuit breakers in-process using `core/resilience.py` rather than distributed state in Redis.

**Rationale:**
- Single-instance deployment makes distributed state unnecessary
- In-process breakers have zero latency overhead
- If scaling to multiple instances, migrate breaker state to Redis using existing `error_rate_tracker.py` sliding window pattern

---

## 5. Frontend Single-Page-App Without Framework

**Decision:** Use vanilla HTML/JS/CSS instead of React, Vue, or Next.js.

**Rationale:**
- Minimizes build complexity — no bundler, no transpilation, no node_modules
- Direct DOM manipulation is sufficient for the current UI scope
- Enables rapid prototyping without framework lock-in
- Trade-off: `app.js` has grown to 2000+ lines; future iteration should split into modules with ES import maps

---

## 6. Agent Stub Architecture

**Decision:** Keep `agents/` as thin interface stubs while business logic lives in `api/` route handlers.

**Rationale:**
- Student journey logic evolved rapidly — keeping it in route handlers allowed faster iteration
- Agent interfaces are preserved for future migration when orchestration patterns stabilize
- Trade-off: Route files (`learning.py`, `onboarding.py`) are oversized; future iteration should split files and migrate logic into agents

---

## 7. JWT-Based Admin Authentication

**Decision:** Use JWT tokens for admin authentication with configurable username/password via environment variables.

**Rationale:**
- Simple, stateless auth suitable for single-admin deployment
- No external auth provider dependency
- Credentials documented in `.env.example` with "change-in-production" guidance
