import logging
import uuid

from sqlalchemy.exc import StatementError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.models.base import Base
from app.models.entities import ConceptChunk
from app.rag.embeddings import embed_text

logger = logging.getLogger(__name__)


SAMPLE_CHUNKS = [
    (
        "fractions",
        "NCERT_Class10_Ch1",
        1,
        "A fraction represents a part of a whole. Equivalent fractions have the same value.",
    ),
    (
        "linear_equations",
        "NCERT_Class10_Ch2",
        1,
        "A linear equation in one variable can be solved by isolating the variable on one side.",
    ),
    (
        "quadratic_equations",
        "NCERT_Class10_Ch4",
        2,
        "Quadratic equations can be solved by factorization, completing square, or quadratic formula.",
    ),
]


async def initialize_database(session: AsyncSession, engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    async def seed_chunks():
        existing = await session.execute(text("SELECT COUNT(*) FROM concept_chunks"))
        count = int(existing.scalar_one())
        if count > 0:
            return

        for concept, source, difficulty, content in SAMPLE_CHUNKS:
            session.add(
                ConceptChunk(
                    id=uuid.uuid4(),
                    concept=concept,
                    source=source,
                    difficulty=difficulty,
                    content=content,
                    embedding=embed_text(f"{concept}. {content}"),
                )
            )
        await session.commit()
        logger.info("Seeded initial concept chunks")

    try:
        await seed_chunks()
    except StatementError as exc:
        await session.rollback()
        if "expected" in str(exc) and "dimensions" in str(exc):
            logger.warning(
                "Vector dimension mismatch detected. Recreating concept_chunks with dim=%s.",
                settings.embedding_dimensions,
            )
            async with engine.begin() as conn:
                await conn.execute(text("DROP TABLE IF EXISTS concept_chunks"))
                await conn.run_sync(Base.metadata.create_all)
            await seed_chunks()
        else:
            raise
