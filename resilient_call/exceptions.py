"""
Custom exceptions raised by the resilient-call library.
"""


class CircuitBreakerError(Exception):
    """Raised when a call is blocked because the circuit breaker is OPEN.

    Args:
        name: Name of the circuit breaker that blocked the call.
        reset_timeout: Seconds remaining until the breaker moves to HALF_OPEN.

    Example::

        try:
            result = executor.execute(call_service)
        except CircuitBreakerError as e:
            print(f"Circuit '{e.name}' is open. Retry after {e.reset_timeout:.1f}s.")
    """

    def __init__(self, name: str, reset_timeout: float = 0.0) -> None:
        self.name = name
        self.reset_timeout = reset_timeout
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Retry after {reset_timeout:.1f} seconds."
        )


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted.

    Args:
        attempts: Number of attempts that were made.
        last_exception: The exception raised on the final attempt.

    Example::

        try:
            result = executor.execute(call_service)
        except RetryExhaustedError as e:
            print(f"Failed after {e.attempts} attempts: {e.last_exception}")
    """

    def __init__(self, attempts: int, last_exception: Exception) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"All {attempts} retry attempt(s) exhausted. "
            f"Last error: {last_exception!r}"
        )
