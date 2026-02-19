from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ConceptChunk
from app.rag.embeddings import embed_text


async def retrieve_concept_chunks(
    db: AsyncSession, concept: str, top_k: int = 5, difficulty: int | None = None
) -> list[str]:
    _query_vec = embed_text(concept)  # Kept for future vector similarity ordering.
    stmt: Select = select(ConceptChunk).where(ConceptChunk.concept == concept)
    if difficulty is not None:
        stmt = stmt.where(ConceptChunk.difficulty <= difficulty + 1)
    stmt = stmt.limit(top_k)
    rows = (await db.execute(stmt)).scalars().all()
    return [r.content for r in rows]
