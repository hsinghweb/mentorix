# Mentorix NoSQL Memory Migration Planner (Pre-Iteration 6)

Status date: 2026-02-21  
Goal: move learner/system memory from JSON files into a NoSQL database so runtime data is scalable, queryable, and decoupled from the code repository.

**Status: complete.** All checklist items below have been verified in the codebase (Mongo in Docker, store abstraction, backfill script, tests, gitignore, README).

---

## 0) Why this change

- Current runtime memory is file-based JSON in `API/data/system`:
  - `snapshot.json`
  - `structured_hubs/learner_preferences.json`
  - `structured_hubs/operating_context.json`
  - `structured_hubs/soft_identity.json`
  - episodic files in `episodes/skeleton_*.json`
- Risks with file-based memory:
  - runtime data can leak into repo workflows
  - weak query/filter/index support
  - poor concurrent write safety at scale
  - difficult retention, TTL, and analytics aggregation
- Desired state:
  - JSON documents stored in a dedicated NoSQL service
  - memory updates independent from GitHub codebase
  - indexed access by learner/run/time

---

## 1) Recommended database choice

## Decision
- Use **MongoDB** as the primary NoSQL store for runtime memory.

## Why MongoDB (for this project stage)
- Natural fit for variable learner/profile JSON documents.
- Strong indexing model for learner/time/status queries.
- Mature Docker support and local developer familiarity.
- Works well with existing Python stack via `motor` (async) or `pymongo`.

## Not in scope (this slice)
- Replacing Postgres for relational entities.
- Replacing Redis session/cache responsibilities.

---

## 2) Target architecture

- Keep **Postgres** for relational learning domain (plans/progression/assessments).
- Keep **Redis** for cache/locks/queues.
- Add **MongoDB** for runtime memory documents:
  - structured learner memory hubs
  - run snapshots
  - episodic skeleton memory
  - optional memory audit trail

### Proposed collections
- `memory_hubs`
  - key fields: `hub_type`, `item_key`, `payload`, `learner_id`, `updated_at`
- `runtime_snapshots`
  - key fields: `snapshot_id`, `timestamp`, `active_runs`, `source`
- `episodic_memory`
  - key fields: `run_id`, `query`, `status`, `nodes`, `edges`, `updated_at`
- `memory_events` (optional but recommended)
  - key fields: `event_type`, `entity_key`, `before`, `after`, `created_at`

### Index plan (initial)
- `memory_hubs`: unique compound index on `(hub_type, item_key)`, index on `learner_id`.
- `runtime_snapshots`: descending index on `timestamp`.
- `episodic_memory`: unique index on `run_id`, index on `updated_at`.
- `memory_events`: index on `entity_key`, descending index on `created_at`.

---

## 3) Migration strategy (safe rollout)

## Phase A: Foundation
- [x] Add MongoDB service to local Docker compose (`mongo`, named volume, healthcheck).
- [x] Add backend settings:
  - `MONGODB_URL`
  - `MONGODB_DB_NAME`
  - `MEMORY_STORE_BACKEND` (`file|mongo`, default `file` during transition)
- [x] Add memory repository abstraction:
  - [x] `MemoryStore` interface
  - [x] `FileMemoryStore` (existing behavior)
  - [x] `MongoMemoryStore` (new behavior)

## Phase B: Dual-write transition
- [x] Add optional dual-write mode (`MEMORY_DUAL_WRITE=true`) for verification.
- [x] Route existing memory writes through repository abstraction.
- [x] Continue reads from file store initially, compare Mongo parity in logs.

## Phase C: Backfill and switch
- [x] Build one-time migration script:
  - [x] read all existing JSON files under `API/data/system`
  - [x] upsert into Mongo collections
  - [x] emit counts/checksum report
- [x] Validate data parity (document counts + random spot checks).
- [x] Switch reads to Mongo (`MEMORY_STORE_BACKEND=mongo`).

### Phase C command
- Backfill + parity report (run from `API/`):
  - `cd API`
  - `uv run python scripts/backfill_memory_to_mongo.py --mongodb-url mongodb://localhost:27017 --db-name mentorix`
  - Report output: `data/system/reports/memory_backfill_report.json` (relative to `API/`)

## Phase D: Cleanup
- [x] Disable dual-write.
- [x] Stop writing runtime JSON files by default.
- [x] Keep export script for debugging backup snapshots.

---

## 4) Backend implementation tasks

