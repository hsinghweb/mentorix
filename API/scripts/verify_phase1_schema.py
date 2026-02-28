#!/usr/bin/env python3
"""Verify Phase 1.1: required PostgreSQL tables exist (run when DB is up)."""
from __future__ import annotations

import asyncio
import sys

# Phase 1.1 required tables (antigravity_planner.md)
REQUIRED_TABLES = frozenset({
    "learners",
    "student_auth",
    "learner_profile",
    "learner_profile_snapshots",
    "chapter_progression",
    "weekly_plans",
    "weekly_plan_versions",
    "tasks",
    "task_attempts",
    "assessment_results",
    "embedding_chunks",
    "curriculum_documents",
    "syllabus_hierarchy",
    "revision_queue",
})


async def main() -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.settings import settings

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            existing = {row[0] for row in result}
    except Exception as e:
        print("Phase 1.1 schema verification SKIP: cannot connect to DB (is the stack up?).", e)
        return 1
    finally:
        await engine.dispose()

    missing = REQUIRED_TABLES - existing
    if missing:
        print("Phase 1.1 schema verification FAILED: missing tables:", sorted(missing))
        return 1
    print("Phase 1.1 schema verification OK: all 14 required tables exist.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
