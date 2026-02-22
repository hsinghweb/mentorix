from __future__ import annotations

from fastapi import APIRouter

from app.memory.hubs import structured_hubs
from app.memory.ingest import get_memory_context
from app.memory.store import get_memory_runtime_status

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/hubs")
async def memory_hubs():
    return structured_hubs.get_all()


@router.get("/context/{learner_id}")
async def memory_context(learner_id: str):
    return {"learner_id": learner_id, "context": get_memory_context(learner_id)}


@router.get("/status")
async def memory_status():
    return get_memory_runtime_status()
