"""
Async task queue — priority-based in-process queue for LLM-intensive operations.

Provides:
- Configurable concurrency limit (default: 3 parallel LLM calls)
- Priority levels: CRITICAL > HIGH > NORMAL > LOW
- Queue depth exposed via Prometheus-compatible gauge
- Fire-and-forget or await-result modes
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable
from uuid import uuid4

from app.core.logging import get_domain_logger

logger = get_domain_logger(__name__, "scalability")


class TaskPriority(IntEnum):
    """Task priority levels (lower number = higher priority)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True)
class QueuedTask:
    """A task in the priority queue."""
    priority: int
    created_at: float = field(compare=True)
    task_id: str = field(default_factory=lambda: str(uuid4())[:8], compare=False)
    name: str = field(default="unnamed", compare=False)
    coro_factory: Callable[[], Awaitable[Any]] = field(default=None, compare=False)  # type: ignore
    future: asyncio.Future | None = field(default=None, compare=False)


class TaskQueue:
    """
    Priority-based async task queue with configurable concurrency.

    Usage::

        queue = TaskQueue(max_concurrent=3)
        await queue.start()

        # Fire and forget
        queue.enqueue(
            priority=TaskPriority.HIGH,
            name="generate_content",
            coro_factory=lambda: generate_content(chapter=5),
        )

        # Await result
        result = await queue.enqueue_and_wait(
            priority=TaskPriority.NORMAL,
            name="generate_test",
            coro_factory=lambda: generate_test(chapter=5),
        )
    """

    def __init__(self, max_concurrent: int = 3):
        self._max_concurrent = max_concurrent
        self._queue: asyncio.PriorityQueue[QueuedTask] = asyncio.PriorityQueue()
        self._running = False
        self._active_count = 0
        self._total_processed = 0
        self._total_failed = 0
        self._workers: list[asyncio.Task] = []

    @property
    def queue_depth(self) -> int:
        """Current number of tasks waiting in the queue."""
        return self._queue.qsize()

    @property
    def active_count(self) -> int:
        """Number of currently executing tasks."""
        return self._active_count

    @property
    def stats(self) -> dict[str, Any]:
        """Current queue statistics."""
        return {
            "queue_depth": self.queue_depth,
            "active_tasks": self._active_count,
            "max_concurrent": self._max_concurrent,
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
            "running": self._running,
        }

    async def start(self) -> None:
        """Start the worker pool."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_concurrent):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
        logger.info("event=task_queue_started workers=%d", self._max_concurrent)

    async def stop(self) -> None:
        """Stop the worker pool gracefully."""
        self._running = False
        # Signal workers to stop
        for _ in self._workers:
            sentinel = QueuedTask(
                priority=999,
                created_at=time.time(),
                name="__stop__",
            )
            await self._queue.put(sentinel)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("event=task_queue_stopped")

    def enqueue(
        self,
        priority: TaskPriority,
        name: str,
        coro_factory: Callable[[], Awaitable[Any]],
    ) -> str:
        """Enqueue a task for fire-and-forget execution. Returns task_id."""
        task = QueuedTask(
            priority=int(priority),
            created_at=time.time(),
            name=name,
            coro_factory=coro_factory,
        )
        self._queue.put_nowait(task)
        logger.debug(
            "event=task_enqueued id=%s name=%s priority=%s depth=%d",
            task.task_id, name, priority.name, self.queue_depth,
        )
        return task.task_id

    async def enqueue_and_wait(
        self,
        priority: TaskPriority,
        name: str,
        coro_factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Enqueue a task and wait for its result."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        task = QueuedTask(
            priority=int(priority),
            created_at=time.time(),
            name=name,
            coro_factory=coro_factory,
            future=future,
        )
        self._queue.put_nowait(task)
        return await future

    async def _worker(self, worker_name: str) -> None:
        """Worker loop that processes tasks from the priority queue."""
        while self._running:
            try:
                task = await self._queue.get()
                if task.name == "__stop__":
                    break

                self._active_count += 1
                start = time.monotonic()
                try:
                    result = await task.coro_factory()
                    self._total_processed += 1
                    if task.future and not task.future.done():
                        task.future.set_result(result)
                    elapsed = (time.monotonic() - start) * 1000
                    logger.debug(
                        "event=task_completed worker=%s id=%s name=%s ms=%.1f",
                        worker_name, task.task_id, task.name, elapsed,
                    )
                except Exception as exc:
                    self._total_failed += 1
                    if task.future and not task.future.done():
                        task.future.set_exception(exc)
                    logger.warning(
                        "event=task_failed worker=%s id=%s name=%s error=%s",
                        worker_name, task.task_id, task.name, exc,
                    )
                finally:
                    self._active_count -= 1
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("event=worker_error worker=%s error=%s", worker_name, exc)


# ── Global instance ──────────────────────────────────────────────────

_global_queue: TaskQueue | None = None


def get_task_queue(max_concurrent: int = 3) -> TaskQueue:
    """Get or create the global task queue instance."""
    global _global_queue
    if _global_queue is None:
        _global_queue = TaskQueue(max_concurrent=max_concurrent)
    return _global_queue
