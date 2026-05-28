"""
Quickstart — get up and running in under 5 minutes.

This file covers the three most common patterns:
  1. Simple retry decorator
  2. Circuit breaker decorator
  3. Programmatic executor with both mechanisms + fallback

Run:
    python examples/quickstart.py
"""

import random
import time

from resilient_call import (
    BackoffStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    ResilientExecutor,
    RetryPolicy,
    circuit_breaker,
    retry,
)


# ---------------------------------------------------------------------------
# 1. Retry decorator — simplest usage
# ---------------------------------------------------------------------------

attempt_counter = 0


@retry(max_attempts=4, delay=0.05, backoff=BackoffStrategy.EXPONENTIAL)
def fetch_weather(city: str) -> dict:
    """Simulates a flaky weather API that fails the first 3 times."""
    global attempt_counter
    attempt_counter += 1
    print(f"  attempt {attempt_counter} for '{city}'...")
    if attempt_counter < 4:
        raise ConnectionError("service unavailable")
    return {"city": city, "temp_c": 22}


print("=== 1. Retry decorator ===")
result = fetch_weather("Istanbul")
print(f"Got: {result}\n")


# ---------------------------------------------------------------------------
# 2. Circuit breaker decorator — protects against cascading failures
# ---------------------------------------------------------------------------

call_count = 0


@circuit_breaker(
    "weather-api",
    failure_threshold=3,
    timeout=2.0,
    fallback=lambda exc: {"error": str(exc)},
)
def get_forecast(city: str) -> dict:
    """Always fails — demonstrates the circuit tripping open."""
    global call_count
    call_count += 1
    raise TimeoutError("gateway timeout")


print("=== 2. Circuit breaker decorator ===")
for i in range(6):
    result = get_forecast("Ankara")
    print(f"  call {i + 1}: {result}")

print(f"Total actual calls made: {call_count} (circuit blocked the rest)\n")


# ---------------------------------------------------------------------------
# 3. Programmatic executor — retry + circuit breaker + fallback together
# ---------------------------------------------------------------------------

calls_made = 0


def inventory_api(sku: str) -> list[str]:
    """Simulates an inventory service that recovers after a few failures."""
    global calls_made
    calls_made += 1
    if calls_made <= 4:
        raise IOError(f"inventory service down (attempt {calls_made})")
    return [f"{sku}-batch-A", f"{sku}-batch-B"]


executor = ResilientExecutor(
    retry_policy=RetryPolicy(
        max_attempts=6,
        delay=0.02,
        backoff=BackoffStrategy.JITTER,
        on_retry=lambda attempt, delay, exc: print(
            f"  retry {attempt}: sleeping {delay:.3f}s after {exc}"
        ),
    ),
    circuit_breaker=CircuitBreaker(
        "inventory",
        CircuitBreakerConfig(failure_threshold=10, timeout=30.0),
    ),
    fallback=lambda exc: ["FALLBACK-SKU"],
)

print("=== 3. Programmatic executor ===")
items = executor.execute(inventory_api, sku="WIDGET-42")
print(f"Got items: {items}\n")

print("All examples completed successfully.")