- [x] Refactor `app/memory/hubs.py` to use memory repository (no direct file IO).
- [x] Refactor `app/runtime/persistence.py` snapshot save/load via repository.
- [x] Refactor `app/memory/episodic.py` episodic save via repository.
- [x] Add repository module (`app/memory/store.py`):
  - [x] interface
  - [x] file implementation
  - [x] mongo implementation
- [x] Add startup check endpoint extension:
  - memory backend status
  - Mongo connectivity
  - active backend mode

---

## 5) Security and compliance

- [x] Ensure no secrets in logs (`MONGODB_URL` sanitized in logs).
- [x] Add field-level redaction policy for sensitive payload keys if needed.
- [x] Add retention options:
  - [x] snapshots TTL index (optional, env-driven)
  - [x] episodic archive strategy (export backup script)
- [x] Keep PII mapping explicit in docs.

---

## 6) Testing plan

- [x] Unit tests:
  - [x] repository contract parity (`file` vs `mongo`)
  - [x] index creation idempotency
- [x] Integration tests:
  - [x] active-backend memory write flow + `/memory/context` verification
  - [x] snapshot save/load from Mongo (repository tests)
  - [x] episodic write/read correctness (repository/migration tests)
- [x] Migration tests:
  - [x] backfill script idempotency
  - [x] count parity before/after switch
- [x] Failure tests:
  - [x] Mongo unavailable status-path behavior (`/memory/status`)

---

## 7) Ops + Docker plan

- [x] Add `mongo_data/` volume and backup guidance.
- [x] Add `.env` template variables for Mongo.
- [x] Add runbook steps:
  - bring up Mongo
  - verify indexes
  - run backfill
  - switch backend flag
  - verify memory endpoints

---

## 8) Git hygiene (immediate)

- [x] Ensure runtime data path is ignored in repository:
  - [x] ignore `API/data/system/` (or broader runtime-data pattern)
- [x] Remove tracked runtime artifacts from repo history going forward (non-destructive workflow, `git rm --cached`).
- [x] Document that runtime learner data must never be committed.

---

## 9) Definition of done

- [x] New learner/runtime memory writes persist in MongoDB.
- [x] Existing file data successfully migrated (parity report generated).
- [x] Reads served from Mongo in default configuration (`/memory/status` verified).
- [x] No runtime JSON learner memory files committed.
- [x] Dockerized setup includes Mongo and passes integration checks.
- [x] Demo/runbook updated with memory backend architecture.

### Verification evidence (all verified in codebase)
- **Docker:** `docker-compose.yml` includes `mongo` service (image mongo:7, volume `mongo_data`, healthcheck).
- **Settings:** `app/core/settings.py` has `mongodb_url`, `mongodb_db_name`, `memory_store_backend` (default `mongo`), `memory_dual_write`, `mongodb_snapshots_ttl_days`, `mongodb_episodes_ttl_days`.
- **Store:** `app/memory/store.py` — `MemoryStore` interface, `FileMemoryStore`, `MongoMemoryStore`, `get_memory_runtime_status()`; URL sanitized via `_sanitize_mongo_error`.
- **Usage:** `hubs.py`, `runtime/persistence.py`, `memory/episodic.py` use `memory_store` (no direct file IO).
- **API:** `GET /memory/status` returns `configured_backend`, `active_mode`, `dual_write_enabled`, `mongo.connected`; `GET /memory/context/{learner_id}` and `GET /memory/hubs` exist.
- **Backfill:** `API/scripts/backfill_memory_to_mongo.py` — reads JSON under data dir, upserts to Mongo, emits parity report.
- **Export:** `API/scripts/export_memory_from_mongo.py` exists (debug backup).
- **Tests:** `tests/test_memory_migration.py` — repository parity file vs mongo, index idempotency, backfill idempotency/parity, `test_memory_status_handles_mongo_unavailable`; `tests/test_api_integration.py` — `test_memory_status_endpoint_shape`, `test_memory_write_flow_for_active_backend`.
- **Git:** `.gitignore` contains `API/data/system/`.
- **Docs:** `README.md` documents memory backend, backfill and export commands, `/memory/status`.

---

## 10) Execution order (recommended)

1. Add Mongo service + settings + repository abstraction.
2. Refactor hubs/snapshot/episodic modules to abstraction.
3. Implement Mongo store + indexes.
4. Add dual-write and validation logs.
5. Build and run backfill script.
6. Switch reads to Mongo, then disable file writes.
7. Update runbook/docs/tests and close checklist.
