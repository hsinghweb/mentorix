"""
Content & Test Cache — MongoDB-backed persistence for LLM-generated artifacts.

Saves generated reading content and test questions so they can be reused
without re-calling the LLM. Supports explicit regeneration via `invalidate()`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.settings import settings

logger = logging.getLogger(__name__)

_client = None
_db = None


def _get_db():
    """Lazy-init pymongo connection, reusing across calls."""
    global _client, _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient
        _client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=3000)
        _db = _client[settings.mongodb_db_name]
        # Ensure indexes
        _db["generated_content"].create_index(
            [("learner_id", 1), ("chapter_number", 1), ("section_id", 1)],
            unique=True, name="ux_content_learner_chapter_section",
        )
        _db["generated_tests"].create_index(
            [("learner_id", 1), ("chapter_number", 1), ("section_id", 1)],
            unique=True, name="ux_test_learner_chapter_section",
        )
        logger.info("ContentCache MongoDB connected: %s", settings.mongodb_db_name)
    except Exception as exc:
        logger.warning("ContentCache MongoDB init failed: %s", exc)
        _db = None
    return _db


# ── Content Cache ────────────────────────────────────────────────────────────

def get_cached_content(learner_id: str, chapter_number: int, section_id: str) -> dict | None:
    """Return cached reading content or None."""
    db = _get_db()
    if db is None:
        return None
    try:
        doc = db["generated_content"].find_one({
            "learner_id": str(learner_id),
            "chapter_number": chapter_number,
            "section_id": section_id,
        })
        if doc:
            doc.pop("_id", None)
            return doc
    except Exception as exc:
        logger.warning("ContentCache read failed: %s", exc)
    return None


def save_content_cache(
    learner_id: str, chapter_number: int, section_id: str,
    section_title: str, content: str, tone: str,
) -> None:
    """Save generated reading content to cache."""
    db = _get_db()
    if db is None:
        return
    try:
        db["generated_content"].replace_one(
            {
                "learner_id": str(learner_id),
                "chapter_number": chapter_number,
                "section_id": section_id,
            },
            {
                "learner_id": str(learner_id),
                "chapter_number": chapter_number,
                "section_id": section_id,
                "section_title": section_title,
                "content": content,
                "tone": tone,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning("ContentCache write failed: %s", exc)


# ── Test Cache ───────────────────────────────────────────────────────────────

def get_cached_test(learner_id: str, chapter_number: int, section_id: str) -> dict | None:
    """Return cached test questions or None."""
    db = _get_db()
    if db is None:
        return None
    try:
        doc = db["generated_tests"].find_one({
            "learner_id": str(learner_id),
            "chapter_number": chapter_number,
            "section_id": section_id,
        })
        if doc:
            doc.pop("_id", None)
            return doc
    except Exception as exc:
        logger.warning("TestCache read failed: %s", exc)
    return None


def save_test_cache(
    learner_id: str, chapter_number: int, section_id: str,
    section_title: str, test_id: str, questions: list, answer_key: dict,
) -> None:
    """Save generated test to cache."""
    db = _get_db()
    if db is None:
        return
    try:
        db["generated_tests"].replace_one(
            {
                "learner_id": str(learner_id),
                "chapter_number": chapter_number,
                "section_id": section_id,
            },
            {
                "learner_id": str(learner_id),
                "chapter_number": chapter_number,
                "section_id": section_id,
                "section_title": section_title,
                "test_id": test_id,
                "questions": questions,
                "answer_key": answer_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning("TestCache write failed: %s", exc)


def invalidate_content(learner_id: str, chapter_number: int, section_id: str) -> bool:
    """Delete cached content to force regeneration."""
    db = _get_db()
    if db is None:
        return False
    try:
        result = db["generated_content"].delete_one({
            "learner_id": str(learner_id),
            "chapter_number": chapter_number,
            "section_id": section_id,
        })
        return result.deleted_count > 0
    except Exception:
        return False


def invalidate_test(learner_id: str, chapter_number: int, section_id: str) -> bool:
    """Delete cached test to force regeneration."""
    db = _get_db()
    if db is None:
        return False
    try:
        result = db["generated_tests"].delete_one({
            "learner_id": str(learner_id),
            "chapter_number": chapter_number,
            "section_id": section_id,
        })
        return result.deleted_count > 0
    except Exception:
        return False
