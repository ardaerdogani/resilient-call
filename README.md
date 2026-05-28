# resilient-call

A Python library that provides **retry** and **circuit-breaker** resilience patterns for any callable. Zero external dependencies, full async support, and thread-safe by design.

## Features

- **Retry** with configurable backoff strategies: fixed, exponential, and jitter
- **Circuit breaker** with the classic three-state machine (CLOSED → OPEN → HALF_OPEN)
- **Composable executor** that layers retry inside a circuit breaker with optional fallback
- **Decorator API** for minimal boilerplate
- **Named registry** for sharing circuit breakers across modules
- Full `asyncio` support alongside synchronous execution
- Thread-safe state management via `threading.Lock`
- No runtime dependencies — Python 3.10+ only

## Installation

```bash
pip install resilient-call
```

For development (includes test and docs extras):

```bash
pip install -e ".[dev,docs]"
```

## Quick Start

### Decorator API

```python
from resilient_call import retry, circuit_breaker

@retry(max_attempts=3, delay=0.5, strategy="exponential")
def fetch_data(url):
    ...

@circuit_breaker(failure_threshold=5, timeout=30.0)
def call_service(payload):
    ...
```

### Programmatic API

```python
from resilient_call import RetryPolicy, CircuitBreaker, CircuitBreakerConfig, ResilientExecutor

policy = RetryPolicy(max_attempts=4, delay=0.2, strategy="jitter")
config = CircuitBreakerConfig(failure_threshold=5, timeout=60.0)
breaker = CircuitBreaker(config)

executor = ResilientExecutor(
    retry_policy=policy,
    circuit_breaker=breaker,
    fallback=lambda: {"status": "unavailable"},
)

result = executor.execute(call_external_service, arg1, arg2)
```

### Async

Both `RetryPolicy` and `ResilientExecutor` expose `execute_async()` for use with `asyncio`:

```python
import asyncio
from resilient_call import RetryPolicy

policy = RetryPolicy(max_attempts=3, delay=0.1, strategy="exponential")

async def main():
    result = await policy.execute_async(async_fetch, "https://example.com")
```

### Shared Circuit Breakers

```python
from resilient_call import registry, CircuitBreakerConfig

breaker = registry.get_or_create("payments", CircuitBreakerConfig(failure_threshold=3))

# Same breaker instance retrieved anywhere in the application
breaker = registry.get("payments")
```

## Backoff Strategies

| Strategy | Behaviour |
|---|---|
| `fixed` | Constant delay between retries |
| `exponential` | Delay doubles each attempt: `delay * 2^n` (capped at `max_delay`) |
| `jitter` | Uniform random delay in `[0, delay]` to avoid thundering herd |

## Callbacks

```python
def on_retry(attempt, delay, exc):
    print(f"Retry {attempt} after {delay:.2f}s — {exc}")

policy = RetryPolicy(max_attempts=3, on_retry=on_retry)

def on_state_change(old_state, new_state):
    print(f"Circuit breaker: {old_state} → {new_state}")

config = CircuitBreakerConfig(on_state_change=on_state_change)
```

## Running Tests

```bash
pytest tests/
pytest tests/ --cov=resilient_call  # with coverage
```

The test suite contains 42 tests covering retry, circuit breaker, decorators, and the executor, with 100% branch coverage.

## Building Documentation

```bash
cd docs/
sphinx-build -b html . _build/html
```

## Examples

```bash
python examples/quickstart.py           # Basic decorator and executor patterns
python examples/fallback_pattern.py     # Static default, cache, and partial-result fallbacks
python examples/microservice_http.py    # Realistic microservice scenario
```

## License

[MIT](LICENSE)
