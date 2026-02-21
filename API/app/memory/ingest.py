from __future__ import annotations

from app.memory.hubs import structured_hubs


def ingest_session_signal(*, learner_id: str, concept: str, score: float, adaptation_score: float) -> None:
    structured_hubs.upsert(
        "learner_preferences",
        learner_id,
        {
            "preferred_explanation_density": "high" if score < 0.6 else "compact",
            "last_concept": concept,
            "last_score": score,
        },
    )
    structured_hubs.upsert(
        "operating_context",
        learner_id,
        {
            "recent_adaptation_score": adaptation_score,
            "intervention_required": adaptation_score > 0.6,
        },
    )
    structured_hubs.upsert(
        "soft_identity",
        learner_id,
        {
            "confidence_band": "low" if score < 0.6 else "improving",
            "engagement_hint": "encourage_with_examples",
        },
    )


def get_memory_context(learner_id: str) -> dict:
    all_hubs = structured_hubs.get_all()
    return {
        "learner_preferences": all_hubs["learner_preferences"].get(learner_id, {}),
        "operating_context": all_hubs["operating_context"].get(learner_id, {}),
        "soft_identity": all_hubs["soft_identity"].get(learner_id, {}),
    }
