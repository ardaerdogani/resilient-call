"""
Fallback patterns — returning cached or default data when a service is down.

Three patterns are shown:

1. Static default value
2. Cache-backed fallback (stale-while-revalidate)
3. Graceful degradation with partial results
"""

from __future__ import annotations

import time
from typing import Any

from resilient_call import (
    CircuitBreaker,
    CircuitBreakerConfig,
    ResilientExecutor,
    RetryPolicy,
)


# ---------------------------------------------------------------------------
# Pattern 1 — Static default
# ---------------------------------------------------------------------------

def demo_static_default() -> None:
    print("=== Pattern 1: Static default value ===")

    executor = ResilientExecutor(
        retry_policy=RetryPolicy(max_attempts=2, delay=0.0),
        circuit_breaker=CircuitBreaker("feature-flags", CircuitBreakerConfig(failure_threshold=2)),
        fallback=lambda exc: {"dark_mode": False, "beta_features": False},
    )

    def fetch_feature_flags(user_id: int) -> dict:
        raise ConnectionError("feature flag service is down")

    flags = executor.execute(fetch_feature_flags, user_id=42)
    print(f"Flags (default): {flags}\n")


# ---------------------------------------------------------------------------
# Pattern 2 — Cache-backed fallback (stale-while-revalidate)
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}


def demo_cache_fallback() -> None:
    print("=== Pattern 2: Cache-backed fallback ===")

    def fetch_product(sku: str) -> dict:
        raise IOError("product service unavailable")

    def cached_product(exc: Exception) -> dict:
        if _cache.get("product"):
            print(f"  Serving stale cache: {_cache['product']}")
            return _cache["product"]
        return {"sku": "UNKNOWN", "price": 0.0, "stale": True}

    _cache["product"] = {"sku": "WIDGET-42", "price": 9.99, "stale": False}

    executor = ResilientExecutor(
        retry_policy=RetryPolicy(max_attempts=1, delay=0.0),
        fallback=cached_product,
    )

    result = executor.execute(fetch_product, sku="WIDGET-42")
    print(f"Got: {result}\n")


# ---------------------------------------------------------------------------
# Pattern 3 — Partial results (fan-out with individual fallbacks)
# ---------------------------------------------------------------------------

def demo_partial_results() -> None:
    print("=== Pattern 3: Partial results (fan-out) ===")

    services = {
        "inventory": lambda: {"units": 150},
        "pricing":   lambda: (_ for _ in ()).throw(IOError("pricing down")),
        "reviews":   lambda: {"rating": 4.7, "count": 382},
    }

    def call_service(name: str) -> dict:
        return services[name]()

    results = {}
    for service_name in services:
        executor = ResilientExecutor(
            retry_policy=RetryPolicy(max_attempts=1, delay=0.0),
            fallback=lambda exc, sn=service_name: {"error": str(exc), "service": sn},
        )
        results[service_name] = executor.execute(call_service, name=service_name)

    for svc, data in results.items():
        print(f"  {svc}: {data}")
    print()


if __name__ == "__main__":
    demo_static_default()
    demo_cache_fallback()
    demo_partial_results()
    print("Done.")
