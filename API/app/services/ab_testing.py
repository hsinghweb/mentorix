"""
A/B Testing Framework — experiment assignment and tracking for content strategies.

Enables randomized experiments across:
- Content difficulty strategies (adaptive vs. fixed)
- Tone/style variations (supportive vs. challenging)
- Revision frequency policies

Stores experiment state in PostgreSQL for reproducibility.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Column, DateTime, Integer, String, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_domain_logger

logger = get_domain_logger(__name__, "analytics")


# ── Experiment Configuration ─────────────────────────────────────────

@dataclass
class Experiment:
    """Definition of an A/B experiment."""
    experiment_id: str
    name: str
    description: str
    groups: list[str] = field(default_factory=lambda: ["control", "treatment"])
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Built-in Experiments ─────────────────────────────────────────────

EXPERIMENTS: dict[str, Experiment] = {
    "content_difficulty": Experiment(
        experiment_id="content_difficulty",
        name="Adaptive vs Fixed Difficulty",
        description="Compare adaptive difficulty adjustment against fixed medium difficulty",
        groups=["adaptive", "fixed_medium"],
    ),
    "tone_strategy": Experiment(
        experiment_id="tone_strategy",
        name="Supportive vs Neutral Tone",
        description="Compare supportive tone with neutral delivery for learning outcomes",
        groups=["supportive", "neutral", "challenging"],
    ),
    "revision_frequency": Experiment(
        experiment_id="revision_frequency",
        name="Revision Queue Frequency",
        description="Compare aggressive vs relaxed revision scheduling",
        groups=["aggressive", "standard", "relaxed"],
    ),
    "explanation_style": Experiment(
        experiment_id="explanation_style",
        name="Analogy vs Direct Explanation",
        description="Test whether analogy-heavy explanations improve mastery over direct explanations",
        groups=["analogy_heavy", "direct", "mixed"],
    ),
}


def _deterministic_group(learner_id: str, experiment_id: str, groups: list[str]) -> str:
    """
    Deterministically assign a learner to an experiment group using
    consistent hashing. Same learner always gets the same group.
    """
    hash_input = f"{learner_id}:{experiment_id}"
    hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
    return groups[hash_value % len(groups)]


# ── Assignment tracking ──────────────────────────────────────────────

_assignments: dict[str, dict[str, str]] = {}


def get_experiment_group(
    learner_id: str,
    experiment_id: str,
) -> str | None:
    """
    Get the experiment group for a learner. Returns None if experiment
    doesn't exist or is inactive.
    """
    experiment = EXPERIMENTS.get(experiment_id)
    if not experiment or not experiment.active:
        return None

    key = f"{learner_id}:{experiment_id}"
    if key in _assignments:
        return _assignments[key]

    group = _deterministic_group(learner_id, experiment_id, experiment.groups)
    _assignments[key] = group

    logger.info(
        "event=experiment_assigned learner=%s experiment=%s group=%s",
        learner_id, experiment_id, group,
    )
    return group


def get_all_assignments(learner_id: str) -> dict[str, str]:
    """Get all experiment group assignments for a learner."""
    result = {}
    for exp_id, exp in EXPERIMENTS.items():
        if exp.active:
            group = get_experiment_group(learner_id, exp_id)
            if group:
                result[exp_id] = group
    return result


# ── Experiment results tracking ──────────────────────────────────────

@dataclass
class ExperimentEvent:
    """A tracked event within an experiment."""
    learner_id: str
    experiment_id: str
    group: str
    event_type: str  # "content_view", "test_score", "chapter_complete"
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_events: list[ExperimentEvent] = []


def track_experiment_event(
    learner_id: str,
    experiment_id: str,
    event_type: str,
    value: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Track an event for experiment analysis."""
    group = get_experiment_group(learner_id, experiment_id)
    if not group:
        return

    event = ExperimentEvent(
        learner_id=learner_id,
        experiment_id=experiment_id,
        group=group,
        event_type=event_type,
        value=value,
        metadata=metadata or {},
    )
    _events.append(event)
    logger.debug(
        "event=experiment_tracked experiment=%s group=%s type=%s value=%.2f",
        experiment_id, group, event_type, value,
    )


def get_experiment_results(experiment_id: str) -> dict[str, Any]:
    """
    Compute summary statistics for an experiment.

    Returns per-group aggregates: count, mean, min, max for each event type.
    """
    experiment = EXPERIMENTS.get(experiment_id)
    if not experiment:
        return {"error": f"Unknown experiment: {experiment_id}"}

    relevant = [e for e in _events if e.experiment_id == experiment_id]
    if not relevant:
        return {
            "experiment_id": experiment_id,
            "name": experiment.name,
            "total_events": 0,
            "groups": {},
        }

    groups: dict[str, dict[str, list[float]]] = {}
    for event in relevant:
        if event.group not in groups:
            groups[event.group] = {}
        if event.event_type not in groups[event.group]:
            groups[event.group][event.event_type] = []
        groups[event.group][event.event_type].append(event.value)

    summary: dict[str, Any] = {}
    for group, event_types in groups.items():
        summary[group] = {}
        for event_type, values in event_types.items():
            n = len(values)
            summary[group][event_type] = {
                "count": n,
                "mean": round(sum(values) / n, 4) if n > 0 else 0,
                "min": round(min(values), 4) if values else 0,
                "max": round(max(values), 4) if values else 0,
            }

    return {
        "experiment_id": experiment_id,
        "name": experiment.name,
        "description": experiment.description,
        "total_events": len(relevant),
        "unique_learners": len(set(e.learner_id for e in relevant)),
        "groups": summary,
    }


def list_experiments() -> list[dict[str, Any]]:
    """List all defined experiments with their status."""
    return [
        {
            "experiment_id": exp.experiment_id,
            "name": exp.name,
            "description": exp.description,
            "groups": exp.groups,
            "active": exp.active,
            "total_events": sum(1 for e in _events if e.experiment_id == exp.experiment_id),
        }
        for exp in EXPERIMENTS.values()
    ]
