"""
Retry policy with configurable backoff strategies.

Three strategies are supported:

* **FIXED** — constant delay between every attempt.
* **EXPONENTIAL** — delay doubles after each failure: ``delay * 2^attempt``,
  capped at ``max_delay``.
* **JITTER** — exponential delay plus a random fraction, reducing thundering
  herd when many callers retry simultaneously.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Type

from .exceptions import RetryExhaustedError


class BackoffStrategy(Enum):
    """Delay strategy used between retry attempts.

    Attributes:
        FIXED: Same delay every time.
        EXPONENTIAL: Delay grows as ``base_delay * 2 ** attempt``.
        JITTER: Exponential base plus uniform random noise up to the same
            exponent value — good for avoiding thundering-herd.
    """

    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    JITTER = "jitter"


@dataclass
class RetryPolicy:
    """Configures how retries are attempted.

    Args:
        max_attempts: Maximum number of calls total (including the first).
            A value of ``1`` means no retries. Default: ``3``.
        delay: Base delay in seconds between attempts. Default: ``1.0``.
        backoff: :class:`BackoffStrategy` that controls how the delay grows.
            Default: ``BackoffStrategy.EXPONENTIAL``.
        max_delay: Upper bound on the computed delay regardless of strategy.
            Default: ``60.0`` seconds.
        retryable_exceptions: Tuple of exception types that trigger a retry.
            Other exceptions are re-raised immediately without consuming
            remaining attempts. Default: ``(Exception,)``.
        on_retry: Optional callback invoked before each retry sleep.
            Signature: ``(attempt: int, delay: float, exc: Exception) -> None``.

    Example::

        policy = RetryPolicy(
            max_attempts=5,
            delay=0.5,
            backoff=BackoffStrategy.JITTER,
            retryable_exceptions=(IOError, TimeoutError),
        )
        result = policy.execute(fetch_data, url)
    """

    max_attempts: int = 3
    delay: float = 1.0
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    max_delay: float = 60.0
    retryable_exceptions: Tuple[Type[BaseException], ...] = field(
        default_factory=lambda: (Exception,)
    )
    on_retry: Optional[Callable[[int, float, Exception], None]] = field(
        default=None, repr=False
    )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *func*, retrying on :attr:`retryable_exceptions`.

        Args:
            func: Callable to execute.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            Whatever *func* returns on a successful call.

        Raises:
            RetryExhaustedError: When all attempts fail.
            Exception: Any non-retryable exception is re-raised immediately.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except self.retryable_exceptions as exc:
                last_exc = exc
                if attempt == self.max_attempts:
                    break
                sleep_duration = self._compute_delay(attempt)
                if self.on_retry:
                    try:
                        self.on_retry(attempt, sleep_duration, exc)
                    except Exception:
                        pass
                time.sleep(sleep_duration)
            except BaseException:
                raise

        raise RetryExhaustedError(self.max_attempts, last_exc)  # type: ignore[arg-type]

    async def execute_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Async variant of :meth:`execute` — awaits *func* and ``asyncio.sleep``.

        Args:
            func: Async callable (coroutine function) to execute.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            Whatever *func* returns on a successful call.

        Raises:
            RetryExhaustedError: When all attempts fail.
        """
        import asyncio

        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except self.retryable_exceptions as exc:
                last_exc = exc
                if attempt == self.max_attempts:
                    break
                sleep_duration = self._compute_delay(attempt)
                if self.on_retry:
                    try:
                        self.on_retry(attempt, sleep_duration, exc)
                    except Exception:
                        pass
                await asyncio.sleep(sleep_duration)
            except BaseException:
                raise

        raise RetryExhaustedError(self.max_attempts, last_exc)  # type: ignore[arg-type]

    def get_delay(self, attempt: int) -> float:
        """Return the computed delay (in seconds) for a given *attempt* number.

        Useful for previewing the retry schedule without executing anything.

        Args:
            attempt: 1-based attempt number (1 = after the first failure).

        Returns:
            Delay in seconds, bounded by :attr:`max_delay`.
        """
        return self._compute_delay(attempt)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_delay(self, attempt: int) -> float:
        if self.backoff == BackoffStrategy.FIXED:
            computed = self.delay
        elif self.backoff == BackoffStrategy.EXPONENTIAL:
            computed = self.delay * (2 ** (attempt - 1))
        else:  # JITTER
            exp = self.delay * (2 ** (attempt - 1))
            computed = random.uniform(0, exp)
        return min(computed, self.max_delay)
