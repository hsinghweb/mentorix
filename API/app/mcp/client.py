from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from app.core.mcp_metrics import record_mcp_call
from app.mcp.contracts import MCPRequest, MCPResponse
from app.mcp.server import mcp_server


async def execute_mcp(
    request: MCPRequest,
    *,
    fallback: Callable[[], Awaitable[dict]] | None = None,
) -> MCPResponse:
    start = time.perf_counter()
    failed = False
    fallback_used = False
    try:
        result = await mcp_server.execute(request)
        latency_ms = (time.perf_counter() - start) * 1000.0
        record_mcp_call(latency_ms=latency_ms, failed=False, fallback_used=False)
        return MCPResponse(
            operation=request.operation,
            ok=True,
            result=result if isinstance(result, dict) else {"value": result},
            latency_ms=round(latency_ms, 2),
        )
    except Exception as exc:
        failed = True
        if fallback is None:
            latency_ms = (time.perf_counter() - start) * 1000.0
            record_mcp_call(latency_ms=latency_ms, failed=True, fallback_used=False)
            return MCPResponse(
                operation=request.operation,
                ok=False,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )
        try:
            fallback_used = True
            result = await fallback()
            latency_ms = (time.perf_counter() - start) * 1000.0
            record_mcp_call(latency_ms=latency_ms, failed=failed, fallback_used=fallback_used)
            return MCPResponse(
                operation=request.operation,
                ok=True,
                result=result if isinstance(result, dict) else {"value": result},
                error=str(exc),
                fallback_used=True,
                latency_ms=round(latency_ms, 2),
            )
        except Exception as fallback_exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            record_mcp_call(latency_ms=latency_ms, failed=True, fallback_used=fallback_used)
            return MCPResponse(
                operation=request.operation,
                ok=False,
                error=f"{exc}; fallback_failed={fallback_exc}",
                fallback_used=fallback_used,
                latency_ms=round(latency_ms, 2),
            )

