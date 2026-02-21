from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SkillMetadata:
    name: str
    version: str
    description: str
    intent_triggers: list[str]


class BaseSkill(ABC):
    @abstractmethod
    def get_metadata(self) -> SkillMetadata:
        raise NotImplementedError

    async def on_run_start(self, initial_prompt: str) -> str:
        return initial_prompt

    async def on_run_success(self, result: dict) -> dict:
        return {"summary": "completed", "result": result}

    async def on_run_failure(self, error: str) -> dict:
        return {"summary": f"failed: {error}"}
