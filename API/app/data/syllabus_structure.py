"""Class 10 Maths syllabus: chapters and subtopics.

Loads syllabus data from ``syllabus.json`` config file for portability.
Falls back to an empty list if the JSON file is unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path

_SYLLABUS_JSON = Path(__file__).parent / "syllabus.json"


def _load_syllabus() -> list[dict]:
    """Load syllabus chapters from the JSON config file."""
    try:
        return json.loads(_SYLLABUS_JSON.read_text(encoding="utf-8")).get("chapters", [])
    except Exception:
        return []


SYLLABUS_CHAPTERS = _load_syllabus()


def get_syllabus_for_api():
    """Return syllabus as list of chapters with subtopics for API response."""
    return SYLLABUS_CHAPTERS


def chapter_display_name(num: int) -> str:
    """Return 'Chapter N' used in plan/concept_mastery."""
    return f"Chapter {num}"
