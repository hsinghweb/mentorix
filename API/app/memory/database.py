import time
from threading import Lock

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import settings

_cursor_starts: dict[int, float] = {}
_cursor_lock = Lock()


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    with _cursor_lock:
        _cursor_starts[id(cursor)] = time.perf_counter()


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    with _cursor_lock:
        start = _cursor_starts.pop(id(cursor), None)
    if start is not None:
        try:
            from app.core.db_metrics import record_query
            record_query(time.perf_counter() - start)
        except Exception:
            pass


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
event.listen(engine.sync_engine, "before_cursor_execute", _before_cursor_execute)
event.listen(engine.sync_engine, "after_cursor_execute", _after_cursor_execute)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
