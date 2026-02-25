import re

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.models.entities import ConceptChunk, GeneratedArtifact
from app.rag.embeddings import embed_text
from app.rag.vector_backends import get_vector_backend


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", (text or "").lower()))


def _keyword_score(query_tokens: set[str], chunk: ConceptChunk) -> float:
    hay_tokens = _tokenize(f"{chunk.concept} {chunk.content}")
    if not query_tokens or not hay_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(hay_tokens))
    return overlap / max(1, len(query_tokens))


def _keyword_score_text(query_tokens: set[str], text: str) -> float:
    hay_tokens = _tokenize(text)
    if not query_tokens or not hay_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(hay_tokens))
    return overlap / max(1, len(query_tokens))


async def retrieve_concept_chunks(
    db: AsyncSession, concept: str, top_k: int = 5, difficulty: int | None = None
) -> list[str]:
    result = await retrieve_concept_chunks_with_meta(db=db, concept=concept, top_k=top_k, difficulty=difficulty)
    return result["chunks"]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _retrieval_confidence(scored: list[tuple[float, object]], top_k: int) -> float:
    if not scored:
        return 0.0
    top_scores = [_clamp01(score) for score, _ in scored[: max(1, top_k)]]
    avg_top = sum(top_scores) / len(top_scores)
    if len(scored) < 2:
        margin = top_scores[0]
    else:
        margin = _clamp01(float(scored[0][0]) - float(scored[1][0]))
    return round(_clamp01((0.65 * avg_top) + (0.35 * margin)), 3)


async def retrieve_concept_chunks_with_meta(
    db: AsyncSession, concept: str, top_k: int = 5, difficulty: int | None = None
) -> dict:
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
    semantic_fallback_used = False
    backend = get_vector_backend()
    try:
        semantic_stmt = backend.order_concept_chunks(stmt, query_vec)
        rows = (await db.execute(semantic_stmt)).scalars().all()
    except Exception:
        semantic_fallback_used = True
        rows = (await db.execute(stmt)).scalars().all()

    scored: list[tuple[float, ConceptChunk]] = []
    for idx, row in enumerate(rows):
        # Rows are already semantically sorted in best case; convert rank to score.
        semantic_score = 1.0 - min(1.0, idx / max(1, len(rows)))
        keyword_score = _keyword_score(query_tokens, row)
        hybrid_score = (0.75 * semantic_score) + (0.25 * keyword_score)
        scored.append((hybrid_score, row))

    if settings.include_generated_artifacts_in_retrieval:
        artifact_stmt: Select = (
            select(GeneratedArtifact)
            .where(GeneratedArtifact.concept == concept)
            .order_by(GeneratedArtifact.created_at.desc())
            .limit(max(1, settings.generated_artifacts_top_k))
        )
        artifact_rows = (await db.execute(artifact_stmt)).scalars().all()
        for a in artifact_rows:
            keyword_score = _keyword_score_text(query_tokens, f"{a.concept} {a.content}")
            scored.append((0.45 + (0.25 * keyword_score), a))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_items = scored[:top_k]
    chunks = [item.content for _score, item in top_items]
    confidence = _retrieval_confidence(scored, top_k=top_k)

    try:
        from app.core.retrieval_metrics import record_retrieval
        record_retrieval(confidence)
    except Exception:
        pass

    if not chunks:
        message = "No grounded chunks found for requested concept."
    elif confidence < 0.35:
        message = "Low retrieval confidence. Showing best grounded matches; consider narrowing concept."
    else:
        message = "Grounded retrieval confidence is acceptable."

    return {
        "chunks": chunks,
        "retrieval_confidence": confidence,
        "semantic_fallback_used": semantic_fallback_used,
        "message": message,
        "candidate_count": len(scored),
    }
