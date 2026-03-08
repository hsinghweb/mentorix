"""
Adaptive Intervention Engine — derives interventions from learner state profile
and memory timeline signals.

Each intervention carries an explicit reason_code, source_signals dict,
and a UI tooltip for "Why this recommendation".
"""
from __future__ import annotations

from typing import Any


def derive_interventions(
    profile: dict[str, Any],
    memory_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Produce a list of intervention recommendations.

    Args:
        profile: output of ``compute_learner_state_profile``
        memory_summary: output of ``LearnerMemoryTimeline.get_summary``

    Returns:
        list of dicts each containing type, reason_code, source_signals, ui_tooltip
    """
    interventions: list[dict[str, Any]] = []

    confusion_risk = float(profile.get("confusion_risk", 0.0))
    pace = float(profile.get("pace", 0.5))
    error_rate = float(profile.get("admin_metrics", {}).get("error_rate", 0.0))
    motivation = float(profile.get("motivation", 0.5))

    weak_concepts = memory_summary.get("weak_concepts", [])
    mistake_count = int(memory_summary.get("mistakes", 0))

    # --- Remedial ---
    if confusion_risk > 0.6 or mistake_count > 5:
        interventions.append(
            {
                "type": "remedial",
                "reason_code": "HIGH_CONFUSION_RISK",
                "source_signals": {
                    "confusion_risk": confusion_risk,
                    "mistake_count": mistake_count,
                },
                "ui_tooltip": (
                    "We noticed you're struggling with recent concepts. "
                    "Let's do a quick remedial review."
                ),
            }
        )

    # --- Pace-down ---
    if pace > 0.7 and error_rate > 0.4:
        interventions.append(
            {
                "type": "pace-down",
                "reason_code": "FAST_PACE_HIGH_ERROR",
                "source_signals": {"pace": pace, "error_rate": error_rate},
                "ui_tooltip": (
                    "You're moving fast but making some mistakes. "
                    "Let's slow down and focus on accuracy."
                ),
            }
        )

    # --- Pace-up ---
    if pace < 0.4 and error_rate < 0.2 and motivation >= 0.5:
        interventions.append(
            {
                "type": "pace-up",
                "reason_code": "SLOW_PACE_LOW_ERROR",
                "source_signals": {"pace": pace, "error_rate": error_rate},
                "ui_tooltip": (
                    "You are doing great! Let's pick up the pace "
                    "and challenge you more."
                ),
            }
        )

    # --- Revision-first ---
    if weak_concepts:
        interventions.append(
            {
                "type": "revision-first",
                "reason_code": "UNRESOLVED_WEAK_CONCEPTS",
                "source_signals": {"weak_concept_count": len(weak_concepts)},
                "ui_tooltip": (
                    "Before we move on, let's revise some concepts "
                    "you found tricky earlier."
                ),
            }
        )

    # --- Motivation boost ---
    if motivation < 0.3:
        interventions.append(
            {
                "type": "motivation-boost",
                "reason_code": "LOW_MOTIVATION",
                "source_signals": {"motivation": motivation},
                "ui_tooltip": (
                    "It looks like engagement has dipped recently. "
                    "Let's celebrate your wins and set a small goal!"
                ),
            }
        )

    return interventions
