"""
ResilientExecutor — composes a RetryPolicy with a CircuitBreaker.

The execution order is::

    ResilientExecutor.execute(func)
        └─► CircuitBreaker.call(retry_wrapper)
                └─► RetryPolicy.execute(func)
                        └─► func()

This means that:

* If the circuit is OPEN the call is rejected immediately (no retries).
* Each individual attempt counts as one call for the circuit breaker —
  failures on retry attempts do accumulate toward the breaker threshold.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .retry import RetryPolicy


class ResilientExecutor:
    """Combines retry logic with a circuit breaker into a single execution unit.

    Either *retry_policy* or *circuit_breaker* (or both) can be omitted; the
    executor then applies only the provided protection mechanism.

    Args:
        retry_policy: :class:`~resilient_call.retry.RetryPolicy` instance.
            When ``None``, the call is attempted exactly once.
        circuit_breaker: :class:`~resilient_call.circuit_breaker.CircuitBreaker`
            instance.  When ``None``, no circuit-breaker protection is applied.
        fallback: Optional callable invoked when the execution ultimately fails
            (all retries exhausted **or** circuit open).  Receives the raised
            exception and must return the desired fallback value.
            Signature: ``(exc: Exception) -> Any``.

    Example::

        from resilient_call import ResilientExecutor, RetryPolicy, CircuitBreaker

        executor = ResilientExecutor(
            retry_policy=RetryPolicy(max_attempts=3, delay=0.5),
            circuit_breaker=CircuitBreaker("inventory-api"),
            fallback=lambda exc: [],
        )

        items = executor.execute(fetch_inventory, warehouse_id=42)
    """

    def __init__(
        self,
        retry_policy: Optional[RetryPolicy] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        fallback: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        self.retry_policy = retry_policy
        self.circuit_breaker = circuit_breaker
        self.fallback = fallback

    # ------------------------------------------------------------------
    # Synchronous execution
    # ------------------------------------------------------------------

    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *func* with all configured resilience mechanisms.

        Args:
            func: Callable to protect.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func*, or the return value of
            :attr:`fallback` if provided and the call ultimately fails.

        Raises:
            Exception: Re-raised from *func* when no fallback is configured.
        """
        try:
            return self._run(func, *args, **kwargs)
        except Exception as exc:
            if self.fallback is not None:
                return self.fallback(exc)
            raise

    def _run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self.retry_policy and self.circuit_breaker:
            return self.circuit_breaker.call(
                self.retry_policy.execute, func, *args, **kwargs
            )
        if self.circuit_breaker:
            return self.circuit_breaker.call(func, *args, **kwargs)
        if self.retry_policy:
            return self.retry_policy.execute(func, *args, **kwargs)
        return func(*args, **kwargs)

    # ------------------------------------------------------------------
    # Async execution
    # ------------------------------------------------------------------

    async def execute_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Async variant of :meth:`execute`.

        The circuit breaker check is still synchronous (state transitions are
        fast in-memory operations); only the *func* invocation and retry sleeps
        are awaited.

        Args:
            func: Async callable (coroutine function) to protect.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func*, or :attr:`fallback` value on failure.

        Raises:
            Exception: Re-raised when no fallback is configured.
        """
        try:
            return await self._run_async(func, *args, **kwargs)
        except Exception as exc:
            if self.fallback is not None:
                return self.fallback(exc)
            raise

    async def _run_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        if self.retry_policy and self.circuit_breaker:
            async def retry_wrapper() -> Any:
                return await self.retry_policy.execute_async(func, *args, **kwargs)

            return self.circuit_breaker.call(
                lambda: __import__("asyncio").get_event_loop().run_until_complete(
                    retry_wrapper()
                )
            )
        if self.circuit_breaker:
            return self.circuit_breaker.call(
                lambda: __import__("asyncio").get_event_loop().run_until_complete(
                    func(*args, **kwargs)
                )
            )
        if self.retry_policy:
            return await self.retry_policy.execute_async(func, *args, **kwargs)
        return await func(*args, **kwargs)

    def __repr__(self) -> str:
        parts = []
        if self.retry_policy:
            parts.append(f"retry={self.retry_policy!r}")
        if self.circuit_breaker:
            parts.append(f"cb={self.circuit_breaker!r}")
        if self.fallback:
            parts.append("fallback=<set>")
        return f"ResilientExecutor({', '.join(parts)})"
