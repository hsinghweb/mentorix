"""
AssessmentAgent — evaluates student answers using LLM-backed reasoning.

Enriched from stub to use the ReasoningEngine for assessment grading
with structured evaluation criteria and error classification.
"""
from __future__ import annotations

from typing import Any

from app.agents.agent_interface import AgentContext, AgentInterface, AgentResult
from app.agents.base import BaseAgent
from app.core.llm_provider import get_llm_provider


class AssessmentAgent(BaseAgent, AgentInterface):
    """Evaluates student answers with LLM-backed reasoning and error classification."""

    name = "assessment_agent"
    role = "evaluator"
    capabilities = ("generate_assessment", "evaluate_answer")
    reads = ["LearnerProfile", "AssessmentResult"]
    writes = ["AssessmentResult", "AgentDecision"]

    # ── Scoring thresholds ───────────────────────────────────────────
    CORRECT_SCORE = 1.0
    PARTIAL_SCORE = 0.6
    INCORRECT_SCORE = 0.35

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Legacy BaseAgent interface: generate a practice question."""
        concept = input_data.get("concept", "unknown")
        difficulty = input_data.get("difficulty", 1)
        question = f"Solve one practice question for '{concept}' at difficulty level {difficulty}."
        expected_answer = concept.split("_")[0] if "_" in concept else concept.split()[0]
        return {"generated_question": question, "expected_answer": expected_answer.lower()}

    async def _execute(self, context: AgentContext) -> AgentResult:
        """
        AgentInterface entry point: evaluate a student's answer using LLM.

        Expected context.extra keys:
            question (str): the question prompt
            student_answer (str): the student's response
            expected_answer (str): the reference answer
            chapter (str): chapter name for context
        """
        question = context.extra.get("question", "")
        student_answer = context.extra.get("student_answer", "")
        expected_answer = context.extra.get("expected_answer", "")
        chapter = context.chapter or "unknown"

        # Attempt LLM evaluation
        try:
            provider = get_llm_provider(role="evaluator")
            eval_prompt = (
                f"You are a math teacher evaluating a Class 10 CBSE student answer.\n"
                f"Chapter: {chapter}\n"
                f"Question: {question}\n"
                f"Expected Answer: {expected_answer}\n"
                f"Student Answer: {student_answer}\n\n"
                f"Evaluate the student's answer. Respond with EXACTLY:\n"
                f"SCORE: <0.0 to 1.0>\n"
                f"ERROR_TYPE: <none|concept_mismatch|calculation_error|incomplete|off_topic>\n"
                f"FEEDBACK: <one sentence feedback>\n"
            )
            text, _ = await provider.generate(eval_prompt)
            if text:
                score, error_type, feedback = self._parse_evaluation(text)
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    decision=f"evaluated_score_{score:.2f}",
                    reasoning=feedback,
                    data={
                        "score": score,
                        "error_type": error_type,
                        "feedback": feedback,
                        "method": "llm",
                    },
                )
        except Exception:
            pass

        # Deterministic fallback
        score, error_type = self._deterministic_evaluate(student_answer, expected_answer)
        return AgentResult(
            success=True,
            agent_name=self.name,
            decision=f"evaluated_score_{score:.2f}",
            reasoning="Deterministic evaluation (LLM unavailable)",
            data={
                "score": score,
                "error_type": error_type,
                "feedback": "Answer evaluated using pattern matching.",
                "method": "deterministic",
            },
        )

    async def evaluate(self, answer: str, expected_answer: str) -> dict:
        """Legacy evaluate interface for backward compatibility."""
        score, error_type = self._deterministic_evaluate(answer, expected_answer)
        return {"score": score, "error_type": error_type}

    def _deterministic_evaluate(self, answer: str, expected_answer: str) -> tuple[float, str]:
        """Deterministic fallback: compare answer against expected using heuristics."""
        answer_l = (answer or "").lower().strip()
        expected_l = (expected_answer or "").lower().strip()
        if not answer_l:
            return self.INCORRECT_SCORE, "incomplete"
        if expected_l in answer_l and len(answer_l) > 8:
            return self.CORRECT_SCORE, "none"
        if any(tok in answer_l for tok in expected_l.split()):
            return self.PARTIAL_SCORE, "incomplete"
        return self.INCORRECT_SCORE, "concept_mismatch"

    @staticmethod
    def _parse_evaluation(text: str) -> tuple[float, str, str]:
        """Parse structured LLM evaluation output."""
        import re
        score = 0.5
        error_type = "none"
        feedback = "Evaluated."
        score_match = re.search(r"SCORE:\s*([\d.]+)", text)
        if score_match:
            score = max(0.0, min(1.0, float(score_match.group(1))))
        error_match = re.search(r"ERROR_TYPE:\s*(\S+)", text)
        if error_match:
            error_type = error_match.group(1).strip().lower()
        feedback_match = re.search(r"FEEDBACK:\s*(.+)", text)
        if feedback_match:
            feedback = feedback_match.group(1).strip()
        return score, error_type, feedback
