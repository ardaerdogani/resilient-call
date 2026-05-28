"""Tests for ResilientExecutor."""

import pytest
from unittest.mock import MagicMock

from resilient_call.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from resilient_call.executor import ResilientExecutor
from resilient_call.exceptions import CircuitBreakerError, RetryExhaustedError
from resilient_call.retry import RetryPolicy


def failing(exc_type=IOError):
    return MagicMock(side_effect=exc_type("err"))


class TestExecutorRetryOnly:
    def test_retries_and_succeeds(self):
        policy = RetryPolicy(max_attempts=3, delay=0.0)
        func = MagicMock(side_effect=[IOError, IOError, "ok"])
        executor = ResilientExecutor(retry_policy=policy)
        assert executor.execute(func) == "ok"

    def test_exhausted_raises(self):
        policy = RetryPolicy(max_attempts=2, delay=0.0)
        executor = ResilientExecutor(retry_policy=policy)
        with pytest.raises(RetryExhaustedError):
            executor.execute(failing())


class TestExecutorCircuitBreakerOnly:
    def test_blocked_when_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("svc", config)
        executor = ResilientExecutor(circuit_breaker=cb)
        with pytest.raises(IOError):
            executor.execute(failing())
        with pytest.raises(CircuitBreakerError):
            executor.execute(lambda: None)


class TestExecutorBoth:
    def test_retry_inside_breaker(self):
        policy = RetryPolicy(max_attempts=3, delay=0.0)
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("svc", config)
        executor = ResilientExecutor(retry_policy=policy, circuit_breaker=cb)

        func = MagicMock(side_effect=[IOError, IOError, "great"])
        assert executor.execute(func) == "great"

    def test_circuit_blocks_after_retry_exhaustion(self):
        """When retry exhausts, the CB records the failure and opens on next call."""
        policy = RetryPolicy(max_attempts=3, delay=0.0)
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("svc", config)
        executor = ResilientExecutor(retry_policy=policy, circuit_breaker=cb)

        # RetryExhaustedError propagates from the CB call; CB records it as 1 failure
        with pytest.raises(RetryExhaustedError):
            executor.execute(failing())
        # Circuit is now OPEN
        with pytest.raises(CircuitBreakerError):
            executor.execute(lambda: None)


class TestFallback:
    def test_fallback_called_on_failure(self):
        policy = RetryPolicy(max_attempts=1, delay=0.0)
        executor = ResilientExecutor(
            retry_policy=policy,
            fallback=lambda exc: "default",
        )
        assert executor.execute(failing()) == "default"

    def test_fallback_called_when_circuit_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("svc", config)
        executor = ResilientExecutor(
            circuit_breaker=cb,
            fallback=lambda exc: "cached",
        )
        # First call fails normally; fallback returns "cached"
        assert executor.execute(failing()) == "cached"
        # Second call: circuit is now OPEN; fallback still returns "cached"
        assert executor.execute(lambda: None) == "cached"

    def test_no_fallback_reraises(self):
        policy = RetryPolicy(max_attempts=1, delay=0.0)
        executor = ResilientExecutor(retry_policy=policy)
        with pytest.raises(RetryExhaustedError):
            executor.execute(failing())
