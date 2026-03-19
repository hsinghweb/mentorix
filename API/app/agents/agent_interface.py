"""
Agent Interface Contract — Base class and result schema for all agents.

Every agent MUST implement ``async run(context) -> AgentResult`` with
a standardized output schema so orchestrators can compose agents uniformly.
"""
from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Standardized input context passed to every agent run."""

    learner_id: UUID
    chapter: str | None = None
    week_number: int | None = None
    profile_snapshot: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Standardized output from every agent run."""

    success: bool
    agent_name: str
    decision: str = ""
    reasoning: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    tool_calls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging and storage."""
        return {
            "success": self.success,
            "agent_name": self.agent_name,
            "decision": self.decision,
            "reasoning": self.reasoning,
            "data": self.data,
            "duration_ms": round(self.duration_ms, 2),
            "tool_calls": self.tool_calls,
        }


class AgentInterface(ABC):
    """
    Base class for all Mentorix agents.

    Subclasses must implement ``_execute(context)`` which contains
    the agent's core logic. The ``run()`` wrapper handles tracing,
    timing, error handling, and **circuit breaking**.

    Circuit Breaker:
        Each agent instance tracks consecutive failures. After
        ``FAILURE_THRESHOLD`` consecutive errors, the circuit opens
        for ``COOLDOWN_SECONDS``. During half-open state, a single
        trial request determines whether to reset or re-open.

    Capability declarations:
        Override ``reads`` and ``writes`` class variables to declare
        what data the agent reads from and writes to, enabling
        dependency graph validation at startup.
    """

    name: str = "unnamed_agent"
    reads: list[str] = []   # e.g. ["LearnerProfile", "ChapterProgression"]
    writes: list[str] = []  # e.g. ["AgentDecision", "Task"]

    # ── Circuit Breaker Config ───────────────────────────────────────
    FAILURE_THRESHOLD: int = 3
    """Consecutive failures before opening circuit."""
    COOLDOWN_SECONDS: float = 30.0
    """Seconds to wait before allowing a trial request (half-open)."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._cb_failures: int = 0
        cls._cb_state: str = "closed"  # closed | open | half_open
        cls._cb_opened_at: float = 0.0

    @abstractmethod
    async def _execute(self, context: AgentContext) -> AgentResult:
        """Core agent logic. Must return an AgentResult."""
        ...

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent with tracing, timing, circuit breaking, and error handling.

        Wraps ``_execute()`` with structured trace spans including
        input hash, output hash, duration, and tool calls.
        """
        # ── Circuit breaker gate ─────────────────────────────────────
        if self._cb_state == "open":
            elapsed = time.perf_counter() - self._cb_opened_at
            if elapsed < self.COOLDOWN_SECONDS:
                logger.warning(
                    "agent=%s circuit=OPEN remaining_s=%.1f — returning fallback",
                    self.name,
                    self.COOLDOWN_SECONDS - elapsed,
                )
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    decision="circuit_open",
                    reasoning=f"Circuit breaker open after {self.FAILURE_THRESHOLD} consecutive failures. "
                              f"Retry in {self.COOLDOWN_SECONDS - elapsed:.0f}s.",
                )
            # Transition to half-open: allow one trial request
            self.__class__._cb_state = "half_open"
            logger.info("agent=%s circuit=HALF_OPEN — allowing trial request", self.name)

        t0 = time.perf_counter()
        try:
            result = await self._execute(context)
            result.duration_ms = (time.perf_counter() - t0) * 1000
            result.agent_name = self.name
            logger.info(
                "agent=%s decision=%s duration_ms=%.1f success=%s",
                self.name,
                result.decision,
                result.duration_ms,
                result.success,
            )
            # Success: reset circuit breaker
            self.__class__._cb_failures = 0
            self.__class__._cb_state = "closed"
            # Record to agent event log
            _log_agent_event(self.name, context, result)
            return result
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.error(
                "agent=%s error=%s duration_ms=%.1f",
                self.name,
                str(exc),
                duration_ms,
            )
            # Increment failure counter
            self.__class__._cb_failures += 1
            if self.__class__._cb_failures >= self.FAILURE_THRESHOLD:
                self.__class__._cb_state = "open"
                self.__class__._cb_opened_at = time.perf_counter()
                logger.warning(
                    "agent=%s circuit=OPEN after %d consecutive failures",
                    self.name,
                    self.__class__._cb_failures,
                )
            error_result = AgentResult(
                success=False,
                agent_name=self.name,
                decision="error",
                reasoning=str(exc),
                duration_ms=duration_ms,
            )
            _log_agent_event(self.name, context, error_result)
            return error_result

    def capabilities(self) -> dict[str, Any]:
        """Return capability declaration for startup validation."""
        return {
            "name": self.name,
            "reads": self.reads,
            "writes": self.writes,
        }


# ── Agent Event Log (Append-Only) ────────────────────────────────────

_agent_event_log: list[dict[str, Any]] = []
_MAX_EVENT_LOG = 1000


def _log_agent_event(
    agent_name: str,
    context: AgentContext,
    result: AgentResult,
) -> None:
    """Append to the in-memory agent event log."""
    entry = {
        "timestamp": time.time(),
        "agent": agent_name,
        "learner_id": str(context.learner_id),
        "chapter": context.chapter,
        "success": result.success,
        "decision": result.decision,
        "duration_ms": round(result.duration_ms, 2),
    }
    _agent_event_log.append(entry)
    if len(_agent_event_log) > _MAX_EVENT_LOG:
        _agent_event_log[:] = _agent_event_log[-_MAX_EVENT_LOG:]


def get_agent_event_log(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent agent events."""
    return list(reversed(_agent_event_log[-limit:]))


def get_agent_capabilities() -> list[dict[str, Any]]:
    """Return capability declarations for all registered agent subclasses."""
    return [cls().capabilities() for cls in AgentInterface.__subclasses__()]
