"""
Webhook alert sink — sends alerts when error rates exceed thresholds.

Supports Discord- and Slack-compatible webhook payloads. Integrates with
the existing ``ErrorRateTracker`` in telemetry to fire alerts for sustained
high error rates.

This addresses the V2 audit gap: "Error rate tracker exists but no alerting integration."
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger
from app.core.settings import settings

logger = get_domain_logger(__name__, DOMAIN_COMPLIANCE)


# ── Configuration ────────────────────────────────────────────────────

@dataclass
class AlertConfig:
    """Configuration for the alerting system."""
    webhook_url: str = ""
    error_rate_threshold: float = 0.2
    cooldown_seconds: float = 300.0
    include_details: bool = True
    webhook_format: str = "slack"  # "slack" or "discord"


def _get_alert_config() -> AlertConfig:
    """Build AlertConfig from application settings."""
    return AlertConfig(
        webhook_url=getattr(settings, "alert_webhook_url", "") or "",
        error_rate_threshold=float(getattr(settings, "alert_error_rate_threshold", 0.2) or 0.2),
        cooldown_seconds=float(getattr(settings, "alert_cooldown_seconds", 300) or 300),
        include_details=bool(getattr(settings, "alert_include_details", True)),
        webhook_format=str(getattr(settings, "alert_webhook_format", "slack") or "slack"),
    )


# ── Alert state ──────────────────────────────────────────────────────

_last_alert_time: float = 0.0
_alert_count: int = 0


# ── Payload builders ─────────────────────────────────────────────────

def _build_slack_payload(
    alert_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict:
    """Build a Slack-compatible webhook payload."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🚨 Mentorix Alert: {alert_type}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": message},
        },
    ]
    if details:
        detail_lines = "\n".join(f"• *{k}*: {v}" for k, v in details.items())
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": detail_lines},
        })
    return {"blocks": blocks, "text": f"Mentorix Alert: {alert_type} — {message}"}


def _build_discord_payload(
    alert_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict:
    """Build a Discord-compatible webhook payload."""
    embed: dict[str, Any] = {
        "title": f"🚨 Mentorix Alert: {alert_type}",
        "description": message,
        "color": 15158332,  # Red
    }
    if details:
        embed["fields"] = [
            {"name": k, "value": str(v), "inline": True}
            for k, v in details.items()
        ]
    return {"embeds": [embed]}


# ── Public API ───────────────────────────────────────────────────────

async def send_alert(
    alert_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> bool:
    """
    Send an alert via webhook if configured and not in cooldown.

    Returns True if alert was sent, False if skipped or failed.
    """
    global _last_alert_time, _alert_count

    config = _get_alert_config()
    if not config.webhook_url:
        logger.debug("event=alert_skipped reason=no_webhook_url")
        return False

    # Cooldown check
    now = time.time()
    if now - _last_alert_time < config.cooldown_seconds:
        remaining = config.cooldown_seconds - (now - _last_alert_time)
        logger.debug(
            "event=alert_cooldown remaining_s=%.0f type=%s",
            remaining, alert_type,
        )
        return False

    # Build payload
    if config.webhook_format == "discord":
        payload = _build_discord_payload(alert_type, message, details if config.include_details else None)
    else:
        payload = _build_slack_payload(alert_type, message, details if config.include_details else None)

    # Send webhook
    try:
        import urllib.request

        req = urllib.request.Request(
            config.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=10),
        )

        _last_alert_time = now
        _alert_count += 1
        logger.info(
            "event=alert_sent type=%s count=%d webhook_format=%s",
            alert_type, _alert_count, config.webhook_format,
        )
        return True
    except Exception as exc:
        logger.warning(
            "event=alert_send_failed type=%s error=%s",
            alert_type, exc,
        )
        return False


async def check_and_alert_error_rate(
    error_rate: float,
    window_seconds: int = 300,
    total_requests: int = 0,
    failed_requests: int = 0,
) -> bool:
    """
    Check if error rate exceeds threshold and send alert if needed.

    Designed to be called by the ErrorRateTracker periodically.
    """
    config = _get_alert_config()
    if error_rate < config.error_rate_threshold:
        return False

    return await send_alert(
        alert_type="High Error Rate",
        message=(
            f"Error rate has reached *{error_rate:.1%}* "
            f"(threshold: {config.error_rate_threshold:.1%}) "
            f"over the last {window_seconds}s window."
        ),
        details={
            "error_rate": f"{error_rate:.2%}",
            "threshold": f"{config.error_rate_threshold:.2%}",
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "window": f"{window_seconds}s",
        },
    )


async def alert_agent_circuit_open(
    agent_name: str,
    failure_count: int,
    cooldown_seconds: float,
) -> bool:
    """Send alert when an agent circuit breaker opens."""
    return await send_alert(
        alert_type="Agent Circuit Breaker Open",
        message=(
            f"Agent *{agent_name}* circuit breaker opened after "
            f"{failure_count} consecutive failures. "
            f"Cooldown: {cooldown_seconds}s."
        ),
        details={
            "agent": agent_name,
            "failures": failure_count,
            "cooldown_s": cooldown_seconds,
        },
    )


def get_alert_stats() -> dict[str, Any]:
    """Return current alerting statistics for the admin dashboard."""
    config = _get_alert_config()
    return {
        "configured": bool(config.webhook_url),
        "webhook_format": config.webhook_format,
        "error_rate_threshold": config.error_rate_threshold,
        "cooldown_seconds": config.cooldown_seconds,
        "total_alerts_sent": _alert_count,
        "last_alert_time": _last_alert_time if _last_alert_time > 0 else None,
    }
