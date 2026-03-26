"""
Question quality service — dedup, relevance, and quality checks for LLM-generated questions.

Extracted from ``learning/routes.py`` to centralise question quality logic
that is used across test generation, section tests, and chapter-final tests.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


# ── Stopwords for relevance check ────────────────────────────────────

_QUESTION_STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "into", "this", "which", "about", "using", "what",
    "when", "where", "your", "their", "there", "these", "those", "chapter", "class", "cbse", "math",
    "mathematics", "choose", "following", "statement", "correct", "option", "best", "most",
}


# ── Public API ───────────────────────────────────────────────────────

def normalized_question_text(text: str) -> str:
    """Normalize question text for de-dup checks."""
    txt = re.sub(r"\\\(|\\\)|\\\[|\\\]", " ", str(text or ""))
    txt = re.sub(r"[^a-zA-Z0-9]+", " ", txt).strip().lower()
    return re.sub(r"\s+", " ", txt)


def keyword_tokens(text: str) -> set[str]:
    """Extract keyword tokens from *text*, filtering out stopwords."""
    tokens = re.findall(r"[a-zA-Z]{3,}", str(text or "").lower())
    return {t for t in tokens if t not in _QUESTION_STOPWORDS}


def is_near_duplicate(candidate: str, existing: list[str], threshold: float = 0.9) -> bool:
    """Check if *candidate* is a near-duplicate of any entry in *existing*."""
    return any(SequenceMatcher(a=candidate, b=prev).ratio() >= threshold for prev in existing)


def question_looks_relevant(prompt: str, chapter_name: str, topic_titles: list[str]) -> bool:
    """Heuristic check whether *prompt* is relevant to the given chapter and topics."""
    q_tokens = keyword_tokens(prompt)
    if not q_tokens:
        return False
    source_tokens = keyword_tokens(chapter_name)
    for topic in topic_titles or []:
        source_tokens |= keyword_tokens(topic)
    if q_tokens & source_tokens:
        return True
    return bool(re.search(
        r"[=+\-*/^]|\\frac|\\sqrt|ratio|equation|factor|multiple|polynomial",
        prompt, flags=re.IGNORECASE,
    ))


def has_valid_options(options: list) -> bool:
    """Check that *options* has at least 4 unique non-empty entries."""
    if not isinstance(options, list) or len(options) < 4:
        return False
    normalized = [re.sub(r"\s+", " ", str(opt or "").strip().lower()) for opt in options]
    normalized = [opt for opt in normalized if opt]
    return len(normalized) >= 4 and len(set(normalized[:4])) == 4


def dedupe_generated_questions(
    raw_items: list[dict],
    target_count: int,
    *,
    chapter_name: str = "",
    topic_titles: list[str] | None = None,
) -> tuple[list[dict], int]:
    """Drop exact/normalized/near-duplicate question stems from LLM output."""
    out: list[dict] = []
    seen_norm: list[str] = []
    duplicates_removed = 0
    for item in raw_items:
        if not isinstance(item, dict):
            duplicates_removed += 1
            continue
        q = str(item.get("q", "")).strip()
        options = item.get("options", [])
        if not q or not has_valid_options(options):
            duplicates_removed += 1
            continue
        if chapter_name and not question_looks_relevant(q, chapter_name, topic_titles or []):
            duplicates_removed += 1
            continue
        norm = normalized_question_text(q)
        if not norm:
            duplicates_removed += 1
            continue
        if norm in seen_norm or is_near_duplicate(norm, seen_norm):
            duplicates_removed += 1
            continue
        seen_norm.append(norm)
        out.append(item)
        if len(out) >= target_count:
            break
    return out, duplicates_removed


def reading_content_is_high_quality(
    content: str,
    chapter_name: str,
    topic_titles: list[str] | None = None,
) -> bool:
    """Check if *content* meets minimum quality requirements for reading material."""
    text = str(content or "").strip()
    if not text:
        return False
    words = re.findall(r"\b\w+\b", text)
    if len(words) < 45:
        return False
    low_quality_markers = [
        "correct definition",
        "incorrect variant",
        "select the statement that best matches",
        "which concept is central",
    ]
    lowered = text.lower()
    if any(marker in lowered for marker in low_quality_markers):
        return False
    topic_titles = topic_titles or []
    if not keyword_tokens(" ".join(topic_titles) + " " + chapter_name):
        return True
    return bool(keyword_tokens(text) & keyword_tokens(" ".join(topic_titles) + " " + chapter_name))


def question_set_is_high_quality(
    questions: list[Any],
    *,
    chapter_name: str,
    topic_titles: list[str] | None = None,
    min_count: int,
) -> bool:
    """Check if a generated question set meets quality requirements."""
    if len(questions) < min_count:
        return False
    prompts = [str(getattr(q, "prompt", "") or "") for q in questions]
    normalized = [normalized_question_text(p) for p in prompts]
    if len(set(normalized)) < len(normalized):
        return False
    lowered = " ".join(prompts).lower()
    if "correct definition" in lowered or "incorrect variant" in lowered:
        return False
    relevant_count = 0
    for q in questions:
        if question_looks_relevant(str(getattr(q, "prompt", "") or ""), chapter_name, topic_titles or []):
            relevant_count += 1
    return relevant_count >= max(min_count - 1, int(0.8 * len(questions)))
