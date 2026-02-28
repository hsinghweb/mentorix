"""
Agent Decision Logger — writes every agent decision to the agent_decisions table.

Provides a single helper function that any agent or endpoint can call
to record decisions for full observability.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AgentDecision

logger = logging.getLogger(__name__)


async def log_agent_decision(
    db: AsyncSession,
    learner_id: UUID,
    agent_name: str,
    decision_type: str,
    chapter: str | None = None,
    section_id: str | None = None,
    input_snapshot: dict | None = None,
    output_payload: dict | None = None,
    confidence: float | None = None,
    reasoning: str | None = None,
) -> None:
    """Record an agent decision to database for observability."""
    try:
        decision = AgentDecision(
            learner_id=learner_id,
            agent_name=agent_name,
            decision_type=decision_type,
            chapter=chapter,
            section_id=section_id,
            input_snapshot=input_snapshot or {},
            output_payload=output_payload or {},
            confidence=confidence,
            reasoning=reasoning,
        )
        db.add(decision)
        await db.flush()
        logger.info(
            "Agent decision logged: agent=%s type=%s learner=%s chapter=%s",
            agent_name, decision_type, learner_id, chapter,
        )
    except Exception as exc:
        logger.warning("Failed to log agent decision: %s", exc)
        # Non-critical — don't let logging failure break the flow
