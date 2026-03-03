from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """
    Base contract for all Mentorix agents.

    Session-17 compliance:
    - Each concrete agent should declare `role` and `capabilities`.
    - `run(...)` remains the canonical entrypoint for orchestration calls unless a
      specific capability explicitly maps to another method (for example `evaluate`).
    """
    role: str = "unspecified"
    capabilities: tuple[str, ...] = ()

    @abstractmethod
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
