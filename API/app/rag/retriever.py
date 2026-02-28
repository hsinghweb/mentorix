import hashlib
import json
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


_RAG_CACHE_TTL = 300  # seconds


def _rag_cache_key(concept: str, difficulty: int | None, top_k: int) -> str:
    raw = f"{concept}|{difficulty}|{top_k}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"rag:{h}"


async def retrieve_concept_chunks_with_meta(
    db: AsyncSession, concept: str, top_k: int = 5, difficulty: int | None = None,
    chapter_number: int | None = None, section_id: str | None = None,
) -> dict:
    """
    Hybrid retrieval:
    1) Redis cache for repeated concept queries (TTL 300s).
    2) If chapter_number/section_id given, use EmbeddingChunk table (section-aware).
    3) Otherwise fall back to ConceptChunk (legacy).
    4) Keyword overlap re-scoring (secondary signal).
    """
    cache_key = _rag_cache_key(f"{concept}:{chapter_number}:{section_id}", difficulty, top_k)
    try:
        from app.memory.cache import redis_client
        raw = await redis_client.get(cache_key)
        if raw:
            data = json.loads(raw)
            try:
                from app.core.retrieval_metrics import record_retrieval
                record_retrieval(float(data.get("retrieval_confidence", 0)))
            except Exception:
                pass
            return data
    except Exception:
        pass

    query_text = concept.replace("_", " ").strip()
    query_vec = embed_text(query_text)
    query_tokens = _tokenize(query_text)

    # ── Section-aware retrieval via EmbeddingChunk ──
    if chapter_number is not None:
        from app.models.entities import EmbeddingChunk
        ec_stmt: Select = select(EmbeddingChunk).where(EmbeddingChunk.chapter_number == chapter_number)
        if section_id is not None:
            ec_stmt = ec_stmt.where(EmbeddingChunk.section_id == section_id)
        ec_stmt = ec_stmt.limit(max(top_k * 4, 12))

        ec_rows = (await db.execute(ec_stmt)).scalars().all()

        scored: list[tuple[float, object]] = []
        for idx, row in enumerate(ec_rows):
            semantic_score = 1.0 - min(1.0, idx / max(1, len(ec_rows)))
            kw_tokens = _tokenize(row.content)
            kw_overlap = len(query_tokens.intersection(kw_tokens)) / max(1, len(query_tokens))
            hybrid_score = (0.7 * semantic_score) + (0.3 * kw_overlap)
            scored.append((hybrid_score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_items = scored[:top_k]
        chunks = [item.content for _score, item in top_items]
        confidence = _retrieval_confidence(scored, top_k=top_k)

        if not chunks:
            message = f"No grounded chunks found for chapter {chapter_number}" + (f" section {section_id}" if section_id else "") + "."
        elif confidence < 0.35:
            message = "Low retrieval confidence. Showing best grounded matches."
        else:
            message = "Grounded retrieval confidence is acceptable."

        result = {
            "chunks": chunks,
            "retrieval_confidence": confidence,
            "semantic_fallback_used": False,
            "message": message,
            "candidate_count": len(scored),
            "retrieval_mode": "section_aware",
        }
        try:
            from app.memory.cache import redis_client
            await redis_client.set(cache_key, json.dumps(result), ex=_RAG_CACHE_TTL)
        except Exception:
            pass
        return result

    # ── Legacy ConceptChunk retrieval ──
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

    result = {
        "chunks": chunks,
        "retrieval_confidence": confidence,
        "semantic_fallback_used": semantic_fallback_used,
        "message": message,
        "candidate_count": len(scored),
    }
    try:
        from app.memory.cache import redis_client
        await redis_client.set(cache_key, json.dumps(result), ex=_RAG_CACHE_TTL)
    except Exception:
        pass
    return result
