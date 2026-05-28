# Changelog

All notable changes to **resilient-call** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-05-27

### Added
- `CircuitBreaker` with three-state machine: CLOSED → OPEN → HALF_OPEN.
- `CircuitBreakerConfig` with configurable `failure_threshold`, `success_threshold`, `timeout`, and `expected_exceptions`.
- `CircuitBreakerState` enum.
- `RetryPolicy` with three backoff strategies: `FIXED`, `EXPONENTIAL`, `JITTER`.
- `BackoffStrategy` enum.
- `ResilientExecutor` composing retry and circuit breaker with optional fallback.
- `CircuitBreakerRegistry` — thread-safe named registry with module-level `registry` singleton.
- `@retry` decorator shorthand.
- `@circuit_breaker` decorator shorthand; automatically registers in `registry`.
- `CircuitBreakerError` — raised when circuit is OPEN.
- `RetryExhaustedError` — raised when all retry attempts are consumed.
- Async support: `RetryPolicy.execute_async`, `ResilientExecutor.execute_async`.
- `on_retry` callback hook on `RetryPolicy`.
- `on_state_change` callback hook on `CircuitBreakerConfig`.
- Full Sphinx API documentation.
- 100 % branch coverage in unit tests.
