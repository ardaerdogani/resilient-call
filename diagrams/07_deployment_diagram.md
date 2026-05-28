# Deployment Diagram

`resilient-call` is a pure Python library — it ships as a single pip package with
no server-side components and no runtime infrastructure requirements.

```mermaid
graph TB
    subgraph Developer["Developer Machine"]
        direction TB
        PYPI[("PyPI\nresilient-call 1.0.0")]
        PIP["pip install resilient-call"]
        PYPI --> PIP
    end

    subgraph AppServer["Application Server  (Python 3.10+)"]
        direction TB

        subgraph App["User Application"]
            CODE["app code\n(uses @retry / @circuit_breaker)"]
            EXEC["ResilientExecutor"]
            REG["CircuitBreakerRegistry\n(in-process singleton)"]
            CODE --> EXEC
            EXEC --> REG
        end

        subgraph Lib["resilient-call (installed)"]
            CB["circuit_breaker.py"]
            RP["retry.py"]
            DEC["decorators.py"]
        end

        App --> Lib
    end

    subgraph External["External Services"]
        SVC1["Payments API"]
        SVC2["Inventory API"]
        SVC3["Notification API"]
    end

    PIP -->|installs into| AppServer
    EXEC -->|protected calls| SVC1
    EXEC -->|protected calls| SVC2
    EXEC -->|protected calls| SVC3
```

## Deployment Notes

| Concern | Detail |
|---|---|
| **Installation** | `pip install resilient-call` — no system dependencies |
| **Python version** | 3.10 or higher |
| **External dependencies** | None |
| **Runtime infrastructure** | None — all state is in-process memory |
| **Multi-replica caveat** | Circuit breaker state is **not shared** across processes or pods. Each replica maintains its own state. For shared state, wrap with a Redis-backed store. |
| **Thread safety** | All state transitions are protected by `threading.Lock` |
| **Async** | Compatible with `asyncio`; use `execute_async` / `execute_async` |
