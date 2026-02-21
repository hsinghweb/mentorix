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
        # Ensure indexes also exist for DBs created before index metadata changes.
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_session_logs_learner_id ON session_logs (learner_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_session_logs_concept ON session_logs (concept)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_session_logs_timestamp ON session_logs (timestamp)"))
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_session_logs_learner_timestamp "
                "ON session_logs (learner_id, timestamp)"
            )
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_assessment_results_learner_id ON assessment_results (learner_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_assessment_results_concept ON assessment_results (concept)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_assessment_results_timestamp ON assessment_results (timestamp)")
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_assessment_results_learner_timestamp "
                "ON assessment_results (learner_id, timestamp)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_concept_chunks_concept_difficulty "
                "ON concept_chunks (concept, difficulty)"
            )
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_generated_artifacts_concept ON generated_artifacts (concept)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_generated_artifacts_type ON generated_artifacts (artifact_type)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_generated_artifacts_created_at ON generated_artifacts (created_at)")
        )

        if settings.retention_cleanup_enabled and settings.session_retention_days > 0:
            params = {"days": settings.session_retention_days}
            session_cleanup = await conn.execute(
                text(
                    "DELETE FROM session_logs "
                    "WHERE timestamp IS NOT NULL "
                    "AND timestamp < (NOW() - make_interval(days => :days))"
                ),
                params,
            )
            assessment_cleanup = await conn.execute(
                text(
                    "DELETE FROM assessment_results "
                    "WHERE timestamp IS NOT NULL "
                    "AND timestamp < (NOW() - make_interval(days => :days))"
                ),
                params,
            )
            logger.info(
                "Retention cleanup completed: session_logs=%s, assessment_results=%s, retention_days=%s",
                max(0, session_cleanup.rowcount or 0),
                max(0, assessment_cleanup.rowcount or 0),
                settings.session_retention_days,
            )

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
