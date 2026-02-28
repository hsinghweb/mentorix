"""
Progress & Revision Agent — monitors mastery gaps and schedules revision.

Scans mastery map and assessment history to identify chapters needing revision,
computes retention decay, and recommends revision scheduling.
"""
import logging
from app.agents.base import BaseAgent
from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name

logger = logging.getLogger(__name__)

# Retention decay parameters
DECAY_WINDOW_WEEKS = 4    # After N weeks without practice, mastery decays
DECAY_RATE = 0.15         # 15% decay per window
REVISION_THRESHOLD = 0.50  # Below this, queue for revision


class ProgressRevisionAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        mastery_map = input_data.get("mastery_map", {})
        learner_id = input_data.get("learner_id")
        current_week = input_data.get("current_week", 1)
        completed_chapters = input_data.get("completed_chapters", [])
        # chapter_last_practiced: {ch_key: week_number} — when each chapter was last worked on
        last_practiced = input_data.get("chapter_last_practiced", {})

        revision_recommendations = []
        retention_adjustments = []
        overall_retention = 0.0
        chapters_assessed = 0

        for ch in SYLLABUS_CHAPTERS:
            ch_key = chapter_display_name(ch["number"])
            score = float(mastery_map.get(ch_key, 0.0))

            if score <= 0.0:
                continue  # Not started yet, skip

            chapters_assessed += 1
            last_week = last_practiced.get(ch_key, 1)
            weeks_since = max(0, current_week - last_week)

            # Apply retention decay
            decay_factor = max(0.0, 1.0 - (weeks_since / DECAY_WINDOW_WEEKS) * DECAY_RATE)
            adjusted_score = round(score * decay_factor, 3)
            overall_retention += adjusted_score

            if adjusted_score != score:
                retention_adjustments.append({
                    "chapter": ch_key,
                    "original_mastery": score,
                    "adjusted_mastery": adjusted_score,
                    "weeks_since_practice": weeks_since,
                    "decay_applied": round(score - adjusted_score, 3),
                })

            # Queue for revision if below threshold
            if adjusted_score < REVISION_THRESHOLD and ch_key in completed_chapters:
                urgency = "high" if adjusted_score < 0.30 else "medium"
                revision_recommendations.append({
                    "chapter": ch_key,
                    "title": ch["title"],
                    "current_mastery": adjusted_score,
                    "urgency": urgency,
                    "reason": f"Mastery decayed to {adjusted_score:.0%} after {weeks_since} weeks",
                })

        avg_retention = overall_retention / max(chapters_assessed, 1)

        # Sort by urgency (high first) then by mastery (lowest first)
        revision_recommendations.sort(
            key=lambda x: (0 if x["urgency"] == "high" else 1, x["current_mastery"])
        )

        return {
            "learner_id": str(learner_id) if learner_id else None,
            "chapters_assessed": chapters_assessed,
            "average_retention": round(avg_retention, 3),
            "retention_adjustments": retention_adjustments,
            "revision_recommendations": revision_recommendations[:5],  # Top 5 most urgent
            "revision_count": len(revision_recommendations),
            "agent": "progress_revision",
            "decision_type": "revision_analysis",
        }
