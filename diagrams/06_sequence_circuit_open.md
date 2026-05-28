# Sequence Diagram — Scenario 3: Circuit Trips Open → Fallback Returned

The circuit breaker has already accumulated enough failures and is OPEN.
All calls are rejected immediately without touching the downstream service.
The executor's fallback function is invoked instead.

```mermaid
sequenceDiagram
    autonumber

    actor Client
    participant Executor as ResilientExecutor
    participant CB as CircuitBreaker
    participant Service as Downstream Service

    Note over CB: state = OPEN\n(failure_threshold already exceeded)

    Client->>Executor: execute(fetch_data, url)

    Executor->>CB: call(retry_wrapper)
    CB->>CB: check state == OPEN ✗
    CB->>CB: _remaining_timeout() → 47.3 s
    CB-->>Executor: raise CircuitBreakerError("payments-api", reset_timeout=47.3)

    Note over Service: Service is never called

    Executor->>Executor: fallback(CircuitBreakerError)
    Executor-->>Client: [] (safe default value)
```

## Notes

- The downstream service receives **zero** requests while the circuit is OPEN.
- The fallback is configured on `ResilientExecutor(fallback=lambda exc: [])`.
- Without a fallback, `CircuitBreakerError` is re-raised to the client.
