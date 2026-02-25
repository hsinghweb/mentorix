"""Generate 25 MCQ diagnostic questions via LLM (Class 9 passed, Class 10 CBSE, syllabus-aware)."""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from app.core.json_parser import parse_llm_json
from app.core.llm_provider import get_llm_provider

if TYPE_CHECKING:
    from app.schemas.onboarding import DiagnosticQuestion

logger = logging.getLogger(__name__)

SYLLABUS_OUTLINE = """
1. Real Numbers
2. Polynomials
3. Pair of Linear Equations in Two Variables
4. Quadratic Equations
5. Arithmetic Progressions
6. Triangles
7. Coordinate Geometry
8. Introduction to Trigonometry
9. Some Applications of Trigonometry
10. Circles
11. Areas Related to Circles
12. Surface Areas and Volumes
13. Statistics
14. Probability
"""

PROMPT = f"""You are a mathematics assessment designer for CBSE Class 10 (English medium).
The student has passed Class 9 Mathematics and is starting Class 10. Generate exactly 25 multiple-choice questions (MCQs) to assess their baseline.
Topics must be from Class 10 CBSE Mathematics syllabus only. Cover a mix of chapters 1-14 below. Keep difficulty appropriate for someone who just completed Class 9.

Syllabus chapters:
{SYLLABUS_OUTLINE.strip()}

Output ONLY a valid JSON array of exactly 25 objects. No markdown, no explanation. Each object must have:
- "question_id": "q_1", "q_2", ... "q_25"
- "prompt": "Question text?"
- "options": ["A", "B", "C", "D"]  (exactly 4 options)
- "correct_index": 0  (0-3, index of correct option in options array)
- "chapter_number": 1  (1-14, which chapter this relates to)

Example format:
[{{"question_id":"q_1","prompt":"What is the HCF of 12 and 18?","options":["3","6","9","12"],"correct_index":1,"chapter_number":1}}, ...]

Generate 25 such objects now."""


async def generate_diagnostic_mcq() -> tuple[list["DiagnosticQuestion"], dict[str, str]]:
    """Generate 25 MCQs via LLM. Returns (questions, answer_key). answer_key maps question_id -> correct option text."""
    from app.schemas.onboarding import DiagnosticQuestion

    provider = get_llm_provider(role="content_generator")
    try:
        text, meta = await provider.generate(PROMPT)
    except Exception as exc:
        logger.warning("Diagnostic MCQ LLM call failed: %s", exc)
        return [], {}

    if isinstance(meta, dict) and meta.get("reason"):
        logger.info("Diagnostic MCQ LLM meta: %s", meta)
    if not text:
        logger.warning("Diagnostic MCQ LLM returned empty text (reason=%s)", getattr(meta, "get", lambda *_: None)("reason") if isinstance(meta, dict) else None)
        return [], {}

    parsed = parse_llm_json(text)
    if isinstance(parsed, dict):
        parsed = parsed.get("questions", parsed.get("items", []))
    if not isinstance(parsed, list):
        return [], {}

    questions: list[DiagnosticQuestion] = []
    answer_key: dict[str, str] = {}
    for i, item in enumerate(parsed[:25]):
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id") or f"q_{i+1}"
        prompt_text = (item.get("prompt") or "").strip()
        opts = item.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            continue
        options = [str(o).strip() for o in opts[:4]]
        correct_idx = int(item.get("correct_index", 0))
        if correct_idx < 0 or correct_idx >= len(options):
            correct_idx = 0
        chapter_num = int(item.get("chapter_number", 1))
        if chapter_num < 1 or chapter_num > 14:
            chapter_num = 1

        questions.append(
            DiagnosticQuestion(
                question_id=qid,
                question_type="mcq",
                chapter_number=chapter_num,
                prompt=prompt_text or "Select the correct answer.",
                options=options,
            )
        )
        answer_key[qid] = options[correct_idx].lower()

    return questions, answer_key
