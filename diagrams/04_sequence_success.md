# Sequence Diagram — Scenario 1: Successful Call (No Retry Needed)

The happy path. The downstream service responds on the first attempt.
The circuit breaker records a success and resets the failure counter.

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
    Service-->>RP: {"status": "ok", "data": [...]}

    RP-->>CB: {"status": "ok", "data": [...]}
    CB->>CB: _record_success() → failure_count = 0

    CB-->>Executor: {"status": "ok", "data": [...]}
    Executor-->>Client: {"status": "ok", "data": [...]}
```
