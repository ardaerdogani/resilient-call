Quickstart
==========

Installation
------------

.. code-block:: bash

   pip install resilient-call

**Requirements:** Python 3.10+, no third-party dependencies.

5-Minute Examples
-----------------

Retry a flaky function
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from resilient_call import retry, BackoffStrategy

   @retry(max_attempts=4, delay=0.5, backoff=BackoffStrategy.EXPONENTIAL)
   def fetch_data(url: str) -> dict:
       import urllib.request, json
       with urllib.request.urlopen(url, timeout=5) as r:
           return json.loads(r.read())

   data = fetch_data("https://api.example.com/data")

The decorator retries up to 4 times with exponentially growing delays
(0.5 s → 1 s → 2 s).  If all attempts fail, :exc:`RetryExhaustedError`
is raised.

Protect a service with a circuit breaker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from resilient_call import circuit_breaker

   @circuit_breaker("payments-api", failure_threshold=5, timeout=30.0)
   def charge(amount: float) -> dict:
       return payments_client.post("/charge", json={"amount": amount})

After 5 consecutive failures the circuit opens for 30 seconds.
All calls during that window immediately raise :exc:`CircuitBreakerError`
instead of hitting the downstream service.

Full resilience with a fallback
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from resilient_call import ResilientExecutor, RetryPolicy, CircuitBreaker

   executor = ResilientExecutor(
       retry_policy=RetryPolicy(max_attempts=3, delay=0.5),
       circuit_breaker=CircuitBreaker("inventory"),
       fallback=lambda exc: [],          # return empty list on any failure
   )

   items = executor.execute(fetch_inventory, warehouse_id=7)
