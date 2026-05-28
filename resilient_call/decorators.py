"""
Decorator helpers for :class:`RetryPolicy` and :class:`CircuitBreaker`.

These decorators are the quickest way to add resilience to an existing
function without changing its call signature::

    @retry(max_attempts=4, delay=0.5)
    def fetch_user(user_id: int) -> dict:
        return requests.get(f"/users/{user_id}").json()

    @circuit_breaker("payments-api", failure_threshold=3)
    def charge_card(amount: float) -> str:
        return payments_client.charge(amount)
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional, Tuple, Type

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from .registry import registry
from .retry import BackoffStrategy, RetryPolicy


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that retries the wrapped function on failure.

    Args:
        max_attempts: Total number of calls (including the first).
        delay: Base delay in seconds between attempts.
        backoff: :class:`~resilient_call.retry.BackoffStrategy` — how the
            delay grows between attempts.
        max_delay: Maximum sleep time between any two attempts.
        retryable_exceptions: Only retry when one of these is raised.
        on_retry: Called just before sleeping; receives
            ``(attempt, sleep_seconds, exc)``.

    Returns:
        A decorator that wraps the function in a :class:`RetryPolicy`.

    Example::

        @retry(max_attempts=5, delay=0.2, backoff=BackoffStrategy.JITTER)
        def send_notification(msg: str) -> None:
            notification_client.send(msg)
    """
    policy = RetryPolicy(
        max_attempts=max_attempts,
        delay=delay,
        backoff=backoff,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions,
        on_retry=on_retry,
    )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return policy.execute(func, *args, **kwargs)

        wrapper.__retry_policy__ = policy  # type: ignore[attr-defined]
        return wrapper

    return decorator


def circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 60.0,
    expected_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_state_change: Optional[
        Callable[[str, CircuitBreakerState, CircuitBreakerState], None]
    ] = None,
    fallback: Optional[Callable[[Exception], Any]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that wraps a function with a circuit breaker.

    The breaker is stored in the module-level
    :data:`~resilient_call.registry.registry` under *name* (which defaults
    to the decorated function's qualified name).  This means all calls to the
    decorated function share the same breaker state.

    Args:
        name: Registry key for this breaker.  Defaults to
            ``func.__qualname__``.
        failure_threshold: Failures required to trip OPEN.
        success_threshold: Successes in HALF_OPEN required to close.
        timeout: Seconds to remain OPEN before moving to HALF_OPEN.
        expected_exceptions: Exception types that count as failures.
        on_state_change: Callback on state transitions.
        fallback: Called with the exception when the circuit is open or all
            retries are exhausted.  Its return value is used instead of
            raising.

    Returns:
        A decorator that wraps the function with a :class:`CircuitBreaker`.

    Example::

        @circuit_breaker("inventory-api", failure_threshold=3, timeout=30.0)
        def get_stock(sku: str) -> int:
            return inventory_client.get(sku)
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout=timeout,
        expected_exceptions=expected_exceptions,
        on_state_change=on_state_change,
    )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        breaker_name = name or func.__qualname__
        cb = registry.get_or_create(breaker_name, config)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return cb.call(func, *args, **kwargs)
            except Exception as exc:
                if fallback is not None:
                    return fallback(exc)
                raise

        wrapper.__circuit_breaker__ = cb  # type: ignore[attr-defined]
        return wrapper

    return decorator
