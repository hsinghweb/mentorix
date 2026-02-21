import re

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ConceptChunk
from app.rag.embeddings import embed_text


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()))


def _keyword_score(query_tokens: set[str], chunk: ConceptChunk) -> float:
    hay_tokens = _tokenize(f"{chunk.concept} {chunk.content}")
    if not query_tokens or not hay_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(hay_tokens))
    return overlap / max(1, len(query_tokens))


async def retrieve_concept_chunks(
    db: AsyncSession, concept: str, top_k: int = 5, difficulty: int | None = None
) -> list[str]:
    """
    Hybrid retrieval:
    1) Vector-semantic retrieval (primary, concept-focused).
    2) Keyword overlap re-scoring (secondary signal).
    """
    query_text = concept.replace("_", " ").strip()
    query_vec = embed_text(query_text)
    query_tokens = _tokenize(query_text)

    stmt: Select = select(ConceptChunk).where(ConceptChunk.concept == concept)
    if difficulty is not None:
        stmt = stmt.where(ConceptChunk.difficulty <= difficulty + 1)

    # Pull a broader candidate pool for reranking.
    stmt = stmt.limit(max(top_k * 6, 12))

    rows: list[ConceptChunk] = []
    try:
        # Prefer semantic ordering in DB if pgvector comparator is available.
        semantic_stmt = stmt.order_by(ConceptChunk.embedding.cosine_distance(query_vec))
        rows = (await db.execute(semantic_stmt)).scalars().all()
    except Exception:
        rows = (await db.execute(stmt)).scalars().all()

    scored: list[tuple[float, ConceptChunk]] = []
    for idx, row in enumerate(rows):
        # Rows are already semantically sorted in best case; convert rank to score.
        semantic_score = 1.0 - min(1.0, idx / max(1, len(rows)))
        keyword_score = _keyword_score(query_tokens, row)
        hybrid_score = (0.75 * semantic_score) + (0.25 * keyword_score)
        scored.append((hybrid_score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk.content for _score, chunk in scored[:top_k]]
