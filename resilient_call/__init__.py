"""
resilient-call
==============

A Python library that adds **retry** and **circuit-breaker** resilience to any
callable with minimal boilerplate.

Quick start::

    from resilient_call import retry, circuit_breaker, ResilientExecutor

    # --- Decorator API ---

    @retry(max_attempts=3, delay=0.5)
    def fetch(url: str) -> dict: ...

    @circuit_breaker("payments-api", failure_threshold=3)
    def charge(amount: float) -> str: ...

    # --- Programmatic API ---

    executor = ResilientExecutor(
        retry_policy=RetryPolicy(max_attempts=5),
        circuit_breaker=CircuitBreaker("inventory"),
        fallback=lambda exc: [],
    )
    result = executor.execute(fetch_items)
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from .decorators import circuit_breaker, retry
from .exceptions import CircuitBreakerError, RetryExhaustedError
from .executor import ResilientExecutor
from .registry import CircuitBreakerRegistry, registry
from .retry import BackoffStrategy, RetryPolicy

__version__ = "1.0.0"
__author__ = "Arda Erdoğan"
__license__ = "MIT"

__all__ = [
    # Core classes
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerState",
    "RetryPolicy",
    "BackoffStrategy",
    "ResilientExecutor",
    "CircuitBreakerRegistry",
    "registry",
    # Exceptions
    "CircuitBreakerError",
    "RetryExhaustedError",
    # Decorators
    "retry",
    "circuit_breaker",
]
