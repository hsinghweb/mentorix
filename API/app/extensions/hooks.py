from abc import ABC, abstractmethod
from typing import Any


class BKTStrategy(ABC):
    @abstractmethod
    async def update_knowledge(self, learner_id: str, concept: str, signal: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class RLPolicy(ABC):
    @abstractmethod
    async def choose_action(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class MultimodalGenerator(ABC):
    @abstractmethod
    async def generate(self, concept: str, difficulty: int, context: str) -> dict[str, Any]:
        raise NotImplementedError


class ExplainabilityAdapter(ABC):
    @abstractmethod
    async def build_trace(self, decision_payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
