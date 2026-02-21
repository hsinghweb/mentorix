from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.database import get_db
from app.rag.grounding_ingest import ensure_grounding_ready, run_grounding_ingestion

router = APIRouter(prefix="/grounding", tags=["grounding"])


@router.get("/status")
async def grounding_status(db: AsyncSession = Depends(get_db)):
    ready, detail = await ensure_grounding_ready(db)
    return {"ready": ready, **detail}


@router.post("/ingest")
async def grounding_ingest(
    force_rebuild: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    summary = await run_grounding_ingestion(db, force_rebuild=force_rebuild)
    ready, detail = await ensure_grounding_ready(db)
    return {"ingestion": summary, "ready": ready, "validation": detail}
