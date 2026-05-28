"""
Circuit Breaker implementation.

The circuit breaker wraps an operation and tracks its success/failure rate.
When failures exceed a configured threshold the breaker "trips" to OPEN,
short-circuiting all subsequent calls without even attempting the operation.
After a configurable timeout it moves to HALF_OPEN and allows a probe call
through; on success it closes again, on failure it re-opens.

State machine::

    CLOSED ──(failures >= threshold)──► OPEN
    OPEN   ──(timeout elapsed)────────► HALF_OPEN
    HALF_OPEN ──(success)─────────────► CLOSED
    HALF_OPEN ──(failure)─────────────► OPEN
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Optional, Tuple, Type

from .exceptions import CircuitBreakerError


class CircuitBreakerState(Enum):
    """Possible states of a :class:`CircuitBreaker`.

    Attributes:
        CLOSED: Normal operation — calls pass through.
        OPEN: Failure threshold exceeded — calls are blocked immediately.
        HALF_OPEN: Probe state — one call is allowed to test recovery.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a :class:`CircuitBreaker`.

    Args:
        failure_threshold: Number of consecutive failures required to trip the
            breaker from CLOSED to OPEN. Default: ``5``.
        success_threshold: Number of consecutive successes in HALF_OPEN state
            required to close the breaker again. Default: ``2``.
        timeout: Seconds to remain OPEN before transitioning to HALF_OPEN.
            Default: ``60.0``.
        expected_exceptions: Tuple of exception types that count as failures.
            Any other exception type is re-raised without incrementing the
            failure counter. Default: ``(Exception,)``.
        on_state_change: Optional callback invoked whenever the breaker
            transitions between states.  Signature:
            ``(name: str, old: CircuitBreakerState, new: CircuitBreakerState) -> None``.

    Example::

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout=30.0,
            expected_exceptions=(IOError, TimeoutError),
        )
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0
    expected_exceptions: Tuple[Type[BaseException], ...] = field(
        default_factory=lambda: (Exception,)
    )
    on_state_change: Optional[Callable[[str, CircuitBreakerState, CircuitBreakerState], None]] = field(
        default=None, repr=False
    )


class CircuitBreaker:
    """Thread-safe circuit breaker that protects a downstream dependency.

    The breaker transitions between three states: CLOSED (normal), OPEN
    (short-circuiting), and HALF_OPEN (probing for recovery).  All state
    transitions are protected by an internal ``threading.Lock``.

    Args:
        name: Unique name for this breaker, used in error messages and
            registry look-ups.
        config: :class:`CircuitBreakerConfig` instance.  Uses library
            defaults when omitted.

    Example::

        cb = CircuitBreaker("payments-api")

        try:
            result = cb.call(requests.get, "https://pay.example.com/status")
        except CircuitBreakerError:
            result = cached_status()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: Optional[float] = None
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitBreakerState:
        """Current state of the breaker (read-only)."""
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        """Number of consecutive failures recorded in CLOSED state."""
        return self._failure_count

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *func* with circuit-breaker protection.

        Args:
            func: Callable to execute.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            Whatever *func* returns on success.

        Raises:
            CircuitBreakerError: If the breaker is OPEN.
            Exception: Any exception raised by *func* that is listed in
                ``config.expected_exceptions`` (after recording the failure).
                Non-expected exceptions are re-raised transparently.
        """
        with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitBreakerState.OPEN:
                remaining = self._remaining_timeout()
                raise CircuitBreakerError(self.name, remaining)

        try:
            result = func(*args, **kwargs)
        except self.config.expected_exceptions as exc:
            self._record_failure()
            raise
        except BaseException:
            raise
        else:
            self._record_success()
            return result

    def reset(self) -> None:
        """Manually force the breaker back to CLOSED and clear counters."""
        with self._lock:
            self._transition(CircuitBreakerState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._opened_at = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_success(self) -> None:
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition(CircuitBreakerState.CLOSED)
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitBreakerState.CLOSED:
                self._failure_count = 0

    def _record_failure(self) -> None:
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._transition(CircuitBreakerState.OPEN)
                self._opened_at = time.monotonic()
                self._success_count = 0
            elif self._state == CircuitBreakerState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._transition(CircuitBreakerState.OPEN)
                    self._opened_at = time.monotonic()

    def _maybe_transition_to_half_open(self) -> None:
        """Called under the lock — promotes OPEN → HALF_OPEN if timeout elapsed."""
        if (
            self._state == CircuitBreakerState.OPEN
            and self._opened_at is not None
            and (time.monotonic() - self._opened_at) >= self.config.timeout
        ):
            self._transition(CircuitBreakerState.HALF_OPEN)
            self._opened_at = None

    def _remaining_timeout(self) -> float:
        if self._opened_at is None:
            return 0.0
        elapsed = time.monotonic() - self._opened_at
        return max(0.0, self.config.timeout - elapsed)

    def _transition(self, new_state: CircuitBreakerState) -> None:
        old_state = self._state
        self._state = new_state
        if self.config.on_state_change and old_state != new_state:
            try:
                self.config.on_state_change(self.name, old_state, new_state)
            except Exception:
                pass

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.value!r}, "
            f"failures={self._failure_count})"
        )
