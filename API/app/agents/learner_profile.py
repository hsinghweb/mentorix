"""
Learner Profiling Agent — analyzes mastery map and engagement to produce profile updates.

Categorizes chapters into bands, identifies weak zones, computes confidence metrics,
and recommends focus areas.
"""
import logging
from app.agents.base import BaseAgent
from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name

logger = logging.getLogger(__name__)


def _mastery_band(score: float) -> str:
    if score >= 0.80:
        return "mastered"
    if score >= 0.60:
        return "proficient"
    if score >= 0.30:
        return "developing"
    return "beginner"


class LearnerProfilingAgent(BaseAgent):
    async def run(self, input_data: dict) -> dict:
        mastery_map = input_data.get("mastery_map", {})
        learner_id = input_data.get("learner_id")
        cognitive_depth = input_data.get("cognitive_depth", 0.5)
        engagement_score = input_data.get("engagement_score", 0.5)

        # Per-chapter breakdown
        chapter_breakdown = []
        total_mastery = 0.0
        weak_zones = []
        strong_zones = []

        for ch in SYLLABUS_CHAPTERS:
            ch_key = chapter_display_name(ch["number"])
            score = float(mastery_map.get(ch_key, 0.0))
            band = _mastery_band(score)
            total_mastery += score

            entry = {
                "chapter": ch_key,
                "title": ch["title"],
                "mastery_score": round(score, 3),
                "band": band,
                "subtopic_count": len(ch.get("subtopics", [])),
            }
            chapter_breakdown.append(entry)

            if score < 0.40:
                weak_zones.append(ch_key)
            elif score >= 0.80:
                strong_zones.append(ch_key)

        avg_mastery = total_mastery / max(len(SYLLABUS_CHAPTERS), 1)

        # Confidence metric: weighted blend of mastery, cognitive depth, engagement
        confidence = round(
            0.50 * avg_mastery + 0.30 * cognitive_depth + 0.20 * engagement_score, 3
        )

        # Recommended focus: weakest chapters first
        focus_chapters = sorted(
            chapter_breakdown, key=lambda x: x["mastery_score"]
        )[:3]

        return {
            "learner_id": str(learner_id) if learner_id else None,
            "chapter_breakdown": chapter_breakdown,
            "average_mastery": round(avg_mastery, 3),
            "confidence_metric": confidence,
            "weak_zones": weak_zones,
            "strong_zones": strong_zones,
            "recommended_focus": [c["chapter"] for c in focus_chapters],
            "mastery_distribution": {
                "mastered": sum(1 for c in chapter_breakdown if c["band"] == "mastered"),
                "proficient": sum(1 for c in chapter_breakdown if c["band"] == "proficient"),
                "developing": sum(1 for c in chapter_breakdown if c["band"] == "developing"),
                "beginner": sum(1 for c in chapter_breakdown if c["band"] == "beginner"),
            },
            "agent": "profiling",
            "decision_type": "profile_analysis",
        }
