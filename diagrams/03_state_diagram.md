# State Diagram — Circuit Breaker

The circuit breaker has three states. Transitions are triggered by failure counts,
success counts, and elapsed time.

```mermaid
stateDiagram-v2
    [*] --> CLOSED : initial state

    CLOSED --> CLOSED : call succeeds\n(reset failure counter)
    CLOSED --> CLOSED : call fails\n(count < failure_threshold)
    CLOSED --> OPEN   : call fails\n(count >= failure_threshold)

    OPEN --> OPEN      : call attempted\n→ CircuitBreakerError raised immediately
    OPEN --> HALF_OPEN : timeout elapsed\n(no calls attempted during wait)

    HALF_OPEN --> CLOSED    : successes >= success_threshold\n(circuit healed)
    HALF_OPEN --> OPEN      : any failure\n(circuit re-opens, timer resets)
    HALF_OPEN --> HALF_OPEN : success\n(count < success_threshold)
```

## Transition Conditions

| From       | To         | Condition                                              |
|------------|------------|--------------------------------------------------------|
| CLOSED     | OPEN       | Consecutive failures reach `failure_threshold`         |
| OPEN       | HALF_OPEN  | `timeout` seconds have elapsed since the breaker opened|
| HALF_OPEN  | CLOSED     | Consecutive successes reach `success_threshold`        |
| HALF_OPEN  | OPEN       | Any single failure — timer resets                      |
