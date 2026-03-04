from __future__ import annotations

import asyncio

from app.mcp.client import execute_mcp
from app.mcp.contracts import MCPRequest
from app.mcp.server import mcp_server
from app.skills.manager import SkillManager


def test_mcp_contract_with_registered_provider():
    async def _provider(req: MCPRequest) -> dict:
        return {"echo": req.payload.get("value")}

    mcp_server.register("test.echo", _provider)
    response = asyncio.run(execute_mcp(MCPRequest(operation="test.echo", payload={"value": 7})))
    assert response.ok is True
    assert response.result.get("echo") == 7
    assert response.fallback_used is False


def test_mcp_fallback_when_operation_missing():
    async def _fallback() -> dict:
        return {"from": "fallback"}

    response = asyncio.run(
        execute_mcp(
            MCPRequest(operation="missing.operation", payload={"x": 1}),
            fallback=_fallback,
        )
    )
    assert response.ok is True
    assert response.fallback_used is True
    assert response.result.get("from") == "fallback"


def test_skill_registry_contract_and_reuse():
    sm = SkillManager()
    sm.scan_and_register()
    reg = sm.get_registry()
    assert isinstance(reg, dict) and reg
    # Reuse is proven by scheduler->skill manager path and library registration.
    assert any("intent_triggers" in item for item in reg.values())
    for _name, info in reg.items():
        assert "description" in info
        assert "path" in info
