"""
Microservice HTTP client with retry + circuit breaker.

Demonstrates realistic usage: wrapping HTTP calls to a downstream REST API.
The circuit breaker prevents cascading failures when the payments service
goes down, and the retry policy handles transient network blips automatically.

Run (will fail gracefully because the URL is not real):
    python examples/microservice_http.py
"""

from __future__ import annotations

from resilient_call import (
    BackoffStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    ResilientExecutor,
    RetryPolicy,
    registry,
)
from resilient_call.exceptions import CircuitBreakerError


PAYMENTS_BREAKER_NAME = "payments-service"


# ---------------------------------------------------------------------------
# Callbacks — must be defined before the executor that references them
# ---------------------------------------------------------------------------

def _log_state_change(
    name: str, old: CircuitBreakerState, new: CircuitBreakerState
) -> None:
    print(f"[circuit-breaker] '{name}': {old.value} → {new.value}")


def _payments_fallback(exc: Exception) -> dict:
    if isinstance(exc, CircuitBreakerError):
        return {
            "status": "unavailable",
            "reason": "circuit open",
            "retry_after": exc.reset_timeout,
        }
    return {"status": "error", "reason": str(exc)}


# ---------------------------------------------------------------------------
# Executor configuration
# ---------------------------------------------------------------------------

payments_executor = ResilientExecutor(
    retry_policy=RetryPolicy(
        max_attempts=3,
        delay=0.5,
        backoff=BackoffStrategy.EXPONENTIAL,
        max_delay=10.0,
        retryable_exceptions=(ConnectionError, TimeoutError, IOError),
        on_retry=lambda attempt, sleep, exc: print(
            f"[payments] retry {attempt} in {sleep:.2f}s ({exc})"
        ),
    ),
    circuit_breaker=CircuitBreaker(
        PAYMENTS_BREAKER_NAME,
        CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout=30.0,
            expected_exceptions=(ConnectionError, TimeoutError, IOError),
            on_state_change=_log_state_change,
        ),
    ),
    fallback=_payments_fallback,
)


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

def _do_charge(amount: float, currency: str) -> dict:
    """Raw HTTP call — replace with real requests.post() in production."""
    import json
    import urllib.request

    body = json.dumps({"amount": amount, "currency": currency}).encode()
    req = urllib.request.Request(
        "http://localhost:8080/payments/charge",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def charge_card(amount: float, currency: str = "USD") -> dict:
    """Charge a payment card with full resilience protection.

    Args:
        amount: Amount to charge in the given currency.
        currency: ISO 4217 currency code.

    Returns:
        Payment response dict, or a fallback dict when the service is down.
    """
    return payments_executor.execute(_do_charge, amount, currency)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Attempting to charge $99.00 (payments service is not running)...\n")
    result = charge_card(99.00)
    print(f"\nResult: {result}")

    cb = registry.get(PAYMENTS_BREAKER_NAME)
    if cb:
        print(f"\nCircuit breaker state : {cb.state.value}")
        print(f"Failure count         : {cb.failure_count}")
