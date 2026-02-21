from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.event_bus import event_bus
from app.runtime.graph_adapter import to_react_flow
from app.runtime.run_manager import run_manager

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/start")
async def start_run(payload: dict):
    query = (payload or {}).get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    run_id = await run_manager.start_run(query)
    return {"run_id": run_id, "status": "started"}


@router.post("/{run_id}/stop")
async def stop_run(run_id: str):
    stopped = await run_manager.stop_run(run_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "status": "stopped"}


@router.get("")
async def list_runs():
    return {"runs": run_manager.list_runs()}


@router.get("/{run_id}")
async def get_run(run_id: str):
    context = run_manager.get_context(run_id)
    if not context:
        raise HTTPException(status_code=404, detail="run not found")
    return context.to_dict()


@router.get("/{run_id}/graph")
async def get_run_graph(run_id: str):
    context = run_manager.get_context(run_id)
    if not context:
        raise HTTPException(status_code=404, detail="run not found")
    return to_react_flow(context)


@router.get("/events/history")
async def run_events_history():
    return {"events": event_bus.history()}
