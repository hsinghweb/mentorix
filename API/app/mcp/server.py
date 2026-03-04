from __future__ import annotations

from typing import Awaitable, Callable

from app.mcp.contracts import MCPRequest

Provider = Callable[[MCPRequest], Awaitable[dict]]


class MCPServer:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, operation: str, provider: Provider) -> None:
        self._providers[operation] = provider

    def has_provider(self, operation: str) -> bool:
        return operation in self._providers

    async def execute(self, request: MCPRequest) -> dict:
        if request.operation not in self._providers:
            raise KeyError(f"Unknown MCP operation: {request.operation}")
        return await self._providers[request.operation](request)


mcp_server = MCPServer()

