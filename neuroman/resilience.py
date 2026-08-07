# neuroman/resilience.py
"""Fault tolerance: retries, circuit breaker, structured errors, degraded mode."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TypeVar

log = logging.getLogger("neuroman.resilience")

T = TypeVar("T")


class ErrorKind(str, Enum):
    NETWORK = "network"
    TIMEOUT = "timeout"
    AUTH = "auth"
    MALFORMED = "malformed"
    DEPENDENCY_DOWN = "dependency_down"
    RATE_LIMIT = "rate_limit"
    INTERNAL = "internal"
    USER = "user"


@dataclass
class NeuroError(Exception):
    """User-facing failure with diagnostics for logs."""

    message: str
    kind: ErrorKind = ErrorKind.INTERNAL
    detail: str = ""
    recoverable: bool = True
    source: str = ""

    def __str__(self) -> str:
        base = self.message
        if self.source:
            base = f"[{self.source}] {base}"
        return base

    def user_line(self) -> str:
        """Short, non-technical line for the rich CLI."""
        hints = {
            ErrorKind.NETWORK: "Zkontroluj sit / lokalni sluzbu.",
            ErrorKind.TIMEOUT: "Sluzba neodpovedela v casovem limitu.",
            ErrorKind.AUTH: "Chybi prihlaseni nebo API klic.",
            ErrorKind.MALFORMED: "Odpoved ma neplatny format (JSON).",
            ErrorKind.DEPENDENCY_DOWN: "Zavislost je nedostupna — pokracuji v degradovanem rezimu.",
            ErrorKind.RATE_LIMIT: "Rate limit — zkusim znovu pozdeji.",
            ErrorKind.INTERNAL: "Interni chyba orchestratoru.",
            ErrorKind.USER: "Neplatny vstup.",
        }
        hint = hints.get(self.kind, "")
        return f"{self.message}" + (f" ({hint})" if hint else "")


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0
    half_open: bool = False


class CircuitBreaker:
    """
    Simple circuit breaker per dependency name.
    OPEN after `failure_threshold` consecutive failures;
    after `recovery_timeout` s allows one trial (half-open).
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState()

    @property
    def is_open(self) -> bool:
        st = self._state
        if st.failures < self.failure_threshold:
            return False
        elapsed = time.monotonic() - st.opened_at
        if elapsed >= self.recovery_timeout:
            st.half_open = True
            return False  # allow probe
        return True

    def record_success(self) -> None:
        self._state = CircuitState()
        log.debug("circuit %s CLOSED", self.name)

    def record_failure(self) -> None:
        st = self._state
        st.failures += 1
        if st.failures >= self.failure_threshold and st.opened_at == 0.0:
            st.opened_at = time.monotonic()
            log.warning("circuit %s OPEN after %d failures", self.name, st.failures)
        elif st.half_open:
            st.opened_at = time.monotonic()
            st.half_open = False
            log.warning("circuit %s re-OPEN (probe failed)", self.name)

    def guard(self) -> None:
        if self.is_open:
            raise NeuroError(
                message=f"Obvod '{self.name}' je otevreny (prilis mnoho chyb).",
                kind=ErrorKind.DEPENDENCY_DOWN,
                source=self.name,
                recoverable=True,
                detail=f"failures={self._state.failures}",
            )


# Shared breakers for known dependencies
BREAKERS: dict[str, CircuitBreaker] = {
    "omniroute": CircuitBreaker("omniroute", failure_threshold=3, recovery_timeout=20.0),
    "ableton": CircuitBreaker("ableton", failure_threshold=2, recovery_timeout=15.0),
    "claude": CircuitBreaker("claude", failure_threshold=3, recovery_timeout=30.0),
}


def get_breaker(name: str) -> CircuitBreaker:
    if name not in BREAKERS:
        BREAKERS[name] = CircuitBreaker(name)
    return BREAKERS[name]


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.4,
    max_delay: float = 8.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    breaker: Optional[CircuitBreaker] = None,
    label: str = "op",
) -> T:
    """
    Exponential backoff retry with optional circuit breaker.
    Does not retry NeuroError with recoverable=False.
    """
    if breaker is not None:
        breaker.guard()

    last: Optional[BaseException] = None
    for i in range(1, attempts + 1):
        try:
            result = await fn()
            if breaker is not None:
                breaker.record_success()
            return result
        except NeuroError as exc:
            last = exc
            if not exc.recoverable:
                if breaker is not None:
                    breaker.record_failure()
                raise
            log.warning("%s attempt %d/%d NeuroError: %s", label, i, attempts, exc)
        except retry_on as exc:  # type: ignore[misc]
            last = exc
            log.warning("%s attempt %d/%d failed: %s", label, i, attempts, exc)

        if i < attempts:
            delay = min(max_delay, base_delay * (2 ** (i - 1)))
            await asyncio.sleep(delay)

    if breaker is not None:
        breaker.record_failure()

    if isinstance(last, NeuroError):
        raise last
    raise NeuroError(
        message=f"Operace '{label}' selhala po {attempts} pokusech.",
        kind=ErrorKind.DEPENDENCY_DOWN,
        detail=repr(last),
        source=label,
        recoverable=True,
    ) from last


def with_timeout(seconds: float, label: str = "op") -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator: wrap coroutine with asyncio.wait_for."""

    def deco(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError as exc:
                raise NeuroError(
                    message=f"Timeout ({seconds:.0f}s) pri '{label}'.",
                    kind=ErrorKind.TIMEOUT,
                    source=label,
                    recoverable=True,
                ) from exc

        return wrapper

    return deco


@dataclass
class DegradedMode:
    """Tracks which subsystems are offline so orchestrator can adapt."""

    omniroute: bool = False
    ableton: bool = False
    claude: bool = False
    notes: list[str] = field(default_factory=list)

    def mark(self, name: str, note: str = "") -> None:
        if hasattr(self, name):
            setattr(self, name, True)
        if note:
            self.notes.append(f"{name}: {note}")
        log.info("degraded mode: %s — %s", name, note)

    def summary(self) -> str:
        down = [n for n in ("omniroute", "ableton", "claude") if getattr(self, n)]
        if not down:
            return "vsechny subsystemy OK"
        return "degradovano: " + ", ".join(down)
