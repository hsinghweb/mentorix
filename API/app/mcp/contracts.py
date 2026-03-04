from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class MCPRequest(BaseModel):
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class MCPResponse(BaseModel):
    operation: str
    ok: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    fallback_used: bool = False
    latency_ms: float = 0.0
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

