"""
Diagnostic MCQ Agent — generates MCQ questions for a topic using LLM + NCERT grounding.

Can generate questions for question_bank or on-the-fly tests. Uses template fallback
when LLM is unavailable.
"""
import json
import logging
import random
from typing import TYPE_CHECKING
from app.agents.base import BaseAgent
from app.core.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.schemas.onboarding import DiagnosticQuestion


class DiagnosticMCQAgent(BaseAgent):
    def __init__(self):
        self.provider = get_llm_provider(role="content_generator")

    async def run(self, input_data: dict) -> dict:
        chapter_number = input_data.get("chapter_number", 1)
        section_id = input_data.get("section_id")
        section_title = input_data.get("section_title", "General")
        chapter_title = input_data.get("chapter_title", f"Chapter {chapter_number}")
        difficulty = input_data.get("difficulty", 2)  # 1-5
        count = input_data.get("count", 5)
        context = input_data.get("context", "")  # RAG chunks

        questions = []

        if context:
            difficulty_label = {1: "easy", 2: "medium", 3: "moderate", 4: "hard", 5: "challenging"}.get(difficulty, "medium")
            prompt = (
                f"You are an expert math teacher creating MCQ questions for Class 10 CBSE.\n"
                f"Chapter: {chapter_title}\n"
                f"Section: {section_id} - {section_title}\n"
                f"Difficulty: {difficulty_label}\n"
                f"Generate exactly {count} multiple-choice questions.\n\n"
                f"Use ONLY this NCERT content:\n{context}\n\n"
                f"Format: Return a JSON array of {count} objects:\n"
                f'  {{"q": "question text", "options": ["A", "B", "C", "D"], "correct": 0, "explanation": "brief explanation"}}\n'
                f"where correct is 0-3 (index of correct option). Use \\\\( \\\\) for inline LaTeX.\n"
                f"Return ONLY the JSON array.\n"
            )

            try:
                llm_text, _ = await self.provider.generate(prompt)
                if llm_text:
                    text = llm_text.strip()
                    start = text.find("[")
                    end = text.rfind("]") + 1
                    if start >= 0 and end > start:
                        parsed = json.loads(text[start:end])
                        for i, item in enumerate(parsed[:count]):
                            options = item.get("options", ["A", "B", "C", "D"])
                            correct_idx = int(item.get("correct", 0))
                            if correct_idx < 0 or correct_idx >= len(options):
                                correct_idx = 0
                            questions.append({
                                "question_text": item.get("q", f"Question {i+1}"),
                                "options": options,
                                "correct_index": correct_idx,
                                "explanation": item.get("explanation", ""),
                                "difficulty": difficulty,
                                "chapter_number": chapter_number,
                                "section_id": section_id,
                                "source": "llm",
                            })
            except Exception as exc:
                logger.warning("DiagnosticMCQ LLM generation failed: %s", exc)

        # Fallback: template questions
        if len(questions) < count:
            for i in range(count - len(questions)):
                questions.append({
                    "question_text": f"Which concept is central to '{section_title}'?",
                    "options": [
                        f"Correct definition of {section_title}",
                        "Incorrect variant A",
                        "Incorrect variant B",
                        "Unrelated concept",
                    ],
                    "correct_index": 0,
                    "explanation": f"This tests basic understanding of {section_title}.",
                    "difficulty": difficulty,
                    "chapter_number": chapter_number,
                    "section_id": section_id,
                    "source": "template",
                })

        return {
            "questions": questions,
            "count": len(questions),
            "chapter_number": chapter_number,
            "section_id": section_id,
            "agent": "diagnostic_mcq",
            "decision_type": "questions_generated",
        }


async def generate_diagnostic_mcq(math_9_percent: int = 0) -> tuple[list["DiagnosticQuestion"], dict[str, str]]:
    """
    Generate onboarding diagnostic MCQs as a fallback when static sets are unavailable.
    Returns:
      - questions: list[DiagnosticQuestion]
      - answer_key: dict[question_id, correct_option_text_lower]
    """
    from app.schemas.onboarding import DiagnosticQuestion

    target_count = 25
    clamped_percent = max(0, min(100, int(math_9_percent)))
    base_chapters = list(range(1, 15))
    questions: list[DiagnosticQuestion] = []
    answer_key: dict[str, str] = {}

    for idx in range(target_count):
        chapter_number = base_chapters[idx % len(base_chapters)]
        prompt = f"Chapter {chapter_number}: Select the correct statement."
        options = [
            f"Core concept of Chapter {chapter_number}",
            f"Incorrect variation A for Chapter {chapter_number}",
            f"Incorrect variation B for Chapter {chapter_number}",
            "None of these",
        ]

        # Slightly vary correct option with prior performance to avoid fixed pattern.
        if clamped_percent >= 70:
            correct_index = (idx + 1) % 4
        elif clamped_percent <= 30:
            correct_index = idx % 2
        else:
            correct_index = random.randint(0, 3)

        question_id = f"gen_q_{idx + 1}"
        questions.append(
            DiagnosticQuestion(
                question_id=question_id,
                question_type="mcq",
                chapter_number=chapter_number,
                prompt=prompt,
                options=options,
            )
        )
        answer_key[question_id] = options[correct_index].strip().lower()

    return questions, answer_key
