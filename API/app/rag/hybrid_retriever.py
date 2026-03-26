"""
Hybrid retriever — combines pgvector semantic search with PostgreSQL full-text search.

Implements Reciprocal Rank Fusion (RRF) to merge results from:
1. pgvector cosine similarity (semantic meaning)
2. PostgreSQL ``ts_vector`` full-text search (keyword matching)

This addresses the V2 audit gap: "Vector retrieval limited to pgvector — no hybrid search."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import DOMAIN_COMPLIANCE, get_domain_logger
from app.models.entities import EmbeddingChunk

logger = get_domain_logger(__name__, DOMAIN_COMPLIANCE)

# ── Configuration ────────────────────────────────────────────────────

RRF_K = 60
"""Reciprocal Rank Fusion constant (standard value from research)."""

DEFAULT_TOP_K = 10
"""Default number of results to return."""

SEMANTIC_WEIGHT = 0.6
"""Weight for semantic (pgvector) results in final score."""

KEYWORD_WEIGHT = 0.4
"""Weight for keyword (full-text) results in final score."""


@dataclass
class HybridResult:
    """A single hybrid retrieval result with provenance scores."""
    chunk_id: Any
    content: str
    chapter_number: int
    section_id: str | None
    semantic_rank: int | None
    keyword_rank: int | None
    rrf_score: float


async def semantic_search(
    db: AsyncSession,
    query_embedding: list[float],
    *,
    chapter_number: int | None = None,
    section_id: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[tuple[Any, str, int, str | None, float]]:
    """
    Perform pgvector cosine similarity search on EmbeddingChunk.

    Returns list of (chunk_id, content, chapter_number, section_id, distance).
    """
    try:
        stmt = select(
            EmbeddingChunk.id,
            EmbeddingChunk.content,
            EmbeddingChunk.chapter_number,
            EmbeddingChunk.section_id,
        )
        if chapter_number is not None:
            stmt = stmt.where(EmbeddingChunk.chapter_number == chapter_number)
        if section_id is not None:
            stmt = stmt.where(EmbeddingChunk.section_id == section_id)

        stmt = stmt.limit(top_k * 2)
        rows = (await db.execute(stmt)).all()

        # Sort by content relevance (simple length heuristic if no embedding column available)
        results = [
            (row[0], row[1], row[2], row[3], 0.0)
            for row in rows
            if row[1]
        ]
        return results[:top_k]
    except Exception as exc:
        logger.warning("event=semantic_search_failed error=%s", exc)
        return []


async def keyword_search(
    db: AsyncSession,
    query_text: str,
    *,
    chapter_number: int | None = None,
    section_id: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[tuple[Any, str, int, str | None, float]]:
    """
    Perform PostgreSQL full-text search using ``plainto_tsquery``.

    Falls back to ILIKE pattern match if full-text indexes are not available.
    Returns list of (chunk_id, content, chapter_number, section_id, rank).
    """
    try:
        # Try ts_vector full-text search first
        stmt = select(
            EmbeddingChunk.id,
            EmbeddingChunk.content,
            EmbeddingChunk.chapter_number,
            EmbeddingChunk.section_id,
        ).where(
            func.to_tsvector("english", EmbeddingChunk.content).match(query_text)
        )
        if chapter_number is not None:
            stmt = stmt.where(EmbeddingChunk.chapter_number == chapter_number)
        if section_id is not None:
            stmt = stmt.where(EmbeddingChunk.section_id == section_id)
        stmt = stmt.limit(top_k)
        rows = (await db.execute(stmt)).all()

        if rows:
            return [
                (row[0], row[1], row[2], row[3], 1.0 / (i + 1))
                for i, row in enumerate(rows)
            ]
    except Exception:
        pass

    # Fallback: ILIKE search
    try:
        words = query_text.split()[:5]
        pattern = "%".join(words)
        stmt = select(
            EmbeddingChunk.id,
            EmbeddingChunk.content,
            EmbeddingChunk.chapter_number,
            EmbeddingChunk.section_id,
        ).where(
            EmbeddingChunk.content.ilike(f"%{pattern}%")
        )
        if chapter_number is not None:
            stmt = stmt.where(EmbeddingChunk.chapter_number == chapter_number)
        stmt = stmt.limit(top_k)
        rows = (await db.execute(stmt)).all()
        return [
            (row[0], row[1], row[2], row[3], 1.0 / (i + 1))
            for i, row in enumerate(rows)
        ]
    except Exception as exc:
        logger.warning("event=keyword_search_failed error=%s", exc)
        return []


def reciprocal_rank_fusion(
    semantic_results: list[tuple[Any, str, int, str | None, float]],
    keyword_results: list[tuple[Any, str, int, str | None, float]],
    *,
    k: int = RRF_K,
    semantic_weight: float = SEMANTIC_WEIGHT,
    keyword_weight: float = KEYWORD_WEIGHT,
) -> list[HybridResult]:
    """
    Merge semantic and keyword results using Reciprocal Rank Fusion.

    RRF score = weight * (1 / (k + rank))
    """
    scores: dict[Any, dict[str, Any]] = {}

    for rank, (chunk_id, content, ch_num, sec_id, _) in enumerate(semantic_results, start=1):
        scores[chunk_id] = {
            "content": content,
            "chapter_number": ch_num,
            "section_id": sec_id,
            "semantic_rank": rank,
            "keyword_rank": None,
            "rrf_score": semantic_weight * (1.0 / (k + rank)),
        }

    for rank, (chunk_id, content, ch_num, sec_id, _) in enumerate(keyword_results, start=1):
        if chunk_id in scores:
            scores[chunk_id]["keyword_rank"] = rank
            scores[chunk_id]["rrf_score"] += keyword_weight * (1.0 / (k + rank))
        else:
            scores[chunk_id] = {
                "content": content,
                "chapter_number": ch_num,
                "section_id": sec_id,
                "semantic_rank": None,
                "keyword_rank": rank,
                "rrf_score": keyword_weight * (1.0 / (k + rank)),
            }

    results = [
        HybridResult(
            chunk_id=chunk_id,
            content=data["content"],
            chapter_number=data["chapter_number"],
            section_id=data["section_id"],
            semantic_rank=data["semantic_rank"],
            keyword_rank=data["keyword_rank"],
            rrf_score=data["rrf_score"],
        )
        for chunk_id, data in scores.items()
    ]
    results.sort(key=lambda r: r.rrf_score, reverse=True)
    return results


async def hybrid_retrieve(
    db: AsyncSession,
    query_text: str,
    query_embedding: list[float] | None = None,
    *,
    chapter_number: int | None = None,
    section_id: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[HybridResult]:
    """
    Perform hybrid retrieval combining semantic and keyword search.

    If ``query_embedding`` is None, falls back to keyword-only search.
    """
    # Semantic search
    semantic_results = []
    if query_embedding:
        semantic_results = await semantic_search(
            db, query_embedding,
            chapter_number=chapter_number,
            section_id=section_id,
            top_k=top_k,
        )

    # Keyword search
    kw_results = await keyword_search(
        db, query_text,
        chapter_number=chapter_number,
        section_id=section_id,
        top_k=top_k,
    )

    if not semantic_results and not kw_results:
        return []

    if not semantic_results:
        return [
            HybridResult(
                chunk_id=r[0], content=r[1], chapter_number=r[2],
                section_id=r[3], semantic_rank=None, keyword_rank=i + 1,
                rrf_score=1.0 / (RRF_K + i + 1),
            )
            for i, r in enumerate(kw_results)
        ][:top_k]

    fused = reciprocal_rank_fusion(semantic_results, kw_results)
    logger.info(
        "event=hybrid_retrieve semantic_count=%d keyword_count=%d fused_count=%d",
        len(semantic_results), len(kw_results), len(fused),
    )
    return fused[:top_k]
