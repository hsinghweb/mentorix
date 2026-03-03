"""
Session-17 multi-agent compliance layer.

This module enforces:
1) Explicit agent role ownership.
2) Capability-based invocation contracts.
3) Structured inter-agent message envelopes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
import inspect

from app.core.event_bus import event_bus


class AgentRole(str, Enum):
    PLANNER = "planner"
    EXECUTOR = "executor"
    MEMORY = "memory"
    EVALUATOR = "evaluator"
    COMPLIANCE = "compliance"


@dataclass(slots=True)
class AgentEnvelope:
    run_id: str
    sender_role: AgentRole
    target_role: AgentRole
    target_agent: str
    capability: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "sender_role": self.sender_role.value,
            "target_role": self.target_role.value,
            "target_agent": self.target_agent,
            "capability": self.capability,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


@dataclass(slots=True)
class AgentContract:
    name: str
    role: AgentRole
    capabilities: dict[str, str]  # capability -> method name
    handler: Any


class AgentCoordinator:
    """Coordinator with capability and role checks before agent invocation."""

    def __init__(self):
        self._contracts: dict[str, AgentContract] = {}

    def register(
        self,
        *,
        name: str,
        role: AgentRole,
        capabilities: dict[str, str],
        handler: Any,
    ) -> None:
        if not capabilities:
            raise ValueError(f"Agent '{name}' must expose at least one capability.")
        self._contracts[name] = AgentContract(
            name=name,
            role=role,
            capabilities=dict(capabilities),
            handler=handler,
        )

    def contract_map(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "role": contract.role.value,
                "capabilities": sorted(contract.capabilities.keys()),
            }
            for name, contract in self._contracts.items()
        }

    async def dispatch(
        self,
        *,
        run_id: str,
        sender_role: AgentRole,
        target_agent: str,
        capability: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if target_agent not in self._contracts:
            raise ValueError(f"Unknown target agent '{target_agent}'.")
        contract = self._contracts[target_agent]
        if capability not in contract.capabilities:
            raise ValueError(
                f"Capability '{capability}' is not allowed for agent '{target_agent}'. "
                f"Allowed: {sorted(contract.capabilities.keys())}"
            )
        method_name = contract.capabilities[capability]
        method: Callable[..., Any] | None = getattr(contract.handler, method_name, None)
        if method is None:
            raise ValueError(
                f"Agent '{target_agent}' is missing required method '{method_name}' for capability '{capability}'."
            )

        envelope = AgentEnvelope(
            run_id=run_id,
            sender_role=sender_role,
            target_role=contract.role,
            target_agent=target_agent,
            capability=capability,
            payload=payload,
        )
        await event_bus.publish("agent_message", "agent_coordinator", envelope.as_dict())
        if method_name == "evaluate":
            result = await method(payload.get("answer", ""), payload.get("expected_answer", ""))
        else:
            params = inspect.signature(method).parameters
            if len(params) == 1:
                result = await method(payload)
            else:
                result = await method(**payload)
        await event_bus.publish(
            "agent_result",
            "agent_coordinator",
            {
                "run_id": run_id,
                "target_agent": target_agent,
                "target_role": contract.role.value,
                "capability": capability,
                "result_keys": sorted(list(result.keys())) if isinstance(result, dict) else [],
            },
        )
        return result
