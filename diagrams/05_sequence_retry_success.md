# Sequence Diagram — Scenario 2: Transient Failure, Retries Succeed

The service fails twice with a transient error, then recovers on the third attempt.
The retry policy applies exponential backoff between attempts.
The circuit breaker does not trip because the call ultimately succeeds.

```mermaid
sequenceDiagram
    autonumber

    actor Client
    participant Executor as ResilientExecutor
    participant CB as CircuitBreaker
    participant RP as RetryPolicy
    participant Service as Downstream Service

    Client->>Executor: execute(fetch_data, url)

    Executor->>CB: call(retry_wrapper)
    CB->>CB: check state == CLOSED ✓

    CB->>RP: execute(fetch_data, url)

    RP->>Service: fetch_data(url)  [attempt 1]
    Service-->>RP: ConnectionError("timeout")
    Note over RP: sleep 0.5 s  (EXPONENTIAL delay)

    RP->>Service: fetch_data(url)  [attempt 2]
    Service-->>RP: ConnectionError("timeout")
    Note over RP: sleep 1.0 s

    RP->>Service: fetch_data(url)  [attempt 3]
    Service-->>RP: {"status": "ok", "data": [...]}

    RP-->>CB: {"status": "ok", "data": [...]}
    CB->>CB: _record_success() → failure_count = 0

    CB-->>Executor: {"status": "ok", "data": [...]}
    Executor-->>Client: {"status": "ok", "data": [...]}
```
