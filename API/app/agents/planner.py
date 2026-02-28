"""
Curriculum Planner Agent — generates and recalculates the weekly plan.

Takes mastery map + profile context and outputs a week-by-chapter assignment plan,
respecting timeline constraints, weak-zone prioritization, and pacing.
"""
import json
import logging
from app.agents.base import BaseAgent
from app.core.llm_provider import get_llm_provider
from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name

logger = logging.getLogger(__name__)


class CurriculumPlannerAgent(BaseAgent):
    def __init__(self):
        self.provider = get_llm_provider(role="content_generator")

    async def run(self, input_data: dict) -> dict:
        mastery_map = input_data.get("mastery_map", {})
        learner_id = input_data.get("learner_id")
        total_weeks = input_data.get("total_weeks", 14)
        current_week = input_data.get("current_week", 1)
        cognitive_depth = input_data.get("cognitive_depth", 0.5)
        mode = input_data.get("mode", "generate")  # "generate" or "recalculate"

        # Classify chapters
        completed = []
        in_progress = []
        remaining = []
        for ch in SYLLABUS_CHAPTERS:
            ch_key = chapter_display_name(ch["number"])
            score = mastery_map.get(ch_key, 0.0)
            if score >= 0.60:
                completed.append({"chapter": ch_key, "title": ch["title"], "mastery": score})
            elif score > 0.0:
                in_progress.append({"chapter": ch_key, "title": ch["title"], "mastery": score})
            else:
                remaining.append({"chapter": ch_key, "title": ch["title"], "mastery": 0.0})

        weeks_left = max(1, total_weeks - current_week + 1)
        chapters_left = len(in_progress) + len(remaining)

        # Heuristic plan (fast path — no LLM needed)
        plan_weeks = []
        all_pending = in_progress + remaining
        chapters_per_week = max(1, (chapters_left + weeks_left - 1) // weeks_left)

        for i, ch_data in enumerate(all_pending):
            week_num = current_week + (i // chapters_per_week)
            if week_num > total_weeks:
                week_num = total_weeks
            plan_weeks.append({
                "week": week_num,
                "chapter": ch_data["chapter"],
                "focus": ch_data["title"],
                "priority": "high" if ch_data["mastery"] > 0 else "normal",
            })

        # For recalculation, try LLM-based optimization
        reasoning = None
        if mode == "recalculate" and chapters_left > 0:
            try:
                in_prog_strs = [c["chapter"] + "(" + f"{c['mastery']:.0%}" + ")" for c in in_progress]
                prompt = (
                    f"You are a curriculum pace optimizer for a Class 10 CBSE math student.\n"
                    f"Cognitive depth: {cognitive_depth:.2f}\n"
                    f"Weeks left: {weeks_left}, Chapters left: {chapters_left}\n"
                    f"Completed: {json.dumps([c['chapter'] for c in completed])}\n"
                    f"In-progress (partial mastery): {json.dumps(in_prog_strs)}\n"
                    f"Remaining: {json.dumps([c['chapter'] for c in remaining])}\n\n"
                    f"Recommend the best weekly assignment. Prioritize chapters where student "
                    f"has partial progress. Return a brief recommendation (2-3 sentences)."
                )
                llm_text, _ = await self.provider.generate(prompt)
                reasoning = llm_text.strip() if llm_text else None
            except Exception as exc:
                logger.warning("Planner LLM recalculation failed: %s", exc)

        return {
            "plan": plan_weeks,
            "completed_chapters": len(completed),
            "remaining_chapters": chapters_left,
            "weeks_left": weeks_left,
            "chapters_per_week": chapters_per_week,
            "reasoning": reasoning,
            "agent": "planner",
            "decision_type": "plan_generated" if mode == "generate" else "plan_recalculated",
        }
