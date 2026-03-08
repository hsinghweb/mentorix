"""
Seed Test Data — Creates a test learner with a complete journey for demo purposes.

Usage:
    python scripts/seed_test_data.py

Creates a learner "Demo Student" with:
  - Student auth credentials (email: demo@mentorix.test, password: demo1234)
  - Learner profile with diagnostic score and timeline
  - Chapter progressions for first 3 chapters (completed)
  - Current week tasks for chapter 4
  - Sample engagement events
  - Sample assessment results
"""
from __future__ import annotations

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from app.memory.database import async_session_factory
from app.models.entities import (
    ChapterProgression,
    EngagementEvent,
    AssessmentResult,
    Learner,
    LearnerProfile,
    StudentAuth,
    Task,
    WeeklyPlan,
)
from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name


DEMO_EMAIL = "demo@mentorix.test"
DEMO_PASSWORD = "demo1234"
DEMO_NAME = "Demo Student"
SELECTED_WEEKS = 20
DIAGNOSTIC_SCORE = 0.68


async def seed():
    """Create demo learner with complete journey data."""
    async with async_session_factory() as db:
        # Check if already seeded
        existing = (
            await db.execute(
                select(StudentAuth).where(StudentAuth.email == DEMO_EMAIL)
            )
        ).scalar_one_or_none()
        if existing:
            print(f"Demo learner already exists: {existing.learner_id}")
            return

        learner_id = uuid4()
        now = datetime.now(timezone.utc)
        onboarding_date = now - timedelta(days=21)  # 3 weeks ago

        # 1. Auth
        from app.core.jwt_auth import hash_password
        db.add(StudentAuth(
            learner_id=learner_id,
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            student_name=DEMO_NAME,
            role="student",
        ))

        # 2. Profile
        concept_mastery = {}
        for i in range(1, 4):
            concept_mastery[chapter_display_name(i)] = 0.75 + (i * 0.03)
        concept_mastery[chapter_display_name(4)] = 0.35

        db.add(LearnerProfile(
            learner_id=learner_id,
            student_name=DEMO_NAME,
            student_email=DEMO_EMAIL,
            math_9_percent=72,
            onboarding_diagnostic_score=DIAGNOSTIC_SCORE,
            selected_timeline_weeks=SELECTED_WEEKS,
            recommended_timeline_weeks=SELECTED_WEEKS + 2,
            current_forecast_weeks=SELECTED_WEEKS + 1,
            timeline_delta_weeks=1,
            onboarding_date=onboarding_date.date(),
            concept_mastery=concept_mastery,
            cognitive_depth=0.55,
            retention_decay=0.1,
            engagement_score=0.7,
            progress_status="in_progress",
            progress_percentage=21.4,
            reminder_enabled=True,
        ))

        # 3. Weekly plan
        rough_plan = []
        for w in range(1, SELECTED_WEEKS + 1):
            ch_num = min(w, 14)
            rough_plan.append({
                "week": w,
                "chapter": chapter_display_name(ch_num),
                "focus": SYLLABUS_CHAPTERS[ch_num - 1]["title"] if ch_num <= len(SYLLABUS_CHAPTERS) else "Revision",
            })
        db.add(WeeklyPlan(
            learner_id=learner_id,
            current_week=4,
            total_weeks=SELECTED_WEEKS,
            rough_plan=rough_plan,
        ))

        # 4. Chapter progressions (first 3 completed)
        for ch in range(1, 4):
            db.add(ChapterProgression(
                learner_id=learner_id,
                chapter=chapter_display_name(ch),
                status="completed",
                attempt_count=1,
                best_score=0.75 + (ch * 0.03),
                last_score=0.75 + (ch * 0.03),
            ))
        # Chapter 4 in progress
        db.add(ChapterProgression(
            learner_id=learner_id,
            chapter=chapter_display_name(4),
            status="in_progress",
            attempt_count=0,
            best_score=0.0,
            last_score=0.0,
        ))

        # 5. Current week tasks for ch4
        ch4 = SYLLABUS_CHAPTERS[3] if len(SYLLABUS_CHAPTERS) >= 4 else {"subtopics": []}
        sort = 0
        for st in ch4.get("subtopics", [])[:3]:
            sort += 1
            db.add(Task(
                learner_id=learner_id,
                week_number=4,
                chapter=chapter_display_name(4),
                task_type="read",
                title=f"Read: {st['id']} {st['title']}",
                sort_order=sort,
                status="pending",
                is_locked=False,
            ))
            sort += 1
            db.add(Task(
                learner_id=learner_id,
                week_number=4,
                chapter=chapter_display_name(4),
                task_type="test",
                title=f"Test: {st['id']} {st['title']}",
                sort_order=sort,
                status="pending",
                is_locked=True,
            ))

        # 6. Engagement events
        for day_offset in range(14):
            db.add(EngagementEvent(
                learner_id=learner_id,
                event_type="login",
                duration_minutes=0,
                created_at=now - timedelta(days=day_offset, hours=8),
            ))
            if day_offset < 10:
                db.add(EngagementEvent(
                    learner_id=learner_id,
                    event_type="reading",
                    duration_minutes=15 + (day_offset * 2),
                    details={"chapter": chapter_display_name(min(day_offset // 3 + 1, 4))},
                    created_at=now - timedelta(days=day_offset, hours=7),
                ))

        # 7. Assessment results
        for ch in range(1, 4):
            for attempt in range(2):
                db.add(AssessmentResult(
                    learner_id=learner_id,
                    chapter=chapter_display_name(ch),
                    score=0.65 + (ch * 0.04) + (attempt * 0.1),
                    response_time=45.0 - (ch * 3),
                    error_type="none" if attempt == 1 else "conceptual",
                    timestamp=now - timedelta(days=14 - ch * 3 - attempt),
                ))

        await db.commit()
        print(f"✅ Demo learner created:")
        print(f"   ID:       {learner_id}")
        print(f"   Email:    {DEMO_EMAIL}")
        print(f"   Password: {DEMO_PASSWORD}")
        print(f"   Chapters: 1-3 completed, ch4 in progress")
        print(f"   Week:     4 of {SELECTED_WEEKS}")


if __name__ == "__main__":
    asyncio.run(seed())
