from __future__ import annotations

from fastapi import APIRouter

from app.core.app_metrics import get_metrics
from app.core.cache_metrics import get_cache_metrics
from app.core.db_metrics import get_db_metrics
from app.core.engagement_metrics import get_engagement_metrics
from app.core.mcp_metrics import get_mcp_metrics
from app.core.metrics_base import all_snapshots
from app.core.retrieval_metrics import get_retrieval_metrics
from app.core.resilience import get_breakers_status
from app.telemetry.aggregator import fleet_telemetry_aggregator

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/app")
async def app_metrics():
    """Request latency (p50/p95), error rate, agent/fleet metrics, and anomaly alerts."""
    out = get_metrics()
    try:
        fleet = fleet_telemetry_aggregator.aggregate()
        out["agents"] = {
            "total_runs": fleet.get("total_runs", 0),
            "total_steps": fleet.get("total_steps", 0),
            "failed_steps": fleet.get("failed_steps", 0),
            "step_success_rate": fleet.get("step_success_rate", 100.0),
            "total_retries": fleet.get("total_retries", 0),
            "top_agents": fleet.get("top_agents", []),
            "max_run_duration_sec": fleet.get("max_run_duration_sec"),
            "p95_run_duration_sec": fleet.get("p95_run_duration_sec"),
        }
        if fleet.get("total_steps", 0) > 0 and fleet.get("step_success_rate", 100.0) < 90.0:
            out["alerts"] = list(out.get("alerts", [])) + ["high_agent_failure_rate"]
        # Scheduler drift: runs taking very long or high retry rate
        steps = fleet.get("total_steps", 0)
        retries = fleet.get("total_retries", 0)
        max_dur = fleet.get("max_run_duration_sec")
        if (max_dur is not None and max_dur > 600) or (steps >= 20 and retries / max(1, steps) > 0.2):
            out["alerts"] = list(out.get("alerts", [])) + ["scheduler_drift"]
    except Exception:
        out["agents"] = None
    out["cache"] = get_cache_metrics()
    # Optional: alert on low cache hit ratio when we have enough reads
    cache = out["cache"]
    if cache.get("cache_get_total", 0) >= 10 and (cache.get("cache_hit_ratio") or 1.0) < 0.5:
        out["alerts"] = list(out.get("alerts", [])) + ["low_cache_hit_ratio"]
    out["retrieval"] = get_retrieval_metrics()
    # Optional: alert on low RAG retrieval quality (relevance proxy)
    retrieval = out["retrieval"]
    if retrieval.get("retrieval_count", 0) >= 5 and (retrieval.get("retrieval_avg_confidence") or 1.0) < 0.4:
        out["alerts"] = list(out.get("alerts", [])) + ["low_retrieval_quality"]
    out["engagement"] = get_engagement_metrics()
    eng = out["engagement"]
    if eng.get("disengagement_recent_count", 0) >= 3:
        out["alerts"] = list(out.get("alerts", [])) + ["disengagement_risk"]
    out["db"] = get_db_metrics()
    out["mcp"] = get_mcp_metrics()
    db = out["db"]
    if db.get("db_query_count", 0) >= 10 and (db.get("db_p95_ms") or 0) > 1000:
        out["alerts"] = list(out.get("alerts", [])) + ["high_db_latency"]
    return out


@router.get("/fleet")
async def fleet_metrics():
    return fleet_telemetry_aggregator.aggregate()


@router.get("/resilience")
async def resilience_metrics():
    return {"breakers": get_breakers_status()}


@router.get("/prometheus")
async def prometheus_metrics():
    """
    Prometheus-compatible text exposition format endpoint.

    Renders all MetricsCollector counters, gauges, and histogram stats
    in the standard Prometheus text format for scraping.
    """
    from fastapi.responses import PlainTextResponse

    snapshots = all_snapshots()
    lines: list[str] = []
    for domain, snap in snapshots.items():
        prefix = f"mentorix_{domain}"
        # Counters
        for name, value in snap.get("counters", {}).items():
            metric_name = f"{prefix}_{name}_total"
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value}")
        # Gauges
        for name, value in snap.get("gauges", {}).items():
            metric_name = f"{prefix}_{name}"
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {value}")
        # Histogram summaries (exported as gauges with suffixes)
        for name, stats in snap.get("histograms", {}).items():
            for stat_key, stat_val in stats.items():
                metric_name = f"{prefix}_{name}_{stat_key}"
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name} {stat_val}")
        # Uptime
        uptime = snap.get("uptime_seconds", 0)
        lines.append(f"# TYPE {prefix}_uptime_seconds gauge")
        lines.append(f"{prefix}_uptime_seconds {uptime}")

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@router.get("/interventions/{learner_id}")
async def learner_interventions(learner_id: str):
    """
    Derive adaptive interventions for a learner using their state profile
    and memory summary. Wires the intervention_engine into the active flow.
    """
    from app.memory.database import get_session
    from app.services.learner_state_profile import compute_learner_state_profile
    from app.services.intervention_engine import derive_interventions

    async with get_session() as session:
        profile = await compute_learner_state_profile(session, learner_id)

    # Build a lightweight memory summary from profile signals
    memory_summary = {
        "weak_concepts": [],
        "mistakes": profile.get("admin_metrics", {}).get("total_assessments", 0)
                    - int(
                        profile.get("admin_metrics", {}).get("total_assessments", 0)
                        * (1 - profile.get("admin_metrics", {}).get("error_rate", 0.0))
                    ),
    }

    interventions = derive_interventions(profile, memory_summary)
    return {
        "learner_id": learner_id,
        "interventions": interventions,
        "profile_summary": {
            "motivation": profile.get("motivation"),
            "confusion_risk": profile.get("confusion_risk"),
            "pace": profile.get("pace"),
            "confidence": profile.get("confidence"),
        },
    }

