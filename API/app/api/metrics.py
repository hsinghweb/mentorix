from __future__ import annotations

from fastapi import APIRouter

from app.core.resilience import get_breakers_status
from app.telemetry.aggregator import fleet_telemetry_aggregator

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/fleet")
async def fleet_metrics():
    return fleet_telemetry_aggregator.aggregate()


@router.get("/resilience")
async def resilience_metrics():
    return {"breakers": get_breakers_status()}
