"""
Learner Memory Timeline — compact event timeline with pruning and reflection.

Tracks wins, mistakes, weak_concepts, and interventions using the existing
memory hub infrastructure. Provides pruning policies and reflection generation
triggered on major events.
"""
from __future__ import annotations

import time
from typing import Any, Literal

from app.memory.store import memory_store

EVENT_TYPES = ("win", "mistake", "weak_concept", "intervention")
REFLECTION_TRIGGERS = ("final_test_completed", "week_transition")
HUB_TYPE = "learner_memory"


class LearnerMemoryTimeline:
    """Compact memory timeline per learner, stored in the memory hub."""

    def __init__(self, learner_id: str):
        self.learner_id = learner_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_timeline(self) -> dict:
        hubs = memory_store.get_all_hubs()
        bucket = hubs.get(HUB_TYPE, {})
        stored = bucket.get(self.learner_id)
        if isinstance(stored, dict) and "events" in stored:
            return stored
        return {"events": [], "reflections": []}

    def _save_timeline(self, payload: dict) -> None:
        memory_store.upsert_hub_entry(
            HUB_TYPE, self.learner_id, payload, learner_id=self.learner_id
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_event(
        self,
        event_type: Literal["win", "mistake", "weak_concept", "intervention"],
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        timeline = self._get_timeline()
        timeline["events"].append(
            {
                "timestamp": int(time.time()),
                "type": event_type,
                "content": content,
                "metadata": metadata or {},
            }
        )
        self._save_timeline(timeline)

    def get_events(self, event_type: str | None = None) -> list[dict]:
        timeline = self._get_timeline()
        events = timeline.get("events", [])
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        return events

    def get_summary(self) -> dict[str, Any]:
        """Single shared summary contract consumed by planner, reminders, analytics."""
        timeline = self._get_timeline()
        events = timeline.get("events", [])
        return {
            "total_events": len(events),
            "wins": sum(1 for e in events if e.get("type") == "win"),
            "mistakes": sum(1 for e in events if e.get("type") == "mistake"),
            "weak_concepts": [
                e.get("content") for e in events if e.get("type") == "weak_concept"
            ],
            "interventions": sum(
                1 for e in events if e.get("type") == "intervention"
            ),
            "latest_reflection": (
                timeline.get("reflections", [])[-1]
                if timeline.get("reflections")
                else None
            ),
        }

    # ------------------------------------------------------------------
    # Pruning
    # ------------------------------------------------------------------

    def prune(
        self, policy: Literal["recent-only", "mixed", "full"] = "recent-only"
    ) -> None:
        timeline = self._get_timeline()
        events = sorted(
            timeline.get("events", []),
            key=lambda x: x.get("timestamp", 0),
            reverse=True,
        )
        if policy == "recent-only":
            timeline["events"] = events[:50]
        elif policy == "mixed":
            recent = events[:20]
            important = [
                e
                for e in events[20:]
                if e.get("metadata", {}).get("important", False)
            ]
            timeline["events"] = recent + important
        # "full" keeps everything
        self._save_timeline(timeline)

    # ------------------------------------------------------------------
    # Reflections
    # ------------------------------------------------------------------

    def add_reflection(self, trigger: str, summary: str) -> None:
        if trigger not in REFLECTION_TRIGGERS:
            return
        timeline = self._get_timeline()
        timeline.setdefault("reflections", []).append(
            {"timestamp": int(time.time()), "trigger": trigger, "summary": summary}
        )
        self._save_timeline(timeline)
