import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


async def retry_with_backoff(
    async_func,
    *,
    max_retries: int = 3,
    base_delay_seconds: float = 0.5,
    retryable_errors: tuple[type[Exception], ...] = (TimeoutError, ConnectionError, asyncio.TimeoutError),
):
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await async_func()
        except retryable_errors as exc:  # type: ignore[misc]
            last_exception = exc
            if attempt == max_retries - 1:
                break
            await asyncio.sleep(base_delay_seconds * (2**attempt))
    if last_exception:
        raise last_exception


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 4
    recovery_timeout_seconds: float = 30.0
    half_open_max_calls: int = 1
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    last_failure_time: float = field(default=0.0)
    half_open_calls: int = field(default=0)
    _lock: Lock = field(default_factory=Lock)

    def can_execute(self) -> bool:
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout_seconds:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
                return False
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls < self.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False
            return False

    def record_success(self) -> None:
        with self._lock:
            if self.state in {CircuitState.HALF_OPEN, CircuitState.OPEN}:
                self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.half_open_calls = 0

    def record_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.half_open_calls = 0

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
        }


_registry: dict[str, CircuitBreaker] = {}
_registry_lock = Lock()


def get_breaker(name: str) -> CircuitBreaker:
    with _registry_lock:
        if name not in _registry:
            _registry[name] = CircuitBreaker(name=name)
        return _registry[name]


def get_breakers_status() -> dict[str, dict]:
    return {name: breaker.status() for name, breaker in _registry.items()}
