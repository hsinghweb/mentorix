"""
Unit tests for Iteration 13 core modules.

Covers: config_governance, progress_stream, error_rate_tracker,
        metrics_base, agent_interface, csrf, shared_helpers.
"""
from __future__ import annotations

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# ── config_governance ────────────────────────────────────────────────

class TestConfigGovernance:
    """Tests for app.core.config_governance module."""

    def test_validate_all_returns_report(self):
        from app.core.config_governance import validate_all
        report = validate_all()
        assert isinstance(report, list)
        assert all(isinstance(e, str) for e in report)

    def test_validate_all_does_not_raise(self):
        from app.core.config_governance import validate_all
        # Should not raise even if some validations warn
        validate_all()


# ── progress_stream ──────────────────────────────────────────────────

class TestProgressStream:
    """Tests for app.core.progress_stream module."""

    def test_emit_creates_event(self):
        from app.core.progress_stream import emit, _queues
        op_id = f"test_{uuid4().hex[:8]}"
        emit(op_id, "generating", "test detail", progress=0.5)
        assert op_id in _queues
        event = _queues[op_id].get_nowait()
        assert event["stage"] == "generating"
        assert event["detail"] == "test detail"
        assert event["progress"] == 0.5

    def test_emit_complete_marks_completed(self):
        from app.core.progress_stream import emit, _completed
        op_id = f"test_{uuid4().hex[:8]}"
        emit(op_id, "complete", "done")
        assert op_id in _completed
        # Cleanup
        _completed.discard(op_id)

    def test_cleanup_stale(self):
        from app.core.progress_stream import emit, cleanup_stale, _completed
        op_id = f"test_{uuid4().hex[:8]}"
        emit(op_id, "complete")
        removed = cleanup_stale()
        assert removed >= 1
        assert op_id not in _completed


# ── error_rate_tracker ───────────────────────────────────────────────

class TestErrorRateTracker:
    """Tests for app.core.error_rate_tracker module."""

    def test_record_and_rate(self):
        from app.telemetry.error_rate_tracker import record, get_error_rate
        domain = f"test_{uuid4().hex[:8]}"
        record(domain, success=True)
        record(domain, success=False)
        record(domain, success=True)
        rate = get_error_rate(domain)
        assert 0.0 <= rate <= 1.0


# ── metrics_base ─────────────────────────────────────────────────────

class TestMetricsBase:
    """Tests for app.core.metrics_base module."""

    def test_counter_increment(self):
        from app.core.metrics_base import MetricsCollector
        m = MetricsCollector("test")
        m.inc("requests")
        m.inc("requests", 5)
        assert m.counter("requests") == 6

    def test_gauge_set(self):
        from app.core.metrics_base import MetricsCollector
        m = MetricsCollector("test")
        m.set_gauge("cpu", 0.75)
        assert m.gauge("cpu") == 0.75

    def test_histogram_stats(self):
        from app.core.metrics_base import MetricsCollector
        m = MetricsCollector("test")
        for v in [1.0, 2.0, 3.0]:
            m.observe("latency", v)
        stats = m.histogram_stats("latency")
        assert stats["count"] == 3
        assert stats["avg"] == 2.0

    def test_snapshot_format(self):
        from app.core.metrics_base import MetricsCollector
        m = MetricsCollector("test_domain")
        m.inc("hits")
        snap = m.snapshot()
        assert snap["domain"] == "test_domain"
        assert "counters" in snap
        assert "gauges" in snap

    def test_registry(self):
        from app.core.metrics_base import get_collector, all_snapshots
        c = get_collector("test_registry")
        c.inc("x")
        snaps = all_snapshots()
        assert "test_registry" in snaps

    def test_reset(self):
        from app.core.metrics_base import MetricsCollector
        m = MetricsCollector("test")
        m.inc("a", 10)
        m.reset()
        assert m.counter("a") == 0


# ── agent_interface ──────────────────────────────────────────────────

class TestAgentInterface:
    """Tests for app.agents.agent_interface module."""

    def test_agent_result_to_dict(self):
        from app.agents.agent_interface import AgentResult
        r = AgentResult(
            success=True,
            agent_name="test_agent",
            decision="proceed",
            reasoning="looks good",
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["agent_name"] == "test_agent"

    def test_agent_event_log(self):
        from app.agents.agent_interface import (
            _log_agent_event, get_agent_event_log,
            AgentContext, AgentResult,
        )
        ctx = AgentContext(learner_id=uuid4(), chapter="Chapter 1")
        res = AgentResult(success=True, agent_name="test", decision="ok", duration_ms=42.0)
        _log_agent_event("test", ctx, res)
        log = get_agent_event_log(limit=5)
        assert len(log) >= 1
        assert log[0]["agent"] == "test"

    def test_agent_context_defaults(self):
        from app.agents.agent_interface import AgentContext
        ctx = AgentContext(learner_id=uuid4())
        assert ctx.chapter is None
        assert ctx.extra == {}


# ── csrf ─────────────────────────────────────────────────────────────

class TestCSRF:
    """Tests for app.core.csrf module."""

    def test_safe_methods_bypass(self):
        from app.core.csrf import SAFE_METHODS
        assert "GET" in SAFE_METHODS
        assert "POST" not in SAFE_METHODS

    def test_exempt_paths(self):
        from app.core.csrf import EXEMPT_PATHS
        assert "/health" in EXEMPT_PATHS
        assert "/docs" in EXEMPT_PATHS


# ── Integration: /health/status ──────────────────────────────────────

class TestHealthEndpoint:
    """Integration test for the /health/status endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ── Contract: MCP schemas ────────────────────────────────────────────

class TestMCPContracts:
    """Contract tests for MCP request/response schemas."""

    def test_mcp_request_schema(self):
        from app.mcp.contracts import MCPRequest
        req = MCPRequest(operation="llm.generate_text", payload={"prompt": "hello"})
        assert req.operation == "llm.generate_text"
        assert req.payload["prompt"] == "hello"

    def test_mcp_response_schema(self):
        from app.mcp.contracts import MCPResponse
        resp = MCPResponse(operation="test", ok=True, result={"text": "world"})
        assert resp.ok is True
        assert resp.result["text"] == "world"

    def test_mcp_response_error(self):
        from app.mcp.contracts import MCPResponse
        resp = MCPResponse(operation="test", ok=False, error="timeout")
        assert resp.ok is False
        assert resp.error == "timeout"
