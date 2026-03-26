"""
OpenTelemetry instrumentation — distributed tracing for FastAPI, LLM calls, and agents.

Provides a lightweight OTEL setup that can be enabled via configuration.
Exports spans to an OTLP endpoint when configured, otherwise functions
as a no-op tracer for zero overhead.

This addresses the V2 audit gap: "No OpenTelemetry tracing."
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from app.core.logging import get_domain_logger

logger = get_domain_logger(__name__, "telemetry")

# ── State ────────────────────────────────────────────────────────────

_tracer: Any = None
_initialized: bool = False


class _NoOpSpan:
    """Minimal no-op span for when OTEL is not available or disabled."""

    def __init__(self, name: str = ""):
        self._name = name
        self._attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self._attributes[key] = value

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        self.end()


class _NoOpTracer:
    """Minimal no-op tracer for when OTEL is not installed."""

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan(name)

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any) -> Generator[_NoOpSpan, None, None]:
        span = _NoOpSpan(name)
        try:
            yield span
        finally:
            span.end()


def init_tracing(
    service_name: str = "mentorix-api",
    otlp_endpoint: str | None = None,
) -> None:
    """
    Initialize OpenTelemetry tracing if the SDK is available.

    Falls back to no-op tracer if ``opentelemetry`` packages are not installed
    or if no OTLP endpoint is configured.
    """
    global _tracer, _initialized

    if _initialized:
        return

    if not otlp_endpoint:
        logger.info("event=otel_init status=disabled reason=no_endpoint")
        _tracer = _NoOpTracer()
        _initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        _initialized = True
        logger.info("event=otel_init status=enabled endpoint=%s", otlp_endpoint)
    except ImportError:
        logger.info("event=otel_init status=disabled reason=sdk_not_installed")
        _tracer = _NoOpTracer()
        _initialized = True
    except Exception as exc:
        logger.warning("event=otel_init status=failed error=%s", exc)
        _tracer = _NoOpTracer()
        _initialized = True


def get_tracer() -> Any:
    """Return the current tracer (real or no-op)."""
    global _tracer
    if _tracer is None:
        _tracer = _NoOpTracer()
    return _tracer


# ── Convenience decorators ───────────────────────────────────────────

@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """
    Context manager to create a traced span.

    Usage::

        with trace_span("llm_generate", {"model": "gemini-pro"}) as span:
            result = await provider.generate(prompt)
            span.set_attribute("response_length", len(result))
    """
    tracer = get_tracer()
    if hasattr(tracer, "start_as_current_span"):
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            yield span
    else:
        span = _NoOpSpan(name)
        yield span


def trace_llm_call(
    model: str,
    role: str,
    prompt_length: int,
    response_length: int = 0,
    duration_ms: float = 0.0,
    success: bool = True,
) -> None:
    """Record an LLM call as a span event (post-hoc, after the call completes)."""
    tracer = get_tracer()
    with tracer.start_as_current_span("llm_call") if hasattr(tracer, "start_as_current_span") else _NoOpSpan() as span:
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.role", role)
        span.set_attribute("llm.prompt_length", prompt_length)
        span.set_attribute("llm.response_length", response_length)
        span.set_attribute("llm.duration_ms", duration_ms)
        span.set_attribute("llm.success", success)


def trace_agent_execution(
    agent_name: str,
    decision: str,
    duration_ms: float,
    success: bool,
) -> None:
    """Record an agent execution as a span event."""
    tracer = get_tracer()
    with tracer.start_as_current_span("agent_execute") if hasattr(tracer, "start_as_current_span") else _NoOpSpan() as span:
        span.set_attribute("agent.name", agent_name)
        span.set_attribute("agent.decision", decision)
        span.set_attribute("agent.duration_ms", duration_ms)
        span.set_attribute("agent.success", success)


def trace_db_query(
    operation: str,
    table: str,
    duration_ms: float,
) -> None:
    """Record a database query as a span event."""
    tracer = get_tracer()
    with tracer.start_as_current_span("db_query") if hasattr(tracer, "start_as_current_span") else _NoOpSpan() as span:
        span.set_attribute("db.operation", operation)
        span.set_attribute("db.table", table)
        span.set_attribute("db.duration_ms", duration_ms)
