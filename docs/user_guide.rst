User Guide
==========

This guide covers every feature of resilient-call in depth.

Retry Policy
------------

``RetryPolicy`` controls *if* and *how* a failed call is retried.

.. code-block:: python

   from resilient_call import RetryPolicy, BackoffStrategy

   policy = RetryPolicy(
       max_attempts=5,       # 1 original + 4 retries
       delay=1.0,            # base delay in seconds
       backoff=BackoffStrategy.EXPONENTIAL,
       max_delay=30.0,       # never sleep longer than this
       retryable_exceptions=(IOError, TimeoutError),
   )

Backoff strategies
~~~~~~~~~~~~~~~~~~

+---------------+------------------------------------------+
| Strategy      | Delay formula                            |
+===============+==========================================+
| FIXED         | ``delay``                                |
+---------------+------------------------------------------+
| EXPONENTIAL   | ``delay × 2^(attempt-1)``                |
+---------------+------------------------------------------+
| JITTER        | ``uniform(0, delay × 2^(attempt-1))``    |
+---------------+------------------------------------------+

Use **JITTER** when many clients retry the same service simultaneously to
avoid a thundering-herd effect.

on_retry callback
~~~~~~~~~~~~~~~~~

.. code-block:: python

   def log_retry(attempt: int, sleep: float, exc: Exception) -> None:
       print(f"attempt {attempt} failed ({exc}), sleeping {sleep:.2f}s")

   policy = RetryPolicy(max_attempts=3, on_retry=log_retry)

Circuit Breaker
---------------

``CircuitBreaker`` wraps a dependency and stops forwarding calls when it
becomes unhealthy.

State machine
~~~~~~~~~~~~~

.. code-block:: text

   CLOSED ──(failures ≥ threshold)──► OPEN
   OPEN   ──(timeout elapsed)────────► HALF_OPEN
   HALF_OPEN ──(successes ≥ threshold)► CLOSED
   HALF_OPEN ──(failure)─────────────► OPEN

Configuration
~~~~~~~~~~~~~

.. code-block:: python

   from resilient_call import CircuitBreaker, CircuitBreakerConfig

   cb = CircuitBreaker(
       "my-service",
       CircuitBreakerConfig(
           failure_threshold=5,    # consecutive failures to trip OPEN
           success_threshold=2,    # consecutive HALF_OPEN successes to close
           timeout=60.0,           # seconds to stay OPEN
           expected_exceptions=(IOError, TimeoutError),
       ),
   )

Only exceptions listed in ``expected_exceptions`` increment the failure
counter.  All other exceptions propagate transparently.

on_state_change callback
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def alert(name, old, new):
       print(f"ALERT: circuit '{name}' changed {old.value} → {new.value}")

   config = CircuitBreakerConfig(on_state_change=alert)

Registry
--------

The module-level ``registry`` object lets you share breakers across modules
without passing them explicitly.

.. code-block:: python

   from resilient_call.registry import registry

   # anywhere in your codebase
   cb = registry.get_or_create("inventory", config=CircuitBreakerConfig())

   # inspect state from a health-check endpoint
   for breaker in registry:
       print(breaker.name, breaker.state.value)

ResilientExecutor
-----------------

``ResilientExecutor`` composes retry and circuit-breaker in the correct
order: the circuit check happens first, then retries run inside the breaker.

.. code-block:: python

   executor = ResilientExecutor(
       retry_policy=RetryPolicy(max_attempts=4),
       circuit_breaker=CircuitBreaker("svc"),
       fallback=lambda exc: default_value,
   )
   result = executor.execute(my_function, arg1, arg2)

Async support
-------------

Both ``RetryPolicy`` and ``ResilientExecutor`` support ``asyncio``.

.. code-block:: python

   import asyncio
   from resilient_call import RetryPolicy

   policy = RetryPolicy(max_attempts=3, delay=0.5)

   async def main():
       result = await policy.execute_async(my_async_function, url)

   asyncio.run(main())

Restrictions
------------

* **No distributed state.** Circuit-breaker state is in-process only.
  Use a shared store (Redis, etc.) if you need state across multiple
  replicas.
* **Thread safety.** All state transitions are protected by ``threading.Lock``.
  The library is safe to use from multiple threads but is not optimised for
  extremely high-throughput scenarios (> 100 000 calls/sec per breaker).
* **Python 3.10+** is required for ``match``-free union type hints.
