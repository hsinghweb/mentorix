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

def _build_diagnostic_prompt(math_9_percent: int | None) -> str:
    pct = math_9_percent if math_9_percent is not None else 0
    pct_line = f"The percentage of marks obtained by this student in Class 9 Mathematics is {pct}%."
    return f"""You are a mathematics assessment designer for CBSE Class 10 (English medium).

We are onboarding a student to prepare for Class 10 Mathematics. Generate the assessment test based on the student's Class 9 result in Mathematics. {pct_line}
Generate exactly 25 multiple-choice questions to assess readiness for Class 10. We will compare the student's answers against the correct answers you provide and give them the correct result.

STRICT requirements:
- Give EXACTLY 25 questions. No more, no less.
- All questions must be about MATHEMATICS only (no other subjects).
- Each question must be a multiple-choice question (MCQ) with exactly four options: A, B, C, and D. Only one option is correct per question.
- You must provide the correct answer for each question so we can score the paper: set "correct_index" to 0, 1, 2, or 3 (the index of the correct option in the "options" array). This is the answer_key we use to check the student's answers and compute the result.
- Difficulty: appropriate for a student who has completed Class 9 (CBSE) and is starting Class 10. You may slightly adapt difficulty based on the Class 9 percentage given above.
- Cover a mix of chapters 1–14 from the Class 10 CBSE Maths syllabus below.

Syllabus chapters:
{SYLLABUS_OUTLINE.strip()}

Output format (IMPORTANT):
- Output ONLY a valid JSON array of EXACTLY 25 objects.
- No markdown, no code fences, no explanation.

Each object must have:
- "question_id": "q_1", "q_2", ... "q_25"
- "prompt": "Question text?"
- "options": ["option A text", "option B text", "option C text", "option D text"]  (exactly 4 strings)
- "correct_index": 0  (0, 1, 2, or 3 — the index of the ONE correct option; this is the answer_key for scoring)
- "chapter_number": 1  (integer 1–14)

Example (one item):
{{"question_id":"q_1","prompt":"What is the HCF of 12 and 18?","options":["3","6","9","12"],"correct_index":1,"chapter_number":1}}

Output the full JSON array of 25 questions now."""


async def generate_diagnostic_mcq(math_9_percent: int | None = None) -> tuple[list["DiagnosticQuestion"], dict[str, str]]:
    """Generate 25 MCQs via LLM. answer_key maps question_id -> correct option text (for checking answers).
    math_9_percent: student's Class 9 Mathematics percentage (0-100), used in the prompt for context."""
    from app.schemas.onboarding import DiagnosticQuestion

    prompt = _build_diagnostic_prompt(math_9_percent)
    provider = get_llm_provider(role="content_generator")
    try:
        text, meta = await provider.generate(prompt)
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
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id") or f"q_{i+1}"
        prompt_text = (item.get("prompt") or "").strip()
        opts = item.get("options")
        if not isinstance(opts, list) or len(opts) != 4:
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

    # Ensure exactly 25 questions: if the LLM returned more, trim; if fewer, pad by reusing earlier ones.
    if not questions:
        return [], {}
    if len(questions) > 25:
        questions = questions[:25]
        answer_key = {q.question_id: answer_key[q.question_id] for q in questions if q.question_id in answer_key}
    elif len(questions) < 25:
        base = list(questions)
        idx = 0
        while len(questions) < 25 and base:
            src = base[idx % len(base)]
            idx += 1
            dup_id = f"{src.question_id}_copy{len(questions)+1}"
            questions.append(
                DiagnosticQuestion(
                    question_id=dup_id,
                    question_type="mcq",
                    chapter_number=src.chapter_number,
                    prompt=src.prompt,
                    options=list(src.options or []),
                )
            )
            if src.question_id in answer_key and src.options:
                answer_key[dup_id] = answer_key[src.question_id]
    return questions, answer_key
